"""Generates the n8n Workflow SDK sources in src/. Run: python3 gen.py"""
import json, pathlib

API = "http://backend:8000/api/automation"
HEAD = ("import { workflow, node, trigger, ifElse, newCredential, expr, sticky } "
        "from '@n8n/workflow-sdk';\n\nconst API = '%s';\n" % API)
AUTH = ("      authentication: 'genericCredentialType',\n"
        "      genericAuthType: 'httpHeaderAuth',\n")
CRED = "    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }\n"


def webhook(var, name, path, sample):
    return f"""
const {var} = trigger({{
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {{
    name: '{name}',
    parameters: {{ httpMethod: 'POST', path: '{path}', authentication: 'headerAuth', responseMode: 'onReceived' }},
    credentials: {{ httpHeaderAuth: newCredential('Smart Lab webhook token') }}
  }},
  output: [{json.dumps({"body": sample})}]
}});
"""


def schedule(var, name, interval):
    return f"""
const {var} = trigger({{
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: {{ name: '{name}', parameters: {{ rule: {{ interval: [{interval}] }} }} }},
  output: [{{}}]
}});
"""


def get(var, name, url, sample, once=False):
    u = f"expr(API + '{url}')" if "{{" in url else f"API + '{url}'"
    return f"""
const {var} = node({{
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {{
    name: '{name}',{" executeOnce: true," if once else ""}
    parameters: {{
      method: 'GET',
      url: {u},
{AUTH}    }},
{CRED}  }},
  output: [{json.dumps(sample)}]
}});
"""


def post(var, name, path, body_expr, sample, once=False, cont=False):
    extra = (" executeOnce: true," if once else "") + \
            (" onError: 'continueRegularOutput'," if cont else "")
    u = f"expr(API + '{path}')" if "{{" in path else f"API + '{path}'"
    return f"""
const {var} = node({{
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {{
    name: '{name}',{extra}
    parameters: {{
      method: 'POST',
      url: {u},
{AUTH}      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{{{ JSON.stringify({body_expr}) }}}}')
    }},
{CRED}  }},
  output: [{json.dumps(sample)}]
}});
"""


def split(var, name, field, sample):
    return f"""
const {var} = node({{
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: {{ name: '{name}', parameters: {{ fieldToSplitOut: '{field}' }} }},
  output: [{json.dumps(sample)}]
}});
"""


def cond(left, op_type, op, right=None):
    c = {"leftValue": f"@@{left}@@", "operator": {"type": op_type, "operation": op}}
    if right is not None:
        c["rightValue"] = right
    return c


def _conds(conds, combinator):
    body = json.dumps({"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                       "conditions": conds, "combinator": combinator})
    import re
    return re.sub(r'"@@(.*?)@@"', lambda m: f"expr('{{{{ {m.group(1)} }}}}')", body)


def iff(var, name, conds, combinator="and"):
    return f"""
const {var} = ifElse({{
  version: 2.2,
  config: {{ name: '{name}', parameters: {{ conditions: {_conds(conds, combinator)} }} }}
}});
"""


def filt(var, name, conds, combinator="and", sample=None):
    return f"""
const {var} = node({{
  type: 'n8n-nodes-base.filter',
  version: 2.3,
  config: {{ name: '{name}', parameters: {{ conditions: {_conds(conds, combinator)} }} }},
  output: [{json.dumps(sample or {})}]
}});
"""


def run(wf, summary):
    return post("recordRun", "Record Run", "/runs",
                f'{{ workflow: "{wf}", status: "success", summary: {summary}, execution_id: $execution.id }}',
                {"recorded": True}, once=True, cont=True)


def note(text, color=4):
    return f"\nconst note = sticky({json.dumps(text)}, [], {{ color: {color} }});\n"


def notify(var, name, audience, kind, title, body, link, severity, dedupe, extra="", once=False):
    uid = ', user_id: $json.user_id' if audience == "user" else ""
    b = (f'{{ audience: "{audience}"{uid}, kind: "{kind}", title: String({title}).slice(0, 160), '
         f'body: String({body}).slice(0, 500), link: {link}, severity: {severity}, '
         f'dedupe_key: {dedupe}{extra} }}')
    return post(var, name, "/notify", b, {"created": 1, "duplicate": False}, once=once)


W = {}

# 02 ------------------------------------------------------------------------
W["02-booking-reminders"] = (
    "Smart Lab 02 - Upcoming booking reminders",
    schedule("every5", "Every 5 Minutes", "{ field: 'minutes', minutesInterval: 5 }")
    + get("upcoming", "Get Bookings Starting Soon", "/bookings/upcoming?within_minutes=20",
          {"bookings": [{"booking_id": 42, "reminder_sent": False}]})
    + split("each", "One Item Per Booking", "bookings", {"booking_id": 42, "reminder_sent": False})
    + filt("notReminded", "Not Reminded Yet", [cond("$json.reminder_sent", "boolean", "false")],
           sample={"booking_id": 42, "reminder_sent": False})
    + post("remind", "Raise Reminder", "/bookings/{{ $json.booking_id }}/remind", "{}", {"created": True})
    + run("02-booking-reminders", '"Reminders raised: " + $input.all().filter(i => i.json.created).length')
    + note("## Upcoming booking reminders\nIdempotent: the backend raises at most one reminder per booking - shared with the portal's own lazy reminder, so a retry or both paths firing never sends two."),
    ".add(every5).to(upcoming).to(each).to(notReminded).to(remind).to(recordRun).add(note)")

# 03 ------------------------------------------------------------------------
W["03-access-denial-intelligence"] = (
    "Smart Lab 03 - Access denial intelligence",
    webhook("denied", "Access Denied Event", "smartlab-access-denied",
            {"type": "access.denied", "lab_id": 1, "payload": {"reason": "TOKEN_UNKNOWN"}})
    + get("burst", "Evaluate Denial Burst", "/access/denials{{ $json.body.lab_id ? \"?lab_id=\" + $json.body.lab_id : \"\" }}",
          {"level": "warning", "count": 3, "lab_code": "LAB_01", "lab_id": 1, "message": "3 refusals at LAB_01 in 10 min",
           "by_reason": {"TOKEN_UNKNOWN": 3}, "dedupe_key": "denial-burst:1:1"})
    + iff("isBurst", "Is It A Burst?", [cond("$json.level", "string", "equals", "warning")])
    + post("raiseAlert", "Raise Security Alert", "/alerts",
           '{ severity: "WARNING", title: "Repeated refusals at " + $json.lab_code, detail: $json.message + ". Reasons: " + Object.entries($json.by_reason).map(([k, v]) => k + " x" + v).join(", "), lab_id: $json.lab_id, dedupe_key: $json.dedupe_key }',
           {"created": True, "alert_id": 1})
    + notify("tellStaff", "Notify Staff", "staff", "SECURITY_EVENT",
             '"Repeated refusals at " + $("Evaluate Denial Burst").item.json.lab_code',
             '$("Evaluate Denial Burst").item.json.message + " - check the camera and who is at the door."',
             '"/admin/access"', '"warning"', '$("Evaluate Denial Burst").item.json.dedupe_key')
    + run("03-access-denial-intelligence", '"Burst at " + $("Evaluate Denial Burst").item.json.lab_code')
    + note("## Access denial intelligence\n1 refusal = normal (early, wrong code). 3 within 10 min = warning (thresholds in backend config). One alert per burst via dedupe key.\n\nThis workflow NEVER locks or unlocks anything - the door decides on its own.", 3),
    ".add(denied).to(burst).to(isBurst.onTrue(raiseAlert.to(tellStaff).to(recordRun))).add(note)")

# 04 ------------------------------------------------------------------------
W["04-device-offline-escalation"] = (
    "Smart Lab 04 - Device offline alert with escalation",
    webhook("offlineEvent", "Device Offline Event", "smartlab-device-offline", {"type": "device.offline", "device_id": 1})
    + schedule("every5", "Every 5 Minutes", "{ field: 'minutes', minutesInterval: 5 }")
    + get("scan", "Get Offline Devices", "/devices/offline",
          {"offline": [{"device_id": 1, "name": "Master", "level": 2, "audience": "staff", "severity": "warning",
                        "title": "Master offline for 20 min - escalated", "body": "LAB_01", "dedupe_key": "device-offline:1:1:L2"}]},
          once=True)
    + split("each", "One Item Per Device", "offline",
            {"device_id": 1, "level": 2, "audience": "staff", "severity": "warning", "title": "t", "body": "b", "dedupe_key": "k"})
    + post("tell", "Notify By Escalation Level", "/notify",
           '{ audience: $json.audience, kind: "DEVICE_OFFLINE", title: $json.title, body: $json.body, link: "/admin/devices", severity: $json.severity, dedupe_key: $json.dedupe_key }',
           {"created": 1})
    + run("04-device-offline-escalation", '"Offline devices: " + $("Get Offline Devices").first().json.offline.length')
    + note("## Device offline escalation\nLevel 1 at the stale threshold -> staff; level 2 at 15 min -> staff again; level 3 at 60 min -> administrators, critical. One notification per outage per level (dedupe key).\nThe scheduled scan also makes the backend record new outages when nobody has the portal open."),
    ".add(offlineEvent).to(scan).to(each).to(tell).to(recordRun).add(every5).to(scan).add(note)")

# 05 ------------------------------------------------------------------------
W["05-maintenance-automation"] = (
    "Smart Lab 05 - Maintenance automation",
    webhook("created", "Issue Created Event", "smartlab-issue-created", {"type": "issue.created", "object": {"type": "issue", "id": "7"}})
    + get("issue", "Get Issue Context", "/issues/{{ $json.body.object.id }}",
          {"issue_id": 7, "ticket": "ISS-2026-000007", "title": "Scope dead", "severity": "HIGH", "lab_code": "LAB_01",
           "assigned": False, "link": "/issues/7", "bookings_next_24h": 2})
    + iff("urgent", "Urgent And Lab In Use?", [cond("$json.severity", "string", "notEquals", "LOW"),
                                              cond("$json.severity", "string", "notEquals", "MEDIUM"),
                                              cond("$json.bookings_next_24h", "number", "gt", 0)])
    + notify("tellUrgent", "Notify Staff Of Impact", "staff", "MAINTENANCE_DIGEST",
             '$json.severity + " issue in a booked lab: " + $json.ticket',
             '$json.title + " - " + $json.bookings_next_24h + " booking(s) in " + $json.lab_code + " in the next 24 h."',
             '$json.link', '$json.severity === "CRITICAL" ? "critical" : "warning"', '"issue-impact:" + $json.issue_id')
    + schedule("daily", "Daily 08:00", "{ field: 'days', triggerAtHour: 8 }")
    + get("digest", "Get Maintenance Digest", "/maintenance",
          {"open_issues": 3, "overdue": [{"ticket": "ISS-1"}], "unassigned_urgent": [], "assets_due": [], "dedupe_day": "2026-09-26"})
    + iff("anything", "Anything Needs Attention?", [cond("$json.overdue.length + $json.unassigned_urgent.length + $json.assets_due.length", "number", "gt", 0)])
    + notify("tellDigest", "Send Maintenance Digest", "staff", "MAINTENANCE_DIGEST",
             '"Maintenance digest: " + $json.overdue.length + " overdue, " + $json.unassigned_urgent.length + " urgent unassigned"',
             '[...$json.overdue.map(i => i.ticket + " overdue"), ...$json.unassigned_urgent.map(i => i.ticket + " unassigned"), ...$json.assets_due.map(a => a.name + (a.overdue ? " maintenance overdue" : " maintenance due"))].join("; ")',
             '"/issues"', '"warning"', '"maintenance-digest:" + $json.dedupe_day')
    + run("05-maintenance-automation", '"Maintenance notification sent"')
    + note("## Maintenance automation\nEvent path: a HIGH/CRITICAL issue in a lab with bookings in the next 24 h is flagged to staff at once.\nDaily path: overdue (per published SLA), urgent unassigned, and equipment due for maintenance within 7 days."),
    ".add(created).to(issue).to(urgent.onTrue(tellUrgent.to(recordRun))).add(daily).to(digest).to(anything.onTrue(tellDigest.to(recordRun))).add(note)")

# 06 / 07 ------------------------------------------------------------------
for key, title, sched, url, kind, link in (
        ("06-daily-report", "Smart Lab 06 - Daily lab report", "{ field: 'days', triggerAtHour: 20 }", "/reports/daily", "DAILY_REPORT", "Daily 20:00"),
        ("07-weekly-report", "Smart Lab 07 - Weekly lab report", "{ field: 'weeks', weeksInterval: 1, triggerAtDay: [1], triggerAtHour: 7 }", "/reports/weekly", "WEEKLY_REPORT", "Mondays 07:00")):
    W[key] = (title,
        schedule("when", link, sched)
        + get("report", "Build Report In Backend", url,
              ({"title": "Weekly lab report - 2026-09-20 to 2026-09-26", "lines": ["Bookings: none in this period."], "dedupe_key": "weekly-report:2026-09-26"} if key.startswith("07") else {"title": "Daily lab report - 2026-09-26", "lines": ["Bookings: none in this period."], "dedupe_key": "daily-report:2026-09-26"}))
        + notify("send", "Send To Administrators", "admins", kind, "$json.title", '$json.lines.join(" ")',
                 '"/admin/operations"', '"info"', "$json.dedupe_key")
        + run(key, '$("Build Report In Backend").item.json.title')
        + note(f"## {title.split(' - ', 1)[1]}\nThe backend computes every figure from recorded rows (no estimates)"
               + (", including the previous week for comparison" if key.startswith("07") else "")
               + "; n8n only schedules and delivers. Idempotent per period via dedupe key."
               + ("" if key.startswith("07") else " Add an Email/Slack node in parallel to Send To Administrators for an external channel.")),
        ".add(when).to(report).to(send).to(recordRun).add(note)")

# 08 ------------------------------------------------------------------------
W["08-sensor-thresholds"] = (
    "Smart Lab 08 - Sensor threshold alerts",
    schedule("every10", "Every 10 Minutes", "{ field: 'minutes', minutesInterval: 10 }")
    + get("evaluate", "Evaluate Sensors In Backend", "/sensors/evaluate?max_age_minutes=30",
          {"no_data": False, "breaches": [{"lab_id": 1, "lab_code": "LAB_01", "metric": "temperature", "value": 34, "unit": "C",
                                           "status": "high", "min": 16, "max": 30, "title": "LAB_01 temperature high: 34C", "dedupe_key": "sensor:1:temperature:high:2026092610"}]})
    + split("each", "One Item Per Breach", "breaches",
            {"lab_id": 1, "lab_code": "LAB_01", "metric": "temperature", "value": 34, "unit": "C", "status": "high", "min": 16, "max": 30, "title": "t", "dedupe_key": "k"})
    + post("alert", "Raise Threshold Alert", "/alerts",
           '{ severity: "WARNING", title: $json.title, detail: "Allowed range " + ($json.min ?? "-") + " to " + ($json.max ?? "-") + " " + $json.unit + ".", lab_id: $json.lab_id, dedupe_key: $json.dedupe_key }',
           {"created": True})
    + notify("tell", "Notify Staff", "staff", "SENSOR_THRESHOLD", '$("One Item Per Breach").item.json.title',
             '"Latest reading outside the configured range."', '"/admin/operations"', '"warning"',
             '$("One Item Per Breach").item.json.dedupe_key')
    + run("08-sensor-thresholds", '"Breaches: " + $("Evaluate Sensors In Backend").first().json.breaches.length')
    + note("## Sensor thresholds (configuration-driven)\nThresholds live in backend SENSOR_THRESHOLDS (metric=min:max). Stale readings are never treated as OK. With no sensor node installed the backend returns no_data and this workflow does nothing - no simulated values."),
    ".add(every10).to(evaluate).to(each).to(alert).to(tell).to(recordRun).add(note)")

# 09 ------------------------------------------------------------------------
W["09-pre-booking-check"] = (
    "Smart Lab 09 - Pre-booking lab readiness check",
    schedule("every15", "Every 15 Minutes", "{ field: 'minutes', minutesInterval: 15 }")
    + get("upcoming", "Get Bookings In Next Hour", "/bookings/upcoming?within_minutes=60",
          {"bookings": [{"booking_id": 42, "user_id": 2, "lab_code": "LAB_01", "link": "/bookings/42/qr", "readiness": {"level": "warning", "warnings": ["Controller offline"]}}]})
    + split("each", "One Item Per Booking", "bookings",
            {"booking_id": 42, "user_id": 2, "lab_code": "LAB_01", "link": "/bookings/42/qr", "readiness": {"level": "warning", "warnings": ["Controller offline"]}})
    + filt("notReady", "Lab Not Ready", [cond("$json.readiness.level", "string", "equals", "warning")],
           sample={"booking_id": 42, "user_id": 2, "lab_code": "LAB_01", "link": "/bookings/42/qr", "readiness": {"level": "warning", "warnings": ["Controller offline"]}})
    + notify("tellStudent", "Warn Student", "user", "PRE_BOOKING_CHECK",
             '"Heads-up for your " + $json.lab_code + " booking"',
             '$json.readiness.warnings.join(" ") + " Your booking is unchanged."',
             "$json.link", '"warning"', '"pre-booking:" + $json.booking_id', extra=", booking_id: $json.booking_id")
    + notify("tellStaff", "Warn Staff", "staff", "PRE_BOOKING_CHECK",
             '"Lab not ready for booking #" + $("Lab Not Ready").item.json.booking_id',
             '$("Lab Not Ready").item.json.lab_code + ": " + $("Lab Not Ready").item.json.readiness.warnings.join(" ")',
             '"/admin/bookings"', '"warning"', '"pre-booking-staff:" + $("Lab Not Ready").item.json.booking_id')
    + run("09-pre-booking-check", '"Warnings sent"')
    + note("## Pre-booking check\nWarns the student and staff when a lab is not ready (controller offline, critical issue). It never cancels or changes a booking."),
    ".add(every15).to(upcoming).to(each).to(notReady).to(tellStudent).to(tellStaff).to(recordRun).add(note)")

# 10 ------------------------------------------------------------------------
W["10-post-session"] = (
    "Smart Lab 10 - Post-session follow-up",
    schedule("every30", "Every 30 Minutes", "{ field: 'minutes', minutesInterval: 30 }")
    + get("ended", "Get Bookings That Just Ended", "/bookings/ended?minutes=60",
          {"bookings": [{"booking_id": 42, "user_id": 2, "attended": True, "title": "Session ended - LAB_01", "body": "Entered 10:02 UTC.", "link": "/bookings/42", "dedupe_key": "post-session:42"}]})
    + split("each", "One Item Per Booking", "bookings",
            {"booking_id": 42, "user_id": 2, "attended": True, "title": "t", "body": "b", "link": "/bookings/42", "dedupe_key": "post-session:42"})
    + notify("tell", "Send Follow-up", "user", "POST_SESSION", "$json.title", "$json.body", "$json.link",
             '$json.attended ? "info" : "warning"', "$json.dedupe_key", extra=", booking_id: $json.booking_id")
    + run("10-post-session", '"Follow-ups: " + $("Get Bookings That Just Ended").first().json.bookings.length')
    + note("## Post-session\nAttended: summary, and says 'exit not recorded' honestly when no exit was observed. Missed: a gentle no-show note. Text is composed by the backend."),
    ".add(every30).to(ended).to(each).to(tell).to(recordRun).add(note)")

# 11 ------------------------------------------------------------------------
W["11-data-quality"] = (
    "Smart Lab 11 - Daily data quality check",
    schedule("daily", "Daily 06:00", "{ field: 'days', triggerAtHour: 6 }")
    + get("check", "Run Checks In Backend", "/data-quality",
          {"failing": 1, "summary": "1 check(s) need attention", "dedupe_key": "data-quality:2026-09-26"})
    + iff("failing", "Any Check Failing?", [cond("$json.failing", "number", "gt", 0)])
    + notify("tell", "Notify Administrators", "admins", "DATA_QUALITY",
             '"Data quality: " + $json.failing + " check(s) need attention"', "$json.summary",
             '"/admin/operations"', '"info"', "$json.dedupe_key")
    + run("11-data-quality", '$("Run Checks In Backend").item.json.summary')
    + note("## Data quality\nRead-only consistency checks (stale sessions, entries on cancelled bookings, unattributed events, devices never reporting, implausible sensor values...). Nothing is modified - a human decides."),
    ".add(daily).to(check).to(failing.onTrue(tell.to(recordRun))).add(note)")

# 12 ------------------------------------------------------------------------
W["12-anomaly-detection"] = (
    "Smart Lab 12 - Rule-based anomaly detection",
    schedule("hourly", "Every Hour", "{ field: 'hours', hoursInterval: 1 }")
    + get("scan", "Run Anomaly Rules", "/anomalies?hours=24",
          {"count": 1, "anomalies": [{"rule": "denial_burst", "severity": "warning", "lab_code": "LAB_01", "count": 4, "detail": "4 refusals within 10 min.", "dedupe_key": "anomaly:denial_burst:1:2026-09-26"}]})
    + split("each", "One Item Per Anomaly", "anomalies",
            {"rule": "denial_burst", "severity": "warning", "lab_code": "LAB_01", "count": 4, "detail": "d", "dedupe_key": "k"})
    + notify("tell", "Notify Staff", "staff", "ANOMALY",
             '"Anomaly: " + $json.rule.replaceAll("_", " ") + ($json.lab_code ? " at " + $json.lab_code : "")',
             "$json.detail", '"/admin/access"', "$json.severity", "$json.dedupe_key")
    + run("12-anomaly-detection", '"Anomalies: " + $("Run Anomaly Rules").first().json.count')
    + note("## Rule-based anomaly detection\nExplainable rules only, evaluated in the backend: denial bursts, repeated identity mismatch, after-hours access, forced entry / door held open, device flapping, refusals far above the lab's own 7-day baseline. No ML model - there is no training data. One notification per rule, lab and day."),
    ".add(hourly).to(scan).to(each).to(tell).to(recordRun).add(note)")

out = pathlib.Path("src")
for key, (title, body, chain) in W.items():
    code = HEAD + body + f"\nexport default workflow('smartlab-{key[:2]}', '{title}')\n  {chain};\n"
    (out / f"{key}.ts").write_text(code)
print("\n".join(sorted(p.name for p in out.glob("*.ts"))))
