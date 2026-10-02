"""
The wall screen: every laboratory at a glance, for monitoring and security.

One compact tile per lab with only what a person watching the screen acts
on - is the door open, is it locked, who is inside, what is wrong right now,
and what just happened at the door. Staff only: it names the people inside.

A value the hardware never reported stays null and the screen says "no
data"; nothing is guessed. Lab state:
  ALERT - an unresolved CRITICAL alert (forced door, held open, ...)
  WARN  - any other unresolved alert, a faulty component, or the door
          controller offline
  OK    - none of those
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.db.session import get_db
from app.models import (AccessEvent, AccessSession, Alert, AlertSeverity,
                        Booking, BookingStatus, Device, DeviceType, EventType,
                        Lab, SensorReading, User)
from app.services.devices import is_fresh, refresh_liveness
from app.services.sessions import close_expired

router = APIRouter(prefix="/monitor", tags=["monitor"])

# What the "last at the door" line shows: decisions and door movements, not
# the individual factor checks that make up one entry.
_DOOR_EVENTS = (EventType.ACCESS_GRANTED, EventType.ACCESS_DENIED,
                EventType.IDENTITY_MISMATCH, EventType.DOOR_OPENED,
                EventType.DOOR_CLOSED, EventType.EXIT_RECORDED, EventType.ALARM)
# Older environment readings are not shown as current.
_SENSOR_FRESH = timedelta(minutes=10)
_COMPONENT_NAMES = {"rfid": "RFID reader", "fingerprint": "Fingerprint sensor",
                    "camera": "Camera"}
_SEVERITY_RANK = {AlertSeverity.CRITICAL: 0, AlertSeverity.WARNING: 1,
                  AlertSeverity.INFO: 2}


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def _name(db: Session, user_id: int | None) -> str | None:
    u = db.get(User, user_id) if user_id else None
    return u.full_name if u else None


def _grouped(alerts: list[Alert]) -> list[dict]:
    """One line per kind of alert: "Forced entry x7", not seven lines."""
    out: dict[tuple, dict] = {}
    for a in alerts:                       # already most severe, newest first
        g = out.setdefault((a.severity, a.title), {
            "severity": a.severity.value, "title": a.title,
            "at": a.created_at, "count": 0})
        g["count"] += 1
    return list(out.values())


def _tile(db: Session, lab: Lab, now: datetime) -> dict:
    devices = db.scalars(select(Device).where(Device.lab_id == lab.id)).all()
    controller = next((d for d in devices
                       if d.device_type == DeviceType.MASTER_CONTROLLER), None)
    camera = next((d for d in devices if d.device_type == DeviceType.CAMERA), None)
    comp = (controller.component_state or {}) if controller else {}
    controller_online = is_fresh(controller, now) if controller else None

    inside = db.scalars(select(AccessSession).where(
        AccessSession.lab_id == lab.id, AccessSession.ended_at.is_(None))
        .order_by(AccessSession.started_at)).all()

    current = db.scalar(select(Booking).where(
        Booking.lab_id == lab.id, Booking.status == BookingStatus.CONFIRMED,
        Booking.start_time <= now, Booking.end_time > now)
        .order_by(Booking.start_time))
    upcoming = db.scalar(select(Booking).where(
        Booking.lab_id == lab.id, Booking.status == BookingStatus.CONFIRMED,
        Booking.start_time > now).order_by(Booking.start_time))

    alerts = db.scalars(select(Alert).where(
        Alert.lab_id == lab.id, Alert.is_resolved.is_(False))).all()
    alerts = sorted(alerts, key=lambda a: (_SEVERITY_RANK.get(a.severity, 9),
                                           -_utc(a.created_at).timestamp()))

    last = db.scalar(select(AccessEvent).where(
        AccessEvent.lab_id == lab.id, AccessEvent.event_type.in_(_DOOR_EVENTS))
        .order_by(desc(AccessEvent.created_at)))

    env = {}
    for metric in ("temperature", "humidity"):
        r = db.scalar(select(SensorReading).where(
            SensorReading.lab_id == lab.id, SensorReading.metric == metric)
            .order_by(desc(SensorReading.recorded_at)))
        if r is not None and now - _utc(r.recorded_at) <= _SENSOR_FRESH:
            env[metric] = {"value": r.value, "unit": r.unit, "at": r.recorded_at}

    # Only while the controller is reporting: an offline controller's last
    # component report is history, not a current fault.
    faults = [_COMPONENT_NAMES[k] for k, v in comp.items()
              if k in _COMPONENT_NAMES and v is False] if controller_online else []

    if any(a.severity == AlertSeverity.CRITICAL for a in alerts):
        state = "ALERT"
    elif alerts or faults or controller_online is False:
        state = "WARN"
    else:
        state = "OK"

    return {
        "lab_id": lab.id, "code": lab.code, "name": lab.name,
        "has_door": controller is not None,
        "state": state,
        "controller_online": controller_online,
        "camera_online": is_fresh(camera, now) if camera else None,
        "door_closed": controller.door_closed if controller else None,
        "locked": comp.get("relay_locked") if controller else None,
        "faults": faults,
        "people": [{"name": _name(db, s.user_id), "since": s.started_at}
                   for s in inside],
        "booking": {"name": _name(db, current.user_id), "until": current.end_time}
                   if current else None,
        "next_booking_at": upcoming.start_time if upcoming else None,
        "alerts": _grouped(alerts)[:3],
        "alert_count": len(alerts),
        "last_event": {"type": last.event_type.value, "result":
                       last.result.value if last.result else None,
                       "who": _name(db, last.user_id), "reason": last.reason,
                       "at": last.created_at} if last else None,
        "environment": env,
    }


@router.get("")
def wall_screen(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    close_expired(db)
    refresh_liveness(db)
    now = datetime.now(timezone.utc)
    labs = db.scalars(select(Lab).where(Lab.is_active.is_(True))
                      .order_by(Lab.code)).all()
    tiles = [_tile(db, lab, now) for lab in labs]
    # Labs with something wrong first, so they are seen first.
    order = {"ALERT": 0, "WARN": 1, "OK": 2}
    tiles.sort(key=lambda t: (order[t["state"]], not t["has_door"], t["code"]))
    return {"generated_at": now, "labs": tiles}
