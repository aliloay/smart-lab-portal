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

from sqlalchemy import select
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
# Recurring alert -> what to do about it (first matching pattern wins).
ALERT_FIXES: list[tuple[str, str]] = [
    (r"held open", "Check the door closer and the door sensor's magnet alignment; remind users to "
                   "close the door behind them."),
    (r"forced", "Check the door sensor and magnet alignment and the lock relay timing (a door that "
                "bounces open after relocking looks forced); if it was real, review the camera."),
    (r"weight does not match", "Recalibrate the bin's load cell (tare, cal) and check the items' "
                               "tags; review who used the bin at those times."),
    (r"low stock|reorder|below", "Reorder now; if it runs out this often, raise its reorder level."),
    (r"(camera|rfid|fingerprint|reader|sensor|lcd|display).*not responding",
     "A part of the controller stops answering: check its cable and connectors, and its 5 V "
     "supply (a rail that sags when the lock relay switches is a common cause)."),
    (r"offline|not responding|no heartbeat", "Check the node's power supply (a 2 A USB supply) and "
                                             "its Wi-Fi signal; give it a fixed address on the router."),
    (r"temperature|heat|humid", "Check ventilation and air conditioning; make sure the sensor is not "
                                "next to a PC exhaust or in direct sun."),
    (r"gas|smoke|flame|fire", "Inspect for a real hazard first; then check the sensor's warm-up time "
                              "and alarm threshold."),
    (r"moved|no longer looks|equipment", "Fix the equipment's place, or accept the new position on "
                                         "the Security camera page so it stops alerting."),
    (r"refusal|denied", "See the refusal reasons below: most repeated refusals have a simple fix."),
]
DEFAULT_FIX = "Find the root cause, then resolve it or tune the threshold so the alert means something."

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
        fix = next((f for p, f in ALERT_FIXES if re.search(p, title.lower())), DEFAULT_FIX)
        out.append({"kind": "ALERT", "title": title, "lab_code": labs.get(lab_id), "count": len(rows),
                    "first": min(r.created_at for r in rows), "last": max(r.created_at for r in rows),
                    "unresolved": sum(1 for r in rows if not r.is_resolved),
                    "severity": "bad" if any(r.severity.value == "CRITICAL" for r in rows) else "warn",
                    "recommendation": fix})

    # 2) The same door refusal reason, and the same person refused by the biometric.
    denials = db.execute(select(AccessEvent.reason, AccessEvent.lab_id, AccessEvent.user_id,
                                AccessEvent.created_at).where(
        AccessEvent.event_type.in_([EventType.ACCESS_DENIED, EventType.IDENTITY_MISMATCH]),
        AccessEvent.created_at >= start, AccessEvent.created_at < end)).all()
    by_reason = Counter(r.reason for r in denials if r.reason)
    for reason, n in by_reason.most_common():
        if n < DENIAL_MIN:
            break
        out.append({"kind": "DENIAL", "title": f"Door refused {n}x: {denial_sentence(reason)}",
                    "reason": reason, "lab_code": None, "count": n, "severity": "warn",
                    "recommendation": DENIAL_FIXES.get(reason, DEFAULT_FIX)})
    per_person = Counter(r.user_id for r in denials if r.user_id and r.reason in
                         ("IDENTITY_MISMATCH", "BIOMETRIC_FAILED", "BIOMETRIC_TIMEOUT"))
    for uid, n in per_person.most_common():
        if n < PERSON_MIN:
            break
        u = db.get(User, uid)
        who = u.full_name if u else f"user {uid}"
        out.append({"kind": "PERSON", "title": f"{who}: biometric refused {n}x", "count": n,
                    "lab_code": None, "severity": "warn",
                    "recommendation": f"Re-enrol {who}'s fingerprint and face (Users page); "
                                      f"if it still fails, check the sensor."})

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
        out.append({"kind": "DEVICE", "title": f"{d.name if d else did} went offline {n}x",
                    "lab_code": labs.get(d.lab_id) if d else None, "count": n, "severity": "warn",
                    "recommendation": "Check its power supply and Wi-Fi signal (move the router or "
                                      "the node closer); reserve its IP address on the router."})

    # 4) The same equipment reported broken more than once.
    per_asset = Counter(i.asset_id for i in db.scalars(select(Issue).where(
        Issue.asset_id.is_not(None), Issue.created_at >= start, Issue.created_at < end)).all())
    for aid, n in per_asset.most_common():
        if n < 2:
            break
        from app.models import Asset
        a = db.get(Asset, aid)
        out.append({"kind": "EQUIPMENT", "title": f"{a.asset_tag if a else aid} reported {n}x",
                    "lab_code": labs.get(a.lab_id) if a else None, "count": n, "severity": "warn",
                    "recommendation": "A repeating fault on the same item: inspect it properly, "
                                      "repair or replace it rather than patching each report."})

    # 5) Bookings people do not turn up for; sessions without an exit.
    r = period_report(db, start, end)
    b, s = r["bookings"], r["sessions"]
    if b["finished"] >= 5 and b["no_show"] / b["finished"] > 0.3:
        out.append({"kind": "BOOKINGS", "title": f"{b['no_show']} of {b['finished']} bookings were no-shows",
                    "lab_code": None, "count": b["no_show"], "severity": "warn",
                    "recommendation": "Send a reminder before each booking (n8n workflow 02) and "
                                      "release slots that nobody enters within the grace time."})
    if s["started"] >= 5 and s["exit_not_recorded"] / s["started"] > 0.5:
        out.append({"kind": "SESSIONS", "title": f"Exit not recorded for {s['exit_not_recorded']} of "
                                                 f"{s['started']} sessions",
                    "lab_code": None, "count": s["exit_not_recorded"], "severity": "info",
                    "recommendation": "Occupancy is only as good as the exits: check the door "
                                      "sensor, or ask people to tap out."})

    rank = {"bad": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda i: (rank.get(i["severity"], 3), -i["count"]))


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
    ("report_monthly", r"\bmonth(ly)?\b.*\b(report|summary|usage|analysis|overview)\b|"
                       r"\b(report|summary|usage|analysis|overview)\b.*\bmonth(ly)?\b", True),
    ("report_weekly", r"\b(week(ly)?)\b.*\b(report|summary|usage|analysis|overview)\b|"
                      r"\b(report|summary|usage|analysis|overview)\b.*\bweek(ly)?\b", True),
    ("insights", r"\b(recurr\w*|repeat\w*|keeps? (happening|coming)|same (alert|error|problem)|"
                 r"recommend\w*|suggest\w*|insights?|what should (we|i) (fix|do))\b", True),
    ("equipment", r"\b(robots?|pcs?|computers?|equipment|ur5e?|fanuc)\b.*\b(used|usage|use|hours|busiest|most)\b|"
                  r"\bmost used\b", True),
    ("inside", r"\b(who|how many)\b.*\b(inside|in the labs?|present|in lab)\b|\boccupancy\b", True),
    ("offline", r"\b(offline|disconnected|not (responding|connected))\b", True),
    ("open_issues", r"\bopen (issues|tickets|reports)\b|\bmaintenance\b.*\b(open|pending|backlog)\b", True),
    ("next_booking", r"\b(my )?(next|upcoming)\b.*\bbook\w*|\bwhen is my\b", False),
    ("my_bookings", r"\bmy bookings?\b|\bmy reservations?\b", False),
    ("free_labs", r"\b(free|available|empty|open)\b.*\blabs?\b|\blabs?\b.*\b(free|available|empty)\b", False),
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
    if staff:
        # Door history, any period, charts: exact, from the records (agent_history).
        h = agent_history.answer(db, question)
        if h is not None:
            link = None
            if h["intent"] == "range_report":
                period = "monthly" if "last 30 days" in h["text"] else "weekly"
                link = {"label": f"Open the full {period} report (PDF)", "to": f"/report?period={period}"}
            return _answer(h["text"], h["intent"], link, h["charts"])
    intent = detect(question, staff)
    if intent is None:
        return None
    now = datetime.now(timezone.utc)

    if intent in ("report_weekly", "report_monthly"):
        period = "monthly" if intent == "report_monthly" else "weekly"
        r = management_report(db, period)
        return _answer(_report_text(r), intent,
                       {"label": f"Open the full {period} report (PDF)", "to": f"/report?period={period}"},
                       r["charts"])

    if intent == "insights":
        start = now - timedelta(days=30)
        found = insights(db, start, now)
        if not found:
            return _answer("Nothing has repeated enough to flag in the last 30 days.", intent)
        return _answer("**Repeated in the last 30 days**, most urgent first:\n" + _bullets(
            [f"**{i['title']}**" + (f" ({i['lab_code']})" if i.get("lab_code") else "")
             + f" → {i['recommendation']}" for i in found[:6]]), intent,
            {"label": "Open the monthly report (PDF)", "to": "/report?period=monthly"})

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

    if intent == "inside":
        occ = occupancy(db)
        if not occ:
            return _answer("Nobody is inside any lab right now (by the door records).", intent)
        role = {"ADMIN": "admin", "LAB_STAFF": "staff", "STUDENT": "student"}
        return _answer(_bullets([
            f"**{o['lab_code']}**: {len(o['people'])} - "
            + ", ".join(f"{p['name']} ({role.get(p['role'], p['role'])})" for p in o["people"])
            for o in occ]), intent)

    if intent == "offline":
        devices = refresh_liveness(db)
        off = [d for d in devices if is_fresh(d, now) is False]
        if not off:
            return _answer("Every device that has reported is online.", intent)
        return _answer("**Offline now:**\n" + _bullets(
            [f"{d.name} ({d.device_uid}) - last seen {_when(d.last_seen_at)}" for d in off]), intent)

    if intent == "open_issues":
        issues = db.scalars(select(Issue).where(Issue.status.in_(ISSUE_ACTIVE))
                            .order_by(Issue.created_at)).all()
        if not issues:
            return _answer("No maintenance issue is open.", intent)
        sev = Counter(i.severity.value for i in issues)
        return _answer(f"**{len(issues)} open** ("
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
        "SNAPSHOT (from the database, " + _when(now) + "):",
        "Last 7 days: " + " ".join(week["lines"]),
        "This week vs the week before (exact numbers): "
        f"confirmed bookings {b['confirmed']} vs {pb['confirmed']}; booked hours {b['booked_hours']} vs "
        f"{pb['booked_hours']}; no-shows {b['no_show']} vs {pb['no_show']}; door entries granted "
        f"{a['granted']} vs {pa['granted']}; refused {a['denied']} vs {pa['denied']}; issues opened "
        f"{m['opened']} vs {pm['opened']}; issues resolved {m['resolved']} vs {pm['resolved']}.",
        "Top refusal reasons (7 d): " + (", ".join(f"{d['meaning']} x{d['count']}" for d in week["top_denials"])
                                         or "none"),
        f"Alerts not resolved now: {open_alerts}.",
        "Labs by booked hours: " + ", ".join(f"{lab['lab_code']} {lab['hours']}h" for lab in week["labs"][:6]),
        "Equipment running hours (7 d): " + (", ".join(f"{e['name']} {e['running_h']}h"
                                                       for e in week["equipment"][:6]) or "none reported"),
        "Inside now: " + ("; ".join(f"{o['lab_code']}: " + ", ".join(p["name"] for p in o["people"])
                                    for o in occ) or "nobody"),
        "Repeated problems (7 d): " + ("; ".join(f"{i['title']} -> {i['recommendation']}"
                                                 for i in week["insights"][:4]) or "none"),
    ])
    _snapshot.update(at=time.monotonic(), text=text)
    return text
