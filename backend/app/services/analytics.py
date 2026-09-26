"""
Aggregates for the Operations Center, the lab digital twin and the student
dashboard.

Same rule as the reports page: every number is counted from recorded rows.
Where a figure cannot be observed - how long someone stayed when no exit was
recorded, how available a device was when it never reported - the value is
None and the page says why, instead of estimating.

Heatmaps are bucketed in LOCAL_TIMEZONE (the lab's own clock), because "busy
on Tuesday at 10:00" is a statement about the building, not about UTC.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (AccessEvent, AccessSession, AuditLog, Booking,
                        BookingStatus, Device, EventType, IntegrationEvent,
                        Issue, IssueSeverity, Lab, SensorReading,
                        SessionEndReason)
from app.services.devices import is_fresh, refresh_liveness
from app.services.issues import ACTIVE as ISSUE_ACTIVE, is_overdue
from app.services.sessions import close_expired, duration_minutes

LIVE = (BookingStatus.CONFIRMED, BookingStatus.COMPLETED)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(settings.LOCAL_TIMEZONE)
    except Exception:
        return timezone.utc


def _local(dt: datetime) -> datetime:
    return _utc(dt).astimezone(_tz())


def _hour_slots(start: datetime, end: datetime):
    """(weekday, hour, fraction-of-hour) for each local hour a window covers."""
    t = start
    while t < end:
        nxt = min(end, t.replace(minute=0, second=0, microsecond=0)
                  + timedelta(hours=1))
        loc = _local(t)
        yield loc.weekday(), loc.hour, (nxt - t).total_seconds() / 3600
        t = nxt


def _matrix() -> list[list[float]]:
    return [[0.0] * 24 for _ in range(7)]


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return _utc(dt).isoformat() if dt else None


# ---------------------------------------------------------------- operations --
def operations(db: Session, days: int, lab_id: Optional[int] = None) -> dict:
    close_expired(db)
    devices = refresh_liveness(db)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    labs = {l.id: l for l in db.scalars(select(Lab)).all()}

    def scoped(q, col):
        return q.where(col == lab_id) if lab_id else q

    # --- utilisation ------------------------------------------------------
    bookings = db.scalars(scoped(select(Booking).where(
        Booking.start_time < now, Booking.end_time > since,
        Booking.status.in_(LIVE)), Booking.lab_id)).all()
    booked_heat = _matrix()
    per_lab: dict[int, dict] = defaultdict(lambda: {"booked_hours": 0.0,
                                                    "bookings": 0, "used": 0})
    for b in bookings:
        s, e = max(_utc(b.start_time), since), min(_utc(b.end_time), now)
        r = per_lab[b.lab_id]
        r["bookings"] += 1
        r["used"] += 1 if b.first_entry_at else 0
        for wd, h, frac in _hour_slots(s, e):
            booked_heat[wd][h] += frac
            r["booked_hours"] += frac
    available = days * settings.LAB_OPEN_HOURS_PER_DAY
    utilisation = sorted([{
        "lab_id": k, "lab_code": labs[k].code if k in labs else str(k),
        "lab_name": labs[k].name if k in labs else "",
        "booked_hours": round(v["booked_hours"], 1),
        "available_hours": available,
        "utilisation": round(v["booked_hours"] / available, 3) if available else None,
        "bookings": v["bookings"], "used": v["used"],
    } for k, v in per_lab.items()], key=lambda r: -r["booked_hours"])

    sessions = db.scalars(scoped(select(AccessSession).where(
        AccessSession.started_at >= since), AccessSession.lab_id)).all()
    entry_heat = _matrix()
    for s in sessions:
        loc = _local(s.started_at)
        entry_heat[loc.weekday()][loc.hour] += 1

    # --- access funnel ----------------------------------------------------
    counts = Counter(dict(db.execute(scoped(
        select(AccessEvent.event_type, func.count()).where(
            AccessEvent.created_at >= since), AccessEvent.lab_id)
        .group_by(AccessEvent.event_type)).all()))

    def c(*types):
        return sum(counts.get(t, 0) for t in types)

    funnel = [
        {"step": "Credential presented",
         "count": c(EventType.QR_VALIDATED, EventType.QR_REJECTED,
                    EventType.RFID_ACCEPTED, EventType.RFID_REJECTED)},
        {"step": "Step 1 accepted",
         "count": c(EventType.QR_VALIDATED, EventType.RFID_ACCEPTED)},
        {"step": "Identity confirmed",
         "count": c(EventType.FACE_ACCEPTED, EventType.FINGERPRINT_ACCEPTED)},
        {"step": "Access granted", "count": c(EventType.ACCESS_GRANTED)},
        {"step": "Door opened", "count": c(EventType.DOOR_OPENED)},
    ]
    methods = db.execute(scoped(select(AccessEvent.method, func.count()).where(
        AccessEvent.created_at >= since,
        AccessEvent.event_type == EventType.ACCESS_GRANTED), AccessEvent.lab_id)
        .group_by(AccessEvent.method)).all()
    second = Counter((s.entry_method.value,
                      s.second_factor.value if s.second_factor else None)
                     for s in sessions)
    daily = db.execute(scoped(select(
        func.date(AccessEvent.created_at).label("day"),
        AccessEvent.event_type, func.count().label("n")).where(
        AccessEvent.created_at >= since,
        AccessEvent.event_type.in_([EventType.ACCESS_GRANTED,
                                    EventType.ACCESS_DENIED])),
        AccessEvent.lab_id).group_by("day", AccessEvent.event_type)).all()
    outcome_days: dict[str, dict] = {}
    for r in daily:
        row = outcome_days.setdefault(str(r.day), {"day": str(r.day),
                                                   "granted": 0, "denied": 0})
        row["granted" if r.event_type == EventType.ACCESS_GRANTED
            else "denied"] += r.n
    reasons = db.execute(scoped(select(AccessEvent.reason, func.count()).where(
        AccessEvent.created_at >= since,
        AccessEvent.event_type == EventType.ACCESS_DENIED,
        AccessEvent.reason.is_not(None)), AccessEvent.lab_id)
        .group_by(AccessEvent.reason).order_by(func.count().desc())).all()

    # --- sessions ---------------------------------------------------------
    durations = [d for d in (duration_minutes(s) for s in sessions)
                 if d is not None]
    buckets = Counter()
    for d in durations:
        buckets["<30 min" if d < 30 else "30-60 min" if d < 60 else
                "1-2 h" if d < 120 else "2-4 h" if d < 240 else "4 h+"] += 1
    session_block = {
        "started": len(sessions),
        "open_now": db.scalar(scoped(select(func.count()).select_from(
            AccessSession).where(AccessSession.ended_at.is_(None)),
            AccessSession.lab_id)) or 0,
        "end_reasons": dict(Counter(
            s.end_reason.value if s.end_reason else "OPEN" for s in sessions)),
        "exit_recorded": len(durations),
        "median_minutes": median(durations) if durations else None,
        "duration_buckets": [{"label": k, "count": buckets.get(k, 0)} for k in
                             ("<30 min", "30-60 min", "1-2 h", "2-4 h", "4 h+")]
        if durations else [],
        "second_factor": [{"entry": k[0], "second": k[1] or "NOT_RECORDED",
                           "count": n} for k, n in second.most_common()],
    }

    # --- devices ----------------------------------------------------------
    transitions = db.scalars(select(AccessEvent).where(
        AccessEvent.created_at >= since,
        AccessEvent.event_type.in_([EventType.DEVICE_OFFLINE,
                                    EventType.DEVICE_ONLINE]),
        AccessEvent.device_id.is_not(None)).order_by(AccessEvent.created_at)).all()
    by_dev: dict[int, list[AccessEvent]] = defaultdict(list)
    for t in transitions:
        by_dev[t.device_id].append(t)
    device_rows = []
    for d in devices:
        if lab_id and d.lab_id != lab_id:
            continue
        fresh = is_fresh(d, now)
        evs = by_dev.get(d.id, [])
        outages = []
        down_at = None
        for e in evs:
            if e.event_type == EventType.DEVICE_OFFLINE:
                down_at = _utc(e.created_at)
            elif down_at is not None:
                outages.append((down_at, _utc(e.created_at)))
                down_at = None
        if down_at is not None and fresh is False:
            outages.append((down_at, now))
        # Observed outages only: from a recorded DEVICE_OFFLINE to the next
        # DEVICE_ONLINE (or now). A device that never reported has no figure.
        offline_min = sum((b - a).total_seconds() / 60 for a, b in outages)
        device_rows.append({
            "device_id": d.id, "name": d.name, "type": d.device_type.value,
            "lab_code": labs[d.lab_id].code if d.lab_id in labs else None,
            "state": "NO_DATA" if fresh is None else
                     ("ONLINE" if fresh else "OFFLINE"),
            "last_seen_at": _iso(d.last_seen_at),
            "components": d.component_state,
            "offline_events": sum(1 for e in evs
                                  if e.event_type == EventType.DEVICE_OFFLINE),
            "offline_minutes": round(offline_min) if fresh is not None else None,
            "outages": [{"from": a.isoformat(), "to": b.isoformat()}
                        for a, b in outages][-20:],
        })

    # --- maintenance ------------------------------------------------------
    issues = db.scalars(scoped(select(Issue), Issue.lab_id)).all()
    open_issues = [i for i in issues if i.status in ISSUE_ACTIVE]
    ttr: dict[str, list[float]] = defaultdict(list)
    opened_days, resolved_days = Counter(), Counter()
    for i in issues:
        if _utc(i.created_at) >= since:
            opened_days[_utc(i.created_at).date().isoformat()] += 1
        if i.resolved_at and _utc(i.resolved_at) >= since:
            resolved_days[_utc(i.resolved_at).date().isoformat()] += 1
            ttr[i.severity.value].append(
                (_utc(i.resolved_at) - _utc(i.created_at)).total_seconds() / 3600)
    days_axis = sorted(set(opened_days) | set(resolved_days))
    maintenance = {
        "open": len(open_issues),
        "overdue": sum(1 for i in open_issues if is_overdue(i, now)),
        "unassigned": sum(1 for i in open_issues if i.assigned_to_id is None),
        "by_severity": [{"severity": s.value, "count": sum(
            1 for i in open_issues if i.severity == s)} for s in
            (IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.MEDIUM,
             IssueSeverity.LOW)],
        "flow": [{"day": d, "opened": opened_days.get(d, 0),
                  "resolved": resolved_days.get(d, 0)} for d in days_axis],
        "median_hours_to_resolve": [
            {"severity": k, "hours": round(median(v), 1), "resolved": len(v)}
            for k, v in sorted(ttr.items())],
        "sla_hours": {"CRITICAL": settings.ISSUE_SLA_HOURS_CRITICAL,
                      "HIGH": settings.ISSUE_SLA_HOURS_HIGH,
                      "MEDIUM": settings.ISSUE_SLA_HOURS_MEDIUM,
                      "LOW": settings.ISSUE_SLA_HOURS_LOW},
    }

    return {
        "period_days": days, "lab_id": lab_id, "generated_at": now.isoformat(),
        "timezone": settings.LOCAL_TIMEZONE,
        "open_hours_per_day": settings.LAB_OPEN_HOURS_PER_DAY,
        "utilisation": utilisation,
        "booked_heatmap": [[round(v, 2) for v in row] for row in booked_heat],
        "entry_heatmap": [[int(v) for v in row] for row in entry_heat],
        "funnel": funnel,
        "granted_by_method": [{"method": m.value if m else "UNKNOWN", "count": n}
                              for m, n in methods],
        "access_outcomes": sorted(outcome_days.values(), key=lambda r: r["day"]),
        "denial_reasons": [{"reason": r, "count": n} for r, n in reasons],
        "security": {
            "identity_mismatch": c(EventType.IDENTITY_MISMATCH),
            # Door alarms only - a component fault is also an ALARM row.
            "alarms": db.scalar(scoped(select(func.count()).select_from(
                AccessEvent).where(AccessEvent.created_at >= since,
                                   AccessEvent.event_type == EventType.ALARM,
                                   AccessEvent.reason.in_(["FORCED_ENTRY",
                                                           "DOOR_HELD_OPEN"])),
                AccessEvent.lab_id)) or 0,
        },
        "sessions": session_block,
        "devices": device_rows,
        "maintenance": maintenance,
        "automation": automation_status(db),
        "environment": environment(db, lab_id),
    }


# ---------------------------------------------------------------- automation --
def automation_status(db: Session) -> dict:
    """What staff need to know about n8n: is it wired, is it delivering."""
    from app.services import integration
    counts = dict(db.execute(select(IntegrationEvent.delivery_status,
                                    func.count()).group_by(
        IntegrationEvent.delivery_status)).all())
    last_ok = db.scalar(select(func.max(IntegrationEvent.delivered_at)))
    last_fail = db.scalars(select(IntegrationEvent).where(
        IntegrationEvent.last_error.is_not(None)).order_by(
        IntegrationEvent.id.desc()).limit(1)).first()
    runs = db.scalars(select(AuditLog).where(
        AuditLog.action == "AUTOMATION_RUN").order_by(
        AuditLog.id.desc()).limit(12)).all()
    disp = integration.dispatcher
    return {
        # Booleans only - never the URL or the keys themselves.
        "api_enabled": bool(settings.AUTOMATION_API_KEY),
        "push_enabled": bool(settings.AUTOMATION_WEBHOOK_BASE),
        "dispatcher_running": bool(disp and disp.running),
        "push_types": sorted(settings.automation_push_types),
        "outbox": {k: counts.get(k, 0) for k in
                   ("PENDING", "DELIVERED", "FAILED", "SKIPPED")},
        "last_delivered_at": _iso(last_ok),
        "last_error": ({"event_type": last_fail.event_type,
                        "error": last_fail.last_error,
                        "at": _iso(last_fail.occurred_at)}
                       if last_fail else None),
        "recent_runs": [{"workflow": r.entity_id,
                         "status": (r.detail or {}).get("status"),
                         "summary": (r.detail or {}).get("summary"),
                         "at": _iso(r.created_at)} for r in runs],
    }


# --------------------------------------------------------------- environment --
def environment(db: Session, lab_id: Optional[int] = None,
                hours: int = 24) -> dict:
    now = datetime.now(timezone.utc)
    q = select(SensorReading).where(
        SensorReading.recorded_at >= now - timedelta(hours=hours))
    if lab_id:
        q = q.where(SensorReading.lab_id == lab_id)
    rows = db.scalars(q.order_by(SensorReading.recorded_at)).all()
    thresholds = settings.sensor_thresholds
    series: dict[str, dict] = {}
    for r in rows:
        s = series.setdefault(r.metric, {"metric": r.metric, "unit": r.unit,
                                         "points": [],
                                         "min": thresholds.get(r.metric, (None, None))[0],
                                         "max": thresholds.get(r.metric, (None, None))[1]})
        s["points"].append({"t": _iso(r.recorded_at), "v": r.value,
                            "lab_id": r.lab_id})
    for s in series.values():
        last = s["points"][-1]
        s["latest"] = last["v"]
        s["latest_at"] = last["t"]
        s["points"] = s["points"][-500:]
    return {"hours": hours, "has_data": bool(rows),
            "message": None if rows else "Awaiting sensor data",
            "series": sorted(series.values(), key=lambda s: s["metric"])}


# --------------------------------------------------------------- lab twin -----
def lab_twin(db: Session, lab: Lab, days: int = 28) -> dict:
    """Typical week and recent days for one lab, visible to every user."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    rows = db.scalars(select(Booking).where(
        Booking.lab_id == lab.id, Booking.status.in_(LIVE),
        Booking.start_time < now + timedelta(days=7),
        Booking.end_time > since)).all()
    heat = _matrix()
    per_day: Counter = Counter()
    for b in rows:
        s, e = max(_utc(b.start_time), since), min(_utc(b.end_time), now)
        for wd, h, frac in _hour_slots(s, e) if s < e else ():
            heat[wd][h] += frac
        per_day[_local(b.start_time).date().isoformat()] += (
            (_utc(b.end_time) - _utc(b.start_time)).total_seconds() / 3600)
    today = _local(now).date()
    strip = [{"day": (today + timedelta(days=i)).isoformat(),
              "booked_hours": round(per_day.get(
                  (today + timedelta(days=i)).isoformat(), 0), 1)}
             for i in range(-13, 8)]
    return {"lab_id": lab.id, "days": days, "timezone": settings.LOCAL_TIMEZONE,
            "open_hours_per_day": settings.LAB_OPEN_HOURS_PER_DAY,
            "heatmap": [[round(v / max(days / 7, 1), 2) for v in r] for r in heat],
            "heatmap_unit": "average booked hours per slot",
            "days_strip": strip,
            "has_bookings": bool(rows),
            "environment": environment(db, lab.id)}


# ------------------------------------------------------------------ student ---
def my_stats(db: Session, user_id: int, days: int = 90) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    rows = db.scalars(select(Booking).where(
        Booking.user_id == user_id, Booking.start_time >= since,
        Booking.start_time < now + timedelta(days=60))).all()
    live = [b for b in rows if b.status in LIVE]
    past = [b for b in live if _utc(b.end_time) <= now]
    attended = [b for b in past if b.first_entry_at]
    hours = sum((_utc(b.end_time) - _utc(b.start_time)).total_seconds() / 3600
                for b in past)
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    by_lab = Counter(labs.get(b.lab_id, str(b.lab_id)) for b in past)
    weeks: Counter = Counter()
    for b in past:
        wk = _local(b.start_time).date()
        wk = wk - timedelta(days=wk.weekday())
        weeks[wk.isoformat()] += (_utc(b.end_time) - _utc(b.start_time)
                                  ).total_seconds() / 3600
    start_wk = _local(now).date()
    start_wk = start_wk - timedelta(days=start_wk.weekday())
    weekly = [{"week": (start_wk - timedelta(weeks=i)).isoformat(),
               "hours": round(weeks.get((start_wk - timedelta(weeks=i))
                                        .isoformat(), 0), 1)}
              for i in range(11, -1, -1)]
    return {"period_days": days,
            "booked_hours": round(hours, 1),
            "sessions_finished": len(past), "attended": len(attended),
            "attendance_rate": round(len(attended) / len(past), 3) if past else None,
            "upcoming": sum(1 for b in live if _utc(b.start_time) > now),
            "cancelled": sum(1 for b in rows
                             if b.status == BookingStatus.CANCELLED),
            "by_lab": [{"lab_code": k, "count": v} for k, v in by_lab.most_common()],
            "weekly_hours": weekly if past else []}
