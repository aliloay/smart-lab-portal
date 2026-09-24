"""
Device liveness.

A device proves it is alive by sending heartbeats; it cannot announce its own
death. So "offline" is derived on read: a device whose last heartbeat is older
than DEVICE_STALE_SECONDS is offline. The first time that transition is
observed it is recorded properly - a DEVICE_OFFLINE event, an alert, and a
notification to staff - instead of silently flipping a flag.

A device that has never sent a heartbeat is neither online nor offline. It
has no data, and is shown that way.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Alert, AlertSeverity, Device, EventType, Lab
from app.services.events import log_event
from app.services.notifications import notify, staff_ids


def stale_after() -> timedelta:
    return timedelta(seconds=settings.DEVICE_STALE_SECONDS)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def is_fresh(d: Device, now: Optional[datetime] = None) -> Optional[bool]:
    """True/False from the heartbeat age; None when it never reported."""
    if d.last_seen_at is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (now - _utc(d.last_seen_at)) < stale_after()


def refresh_liveness(db: Session) -> list[Device]:
    """Recompute is_online for every device and record new outages."""
    now = datetime.now(timezone.utc)
    devices = db.scalars(select(Device).order_by(Device.name)).all()
    changed = False
    for d in devices:
        fresh = is_fresh(d, now)
        if fresh is None:
            continue
        if d.is_online and not fresh:
            d.is_online = False
            changed = True
            lab = db.get(Lab, d.lab_id)
            silent = int((now - _utc(d.last_seen_at)).total_seconds())
            log_event(db, EventType.DEVICE_OFFLINE, lab_id=d.lab_id,
                      device_id=d.id,
                      message=f"{d.name} stopped reporting "
                              f"(no heartbeat for {silent}s)")
            db.add(Alert(lab_id=d.lab_id, device_id=d.id,
                         severity=AlertSeverity.WARNING,
                         title=f"{d.name} offline",
                         detail=f"No heartbeat since "
                                f"{_utc(d.last_seen_at):%Y-%m-%d %H:%M:%S} UTC. "
                                f"Laboratory {lab.code if lab else d.lab_id}."))
            notify(db, staff_ids(db), "DEVICE_OFFLINE",
                   f"{d.name} is offline",
                   body=f"{lab.code if lab else ''} - no heartbeat for "
                        f"{silent} seconds.",
                   link="/admin/devices", severity="warning")
        elif not d.is_online and fresh:
            d.is_online = True
            changed = True
    if changed:
        db.commit()
    return list(devices)


def device_out(d: Device, lab_code: Optional[str] = None,
               now: Optional[datetime] = None):
    from app.schemas import DeviceOut
    now = now or datetime.now(timezone.utc)
    out = DeviceOut.model_validate(d)
    fresh = is_fresh(d, now)
    out.is_online = bool(fresh)
    out.state = "NO_DATA" if fresh is None else ("ONLINE" if fresh else "OFFLINE")
    out.seconds_since_seen = (int((now - _utc(d.last_seen_at)).total_seconds())
                              if d.last_seen_at else None)
    out.lab_code = lab_code
    return out


def resolve_offline_alerts(db: Session, device: Device) -> None:
    """A device came back: its open outage alerts are no longer true."""
    now = datetime.now(timezone.utc)
    for a in db.scalars(select(Alert).where(
            Alert.device_id == device.id,
            Alert.is_resolved.is_(False),
            Alert.title.like("%offline"))).all():
        a.is_resolved = True
        a.resolved_at = now
