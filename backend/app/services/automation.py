"""
The rules behind the automation API.

n8n decides WHEN something runs and WHERE its result goes. What counts as a
denial burst, when an outage escalates, what a daily report contains, which
records are inconsistent - all of that is decided here, once, next to the
data. A workflow that needs a judgement asks this module; it never re-derives
one from raw rows.

Everything is read-only unless the function name says otherwise, and every
figure is computed from recorded rows. Where there is nothing to compute, the
answer says so ("no_data": true, "not_reported") instead of inventing a value.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (AccessEvent, AccessSession, Alert, Asset, AssetStatus,
                        Booking, BookingStatus, Device, DeviceType, EventType,
                        Issue, IssueSeverity, IssueStatus, Lab, RfidCredential,
                        Role, SensorReading, SessionEndReason, User)
from app.services.devices import is_fresh, refresh_liveness
from app.services.issues import ACTIVE as ISSUE_ACTIVE, is_overdue

LIVE = (BookingStatus.CONFIRMED, BookingStatus.COMPLETED)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return _utc(dt).isoformat() if dt else None


def _labs(db: Session) -> dict[int, Lab]:
    return {l.id: l for l in db.scalars(select(Lab)).all()}


# ---------------------------------------------------------------- readiness --
def lab_readiness(db: Session, lab: Lab, now: Optional[datetime] = None) -> dict:
    """
    Is this laboratory in a fit state for a session? Advisory only: a warning
    here never cancels a booking or changes what the door does.
    """
    now = now or _now()
    warnings: list[str] = []
    notes: list[str] = []

    controller = None
    if lab.has_controller:
        masters = db.scalars(select(Device).where(
            Device.lab_id == lab.id,
            Device.device_type == DeviceType.MASTER_CONTROLLER)).all()
        states = [is_fresh(d, now) for d in masters]
        if not masters or all(s is None for s in states):
            controller = "NOT_REPORTED"
            warnings.append("The door controller has never reported.")
        elif any(s for s in states):
            controller = "ONLINE"
        else:
            controller = "OFFLINE"
            warnings.append("The door controller is offline - entry may "
                            "need staff assistance.")
    else:
        notes.append("This laboratory has no door controller; access is not "
                     "automated.")

    issues = db.scalars(select(Issue).where(
        Issue.lab_id == lab.id, Issue.status.in_(ISSUE_ACTIVE))).all()
    critical = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
    high = [i for i in issues if i.severity == IssueSeverity.HIGH]
    for i in critical:
        warnings.append(f"Critical issue open: {i.ticket_number} - {i.title}")
    for i in high:
        notes.append(f"High-severity issue open: {i.ticket_number} - {i.title}")

    open_alerts = db.scalar(select(func.count()).select_from(Alert).where(
        Alert.lab_id == lab.id, Alert.is_resolved.is_(False))) or 0
    if open_alerts:
        notes.append(f"{open_alerts} unresolved alert(s) for this laboratory.")

    in_maintenance = db.scalar(select(func.count()).select_from(Asset).where(
        Asset.lab_id == lab.id, Asset.status == AssetStatus.MAINTENANCE)) or 0
    if in_maintenance:
        notes.append(f"{in_maintenance} item(s) of equipment are in maintenance.")

    level = "warning" if warnings else ("attention" if notes and (
        high or open_alerts or in_maintenance) else "ok")
    return {
        "lab_id": lab.id, "lab_code": lab.code, "lab_name": lab.name,
        "level": level, "controller": controller,
        "open_issues": len(issues), "critical_issues": len(critical),
        "high_issues": len(high), "open_alerts": open_alerts,
        "assets_in_maintenance": in_maintenance,
        "warnings": warnings, "notes": notes,
    }


def booking_context(db: Session, b: Booking, now: Optional[datetime] = None) -> dict:
    now = now or _now()
    lab = db.get(Lab, b.lab_id)
    user = db.get(User, b.user_id)
    start, end = _utc(b.start_time), _utc(b.end_time)
    from app.models import Notification
    reminded = db.scalar(select(Notification.id).where(
        Notification.user_id == b.user_id,
        Notification.kind == "BOOKING_REMINDER",
        Notification.booking_id == b.id)) is not None
    return {
        "booking_id": b.id, "status": b.status.value,
        "user_id": b.user_id, "user_name": user.full_name if user else None,
        "lab_id": b.lab_id, "lab_code": lab.code if lab else None,
        "lab_name": lab.name if lab else None,
        "start_time": start.isoformat(), "end_time": end.isoformat(),
        "minutes_until_start": int((start - now).total_seconds() // 60),
        "reminder_sent": reminded,
        "link": f"/bookings/{b.id}/qr",
        "readiness": lab_readiness(db, lab, now) if lab else None,
    }


def upcoming_bookings(db: Session, within_minutes: int) -> list[dict]:
    now = _now()
    rows = db.scalars(select(Booking).where(
        Booking.status == BookingStatus.CONFIRMED,
        Booking.start_time > now,
        Booking.start_time <= now + timedelta(minutes=within_minutes))
        .order_by(Booking.start_time)).all()
    return [booking_context(db, b, now) for b in rows]


# ----------------------------------------------------------- denial bursts --
def denial_burst(db: Session, lab_id: Optional[int],
                 window_minutes: Optional[int] = None) -> dict:
    """
    Refusals at the door in the last window. One refusal is normal - people
    arrive early or scan the wrong code. DENIAL_WARNING_COUNT in the window is
    a warning. The door itself is never affected by this answer.
    """
    window = window_minutes or settings.DENIAL_WINDOW_MINUTES
    since = _now() - timedelta(minutes=window)
    q = select(AccessEvent).where(AccessEvent.event_type == EventType.ACCESS_DENIED,
                                  AccessEvent.created_at >= since)
    if lab_id is not None:
        q = q.where(AccessEvent.lab_id == lab_id)
    rows = db.scalars(q.order_by(AccessEvent.created_at)).all()
    n = len(rows)
    threshold = settings.DENIAL_WARNING_COUNT
    level = "none" if n == 0 else ("warning" if n >= threshold else "normal")
    lab = db.get(Lab, lab_id) if lab_id else None
    users = db.scalars(select(User).where(User.id.in_(
        {r.user_id for r in rows if r.user_id}))).all() if rows else []
    return {
        "lab_id": lab_id, "lab_code": lab.code if lab else None,
        "window_minutes": window, "count": n, "threshold": threshold,
        "level": level,
        "by_reason": dict(Counter(r.reason or "UNSPECIFIED" for r in rows)),
        "users": [u.full_name for u in users],
        "unidentified": sum(1 for r in rows if r.user_id is None),
        "first_at": _iso(rows[0].created_at) if rows else None,
        "last_at": _iso(rows[-1].created_at) if rows else None,
        # Minute bucket of the window start: one alert per burst, not per scan.
        "dedupe_key": (f"denial-burst:{lab_id}:"
                       f"{int(_utc(rows[0].created_at).timestamp()) // (window * 60)}"
                       if level == "warning" else None),
        "message": (f"{n} refusals at {lab.code if lab else 'the door'} in "
                    f"{window} min" if n else "No refusals in the window."),
    }


# ------------------------------------------------------------------ devices --
def device_escalation(db: Session) -> dict:
    """
    Offline devices and how long they have been silent. Calling this also
    records new outages (refresh_liveness), so a scheduled run makes offline
    detection timely even when nobody has the portal open.
    """
    devices = refresh_liveness(db)
    now = _now()
    labs = _labs(db)
    stale_min = settings.DEVICE_STALE_SECONDS / 60
    out = []
    never = []
    for d in devices:
        fresh = is_fresh(d, now)
        if fresh is None:
            never.append({"device_id": d.id, "name": d.name,
                          "lab_code": labs[d.lab_id].code if d.lab_id in labs
                          else None})
            continue
        if fresh:
            continue
        minutes = int((now - _utc(d.last_seen_at)).total_seconds() // 60)
        level = 3 if minutes >= settings.DEVICE_ESCALATE_L3_MINUTES else \
            2 if minutes >= settings.DEVICE_ESCALATE_L2_MINUTES else 1
        lab = labs.get(d.lab_id)
        out.append({
            "device_id": d.id, "device_uid": d.device_uid, "name": d.name,
            "type": d.device_type.value, "lab_id": d.lab_id,
            "lab_code": lab.code if lab else None,
            "last_seen_at": _iso(d.last_seen_at), "minutes_offline": minutes,
            "level": level,
            "audience": "admins" if level == 3 else "staff",
            "severity": "critical" if level == 3 else "warning",
            # One notification per outage per level.
            "dedupe_key": f"device-offline:{d.id}:"
                          f"{int(_utc(d.last_seen_at).timestamp())}:L{level}",
            "title": f"{d.name} offline for {minutes} min"
                     + (" - escalated" if level > 1 else ""),
            "body": f"{lab.code if lab else ''} - last heartbeat "
                    f"{_utc(d.last_seen_at):%H:%M} UTC. Level {level} of 3.",
        })
    return {"stale_after_minutes": round(stale_min, 1),
            "levels": {"1": f">= {round(stale_min, 1)} min",
                       "2": f">= {settings.DEVICE_ESCALATE_L2_MINUTES} min",
                       "3": f">= {settings.DEVICE_ESCALATE_L3_MINUTES} min"},
            "offline": out, "never_reported": never,
            "online": sum(1 for d in devices if is_fresh(d, now))}


# -------------------------------------------------------------- maintenance --
def maintenance_digest(db: Session) -> dict:
    now = _now()
    labs = _labs(db)
    issues = db.scalars(select(Issue).where(Issue.status.in_(ISSUE_ACTIVE))).all()

    def brief(i: Issue) -> dict:
        return {"issue_id": i.id, "ticket": i.ticket_number, "title": i.title,
                "severity": i.severity.value, "status": i.status.value,
                "lab_code": labs[i.lab_id].code if i.lab_id in labs else None,
                "assigned": i.assigned_to_id is not None,
                "age_hours": int((now - _utc(i.created_at)).total_seconds() // 3600),
                "link": f"/issues/{i.id}"}

    overdue = [brief(i) for i in issues if is_overdue(i, now)]
    unassigned_urgent = [brief(i) for i in issues if i.assigned_to_id is None
                         and i.severity in (IssueSeverity.CRITICAL,
                                            IssueSeverity.HIGH)]
    assets = db.scalars(select(Asset).where(
        Asset.next_maintenance_at.is_not(None),
        Asset.status != AssetStatus.RETIRED,
        Asset.next_maintenance_at <= now + timedelta(days=7))).all()
    due = [{"asset_id": a.id, "asset_tag": a.asset_tag, "name": a.name,
            "lab_code": labs[a.lab_id].code if a.lab_id in labs else None,
            "due_at": _iso(a.next_maintenance_at),
            "overdue": _utc(a.next_maintenance_at) < now,
            "link": f"/equipment/{a.id}"} for a in assets]
    return {"open_issues": len(issues), "overdue": overdue,
            "unassigned_urgent": unassigned_urgent,
            "assets_due": due,
            "dedupe_day": now.date().isoformat()}


def issue_context(db: Session, issue: Issue) -> dict:
    lab = db.get(Lab, issue.lab_id)
    return {"issue_id": issue.id, "ticket": issue.ticket_number,
            "title": issue.title, "severity": issue.severity.value,
            "category": issue.category.value, "status": issue.status.value,
            "lab_code": lab.code if lab else None,
            "assigned": issue.assigned_to_id is not None,
            "link": f"/issues/{issue.id}",
            # Critical and high issues on a lab with a booking in the next
            # 24 h are what staff should look at first.
            "bookings_next_24h": db.scalar(select(func.count()).select_from(
                Booking).where(Booking.lab_id == issue.lab_id,
                               Booking.status == BookingStatus.CONFIRMED,
                               Booking.start_time >= _now(),
                               Booking.start_time <= _now() + timedelta(hours=24))) or 0,
            "readiness": lab_readiness(db, lab) if lab else None}


# ------------------------------------------------------------------ reports --
def period_report(db: Session, start: datetime, end: datetime) -> dict:
    """Everything that happened in [start, end). Counts only, no estimates."""
    now = _now()
    labs = _labs(db)
    bookings = db.scalars(select(Booking).where(
        Booking.start_time >= start, Booking.start_time < end)).all()
    live = [b for b in bookings if b.status in LIVE]
    finished = [b for b in live if _utc(b.end_time) <= min(now, end)]
    attended = [b for b in finished if b.first_entry_at is not None]
    hours = sum((_utc(b.end_time) - _utc(b.start_time)).total_seconds() / 3600
                for b in live)

    ev = db.execute(select(AccessEvent.event_type, AccessEvent.reason,
                           AccessEvent.lab_id)
                    .where(AccessEvent.created_at >= start,
                           AccessEvent.created_at < end)).all()
    et = Counter(r.event_type for r in ev)
    reasons = Counter(r.reason for r in ev
                      if r.event_type == EventType.ACCESS_DENIED and r.reason)
    alarms = Counter(r.reason for r in ev if r.event_type == EventType.ALARM)

    sessions = db.scalars(select(AccessSession).where(
        AccessSession.started_at >= start, AccessSession.started_at < end)).all()
    exits = sum(1 for s in sessions
                if s.end_reason == SessionEndReason.EXIT_RECORDED)

    issues_opened = db.scalar(select(func.count()).select_from(Issue).where(
        Issue.created_at >= start, Issue.created_at < end)) or 0
    issues_resolved = db.scalar(select(func.count()).select_from(Issue).where(
        Issue.resolved_at >= start, Issue.resolved_at < end)) or 0
    open_issues = db.scalars(select(Issue).where(
        Issue.status.in_(ISSUE_ACTIVE))).all()
    alerts_opened = db.scalar(select(func.count()).select_from(Alert).where(
        Alert.created_at >= start, Alert.created_at < end)) or 0

    per_lab: dict[int, dict] = defaultdict(lambda: {"bookings": 0, "hours": 0.0,
                                                    "attended": 0})
    for b in live:
        r = per_lab[b.lab_id]
        r["bookings"] += 1
        r["hours"] += (_utc(b.end_time) - _utc(b.start_time)).total_seconds() / 3600
        if b.first_entry_at:
            r["attended"] += 1

    devices = refresh_liveness(db)
    offline_now = [d.name for d in devices if is_fresh(d, now) is False]

    data = {
        "from": start.isoformat(), "to": end.isoformat(),
        "generated_at": now.isoformat(),
        "bookings": {
            "total": len(bookings), "confirmed": len(live),
            "cancelled": sum(1 for b in bookings
                             if b.status == BookingStatus.CANCELLED),
            "rejected": sum(1 for b in bookings
                            if b.status == BookingStatus.REJECTED),
            "finished": len(finished), "attended": len(attended),
            "no_show": len(finished) - len(attended),
            "attendance_rate": round(len(attended) / len(finished), 3)
            if finished else None,
            "booked_hours": round(hours, 1),
        },
        "access": {
            "granted": et.get(EventType.ACCESS_GRANTED, 0),
            "denied": et.get(EventType.ACCESS_DENIED, 0),
            "identity_mismatch": et.get(EventType.IDENTITY_MISMATCH, 0),
            "forced_entry": alarms.get("FORCED_ENTRY", 0),
            "door_held_open": alarms.get("DOOR_HELD_OPEN", 0),
            "top_denial_reasons": [{"reason": k, "count": v}
                                   for k, v in reasons.most_common(5)],
        },
        "sessions": {"started": len(sessions), "exit_recorded": exits,
                     "exit_not_recorded": len(sessions) - exits},
        "maintenance": {
            "opened": issues_opened, "resolved": issues_resolved,
            "open_now": len(open_issues),
            "critical_open": sum(1 for i in open_issues
                                 if i.severity == IssueSeverity.CRITICAL),
            "overdue_now": sum(1 for i in open_issues if is_overdue(i, now)),
        },
        "devices": {"offline_now": offline_now,
                    "offline_events": et.get(EventType.DEVICE_OFFLINE, 0)},
        "alerts": {"opened": alerts_opened},
        "labs": sorted([{"lab_code": labs[k].code if k in labs else str(k),
                         "bookings": v["bookings"], "hours": round(v["hours"], 1),
                         "attended": v["attended"]} for k, v in per_lab.items()],
                       key=lambda r: -r["hours"]),
    }
    data["lines"] = report_lines(data)
    return data


def report_lines(r: dict) -> list[str]:
    b, a, s, m = r["bookings"], r["access"], r["sessions"], r["maintenance"]
    lines = []
    if b["confirmed"]:
        rate = (f", attendance {round(b['attendance_rate'] * 100)}%"
                if b["attendance_rate"] is not None else "")
        lines.append(f"Bookings: {b['confirmed']} confirmed ({b['booked_hours']} h)"
                     f", {b['no_show']} no-show{rate}.")
    else:
        lines.append("Bookings: none in this period.")
    if a["granted"] or a["denied"]:
        lines.append(f"Access: {a['granted']} granted, {a['denied']} denied"
                     + (f" (mostly {a['top_denial_reasons'][0]['reason']})"
                        if a["top_denial_reasons"] else "") + ".")
    else:
        lines.append("Access: no door activity recorded.")
    if a["identity_mismatch"] or a["forced_entry"] or a["door_held_open"]:
        lines.append(f"Security: {a['identity_mismatch']} identity mismatch, "
                     f"{a['forced_entry']} forced entry, "
                     f"{a['door_held_open']} door held open.")
    if s["started"]:
        lines.append(f"Sessions: {s['started']} started; exit recorded for "
                     f"{s['exit_recorded']}, not recorded for "
                     f"{s['exit_not_recorded']}.")
    lines.append(f"Maintenance: {m['opened']} opened, {m['resolved']} resolved, "
                 f"{m['open_now']} open ({m['critical_open']} critical, "
                 f"{m['overdue_now']} overdue).")
    if r["devices"]["offline_now"]:
        lines.append("Offline now: " + ", ".join(r["devices"]["offline_now"]) + ".")
    return lines


def daily_report(db: Session, day: Optional[date] = None) -> dict:
    day = day or _now().date()
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    r = period_report(db, start, start + timedelta(days=1))
    r["kind"] = "daily"
    r["title"] = f"Daily lab report - {day.isoformat()}"
    r["dedupe_key"] = f"daily-report:{day.isoformat()}"
    return r


def weekly_report(db: Session, end_day: Optional[date] = None) -> dict:
    end_day = end_day or _now().date()
    end = datetime(end_day.year, end_day.month, end_day.day,
                   tzinfo=timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=7)
    r = period_report(db, start, end)
    prev = period_report(db, start - timedelta(days=7), start)
    r["kind"] = "weekly"
    r["title"] = (f"Weekly lab report - {start.date().isoformat()} to "
                  f"{end_day.isoformat()}")
    r["previous"] = {"bookings": prev["bookings"], "access": {
        k: prev["access"][k] for k in ("granted", "denied")},
        "maintenance": {k: prev["maintenance"][k] for k in ("opened", "resolved")}}
    r["dedupe_key"] = f"weekly-report:{end_day.isoformat()}"
    return r


# ------------------------------------------------------------------ sensors --
def sensor_evaluation(db: Session, max_age_minutes: int = 30) -> dict:
    """
    Latest reading per lab and metric, against SENSOR_THRESHOLDS. A reading
    older than max_age_minutes is "stale", not "ok": an old value says
    nothing about the room now.
    """
    now = _now()
    thresholds = settings.sensor_thresholds
    latest_ids = select(func.max(SensorReading.id)).group_by(
        SensorReading.lab_id, SensorReading.metric)
    rows = db.scalars(select(SensorReading).where(
        SensorReading.id.in_(latest_ids))).all()
    labs = _labs(db)
    readings, breaches = [], []
    for r in rows:
        age = int((now - _utc(r.recorded_at)).total_seconds() // 60)
        lo, hi = thresholds.get(r.metric, (None, None))
        if age > max_age_minutes:
            status = "stale"
        elif lo is not None and r.value < lo:
            status = "low"
        elif hi is not None and r.value > hi:
            status = "high"
        else:
            status = "ok" if r.metric in thresholds else "no_threshold"
        item = {"lab_id": r.lab_id,
                "lab_code": labs[r.lab_id].code if r.lab_id in labs else None,
                "metric": r.metric, "value": r.value, "unit": r.unit,
                "recorded_at": _iso(r.recorded_at), "age_minutes": age,
                "min": lo, "max": hi, "status": status}
        readings.append(item)
        if status in ("low", "high"):
            item["dedupe_key"] = (f"sensor:{r.lab_id}:{r.metric}:{status}:"
                                  f"{_utc(r.recorded_at):%Y%m%d%H}")
            item["title"] = (f"{item['lab_code']} {r.metric} {status}: "
                             f"{r.value:g}{r.unit}")
            breaches.append(item)
    return {"no_data": not readings,
            "message": "Awaiting sensor data - no sensor node has reported."
            if not readings else None,
            "thresholds": {k: {"min": v[0], "max": v[1]}
                           for k, v in thresholds.items()},
            "readings": readings, "breaches": breaches}


# ------------------------------------------------------------- post-session --
def ended_bookings(db: Session, minutes: int) -> list[dict]:
    """Bookings whose window closed in the last `minutes`: attended or not."""
    from app.services.sessions import close_expired
    close_expired(db)
    now = _now()
    rows = db.scalars(select(Booking).where(
        Booking.status.in_(LIVE),
        Booking.end_time <= now,
        Booking.end_time > now - timedelta(minutes=minutes))).all()
    out = []
    for b in rows:
        lab = db.get(Lab, b.lab_id)
        sess = db.scalars(select(AccessSession).where(
            AccessSession.booking_id == b.id)).all()
        exit_seen = any(s.end_reason == SessionEndReason.EXIT_RECORDED
                        for s in sess)
        attended = b.first_entry_at is not None
        where = lab.code if lab else "the laboratory"
        if attended:
            title = f"Session ended - {where}"
            body = (f"Entered {_utc(b.first_entry_at):%H:%M} UTC, "
                    f"{b.entry_count} entr{'y' if b.entry_count == 1 else 'ies'}. "
                    + ("Exit recorded." if exit_seen else
                       "Session ended at the booking close - exit not recorded.")
                    + " Report anything broken from the lab page.")
        else:
            title = f"Missed booking - {where}"
            body = ("No entry was recorded for this booking. If you no longer "
                    "need a slot, cancelling it frees the laboratory for others.")
        out.append({"booking_id": b.id, "user_id": b.user_id,
                    "lab_code": lab.code if lab else None,
                    "end_time": _iso(b.end_time), "attended": attended,
                    "entries": b.entry_count, "exit_recorded": exit_seen,
                    "title": title, "body": body,
                    "link": f"/bookings/{b.id}",
                    "dedupe_key": f"post-session:{b.id}"})
    return out


# ------------------------------------------------------------- data quality --
def data_quality(db: Session) -> dict:
    """Consistency checks. Reports only - nothing is changed."""
    now = _now()
    checks: list[dict] = []

    def add(cid: str, title: str, severity: str, ids: list, explain: str):
        checks.append({"id": cid, "title": title, "severity": severity,
                       "count": len(ids), "sample_ids": ids[:10],
                       "explanation": explain})

    cutoff = now - timedelta(hours=settings.MAX_BOOKING_HOURS)
    add("stale_open_sessions", "Open sessions older than the longest booking",
        "warning",
        list(db.scalars(select(AccessSession.id).where(
            AccessSession.ended_at.is_(None),
            AccessSession.started_at < cutoff)).all()),
        "These should have been closed by the booking end or the no-exit "
        "timeout. They close on the next read of the sessions view.")
    add("entry_on_cancelled_booking", "Entries recorded on cancelled/rejected "
        "bookings", "warning",
        list(db.scalars(select(Booking.id).where(
            Booking.status.in_([BookingStatus.CANCELLED, BookingStatus.REJECTED]),
            Booking.first_entry_at.is_not(None))).all()),
        "Someone entered on a booking that is no longer valid - check whether "
        "it was cancelled after the entry.")
    add("unattributed_events", "Access events without a laboratory (7 days)",
        "info",
        list(db.scalars(select(AccessEvent.id).where(
            AccessEvent.lab_id.is_(None),
            AccessEvent.created_at >= now - timedelta(days=7))).all()),
        "Usually a device reporting an unknown lab code.")
    add("devices_never_reported", "Registered devices that never reported",
        "info",
        list(db.scalars(select(Device.id).where(
            Device.last_seen_at.is_(None))).all()),
        "Either not installed yet or misconfigured (wrong device UID).")
    controller_labs = set(db.scalars(select(Device.lab_id).where(
        Device.device_type == DeviceType.MASTER_CONTROLLER)).all())
    add("controller_labs_without_device", "Labs marked as having a controller "
        "with no controller registered", "warning",
        [l.id for l in db.scalars(select(Lab).where(
            Lab.has_controller.is_(True))).all() if l.id not in controller_labs],
        "The lab page will show the door as not reported.")
    add("rfid_on_inactive_users", "Active RFID cards held by deactivated users",
        "warning",
        list(db.scalars(select(RfidCredential.id).join(
            User, User.id == RfidCredential.user_id).where(
            RfidCredential.is_active.is_(True),
            User.is_active.is_(False))).all()),
        "The backend already refuses them; revoking keeps the record clean.")
    add("students_without_door_identity", "Active students with no door "
        "identity (auth subject)", "info",
        list(db.scalars(select(User.id).where(
            User.role == Role.STUDENT, User.is_active.is_(True),
            User.auth_subject.is_(None))).all()),
        "They can book but cannot pass the biometric step until enrolled.")
    add("resolved_without_timestamp", "Resolved issues missing a resolution "
        "time", "info",
        list(db.scalars(select(Issue.id).where(
            Issue.status.in_([IssueStatus.RESOLVED, IssueStatus.CLOSED]),
            Issue.resolved_at.is_(None))).all()),
        "Time-to-resolve cannot be computed for these.")
    add("implausible_sensor_values", "Sensor readings outside physical range",
        "warning",
        list(db.scalars(select(SensorReading.id).where(
            ((SensorReading.metric == "temperature") &
             ((SensorReading.value < -40) | (SensorReading.value > 85))) |
            ((SensorReading.metric == "humidity") &
             ((SensorReading.value < 0) | (SensorReading.value > 100))))).all()),
        "Likely a sensor fault; excluded from nothing - shown as recorded.")

    failing = [c for c in checks if c["count"]]
    return {"generated_at": now.isoformat(), "checks": checks,
            "failing": len(failing),
            "summary": ("All checks passed." if not failing else
                        f"{len(failing)} check(s) need attention: " +
                        "; ".join(f"{c['title']} ({c['count']})"
                                  for c in failing)),
            "dedupe_key": f"data-quality:{now.date().isoformat()}"}


# ---------------------------------------------------------------- anomalies --
def _local_hour(dt: datetime) -> int:
    try:
        from zoneinfo import ZoneInfo
        return _utc(dt).astimezone(ZoneInfo(settings.LOCAL_TIMEZONE)).hour
    except Exception:
        return _utc(dt).hour


def anomalies(db: Session, hours: int = 24) -> dict:
    """
    Rule-based anomaly detection. Each rule is a plain, explainable condition
    over recorded events - no model, no training data required.
    """
    now = _now()
    since = now - timedelta(hours=hours)
    labs = _labs(db)
    code = lambda lid: labs[lid].code if lid in labs else None  # noqa: E731
    found: list[dict] = []

    def add(rule, severity, lab_id, count, detail, key_extra="", first=None,
            last=None):
        found.append({"rule": rule, "severity": severity, "lab_id": lab_id,
                      "lab_code": code(lab_id), "count": count,
                      "detail": detail, "first_at": _iso(first),
                      "last_at": _iso(last),
                      "dedupe_key": f"anomaly:{rule}:{lab_id}:{key_extra}"
                                    f"{now.date().isoformat()}"})

    events = db.scalars(select(AccessEvent).where(
        AccessEvent.created_at >= since).order_by(AccessEvent.created_at)).all()

    # 1. Denial bursts: N refusals inside any sliding window at one lab.
    window = timedelta(minutes=settings.DENIAL_WINDOW_MINUTES)
    denials: dict[Optional[int], list[AccessEvent]] = defaultdict(list)
    for e in events:
        if e.event_type == EventType.ACCESS_DENIED:
            denials[e.lab_id].append(e)
    for lab_id, rows in denials.items():
        best, j = 0, 0
        for i in range(len(rows)):
            while _utc(rows[i].created_at) - _utc(rows[j].created_at) > window:
                j += 1
            best = max(best, i - j + 1)
        if best >= settings.DENIAL_WARNING_COUNT:
            add("denial_burst", "warning", lab_id, best,
                f"{best} refusals within {settings.DENIAL_WINDOW_MINUTES} min.",
                first=rows[0].created_at, last=rows[-1].created_at)

    # 2. Repeated identity mismatch for the same claimed identity.
    mism = Counter((e.lab_id, e.user_id) for e in events
                   if e.event_type == EventType.IDENTITY_MISMATCH)
    for (lab_id, uid), n in mism.items():
        if n >= 2:
            add("repeated_identity_mismatch", "critical", lab_id, n,
                f"Biometric did not match step 1 {n} times for the same "
                f"credential (user {uid}).", key_extra=f"{uid}:")

    # 3. Access granted out of hours.
    s, e_ = settings.AFTER_HOURS_START, settings.AFTER_HOURS_END
    late = [e for e in events if e.event_type == EventType.ACCESS_GRANTED and
            ((_local_hour(e.created_at) >= s) or (_local_hour(e.created_at) < e_))]
    for lab_id in {e.lab_id for e in late}:
        rows = [e for e in late if e.lab_id == lab_id]
        add("after_hours_access", "info", lab_id, len(rows),
            f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'} between "
            f"{s:02d}:00 and {e_:02d}:00 ({settings.LOCAL_TIMEZONE}).",
            first=rows[0].created_at, last=rows[-1].created_at)

    # 4. Door alarms.
    for reason, sev in (("FORCED_ENTRY", "critical"), ("DOOR_HELD_OPEN", "warning")):
        per = Counter(e.lab_id for e in events
                      if e.event_type == EventType.ALARM and e.reason == reason)
        for lab_id, n in per.items():
            if reason == "FORCED_ENTRY" or n >= 2:
                add(reason.lower(), sev, lab_id, n,
                    f"{n} {reason.replace('_', ' ').lower()} alarm(s).")

    # 5. Device flapping: repeated offline transitions.
    flaps = Counter(e.device_id for e in events
                    if e.event_type == EventType.DEVICE_OFFLINE and e.device_id)
    for dev_id, n in flaps.items():
        if n >= 3:
            d = db.get(Device, dev_id)
            add("device_flapping", "warning", d.lab_id if d else None, n,
                f"{d.name if d else dev_id} went offline {n} times - check "
                f"power and Wi-Fi signal.", key_extra=f"{dev_id}:")

    # 6. Refusals far above this lab's own baseline (previous 7 days).
    base_since = since - timedelta(days=7)
    base = db.execute(select(AccessEvent.lab_id, func.count()).where(
        AccessEvent.event_type == EventType.ACCESS_DENIED,
        AccessEvent.created_at >= base_since,
        AccessEvent.created_at < since).group_by(AccessEvent.lab_id)).all()
    baseline = {lid: n / 7 * (hours / 24) for lid, n in base}
    for lab_id, rows in denials.items():
        expected = baseline.get(lab_id, 0)
        if len(rows) >= 5 and len(rows) > 3 * max(expected, 1):
            add("denials_above_baseline", "warning", lab_id, len(rows),
                f"{len(rows)} refusals vs ~{expected:.1f} expected from the "
                f"previous 7 days.")

    return {"generated_at": now.isoformat(), "window_hours": hours,
            "rules": ["denial_burst", "repeated_identity_mismatch",
                      "after_hours_access", "forced_entry", "door_held_open",
                      "device_flapping", "denials_above_baseline"],
            "anomalies": found, "count": len(found)}
