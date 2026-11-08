"""
Device commands: requests the portal leaves for a door controller.

The controller polls for them while it is idle and carries them out itself;
the portal never pushes into it and never drives anything. That keeps the
master ESP32 the final authority for the door - it can refuse, and it only
takes a request between entries.

Rules:
  * one active request per controller at a time;
  * a request not fetched within PICKUP_WINDOW, or not finished within
    RUN_WINDOW after it was fetched, expires;
  * every state change is pushed to staff pages as a live message.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DeviceCommand

ENROLL_FINGERPRINT = "ENROLL_FINGERPRINT"
ENROLL_RFID = "ENROLL_RFID"          # the person taps their card at the door
REMOVE_RFID = "REMOVE_RFID"

ACTIVE = ("PENDING", "SENT", "RUNNING")
FINAL = ("DONE", "FAILED", "EXPIRED", "CANCELLED")

# The controller polls every ~2 s while idle: a request it has not fetched
# in 90 s means it is busy (someone at the door) or offline.
PICKUP_WINDOW = timedelta(seconds=90)
# A fingerprint enrollment waits up to 20 s + 10 s + 20 s for the finger.
RUN_WINDOW = timedelta(seconds=150)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def expire_stale(db: Session, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    for c in db.scalars(select(DeviceCommand).where(
            DeviceCommand.status.in_(ACTIVE))).all():
        late = (c.status == "PENDING" and now > _utc(c.expires_at)) or \
               (c.status != "PENDING" and c.sent_at is not None and
                now > _utc(c.sent_at) + RUN_WINDOW)
        if late:
            c.status = "EXPIRED"
            c.completed_at = now
            c.message = ("The device did not take the request in time "
                         "(busy or offline)." if c.sent_at is None else
                         "The device did not report a result in time.")
            publish_later(db, c)


def active_for_device(db: Session, device_id: int) -> Optional[DeviceCommand]:
    return db.scalar(select(DeviceCommand).where(
        DeviceCommand.device_id == device_id,
        DeviceCommand.status.in_(ACTIVE)).order_by(DeviceCommand.created_at))


def out(c: DeviceCommand) -> dict:
    return {"id": c.id, "command": c.command, "status": c.status, "step": c.step,
            "message": c.message, "args": c.args or {},
            "created_at": c.created_at, "expires_at": c.expires_at,
            "sent_at": c.sent_at, "completed_at": c.completed_at}


_PENDING_KEY = "device_command_messages"


def publish_later(db: Session, c: DeviceCommand) -> None:
    """Queue a live message for after the commit (never before it)."""
    db.info.setdefault(_PENDING_KEY, []).append(
        {"type": "staff", "kind": "device_command", "command_id": c.id,
         "status": c.status, "step": c.step})


def flush_published(db: Session) -> None:
    """Call right after db.commit(). Best effort: pages also poll."""
    messages = db.info.pop(_PENDING_KEY, [])
    if not messages:
        return
    try:
        from app.ws.manager import manager
        for m in messages:
            manager.publish(m)
    except Exception:
        pass
