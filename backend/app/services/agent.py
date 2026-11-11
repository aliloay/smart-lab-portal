"""
Smart Lab agent: instant, exact answers straight from the database.

The local language model is slow on a laptop (seconds per step) and can
misread numbers. Most questions people actually ask have one exact answer
the portal already knows, so the agent answers those itself, in
milliseconds, with no model at all:

    students   my next booking, my bookings, which labs are free now
    staff      weekly / monthly report, who is inside, equipment usage,
               recurring problems with recommendations, offline devices,
               open maintenance

Anything else goes to the language model (app.services.ai), which gets a
compact snapshot of the same data so it rarely needs a tool round-trip.

Also here: the management report (weekly / monthly, with the previous
period for comparison) behind the printable report page, and the insight
rules that turn repeated alerts, refusals and faults into recommendations.
Every figure is counted from stored records; nothing is estimated.
"""
from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (AccessEvent, AccessSession, Alert, Booking, BookingStatus, Device,
                        DeviceType, EquipmentSession, EventType, Issue, Lab, Role, User)
from app.services import agent_history
from app.services.automation import period_report
from app.services.devices import is_fresh, refresh_liveness
from app.services.issues import ACTIVE as ISSUE_ACTIVE
from app.ui_text import denial_sentence


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.LOCAL_TIMEZONE)


def _when(dt: Optional[datetime]) -> str:
    return "-" if dt is None else _utc(dt).astimezone(_tz()).strftime("%a %d %b, %H:%M")


def _hm(dt: datetime) -> str:
    return _utc(dt).astimezone(_tz()).strftime("%H:%M")


def _hours(seconds: float) -> float:
    return round(seconds / 3600, 1)


# ------------------------------------------------------- equipment usage ---
def equipment_usage(db: Session, start: datetime, end: datetime) -> list[dict]:
    """Running / idle / fault time of each robot and PC in [start, end)."""
    out = []
    devices = db.scalars(select(Device).where(
        Device.device_type.in_([DeviceType.ROBOT, DeviceType.PC]))).all()
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    now = datetime.now(timezone.utc)
    for d in devices:
        secs: Counter = Counter()
        faults = 0
        users = set()
        for s in db.scalars(select(EquipmentSession).where(
                EquipmentSession.device_id == d.id, EquipmentSession.started_at < end,
                (EquipmentSession.ended_at.is_(None)) | (EquipmentSession.ended_at > start))).all():
            a = max(_utc(s.started_at), start)
            b = min(_utc(s.ended_at) if s.ended_at else now, end)
            if b > a:
                secs[s.state] += (b - a).total_seconds()
            if s.state == "FAULT" and _utc(s.started_at) >= start:
                faults += 1
            if s.state == "RUNNING" and s.user_id:
                users.add(s.user_id)
        out.append({"device_uid": d.device_uid, "name": d.name, "kind": d.device_type.value,
                    "lab_code": labs.get(d.lab_id), "running_h": _hours(secs["RUNNING"]),
                    "idle_h": _hours(secs["IDLE"]), "fault_h": _hours(secs["FAULT"]),
                    "faults": faults, "users": len(users), "master_pc": bool(d.is_master_pc)})
    return sorted(out, key=lambda r: -r["running_h"])


# -------------------------------------------------------------- insights ---
# Recurring alert -> a plan someone can carry out (first matching pattern wins):
# the likely cause, numbered steps, and a check that says when it is fixed.
# No invented numbers: thresholds come from the parts' datasheets or a test.
PLAYBOOK: list[tuple[str, dict]] = [
    (r"held open", {
        "cause": "The door does not latch by itself, or people leave it open.",
        "steps": ["Open the door fully and let go: it must close and latch on its own.",
                  "Adjust or replace the door closer; align the door-sensor magnet with the switch.",
                  "Put a 'close the door behind you' sign on the inside."],
        "done": "No 'held open' alert in 7 days of normal use."}),
    (r"forced", {
        "cause": "The door sensor saw the door open while it was locked. On a bench rig this is "
                 "usually the magnet switch bouncing or sitting off-centre, not a break-in.",
        "steps": ["For each time listed, check the camera events and who was there; if nobody forced "
                  "the door, mark it a false alarm.",
                  "Check the magnet and switch: aligned, within the switch's rated gap, firmly mounted.",
                  "If the switch chatters, add a short debounce in the door firmware (flash it when the "
                  "door is powered again)."],
        "done": "10 lock / open / close cycles in a row with no false 'forced' alert, recorded as an "
                "experiment."}),
    (r"weight does not match", {
        "cause": "The bin's load cell drifted, or items were taken without being scanned.",
        "steps": ["Tare and recalibrate the load cell with a known weight.",
                  "Check the item tags in the bin match the inventory.",
                  "Review who used the bin at those times."],
        "done": "A week of scans with no weight mismatch."}),
    (r"low stock|reorder|below", {
        "cause": "Use is faster than the reorder level assumes.",
        "steps": ["Reorder now.", "Raise the item's reorder level to cover the time a delivery takes."],
        "done": "The item stays above its reorder level for a month."}),
    (r"(camera|rfid|fingerprint|reader|sensor|lcd|display).*not responding", {
        "cause": "The controller stopped hearing that module: a loose jumper or connector, or its "
                 "supply dipping when the lock relay or the module draws current.",
        "steps": ["Replace the jumper wires to that module with crimped or soldered connections.",
                  "Measure the module's supply with a multimeter while the lock relay switches; if it "
                  "dips, give the lock its own supply and add a capacitor next to the module.",
                  "Power the controller for 24 h and watch the Alerts page."],
        "done": "No 'not responding' alert in a 24 h powered test."}),
    (r"offline|not responding|no heartbeat", {
        "cause": "The node lost power or Wi-Fi - or the laptop running the portal was off, which "
                 "looks the same from here.",
        "steps": ["Compare the times with when the laptop / portal was off; those are not node faults.",
                  "Reserve the node's address on the router (DHCP reservation) and check the Wi-Fi "
                  "signal where it is mounted.",
                  "Use a power supply rated above the board's peak current, with a short USB cable."],
        "done": "The node stays online for 24 h with the portal running."}),
    (r"temperature|heat|humid", {
        "cause": "Poor ventilation, or the sensor sits near a heat source.",
        "steps": ["Move the sensor away from PC exhausts, windows and direct sun.",
                  "Check the ventilation / air conditioning at the times listed."],
        "done": "Readings stay inside the limits for a week."}),
    (r"gas|smoke|flame|fire", {
        "cause": "Flame (infrared) sensors also react to sunlight, lamps and IR remotes; gas sensors "
                 "read high while they warm up after power-on.",
        "steps": ["For each time listed, confirm there was no real flame or smoke (camera, people there).",
                  "Shield the flame sensor from windows and lamps and turn its sensitivity down on the "
                  "module's potentiometer.",
                  "In the environment-node firmware, alarm only when two readings in a row agree, and "
                  "ignore the gas sensor during its warm-up."],
        "done": "A full day under normal lab lighting with no alarm, and a lighter at the test "
                "distance still triggers one."}),
    (r"moved|no longer looks|equipment", {
        "cause": "The equipment was moved, or the camera's reference box is out of date.",
        "steps": ["Put the equipment back, or accept the new position on the Security camera page."],
        "done": "No 'moved' alert for that item in a week."}),
    (r"refusal|denied", {
        "cause": "See the refusal reasons.",
        "steps": ["Open the refusal reasons below: most repeated refusals have a simple fix."],
        "done": "Refusals for that reason fall week over week."}),
]
DEFAULT_PLAN = {
    "cause": "Not in the playbook yet.",
    "steps": ["Open the alerts with this title and find what was happening at those times.",
              "Fix the cause, or raise the threshold if nobody needs to act on this alert."],
    "done": "The alert stops repeating, or every time it fires someone has to act."}
# One-line versions, for older callers.
ALERT_FIXES: list[tuple[str, str]] = [(p, " ".join(d["steps"])) for p, d in PLAYBOOK]
DEFAULT_FIX = " ".join(DEFAULT_PLAN["steps"])
# Proven real use; everything else may be bench testing.
REAL = ("REAL_OPERATION", "PHYSICAL_TEST")
ONGOING_H = 48


def _plan(item: dict, plan: dict) -> dict:
    """The item with its plan; `recommendation` stays the one-line summary."""
    return {**item, "cause": plan["cause"], "steps": plan["steps"], "done_when": plan["done"],
            "recommendation": " ".join(plan["steps"])}


def _denial_plan(reason: str) -> dict:
    """DENIAL_FIXES read 'what is happening: what to do' - split into cause and step."""
    fix = DENIAL_FIXES.get(reason, DEFAULT_FIX)
    cause, _, step = fix.partition(": ")
    if not step:
        cause, step = "", fix
    return {"cause": cause + "." if cause else "", "steps": [step[0].upper() + step[1:]],
            "done": "Refusals for this reason fall week over week (Reports page)."}


def _timing(item: dict, end: datetime) -> dict:
    """Still happening (in the last 48 h of the period) or quiet since its last time."""
    last = item.get("last")
    item["ongoing"] = bool(last and (end - _utc(last)).total_seconds() < ONGOING_H * 3600)
    return item


# Repeated door refusal reason -> what to do about it.
DENIAL_FIXES = {
    "BOOKING_NOT_STARTED": "People arrive before their slot: consider a longer early grace "
                           "(BOOKING_GRACE_MINUTES) or remind them of the start time.",
    "BOOKING_EXPIRED": "People come back after their slot ended: suggest longer bookings or extend them.",
    "NO_ACTIVE_BOOKING": "People try to enter without a booking: point them to Book a lab, or add open hours.",
    "TOKEN_UNKNOWN": "Unknown codes are being scanned: check for photographed or old QR codes.",
    "TOKEN_REVOKED": "Old QR codes are used after re-booking: remind people to open the newest one.",
    "WRONG_LAB": "People go to the wrong lab: make the lab name clearer on the booking and the door.",
    "UNKNOWN_CREDENTIAL": "Unregistered cards are being tapped: enrol them on the user's page.",
    "IDENTITY_MISMATCH": "The fingerprint or face does not match the QR's owner: re-enrol the people "
                         "concerned, or check for someone using another person's code.",
    "BIOMETRIC_FAILED": "Biometric checks fail often: re-enrol those users' fingerprints / faces and "
                        "clean the sensor and camera lens.",
    "BIOMETRIC_TIMEOUT": "People do not finish step 2 in time: add a sign at the door explaining it.",
    "BACKEND_UNAVAILABLE": "The door could not reach the portal: check the laptop and the router.",
    # As the door controller reports them.
    "FACE MISMATCH": "The face does not match the QR's owner: re-enrol those faces with better "
                     "photos (front, good light), check the door light, or someone used another's code.",
    "WRONG FINGER": "The finger does not match the QR's owner: re-enrol those fingerprints (two "
                    "fingers each) and clean the sensor.",
    "FINGER TIMEOUT": "People do not put a finger on the sensor in time: add a sign at the door "
                      "explaining step 2.",
}

ALERT_MIN, DENIAL_MIN, OFFLINE_MIN, PERSON_MIN = 3, 5, 3, 3


def _norm_title(t: str) -> str:
    return re.sub(r"\d+", "#", t.lower()).strip()


def insights(db: Session, start: datetime, end: datetime) -> list[dict]:
    """Repeated problems in [start, end), each with a recommendation. Most frequent first."""
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    out: list[dict] = []

    # 1) The same alert again and again.
    groups: dict[tuple, list[Alert]] = defaultdict(list)
    for a in db.scalars(select(Alert).where(Alert.created_at >= start, Alert.created_at < end)).all():
        groups[(a.lab_id, _norm_title(a.title))].append(a)
    for (lab_id, _), rows in groups.items():
        if len(rows) < ALERT_MIN:
            continue
        title = rows[-1].title
        plan = next((d for p, d in PLAYBOOK if re.search(p, title.lower())), DEFAULT_PLAN)
        out.append(_plan({"kind": "ALERT", "title": title, "lab_code": labs.get(lab_id), "count": len(rows),
                          "first": min(r.created_at for r in rows), "last": max(r.created_at for r in rows),
                          "unresolved": sum(1 for r in rows if not r.is_resolved),
                          "real": sum(1 for r in rows if r.provenance in REAL),
                          "severity": "bad" if any(r.severity.value == "CRITICAL" for r in rows) else "warn"},
                         plan))

    # 2) The same door refusal reason, and the same person refused by the biometric.
    denials = db.execute(select(AccessEvent.reason, AccessEvent.lab_id, AccessEvent.user_id,
                                AccessEvent.created_at, AccessEvent.provenance).where(
        AccessEvent.event_type.in_([EventType.ACCESS_DENIED, EventType.IDENTITY_MISMATCH]),
        AccessEvent.created_at >= start, AccessEvent.created_at < end)).all()
    by_reason = Counter(r.reason for r in denials if r.reason)
    for reason, n in by_reason.most_common():
        if n < DENIAL_MIN:
            break
        rows = [r for r in denials if r.reason == reason]
        out.append(_plan({"kind": "DENIAL", "title": f"Door refused {n}x: {denial_sentence(reason)}",
                          "reason": reason, "lab_code": None, "count": n, "severity": "warn",
                          "first": min(r.created_at for r in rows), "last": max(r.created_at for r in rows),
                          "real": sum(1 for r in rows if r.provenance in REAL)},
                         _denial_plan(reason)))
    per_person = Counter(r.user_id for r in denials if r.user_id and r.reason in
                         ("IDENTITY_MISMATCH", "BIOMETRIC_FAILED", "BIOMETRIC_TIMEOUT"))
    for uid, n in per_person.most_common():
        if n < PERSON_MIN:
            break
        u = db.get(User, uid)
        who = u.full_name if u else f"user {uid}"
        rows = [r for r in denials if r.user_id == uid]
        out.append(_plan({"kind": "PERSON", "title": f"{who}: biometric refused {n}x", "count": n,
                          "lab_code": None, "severity": "warn",
                          "first": min(r.created_at for r in rows), "last": max(r.created_at for r in rows),
                          "real": sum(1 for r in rows if r.provenance in REAL)},
                         {"cause": "This person's stored fingerprint or face no longer matches well.",
                          "steps": [f"Re-enrol {who}'s fingerprint (two fingers) and face (front, good "
                                    f"light) on the Users page.",
                                    "If it still fails, clean the fingerprint sensor and the camera lens."],
                          "done": f"{who} passes step 2 at the first try 5 times in a row."}))

    # 3) The same device dropping off again and again.
    offline = Counter(r.device_id for r in db.execute(select(AccessEvent.device_id).where(
        AccessEvent.event_type == EventType.DEVICE_OFFLINE, AccessEvent.device_id.is_not(None),
        AccessEvent.created_at >= start, AccessEvent.created_at < end)).all())
    for did, n in offline.most_common():
        if n < OFFLINE_MIN:
            break
        d = db.get(Device, did)
        if d and any(d.name in i["title"] and "offline" in i["title"].lower() for i in out):
            continue                   # already flagged by its repeated alert
        out.append(_plan({"kind": "DEVICE", "title": f"{d.name if d else did} went offline {n}x",
                          "lab_code": labs.get(d.lab_id) if d else None, "count": n, "severity": "warn"},
                         next(p for r, p in PLAYBOOK if r.startswith("offline"))))

    # 4) The same equipment reported broken more than once.
    per_asset = Counter(i.asset_id for i in db.scalars(select(Issue).where(
        Issue.asset_id.is_not(None), Issue.created_at >= start, Issue.created_at < end)).all())
    for aid, n in per_asset.most_common():
        if n < 2:
            break
        from app.models import Asset
        a = db.get(Asset, aid)
        out.append(_plan({"kind": "EQUIPMENT", "title": f"{a.asset_tag if a else aid} reported {n}x",
                          "lab_code": labs.get(a.lab_id) if a else None, "count": n, "severity": "warn"},
                         {"cause": "The same item keeps failing: each report was patched, not fixed.",
                          "steps": ["Read the reports together and find what they share.",
                                    "Repair it properly or replace it; note the fix on the ticket."],
                          "done": "No new report on this item for a month."}))

    # 5) Bookings people do not turn up for; sessions without an exit.
    r = period_report(db, start, end)
    b, s = r["bookings"], r["sessions"]
    if b["finished"] >= 5 and b["no_show"] / b["finished"] > 0.3:
        out.append(_plan({"kind": "BOOKINGS", "title": f"{b['no_show']} of {b['finished']} bookings were no-shows",
                          "lab_code": None, "count": b["no_show"], "severity": "warn"},
                         {"cause": "People book and do not come, which blocks the lab for others.",
                          "steps": ["Send a reminder before each booking (n8n workflow 02).",
                                    "Release slots that nobody enters within the grace time."],
                          "done": "No-shows below 30 % of finished bookings."}))
    if s["started"] >= 5 and s["exit_not_recorded"] / s["started"] > 0.5:
        out.append(_plan({"kind": "SESSIONS", "title": f"Exit not recorded for {s['exit_not_recorded']} of "
                                                       f"{s['started']} sessions",
                          "lab_code": None, "count": s["exit_not_recorded"], "severity": "info"},
                         {"cause": "The portal only knows someone left when the door reports an exit.",
                          "steps": ["Check the door sensor reports every close.",
                                    "Ask people to tap out, or add an exit reader."],
                          "done": "Most sessions end with a recorded exit."}))

    # Still happening first, then the most serious, then the most frequent.
    rank = {"bad": 0, "warn": 1, "info": 2}
    out = [_timing(i, end) for i in out]
    return sorted(out, key=lambda i: (not i["ongoing"], rank.get(i["severity"], 3), -i["count"]))


def _day(dt) -> str:
    return _utc(dt).astimezone(_tz()).strftime("%d %b")


def plan_text(found: list[dict], days: int, limit: int = 5) -> str:
    """The 'what should we fix / how do we do better' answer: each repeated
    problem with its evidence, likely cause, steps and a 'done when' check."""
    lines = [f"**Improvement plan - last {days} days** ({len(found)} repeated problem"
             f"{'s' if len(found) != 1 else ''}, still happening first)"]
    real = sum(i.get("real") or 0 for i in found)
    dated = [i for i in found if i.get("first")]
    if dated and real == 0:
        lines.append(f"_Evidence quality: none of these is marked as real lab use. They were recorded "
                     f"between {_day(min(i['first'] for i in dated))} and "
                     f"{_day(max(i['last'] for i in dated))}, before the data mode existed, much of it "
                     f"bench testing. Fix what is cheap now; confirm the rest on the installed system "
                     f"before buying parts._")
    for n, i in enumerate(found[:limit], 1):
        facts = [f"{i['count']}x"]
        if i.get("first"):
            facts.append(f"{_day(i['first'])} - {_day(i['last'])}")
            facts.append("still happening" if i["ongoing"] else f"not seen since {_day(i['last'])}")
        if i.get("unresolved"):
            facts.append(f"{i['unresolved']} still open")
        where = f" ({i['lab_code']})" if i.get("lab_code") else ""
        lines.append(f"\n**{n}. {i['title']}**{where} - " + " · ".join(facts))
        if i.get("cause"):
            lines.append(f"Likely cause: {i['cause']}")
        lines.append("\n".join(f"{k}. {step}" for k, step in enumerate(i["steps"], 1)))
        lines.append(f"Done when: {i['done_when']}")
    if len(found) > limit:
        lines.append(f"\n+ {len(found) - limit} more in the monthly report.")
    first = next((i for i in found if i["ongoing"]), found[0])
    lines.append(f"\n**Next single action:** {first['steps'][0]}")
    return "\n".join(lines)


# ---------------------------------------------------------------- report ---
def _period(period: str, end_day: Optional[date]) -> tuple[datetime, datetime, str]:
    end_day = end_day or datetime.now(_tz()).date()
    end = datetime(end_day.year, end_day.month, end_day.day, tzinfo=timezone.utc) + timedelta(days=1)
    days = 30 if period == "monthly" else 7
    return end - timedelta(days=days), end, f"{days} days"


def _change(now: float, before: float) -> Optional[float]:
    return None if not before else round((now - before) / before * 100)


def management_report(db: Session, period: str = "weekly", end_day: Optional[date] = None) -> dict:
    """Weekly (7 days) or monthly (30 days) report, with the previous period to compare."""
    start, end, span = _period(period, end_day)
    r = period_report(db, start, end)
    prev = period_report(db, start - (end - start), start)
    usage = equipment_usage(db, start, end)
    found = insights(db, start, end)
    b, pb = r["bookings"], prev["bookings"]
    r.update({
        "kind": period, "span": span,
        "title": f"{'Monthly' if period == 'monthly' else 'Weekly'} lab report",
        "period_label": f"{_utc(start).astimezone(_tz()):%d %b} - "
                        f"{(_utc(end) - timedelta(seconds=1)).astimezone(_tz()):%d %b %Y}",
        "previous": {"bookings": pb, "access": {k: prev["access"][k] for k in ("granted", "denied")},
                     "maintenance": {k: prev["maintenance"][k] for k in ("opened", "resolved")}},
        "change_pct": {"bookings": _change(b["confirmed"], pb["confirmed"]),
                       "hours": _change(b["booked_hours"], pb["booked_hours"]),
                       "entries": _change(r["access"]["granted"], prev["access"]["granted"])},
        "equipment": usage,
        "insights": [{**i, "first": i.get("first") and _when(i["first"]),
                      "last": i.get("last") and _when(i["last"])} for i in found],
        "top_denials": [{"reason": d["reason"], "count": d["count"],
                         "meaning": denial_sentence(d["reason"])} for d in r["access"]["top_denial_reasons"]],
        # The same charts the assistant draws, for the printable report / PDF.
        "charts": agent_history.charts(db, *agent_history.last_days(30 if period == "monthly" else 7)),
    })
    return r


# --------------------------------------------------------- live answers ---
def occupancy(db: Session) -> list[dict]:
    """Who is inside each lab now (open sessions), by role."""
    labs = {l.id: l for l in db.scalars(select(Lab).order_by(Lab.code)).all()}
    inside: dict[int, list[User]] = defaultdict(list)
    for s in db.scalars(select(AccessSession).where(AccessSession.ended_at.is_(None))).all():
        u = db.get(User, s.user_id)
        if u:
            inside[s.lab_id].append(u)
    return [{"lab_code": labs[lid].code, "lab_name": labs[lid].name,
             "people": [{"name": u.full_name, "role": u.role.value} for u in people]}
            for lid, people in inside.items() if lid in labs]


def free_labs(db: Session, now: Optional[datetime] = None) -> list[dict]:
    """Active labs with no booking right now, and until when they stay free today."""
    now = now or datetime.now(timezone.utc)
    end_of_day = datetime.now(_tz()).replace(hour=23, minute=59).astimezone(timezone.utc)
    live = (BookingStatus.CONFIRMED, BookingStatus.PENDING)
    out = []
    for lab in db.scalars(select(Lab).where(Lab.is_active.is_(True)).order_by(Lab.code)).all():
        busy = db.scalar(select(Booking).where(Booking.lab_id == lab.id, Booking.status.in_(live),
                                               Booking.start_time <= now, Booking.end_time > now))
        if busy:
            continue
        nxt = db.scalar(select(Booking).where(Booking.lab_id == lab.id, Booking.status.in_(live),
                                              Booking.start_time > now, Booking.start_time < end_of_day)
                        .order_by(Booking.start_time))
        out.append({"code": lab.code, "name": lab.name, "free_until": _hm(nxt.start_time) if nxt else None})
    return out


def _camera_activity(db, now) -> list[str]:
    """The live activity lines the security cameras reported (tools/security_vision/activity.py), fresh cameras only."""
    from app.models import Device, DeviceType
    out = []
    for d in db.scalars(select(Device).where(Device.device_type == DeviceType.SECURITY_CAMERA).order_by(Device.name)).all():
        if not is_fresh(d, now):
            continue
        for a in ((d.component_state or {}).get("activity") or [])[:12]:
            if isinstance(a, dict) and a.get("text"):
                out.append(f"{d.name}: {a['text']}")
    return out


def _bullets(rows: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rows)


def _report_text(r: dict) -> str:
    ch = r["change_pct"]
    pct = lambda v: "" if v is None else f" ({'+' if v >= 0 else ''}{v}% vs previous)"  # noqa: E731
    b = r["bookings"]
    lines = [f"**{r['title']}** · {r['period_label']}",
             _bullets([f"Bookings: {b['confirmed']} confirmed{pct(ch['bookings'])}, "
                       f"{b['booked_hours']} h booked{pct(ch['hours'])}",
                       f"Attendance: {round(b['attendance_rate'] * 100)}%, {b['no_show']} no-show"
                       if b["attendance_rate"] is not None else "Attendance: no finished bookings",
                       f"Door: {r['access']['granted']} entries{pct(ch['entries'])}, "
                       f"{r['access']['denied']} refused",
                       f"Maintenance: {r['maintenance']['opened']} opened, {r['maintenance']['resolved']} "
                       f"resolved, {r['maintenance']['open_now']} open now"])]
    busiest = [lab for lab in r["labs"] if lab["hours"]][:3]
    if busiest:
        lines.append("**Busiest labs:** " + ", ".join(f"{lab['lab_code']} {lab['hours']} h" for lab in busiest))
    used = [e for e in r["equipment"] if e["running_h"]][:3]
    if used:
        lines.append("**Most used equipment:** " + ", ".join(f"{e['name']} {e['running_h']} h" for e in used))
    if r["insights"]:
        lines.append("**Needs attention:**\n" + _bullets(
            [f"{i['title']} → {i['recommendation']}" for i in r["insights"][:3]]))
    return "\n".join(lines)


_PATTERNS: list[tuple[str, str, bool]] = [
    # (intent, regex, staff only)
    # 2026-10-27 instant categories (owner: "instant replies for common questions"): checked before the reports so
    # "compare this week with last week" / "daily summary" / "what is low" never reach the language model.
    # time periods only ("compare the robotics lab and the PLC lab" is about two labs - not this answer)
    # "how to make the ur5e better" / "what's wrong with PC-05": that device's own records, instant (2026-10-27)
    ("device_advice", r"\b(how (to|can (we|i)|do (we|i)|should (we|i)) (make|improve|optimi[sz]e|maintain|fix|speed up)|improv\w*|"
                      r"better|optimi[sz]\w*|what('?s| is) wrong with|problems? with|issues? with|health of|check (the|on))\b"
                      r".*\b(ur5e?|fanuc|robots?|pc[- ]?\d+|cameras?|door|bins?|environment|sensor node|scale)\b", True),
    ("compare", r"\b(compare\w*|comparison|versus|vs\.?)\b.*\b(week|month|yesterday|previous|before|last)\b|"
                r"\bthan (last|the previous|previous) (week|month)\b|\b(this|last) (week|month)\b.*\b(last|previous|before)\b", True),
    ("report_daily", r"\b(daily|today'?s?|day)\b.*\b(report|summary|overview|recap)\b|"
                     r"\b(report|summary|overview|recap)\b.*\b(today|daily)\b|\bwhat happened today\b", True),
    ("low_stock", r"\b(running (low|out)|reorder|re-order|restock|need to (order|buy)|almost empty)\b|"
                  r"\b(low)\b.*\b(stock|bins?|consumables?|parts?|items?|inventory)\b|\bwhat is low\b", True),
    ("recent_activity", r"\b(recent|latest|last)\b.*\b(activity|events?|happen\w*|entries|logs?)\b|"
                        r"\bwhat (just )?happened\b|\bactivity (log|feed)\b", True),
    ("bookings_today", r"\b(bookings?|reservations?)\b.*\b(today|this (morning|afternoon))\b|"
                       r"\btoday'?s? bookings?\b|\bwho (has )?booked\b", True),
    ("empty_labs", r"\b(empty|unoccupied|nobody in|no one in|vacant)\b.*\blabs?\b|\blabs?\b.*\b(empty|unoccupied|vacant)\b|"
                   r"\bwho is where\b", True),
    ("report_monthly", r"\bmonth(ly)?\b.*\b(report|summary|usage|analysis|overview)\b|"
                       r"\b(report|summary|usage|analysis|overview)\b.*\bmonth(ly)?\b", True),
    ("report_weekly", r"\b(week(ly)?)\b.*\b(report|summary|usage|analysis|overview)\b|"
                      r"\b(report|summary|usage|analysis|overview)\b.*\bweek(ly)?\b", True),
    ("insights", r"\b(recurr\w*|repeat\w*|keeps? (happening|coming)|same (alert|error|problem)|"
                 r"recommend\w*|suggest\w*|insights?|what should (we|i) (fix|do|check)|anything unusual|anomal\w*)\b", True),
    ("equipment", r"\b(robots?|pcs?|computers?|equipment|ur5e?|fanuc)\b.*\b(used|usage|use|hours|busiest|most)\b|"
                  r"\bmost used\b", True),
    # 2026-11-11: "what is everyone doing / who is doing what" -> the cameras' live activity lines, instantly
    ("activity_now", r"\b(who is doing what|what is (every|any)one doing|what are (they|people) doing|"
                     r"doing (right )?now|what'?s happening in the lab|activity in the lab)\b", True),
    ("inside", r"\b(who|how many)\b.*\b(inside|in the labs?|present|in lab)\b|\boccupancy\b", True),
    # 2026-10-18: "What is the temperature?" got the data-source overview, and "How many resistors are in
    # the bin?" went to the language model (213 s), which then said it could not answer.
    ("environment_now", r"\b(temperature|humidity|smoke|gas|flame|fire|motion|warm|hot|cold)\b", True),
    ("bins_stock", r"\bhow many\b.*\b(resistors?|parts?|pieces?|items?|components?|left|in (the|a) bins?)\b|"
                   r"\b(bins?|consumables?|stock|inventory|resistors?)\b.*\b(count|left|level|stock|how many|status)\b", True),
    ("system", r"\b(system|data sources?|subsystems?|integrations?)\b.*\b(status|health|fresh\w*|overview|summary|working)\b|"
               r"\bhow is the (lab|system)\b", True),
    ("offline", r"\b(offline|disconnected|not (responding|connected))\b", True),
    # 2026-10-18: status questions answered from the records in milliseconds - they used to go to the
    # language model with the whole lab snapshot (48 s on the CPU, and it starved the camera analysis).
    ("robots_status", r"\b(robots?|ur5e?|fanuc)\b.*\b(online|status|state|connected|running|working|ready|blocked|live)\b|"
                      r"\b(online|status|state)\b.*\b(robots?|ur5e?|fanuc)\b", True),
    ("cameras_status", r"\b(cameras?|cctv)\b.*\b(online|status|state|working|live|connected|running)\b|"
                       r"\b(online|status|state)\b.*\b(cameras?|cctv)\b", True),
    # free / busy / available / in use (2026-11-11): "Which PCs are free?" went to the model - 14-30 s and a wrong,
    # repeating list. The device reports already say it: online + nobody signed in = free.
    ("pcs_status", r"\b(pcs?|computers?)\b.*\b(online|status|state|connected|running|free|busy|available|in use|"
                   r"occupied|taken)\b|\b(online|status|state|free|busy|available)\b.*\b(pcs?|computers?)\b", True),
    ("alerts_open", r"\b(open|active|unresolved|current|pending)\b.*\b(alerts?|alarms?|incidents?)\b|"
                    r"\b(alerts?|alarms?|incidents?)\b.*\b(open|active|unresolved|now|today)\b|"
                    r"\bany (alerts?|alarms?|incidents?)\b", True),
    # "open maintenance issues" reached the model, which printed a raw tool call (2026-10-27 question mix)
    ("open_issues", r"\bopen (maintenance )?(issues|tickets|reports|faults)\b|\bmaintenance\b.*\b(open|pending|backlog|issues|tickets)\b|"
                    r"\b(issues|tickets)\b.*\b(open|pending|unresolved)\b", True),
    # "tell me about the PLC lab" / "how is LAB_02": that lab's state now, from the records (2026-10-27)
    ("lab_info", r"\b(tell me about|about|status of|state of|how is|what about|info(rmation)? (on|about)|describe)\b.*\blab(s|_\w+|\s?\d+)?\b", False),
    ("next_booking", r"\b(my )?(next|upcoming)\b.*\bbook\w*|\bwhen is my\b", False),
    ("my_bookings", r"\bmy bookings?\b|\bmy reservations?\b", False),
    # "what lab is ready now" went to the language model (212 s, 2026-10-19): ready / usable / bookable too.
    ("free_labs", r"\b(free|available|empty|open|ready|usable|bookable)\b.*\blabs?\b|"
                  r"\blabs?\b.*\b(free|available|empty|ready|usable|bookable)\b|\bwhich labs? can i (use|book)\b", False),
]


def detect(question: str, staff: bool) -> Optional[str]:
    q = question.lower()
    for intent, rx, staff_only in _PATTERNS:
        if (staff or not staff_only) and re.search(rx, q):
            return intent
    return None


def _answer(text: str, intent: str, link: Optional[dict] = None, charts: Optional[list] = None) -> dict:
    return {"answer": text, "tools_used": [f"instant:{intent}"], "model": "smartlab-instant",
            "instant": True, **({"link": link} if link else {}), **({"charts": charts} if charts else {})}


def quick_answer(db: Session, user: User, question: str) -> Optional[dict]:
    """An exact answer from the database, or None to let the language model answer."""
    staff = user.role in (Role.ADMIN, Role.LAB_STAFF)
    # the whole-lab answers added 2026-10-27 come before the door-only history (it read "today's summary" as a door report)
    first = detect(question, staff)
    if staff and first not in ("report_daily", "low_stock", "recent_activity", "bookings_today", "empty_labs"):
        # Door history, any period, charts: exact, from the records (agent_history).
        h = agent_history.answer(db, question)
        if h is not None:
            link = None
            if h["intent"] == "range_report":
                period = "monthly" if "last 30 days" in h["text"] else "weekly"
                link = {"label": f"Open the full {period} report (PDF)", "to": f"/report?period={period}"}
            return _answer(h["text"], h["intent"], link, h["charts"])
    intent = first
    if intent is None:
        return None
    now = datetime.now(timezone.utc)

    if intent == "device_advice":
        return _device_advice(db, question, now)

    if intent == "lab_info":
        from app.services import agent_actions
        from app.services import environment as env_svc
        lab, several = agent_actions._lab(db, question.lower())
        if lab is None:
            return None if not several else _answer(
                "Which lab do you mean? " + ", ".join(f"{l.code} {l.name}" for l in several[:5]), intent)
        free = {f["code"]: f for f in free_labs(db, now)}
        occ = next((o for o in occupancy(db) if o["lab_code"] == lab.code), None)
        lines = [f"Capacity {lab.capacity}" + (", door controller installed" if lab.has_controller else ", no door controller"),
                 ("Free now" + (f" until {free[lab.code]['free_until']}" if free[lab.code]["free_until"] else " for the rest of today"))
                 if lab.code in free else "Booked right now"]
        if occ:
            lines.append(f"Inside now: {len(occ['people'])}" + (" - " + ", ".join(p["name"] for p in occ["people"]) if staff else ""))
        else:
            lines.append("Nobody inside (door records)")
        v = env_svc.latest(db, lab, now)
        if v["node"] is not None:
            t, h = (v["metrics"].get("temperature") or {}), (v["metrics"].get("humidity") or {})
            if t.get("value") is not None:
                lines.append(f"Environment: {t['value']:.1f} °C" + (f", {h['value']:.0f} % humidity" if h.get("value") is not None else "")
                             + ("" if t.get("quality") == "VALID" else f" ({str(t.get('quality')).lower().replace('_', ' ')})"))
        if staff:
            al = db.scalar(select(func.count(Alert.id)).where(Alert.lab_id == lab.id, Alert.is_resolved.is_(False))) or 0
            iss = db.scalar(select(func.count(Issue.id)).where(Issue.lab_id == lab.id, Issue.status.in_(ISSUE_ACTIVE))) or 0
            lines.append(f"Open alerts: {al}, open maintenance issues: {iss}")
        return _answer(f"**{lab.code} - {lab.name}**\n" + _bullets(lines), intent,
                       {"label": f"Open {lab.code}", "to": f"/labs/{lab.id}"})

    if intent == "compare":
        period = "monthly" if re.search(r"\bmonth", question.lower()) else "weekly"
        r = management_report(db, period)
        b, pb = r["bookings"], r["previous"]["bookings"]
        a, pa = r["access"], r["previous"]["access"]
        m, pm = r["maintenance"], r["previous"]["maintenance"]

        def row(label, now_v, before_v):
            ch = _change(now_v, before_v)
            trend = "no earlier data" if ch is None else ("no change" if ch == 0 else f"{'+' if ch > 0 else ''}{ch} %")
            return f"{label}: **{now_v}** (previous {before_v}; {trend})"
        span = "30" if period == "monthly" else "7"
        return _answer(f"**Last {span} days vs the {span} days before** ({r['period_label']}):\n" + _bullets([
            row("Confirmed bookings", b["confirmed"], pb["confirmed"]),
            row("Booked hours", b["booked_hours"], pb["booked_hours"]),
            row("Door entries", a["granted"], pa["granted"]),
            row("Refused at the door", a["denied"], pa["denied"]),
            row("Maintenance opened", m["opened"], pm["opened"]),
            row("Maintenance resolved", m["resolved"], pm["resolved"])]), intent,
            {"label": f"Open the full {period} report (PDF)", "to": f"/report?period={period}"})

    if intent == "report_daily":
        local = datetime.now(_tz())
        start = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        r, prev = period_report(db, start, now), period_report(db, start - timedelta(days=1), now - timedelta(days=1))
        alerts = db.scalars(select(Alert).where(Alert.created_at >= start)).all()
        sev = Counter(x.severity.value for x in alerts)
        occ = occupancy(db)
        return _answer(f"**Today so far** ({local:%a %d %b}, until {local:%H:%M}; yesterday at the same time in brackets):\n" + _bullets([
            f"Door entries: **{r['access']['granted']}** ({prev['access']['granted']}), refused: **{r['access']['denied']}** "
            f"({prev['access']['denied']})",
            f"Confirmed bookings: **{r['bookings']['confirmed']}** ({prev['bookings']['confirmed']})",
            f"Alerts raised: **{len(alerts)}**" + (" (" + ", ".join(f"{n} {k.lower()}" for k, n in sev.most_common()) + ")" if alerts else ""),
            f"Maintenance opened / resolved: **{r['maintenance']['opened']} / {r['maintenance']['resolved']}**",
            "Inside now: " + (", ".join(f"{o['lab_code']} {len(o['people'])}" for o in occ) if occ else "nobody (door records)")]),
            intent, {"label": "Open the weekly report", "to": "/report?period=weekly"})

    if intent == "low_stock":
        from app.models import InventoryBin
        from app.services import inventory as inv
        bins = db.scalars(select(InventoryBin).where(InventoryBin.is_active.is_(True)).order_by(InventoryBin.code)).all()
        outs = [inv.bin_out(db, b, now) for b in bins]
        if not outs:
            return _answer("No consumables bin is set up yet.", intent)
        low = [o for o in outs if o["low"]]
        unknown = [o for o in outs if o["qty_est"] is None]
        text = ("**Low - reorder:**\n" + _bullets([f"{o['item_name']} ({o['code']}): {o['qty_est']} pieces left, last reading "
                                                 f"{_when(o['last_reading_at']) if o.get('last_reading_at') else 'never'}" for o in low])
                if low else f"Nothing is low: all {len(outs) - len(unknown)} calibrated bin(s) are above their reorder level.")
        if unknown:
            text += "\nNo count (not calibrated / no reading): " + ", ".join(o["code"] for o in unknown)
        return _answer(text, intent, {"label": "Open Consumables", "to": "/admin/equipment?tab=consumables"})

    if intent == "recent_activity":
        from app.models import RobotEvent
        since = now - timedelta(hours=24)
        rows = []
        for e in db.scalars(select(AccessEvent).where(AccessEvent.created_at >= since)
                            .order_by(AccessEvent.created_at.desc()).limit(8)).all():
            u = db.get(User, e.user_id) if e.user_id else None
            rows.append((_utc(e.created_at), f"Door: {e.event_type.value.replace('_', ' ').lower()}" + (f" - {u.full_name}" if u else "")))
        for a in db.scalars(select(Alert).where(Alert.created_at >= since).order_by(Alert.created_at.desc()).limit(5)).all():
            rows.append((_utc(a.created_at), f"Alert {a.severity.value}: {a.title}"))
        for ev in db.scalars(select(RobotEvent).where(RobotEvent.occurred_at >= since)
                             .order_by(RobotEvent.occurred_at.desc()).limit(5)).all():
            d = db.get(Device, ev.device_id)
            rows.append((_utc(ev.occurred_at), f"Robot {d.name if d else ev.device_id}: {ev.kind.replace('_', ' ').lower()}"))
        if not rows:
            return _answer("Nothing was recorded in the last 24 hours (door, alerts, robots).", intent)
        rows.sort(key=lambda x: x[0], reverse=True)
        return _answer("**Latest activity, last 24 h** (newest first):\n" + _bullets([f"{_when(t)} - {txt}" for t, txt in rows[:12]]),
                       intent, {"label": "Open Access monitor", "to": "/admin/access"})

    if intent == "bookings_today":
        local = datetime.now(_tz())
        start = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        labs_ = {l.id: l for l in db.scalars(select(Lab)).all()}
        rows = db.scalars(select(Booking).where(Booking.status.in_((BookingStatus.CONFIRMED, BookingStatus.PENDING)),
                                                Booking.start_time >= start, Booking.start_time < start + timedelta(days=1))
                          .order_by(Booking.start_time)).all()
        if not rows:
            return _answer("No booking today.", intent, {"label": "Open Bookings", "to": "/admin/bookings"})

        def who(b):
            u = db.get(User, b.user_id)
            return u.full_name if u else "?"
        return _answer(f"**{len(rows)} booking(s) today:**\n" + _bullets([
            f"{_hm(b.start_time)}-{_hm(b.end_time)} **{labs_[b.lab_id].code if b.lab_id in labs_ else b.lab_id}** - {who(b)}"
            + (" (waiting for approval)" if b.status == BookingStatus.PENDING else "") for b in rows[:12]]),
            intent, {"label": "Open Bookings", "to": "/admin/bookings"})

    if intent == "empty_labs":
        occ = {o["lab_code"]: o for o in occupancy(db)}
        labs_all = db.scalars(select(Lab).where(Lab.is_active.is_(True)).order_by(Lab.code)).all()
        empty = [l.code for l in labs_all if l.code not in occ]
        role = {"ADMIN": "admin", "LAB_STAFF": "staff", "STUDENT": "student"}
        lines = [f"**{c}**: " + ", ".join(f"{p['name']} ({role.get(p['role'], p['role'])})" for p in o["people"])
                 for c, o in occ.items()]
        lines.append("Empty: " + (", ".join(empty) if empty else "none"))
        return _answer("**Who is where now** (open door sessions):\n" + _bullets(lines), intent)

    if intent in ("report_weekly", "report_monthly"):
        period = "monthly" if intent == "report_monthly" else "weekly"
        r = management_report(db, period)
        return _answer(_report_text(r), intent,
                       {"label": f"Open the full {period} report (PDF)", "to": f"/report?period={period}"},
                       r["charts"])

    if intent == "insights":
        # 2026-10-27: the proactive findings first (confirmed / possible, with evidence), then the 30-day plan
        from app.services import proactive
        pro = proactive.current(db)["items"]
        head = ("**Right now** (confirmed = the records show it; possible = unusual, check first):\n" + _bullets(
            [f"{i['level'].lower()}: {i['title']} - {i['suggestion']}" for i in pro[:6]]) + "\n\n") if pro else ""
        start = now - timedelta(days=30)
        found = insights(db, start, now)
        if not found:
            return _answer(head + "Nothing has repeated enough to flag in the last 30 days.", intent)
        return _answer(head + plan_text(found, 30), intent,
                       {"label": "Open the monthly report (PDF)", "to": "/report?period=monthly"})

    if intent == "system":
        from app.services import system_analytics
        d = system_analytics.system(db, 7, now)
        names = {"environment": "Environment node", "door": "Door access", "robots": "Robots", "consumables": "Consumables scale",
                 "inventory": "Inventory transactions", "cameras": "Security cameras", "pcs": "Lab PCs",
                 "automation": "n8n automations", "alerts": "Alerts"}

        def ago(sec):
            if sec is None:
                return "never"
            return f"{round(sec / 60)} min ago" if sec < 7200 else f"{round(sec / 3600)} h ago" if sec < 172800 else f"{round(sec / 86400)} days ago"
        lines = [f"{names[k]}: **{f['state']}** - last record {ago(f['age_s'])} ({f['records']:,} total, table `{f['source']}`)"
                 for k, f in d["freshness"].items()]
        env = [x for x in d["environment"]["series"] if "temperature_avg" in x]
        last_env = (f"\nLatest daily environment average ({env[-1]['day']}): {env[-1]['temperature_avg']} °C, "
                    f"{env[-1].get('humidity_avg', '-')} % humidity." if env else "\nNo environment readings in the last 7 days.")
        t = d["totals"]
        return _answer("**Smart Lab data sources** (live = recent for its normal rate, stale = within 7 days):\n" + _bullets(lines)
                       + last_env + f"\nLast 7 days: {int(t['door_events'])} door events, {int(t['robot_events'])} robot events, "
                       f"{int(t['camera_events'])} camera events, {t['pc_hours']} PC hours, {int(t['alerts'])} alerts.",
                       intent, {"label": "Open System analytics", "to": "/admin/system"})

    if intent == "equipment":
        rows = equipment_usage(db, now - timedelta(days=7), now)
        if not rows:
            return _answer("No robot or PC has reported yet, so there is no usage to show.", intent)
        used = [e for e in rows if e["running_h"] or e["idle_h"]]
        if not used:
            return _answer("Robots and PCs are registered, but none has been used in the last 7 days.", intent)
        return _answer("**Equipment use, last 7 days** (running time):\n" + _bullets(
            [f"{e['name']} ({e['lab_code']}): {e['running_h']} h running, {e['idle_h']} h idle"
             + (f", {e['faults']} fault{'s' if e['faults'] != 1 else ''}" if e["faults"] else "")
             for e in used[:8]]), intent)

    if intent in ("inside", "activity_now"):
        occ = occupancy(db)
        seen = _camera_activity(db, now)
        role = {"ADMIN": "admin", "LAB_STAFF": "staff", "STUDENT": "student"}
        lines = [f"**{o['lab_code']}**: {len(o['people'])} - "
                 + ", ".join(f"{p['name']} ({role.get(p['role'], p['role'])})" for p in o["people"]) for o in occ]
        text = ("**By the door records:**\n" + _bullets(lines)) if lines else "Nobody is inside any lab right now (by the door records)."
        if seen:
            text += ("\n\n**What the cameras see now** (names only where the evidence names someone; \"?\" = a guess):\n"
                     + _bullets(seen))
        elif intent == "activity_now":
            text += "\n\nNo camera is reporting people right now."
        return _answer(text, intent)

    if intent == "offline":
        devices = refresh_liveness(db)
        off = [d for d in devices if is_fresh(d, now) is False]
        if not off:
            return _answer("Every device that has reported is online.", intent)
        return _answer("**Offline now:**\n" + _bullets(
            [f"{d.name} ({d.device_uid}) - last seen {_when(d.last_seen_at)}" for d in off]), intent)

    if intent == "environment_now":
        from app.models import Lab as LabRow
        from app.services import environment as env_svc
        labs = db.scalars(select(LabRow).order_by(LabRow.code)).all()
        names = {"temperature": "Temperature", "humidity": "Humidity", "smoke": "Smoke / gas",
                 "flame": "Flame", "motion": "Motion", "water_leak": "Water leak", "emergency": "Emergency button"}
        lines = []
        for lab in labs:
            v = env_svc.latest(db, lab, now)
            if v["node"] is None:
                continue
            parts = []
            for m, label in names.items():
                r = v["metrics"].get(m) or {}
                if r.get("value") is None:
                    continue
                val = (f"{r['value']:.1f} {r['unit'] or ''}".strip() if m in ("temperature", "humidity")
                       else ("DETECTED" if r["value"] >= 0.5 else "none"))
                q = "" if r["quality"] == "VALID" else f" ({r['quality'].lower().replace('_', ' ')})"
                parts.append(f"{label}: **{val}**{q}")
            age = _when(v["node"]["last_seen_at"]) if v["node"]["last_seen_at"] else "never"
            lines.append(f"{lab.code} ({v['node']['device_uid']}, last report {age}): " + " · ".join(parts))
        if not lines:
            return _answer("No environment node has reported yet.", intent)
        return _answer("**Environment now** (the node's latest readings):\n" + _bullets(lines), intent,
                       {"label": "Open Lab Equipment", "to": "/admin/equipment?tab=environment"})

    if intent == "bins_stock":
        from app.models import InventoryBin
        from app.services import inventory as inv
        bins = db.scalars(select(InventoryBin).where(InventoryBin.is_active.is_(True)).order_by(InventoryBin.code)).all()
        if not bins:
            return _answer("No consumables bin is set up yet.", intent)
        lines = []
        for b in bins:
            o = inv.bin_out(db, b, now)
            qty = f"**{o['qty_est']}** pieces" if o["qty_est"] is not None else "not calibrated"
            q = "" if o["quality"] == "VALID" else f" ({o['quality'].lower().replace('_', ' ')})"
            low = " - LOW, reorder" if o["low"] else ""
            when = _when(o["last_reading_at"]) if o.get("last_reading_at") else "never"
            lines.append(f"{o['item_name']} ({o['code']}): {qty}{q}, last reading {when}{low}")
        return _answer("**Consumables** (estimated from each bin's scale):\n" + _bullets(lines), intent,
                       {"label": "Open Consumables", "to": "/admin/equipment?tab=consumables"})

    if intent in ("robots_status", "cameras_status", "pcs_status"):
        kind = {"robots_status": DeviceType.ROBOT, "cameras_status": DeviceType.SECURITY_CAMERA,
                "pcs_status": DeviceType.PC}[intent]
        devs = [d for d in refresh_liveness(db) if d.device_type == kind]
        noun = {"robots_status": "robot", "cameras_status": "security camera", "pcs_status": "PC"}[intent]
        if not devs:
            return _answer(f"No {noun} has reported to the portal yet.", intent)
        lines = []
        from app.services.devices import device_out
        word = {"ONLINE": "online", "DEGRADED": "partly working", "OFFLINE": "offline", "NO_DATA": "never reported"}
        for d in sorted(devs, key=lambda d: d.device_uid):
            cs = d.component_state or {}
            o = device_out(d, now=now)                # the same state and name as System Devices
            on = o.state == "ONLINE"
            tags = []
            if cs.get("source") == "SIMULATION":
                tags.append("SIMULATION")
            if intent == "robots_status":
                q = cs.get("q")
                tags.append("joint feedback" if q and len(q) == 6 else "no joint feedback")
            if intent == "cameras_status" and o.state in ("ONLINE", "DEGRADED"):
                tags.append("picture" if cs.get("source_ok") else "NO picture")
                if cs.get("fps") is not None:
                    tags.append(f"{cs.get('fps')} analyses/s")
            if intent == "pcs_status" and on and cs.get("os_user"):
                tags.append(f"signed in: {cs.get('os_user')}")
            if o.state == "DEGRADED" and o.state_note:
                tags.insert(0, o.state_note)
            lines.append(f"{o.name} ({d.device_uid}): **{word.get(o.state, o.state.lower())}** - last report "
                         f"{_when(d.last_seen_at) if d.last_seen_at else 'never'}" + (f" - {', '.join(tags)}" if tags else ""))
        extra = ""
        if intent == "pcs_status":
            free, used, off = [], [], []
            for d in devs:
                o = device_out(d, now=now)
                (free if o.state == "ONLINE" and not (d.component_state or {}).get("os_user")
                 else used if o.state == "ONLINE" else off).append(o.name)
            extra = (f"\nFree (online, nobody signed in): **{len(free)}**" + (f" - {', '.join(sorted(free))}" if free else "")
                     + f"\nIn use: **{len(used)}**" + (f" - {', '.join(sorted(used))}" if used else "")
                     + f"\nOffline / not reporting: **{len(off)}**")
        if intent == "robots_status":
            from app.services import robot_control
            extra = (f"\nRobot control mode: **{robot_control.MODE.upper()}**"
                     + (" - nothing is sent to a robot." if robot_control.MODE == "dry_run" else "."))
        to = {"robots_status": "/robots", "cameras_status": "/security", "pcs_status": "/admin/equipment"}[intent]
        title = {"robots_status": "Robots", "cameras_status": "Security cameras", "pcs_status": "PCs"}[intent]
        return _answer(f"**{title}** (from their own reports; partly working = it reports, but its camera / robot is missing):\n"
                       + _bullets(lines) + extra, intent, {"label": "Open", "to": to})

    if intent == "alerts_open":
        rows = db.scalars(select(Alert).where(Alert.is_resolved.is_(False))
                          .order_by(Alert.created_at.desc())).all()
        if not rows:
            return _answer("No open alert.", intent, {"label": "Open Incidents", "to": "/admin/incidents"})
        sev = Counter(a.severity.value for a in rows)
        return _answer(f"**{len(rows)} open alert(s)** (" + ", ".join(f"{n} {k.lower()}" for k, n in sev.most_common())
                       + "). Newest:\n" + _bullets([f"{a.severity.value}: {a.title} - {_when(a.created_at)}"
                                                    for a in rows[:5]]),
                       intent, {"label": "Open Incidents", "to": "/admin/incidents"})

    if intent == "open_issues":
        issues = db.scalars(select(Issue).where(Issue.status.in_(ISSUE_ACTIVE))
                            .order_by(Issue.created_at)).all()
        if not issues:
            return _answer("No maintenance issue is open.", intent)
        sev = Counter(i.severity.value for i in issues)
        crit = ""
        if re.search(r"\b(critical|urgent|severe)\b", question.lower()):     # "are any open issues critical?"
            crit = (f"**{sev['CRITICAL']} critical.** " if sev.get("CRITICAL") else "**No critical issue is open (0 critical).** ")
        return _answer(crit + f"**{len(issues)} open** ("
                       + ", ".join(f"{n} {k.lower()}" for k, n in sev.most_common()) + "). Oldest:\n"
                       + _bullets([f"{i.ticket_number or i.id}: {i.title} - since {_when(i.created_at)}"
                                   for i in issues[:5]]), intent,
                       {"label": "Open Maintenance", "to": "/issues"})

    labs = {l.id: l for l in db.scalars(select(Lab)).all()}
    live = (BookingStatus.CONFIRMED, BookingStatus.PENDING)
    if intent in ("next_booking", "my_bookings"):
        rows = db.scalars(select(Booking).where(Booking.user_id == user.id, Booking.status.in_(live),
                                                Booking.end_time > now)
                          .order_by(Booking.start_time).limit(1 if intent == "next_booking" else 5)).all()
        if not rows:
            return _answer("You have no upcoming booking. Book one under **Book a lab**.", intent,
                           {"label": "Book a lab", "to": "/book"})
        fmt = lambda b: (f"**{labs[b.lab_id].code if b.lab_id in labs else b.lab_id}** "  # noqa: E731
                         f"{_when(b.start_time)} - {_hm(b.end_time)}"
                         + (" (waiting for approval)" if b.status == BookingStatus.PENDING else ""))
        if intent == "next_booking":
            b = rows[0]
            return _answer(f"Your next booking: {fmt(b)}. Your QR code is under My bookings.", intent,
                           {"label": "Show my QR code", "to": f"/bookings/{b.id}/qr"})
        return _answer("**Your upcoming bookings:**\n" + _bullets([fmt(b) for b in rows]), intent,
                       {"label": "My bookings", "to": "/bookings"})

    if intent == "free_labs":
        free = free_labs(db, now)
        if not free:
            return _answer("Every lab is booked right now.", intent)
        return _answer("**Free right now:**\n" + _bullets(
            [f"{f['code']} - {f['name']}" + (f" (free until {f['free_until']})" if f["free_until"]
                                             else " (free for the rest of today)") for f in free]),
            intent, {"label": "Book a lab", "to": "/book"})
    return None


def _device_advice(db: Session, question: str, now: datetime) -> dict:
    """One device's health and what its OWN records suggest - status, last 30 days of faults / alerts / telemetry
    drops / use, open maintenance, proactive findings - with the playbook steps for its repeated alerts. Nothing is
    advised that its records do not show."""
    from app.models import RobotEvent
    from app.services import proactive
    from app.services.devices import device_out
    q = question.lower()
    want = {"ur5": ("ur5",), "fanuc": ("fanuc",), "robot": ("ur5", "fanuc", "robot"), "camera": ("cam",),
            "door": ("master", "door"), "bin": ("bin",), "scale": ("bin",), "environment": ("env",), "sensor": ("env",)}
    m = re.search(r"pc[- ]?(\d+)", q)
    keys = (f"pc_{int(m.group(1)):02d}", f"pc-{int(m.group(1)):02d}", f"pc{int(m.group(1)):02d}") if m else next((v for k, v in want.items() if k in q), ())
    devs = [d for d in refresh_liveness(db)
            if any(k in f"{d.device_uid} {d.name}".lower() for k in keys)] if keys else []
    if not devs:
        return _answer("I could not find that device in the portal's registry - name it as it appears on the "
                       "Devices page (e.g. UR5e, FANUC, PC-05, the door controller).", "device_advice")
    since = now - timedelta(days=30)
    usage = {u["device_uid"]: u for u in equipment_usage(db, since, now)}
    pro = proactive.current(db)["items"]
    blocks = []
    for d in devs[:3]:
        o = device_out(d, now=now)
        lines, todo = [], []
        lines.append(f"Status: **{o.state.lower()}**" + (f" - {o.state_note}" if o.state_note else "")
                     + f", last report {_when(d.last_seen_at) if d.last_seen_at else 'never'}")
        if o.state in ("OFFLINE", "NO_DATA"):
            todo.append("Bring it back online first: power, network cable / Wi-Fi, and its collector or agent service.")
        u = usage.get(d.device_uid)
        if u:
            lines.append(f"Last 30 days: {u['running_h']} h running, {u['idle_h']} h idle, {u['faults']} fault(s), {u['users']} user(s)")
            if u["faults"]:
                todo.append(f"{u['faults']} fault session(s) in 30 days - open the robot's event list and look for a pattern (same joint, same program, same time).")
            if not u["running_h"] and d.device_type == DeviceType.ROBOT:
                todo.append("Not used in 30 days - a short supervised test run confirms it still works.")
        if d.device_type == DeviceType.ROBOT:
            ev = Counter(e.kind for e in db.scalars(select(RobotEvent).where(RobotEvent.device_id == d.id,
                                                                              RobotEvent.occurred_at >= since)).all())
            if ev:
                lines.append("Robot events (30 days): " + ", ".join(f"{k.replace('_', ' ').lower()} {n}" for k, n in ev.most_common(4)))
            if ev.get("TELEMETRY_STALE"):
                todo.append(f"Telemetry dropped {ev['TELEMETRY_STALE']} time(s) - check the robot's network cable and the collector PC (tools/robot_monitor).")
        al = db.scalars(select(Alert).where(Alert.device_id == d.id, Alert.created_at >= since)).all()
        if al:
            open_n = sum(1 for a in al if not a.is_resolved)
            top = Counter(_norm_title(a.title) for a in al).most_common(2)
            lines.append(f"Alerts (30 days): {len(al)}, {open_n} still open - most common: "
                         + "; ".join(f"{t} x{n}" for t, n in top))
            for t, n in top:
                plan = next((pl for pat, pl in PLAYBOOK if re.search(pat, t)), None)
                if plan and n >= 2:
                    todo.append(f"Repeated '{t}': " + " ".join(plan["steps"][:2]))
        for i in pro:
            if d.device_uid in i["key"]:
                todo.append(f"{i['level'].lower()}: {i['title']} - {i['suggestion']}")
        if not todo:
            todo.append("Nothing in its records points to a problem - no open alert, no fault, reporting normally.")
        blocks.append(f"**{d.name}** ({d.device_uid})\n" + _bullets(lines) + "\n*What its records suggest:*\n"
                      + _bullets(list(dict.fromkeys(todo))[:5]))
    return _answer("\n\n".join(blocks), "device_advice", {"label": "Open Devices", "to": "/admin/devices"})


# -------------------------------------------- snapshot for the language model ---
_snapshot: dict[str, Any] = {"at": 0.0, "text": ""}


def snapshot(db: Session) -> str:
    """Compact facts handed to the language model with every staff question
    (cached 60 s), so most answers need no tool round-trip."""
    if time.monotonic() - _snapshot["at"] < 60 and _snapshot["text"]:
        return _snapshot["text"]
    now = datetime.now(timezone.utc)
    week = management_report(db, "weekly")
    occ = occupancy(db)
    b, pb = week["bookings"], week["previous"]["bookings"]
    a, pa = week["access"], week["previous"]["access"]
    m, pm = week["maintenance"], week["previous"]["maintenance"]
    open_alerts = db.query(Alert).filter(Alert.is_resolved.is_(False)).count()
    # Both periods as plain numbers: a small model must not have to compute.
    text = "\n".join([
        "SNAPSHOT (from the database):",
        "Last 7 days: " + " ".join(week["lines"]),
        "This week vs the week before (exact numbers): "
        f"confirmed bookings {b['confirmed']} vs {pb['confirmed']}; booked hours {b['booked_hours']} vs "
        f"{pb['booked_hours']}; no-shows {b['no_show']} vs {pb['no_show']}; door entries granted "
        f"{a['granted']} vs {pa['granted']}; refused {a['denied']} vs {pa['denied']}; issues opened "
        f"{m['opened']} vs {pm['opened']}; issues resolved {m['resolved']} vs {pm['resolved']}.",
        "Top refusal reasons (7 d): " + (", ".join(f"{d['meaning']} x{d['count']}" for d in week["top_denials"])
                                         or "none"),
        "Labs by booked hours: " + ", ".join(f"{lab['lab_code']} {lab['hours']}h" for lab in week["labs"][:6]),
        "Repeated problems (7 d): " + ("; ".join(f"{i['title']} -> {i['recommendation']}"
                                                 for i in week["insights"][:4]) or "none"),
        # the lines that change most often last: the local model re-reads only from the first changed line
        "Equipment running hours (7 d): " + (", ".join(f"{e['name']} {e['running_h']}h"
                                                       for e in week["equipment"][:6]) or "none reported"),
        f"Alerts not resolved now: {open_alerts}.",
        "Inside now: " + ("; ".join(f"{o['lab_code']}: " + ", ".join(p["name"] for p in o["people"])
                                    for o in occ) or "nobody"),
        # the time last: everything above stays a cached prompt prefix for the local model (2026-10-26)
        "(Snapshot taken " + _when(now) + ".)",
    ])
    _snapshot.update(at=time.monotonic(), text=text)
    return text
