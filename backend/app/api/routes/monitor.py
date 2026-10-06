"""
The wall screen: every laboratory at a glance, for monitoring and security.

One compact tile per lab with only what a person watching the screen acts
on - is the door open, is it locked, who is inside, what is wrong right now,
and what just happened at the door. Staff only: it names the people inside.

A value the hardware never reported stays null and the screen says "no
data"; nothing is guessed. Lab state:
  ALERT - an unresolved CRITICAL alert (forced door, held open, ...)
  WARN  - any other unresolved alert, a faulty component, or the door
          controller or the environment node offline
  OK    - none of those
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.db.session import get_db
from app.models import (AccessEvent, AccessSession, Alert, AlertSeverity,
                        Booking, BookingStatus, Device, DeviceType, EventType,
                        Lab, User)
from app.services import environment
from app.services.devices import is_fresh, refresh_liveness
from app.services.sessions import close_expired

router = APIRouter(prefix="/monitor", tags=["monitor"])

# What the "last at the door" line shows: decisions and door movements, not
# the individual factor checks that make up one entry.
_DOOR_EVENTS = (EventType.ACCESS_GRANTED, EventType.ACCESS_DENIED,
                EventType.IDENTITY_MISMATCH, EventType.DOOR_OPENED,
                EventType.DOOR_CLOSED, EventType.EXIT_RECORDED, EventType.ALARM)
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


def _prefetch(db: Session, labs: list[Lab], now: datetime) -> dict:
    """Everything the tiles need, for all labs at once: a handful of queries
    instead of ~15 per lab (the wall screen took ~0.5 s)."""
    from app.models import LabEmergency
    ids = [lab.id for lab in labs]
    by = lambda rows, key=lambda r: r.lab_id: _group(rows, key)
    pre = {
        "devices": by(db.scalars(select(Device).where(Device.lab_id.in_(ids))).all()),
        "inside": by(db.scalars(select(AccessSession).where(
            AccessSession.lab_id.in_(ids), AccessSession.ended_at.is_(None))
            .order_by(AccessSession.started_at)).all()),
        "current": by(db.scalars(select(Booking).where(
            Booking.lab_id.in_(ids), Booking.status == BookingStatus.CONFIRMED,
            Booking.start_time <= now, Booking.end_time > now).order_by(Booking.start_time)).all()),
        "upcoming": by(db.scalars(select(Booking).where(
            Booking.lab_id.in_(ids), Booking.status == BookingStatus.CONFIRMED,
            Booking.start_time > now)
            .order_by(Booking.lab_id, Booking.start_time).distinct(Booking.lab_id)).all()),
        "alerts": by(db.scalars(select(Alert).where(
            Alert.lab_id.in_(ids), Alert.is_resolved.is_(False))).all()),
        "last": by(db.scalars(select(AccessEvent).where(
            AccessEvent.lab_id.in_(ids), AccessEvent.event_type.in_(_DOOR_EVENTS))
            .order_by(AccessEvent.lab_id, desc(AccessEvent.created_at))
            .distinct(AccessEvent.lab_id)).all()),
        "env": environment.latest_many(db, labs, now),
    }
    # Loaded once and KEPT (the session only holds weak references): db.get()
    # below then finds them without a query.
    pre["_keep"] = list(db.scalars(select(LabEmergency).where(LabEmergency.lab_id.in_(ids))).all())
    who = {s.user_id for rows in pre["inside"].values() for s in rows}
    who |= {b.user_id for rows in pre["current"].values() for b in rows}
    who |= {e.user_id for rows in pre["last"].values() for e in rows if e.user_id}
    if who:
        pre["_keep"] += list(db.scalars(select(User).where(User.id.in_(who))).all())
    return pre


def _group(rows, key) -> dict:
    out: dict = {}
    for r in rows:
        out.setdefault(key(r), []).append(r)
    return out


def _tile(db: Session, lab: Lab, now: datetime, pre: Optional[dict] = None) -> dict:
    pre = pre or _prefetch(db, [lab], now)
    devices = pre["devices"].get(lab.id, [])
    controller = next((d for d in devices
                       if d.device_type == DeviceType.MASTER_CONTROLLER), None)
    camera = next((d for d in devices if d.device_type == DeviceType.CAMERA), None)
    security_cam = next((d for d in devices if d.device_type == DeviceType.SECURITY_CAMERA), None)
    comp = (controller.component_state or {}) if controller else {}
    controller_online = is_fresh(controller, now) if controller else None

    inside = pre["inside"].get(lab.id, [])
    current = next(iter(pre["current"].get(lab.id, [])), None)
    upcoming = next(iter(pre["upcoming"].get(lab.id, [])), None)
    alerts = sorted(pre["alerts"].get(lab.id, []), key=lambda a: (_SEVERITY_RANK.get(a.severity, 9),
                                           -_utc(a.created_at).timestamp()))

    last = next(iter(pre["last"].get(lab.id, [])), None)

    people = []
    for s in inside:
        u = db.get(User, s.user_id)
        people.append({"name": u.full_name if u else None,
                       "role": u.role.value if u else None, "since": s.started_at})

    # Environment (System 2): only fresh, valid values are shown as current.
    envd = pre["env"][lab.id]
    env = {m: {"value": v["value"], "unit": v["unit"], "at": v["at"]}
           for m, v in envd["metrics"].items()
           if m in ("temperature", "humidity") and v["quality"] == "VALID"}

    # Only while the controller is reporting: an offline controller's last
    # component report is history, not a current fault.
    faults = [_COMPONENT_NAMES[k] for k, v in comp.items()
              if k in _COMPONENT_NAMES and v is False] if controller_online else []

    from app.services import emergency as em
    emg = em.state(db, lab.id, now)
    if em.active(emg) and (emg.door_mode != "NORMAL" or emg.alarm):
        state = "ALERT"
    elif any(a.severity == AlertSeverity.CRITICAL for a in alerts):
        state = "ALERT"
    elif alerts or faults or controller_online is False or (
            envd["node"] is not None and envd["node"]["online"] is False):
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
        "people": people,
        # How many of each role are inside: "2 students, 1 staff".
        "people_by_role": dict(Counter(p["role"] for p in people if p["role"])),
        # In use = someone is inside or the lab is booked right now.
        "in_use": bool(people) or current is not None,
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
        # Active hazard states (smoke, flame, water_leak, emergency) and
        # whether the environment node is reporting (None = no node).
        "hazards": envd["hazards"],
        "env_online": envd["node"]["online"] if envd["node"] else None,
        "motion": envd["metrics"]["motion"]["value"] == 1
                  and envd["metrics"]["motion"]["quality"] == "VALID",
        # The lab's security camera: the tile streams it live; people seen
        # vs inside per the door, and who the camera could name.
        "security_camera": _security(db, security_cam, now) if security_cam else None,
        # Emergency set by an administrator (door held open / lockdown /
        # message / alarm), shown first on the tile.
        "emergency": em.out(emg, now) if em.active(emg) else None,
    }


def _security(db: Session, d: Device, now: datetime) -> dict:
    from app.api.routes.security import camera_summary
    c = camera_summary(db, d, now)
    return {k: c[k] for k in ("device_id", "online", "source_ok", "people", "unknown",
                              "named", "inside", "open_events")}


@router.get("")
def wall_screen(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    close_expired(db)
    refresh_liveness(db)
    now = datetime.now(timezone.utc)
    labs = db.scalars(select(Lab).where(Lab.is_active.is_(True))
                      .order_by(Lab.code)).all()
    pre = _prefetch(db, list(labs), now)
    tiles = [_tile(db, lab, now, pre) for lab in labs]
    db.commit()     # keep a new lab's default emergency row, instead of re-creating it every call
    # Every lab gets a tile, in a fixed order (by code) so each lab keeps its
    # place on the wall screen; the colour shows which needs attention.
    return {"generated_at": now, "labs": tiles}
