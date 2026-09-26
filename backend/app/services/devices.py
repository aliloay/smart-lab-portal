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


# ---------------------------------------------------------------------------
# Component health reported by the door controller
# ---------------------------------------------------------------------------
# The master sends {"rfid": bool, "fingerprint": bool, "camera": bool, ...}
# with every heartbeat, and at once when one of them changes. A component
# that reports False gets one open alert (and one staff notification); the
# alert is resolved when it reports True again. Keyed on the open alert
# rather than on the previous heartbeat, so a restart or a repeated report
# never raises a duplicate. The LCD is not in the list: its bus has no
# return line, so the controller cannot tell whether it works.
COMPONENT_LABELS = {
    "rfid": "RFID reader",
    "fingerprint": "Fingerprint sensor",
    "camera": "Camera",
}


def component_alert_title(device: Device, key: str) -> str:
    return f"{device.name}: {COMPONENT_LABELS[key]} not responding"


def record_component_health(db: Session, device: Device, lab: Lab,
                            components: dict) -> None:
    now = datetime.now(timezone.utc)
    for key, label in COMPONENT_LABELS.items():
        ok = components.get(key)
        if not isinstance(ok, bool):
            continue
        title = component_alert_title(device, key)
        open_alert = db.scalar(select(Alert).where(
            Alert.device_id == device.id, Alert.is_resolved.is_(False),
            Alert.title == title))
        if not ok and open_alert is None:
            db.add(Alert(lab_id=lab.id, device_id=device.id,
                         severity=AlertSeverity.WARNING, title=title,
                         detail=f"The door controller of {lab.code} reports "
                                f"that its {label.lower()} is not responding. "
                                f"Check its wiring and power."))
            log_event(db, EventType.ALARM, lab_id=lab.id, device_id=device.id,
                      reason="COMPONENT_FAULT",
                      message=f"{label} not responding")
            notify(db, staff_ids(db), "DEVICE_FAULT",
                   f"{label} not responding - {lab.code}",
                   body=f"Reported by {device.name}. The door still works "
                        f"with the remaining methods.",
                   link="/admin/devices", severity="warning")
        elif ok and open_alert is not None:
            open_alert.is_resolved = True
            open_alert.resolved_at = now
            log_event(db, EventType.DEVICE_ONLINE, lab_id=lab.id,
                      device_id=device.id, message=f"{label} working again")


# ---------------------------------------------------------------------------
# Door alarms reported by the door controller (reed switch)
# ---------------------------------------------------------------------------
DOOR_ALARMS = {
    # reason: (severity, title template, notification severity)
    "FORCED_ENTRY": (AlertSeverity.CRITICAL, "Forced entry at {lab}", "critical"),
    "DOOR_HELD_OPEN": (AlertSeverity.WARNING, "Door held open at {lab}", "warning"),
}


def record_door_alarm(db: Session, lab: Lab, device: Optional[Device],
                      reason: str, message: str) -> None:
    """A forced entry stays open until staff resolve it; a held-open alert
    resolves itself when the door is closed (resolve_held_open)."""
    if reason not in DOOR_ALARMS:
        return
    severity, template, notify_severity = DOOR_ALARMS[reason]
    title = template.format(lab=lab.code)
    db.add(Alert(lab_id=lab.id, device_id=device.id if device else None,
                 severity=severity, title=title,
                 detail=message or title))
    notify(db, staff_ids(db), "SECURITY_EVENT", title,
           body=message or "", link="/admin/alerts", severity=notify_severity)


def resolve_held_open(db: Session, lab: Lab) -> None:
    now = datetime.now(timezone.utc)
    title = DOOR_ALARMS["DOOR_HELD_OPEN"][1].format(lab=lab.code)
    for a in db.scalars(select(Alert).where(
            Alert.lab_id == lab.id, Alert.is_resolved.is_(False),
            Alert.title == title)).all():
        a.is_resolved = True
        a.resolved_at = now
