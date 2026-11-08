---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/devices.py"
source_hash: "a12ef315403ed15e2a21abde0767749d874819a7f92fd31087354b4597bb9ea4"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/devices.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_access.py]] - imports
- [[backend_app_api_routes_admin.py]] - imports
- [[backend_app_api_routes_automation.py]] - imports
- [[backend_app_api_routes_commands.py]] - imports
- [[backend_app_api_routes_emergency.py]] - imports
- [[backend_app_api_routes_equipment.py]] - imports
- [[backend_app_api_routes_labs.py]] - imports
- [[backend_app_api_routes_monitor.py]] - imports
- [[backend_app_api_routes_opcua.py]] - imports
- [[backend_app_api_routes_reusable.py]] - imports
- [[backend_app_api_routes_robots.py]] - imports
- [[backend_app_api_routes_scan.py]] - imports
- [[backend_app_api_routes_security.py]] - imports

```py
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
from app.models import Alert, AlertSeverity, Device, DeviceType, EventType, Lab
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


_last_refresh = {"at": 0.0}


NO_PICTURE_S = 300
_no_picture: dict[int, datetime] = {}      # camera device id -> first refresh that saw no picture


def refresh_liveness(db: Session) -> list[Device]:
    """Recompute is_online for every device and record new outages.
    One page asks for this 4-5 times at once; within LIVENESS_THROTTLE_S (default 3 s) the transition
    scan is skipped and the device list is returned as is (an outage is recorded at most 3 s later)."""
    import os
    import time as _time
    now = datetime.now(timezone.utc)
    devices = db.scalars(select(Device).order_by(Device.name)).all()
    throttle = float(os.environ.get("LIVENESS_THROTTLE_S", "3"))
    if throttle > 0 and _time.monotonic() - _last_refresh["at"] < throttle:
        return list(devices)
    _last_refresh["at"] = _time.monotonic()
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
            # One incident per device being offline (alert_grouping): a repeat while it is open
            # is counted, going offline again within 30 min of recovering REOPENS it (flapping
            # shows as reopened, not as new rows). Two requests refreshing at the same moment
            # count once (dedupe_s).
            from app.services.alert_grouping import raise_or_group
            raise_or_group(db, lab_id=d.lab_id, device_id=d.id, severity=AlertSeverity.WARNING,
                           title=f"{d.name} offline",
                           detail=f"No heartbeat since {_utc(d.last_seen_at):%Y-%m-%d %H:%M:%S} UTC. "
                                  f"Laboratory {lab.code if lab else d.lab_id}.",
                           now=now, dedupe_s=5)
            notify(db, staff_ids(db), "DEVICE_OFFLINE",
                   f"{d.name} is offline",
                   body=f"{lab.code if lab else ''} - no heartbeat for "
                        f"{silent} seconds.",
                   link="/admin/devices", severity="warning")
        elif not d.is_online and fresh:
            d.is_online = True
            changed = True
            # Back online: its offline alert is no longer true.
            for a in db.scalars(select(Alert).where(
                    Alert.device_id == d.id, Alert.title == f"{d.name} offline",
                    Alert.is_resolved.is_(False))).all():
                a.is_resolved = True
                a.resolved_at = now
    # A device that reports again clears its own offline incident even when its ingestion route set
    # is_online itself (PC agents, robot collectors and camera services do): before 2026-10-18 those
    # incidents stayed OPEN while the device was reporting - found with the investigation view. The
    # fresh report is the verification; nothing else is resolved here.
    fresh = {d.id: d for d in devices if is_fresh(d, now) is True}
    if fresh:
        for a in db.scalars(select(Alert).where(Alert.is_resolved.is_(False), Alert.device_id.in_(list(fresh)),
                                                Alert.title.like("% offline"))).all():
            if a.title == f"{fresh[a.device_id].name} offline":
                a.is_resolved, a.resolved_at, a.state = True, now, "RESOLVED"
                changed = True
    # A camera service that runs but gets NO PICTURE from its camera for NO_PICTURE_S is a service
    # problem of its own (camera off, unplugged, wrong address): one grouped incident, cleared as soon
    # as frames arrive again. (Robots are not treated this way: a robot switched off is normal.)
    for d in fresh.values():
        if d.device_type != DeviceType.SECURITY_CAMERA:
            continue
        title = f"{d.name}: no picture from the camera"
        if (d.component_state or {}).get("source_ok") is False:
            since = _no_picture.setdefault(d.id, now)
            if (now - since).total_seconds() >= NO_PICTURE_S:
                from app.services.alert_grouping import raise_or_group
                raise_or_group(db, lab_id=d.lab_id, device_id=d.id, severity=AlertSeverity.WARNING, title=title,
                               detail=f"The camera service of {d.device_uid} runs but has received no frame for "
                                      f"{int((now - since).total_seconds() // 60)} min. Check the camera's power, "
                                      f"network and RTSP address (camera*.env).", now=now, dedupe_s=3600)
                changed = True
        else:
            _no_picture.pop(d.id, None)
            for a in db.scalars(select(Alert).where(Alert.is_resolved.is_(False), Alert.device_id == d.id,
                                                    Alert.title == title)).all():
                a.is_resolved, a.resolved_at, a.state = True, now, "RESOLVED"
                changed = True
    # The database backups are watched on the same refresh (app.services.backups).
    from app.services import backups
    before = len(db.new) + len(db.dirty)
    backups.check(db)
    if changed or len(db.new) + len(db.dirty) != before:
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
    out.has_own_key = d.key_hash is not None
    if d.device_type == DeviceType.MASTER_CONTROLLER:
        out.component_state = effective_components(d, now)
    _derived_state(d, out, now)
    return out


_face_probe: dict = {"at": 0.0, "ok": None, "busy": False}
_cam_probe: dict = {"at": 0.0, "ok": None, "busy": False}


def _probe(state: dict, url: str, good) -> Optional[bool]:
    """Answer from the cache at once; refresh it in the background every 15 s (1 s timeout).
    The probe used to run inside the request, so while a device was off one request in every
    15 s waited a full second (seen as 1.0 s spikes on /devices and /labs/{id})."""
    import threading
    import time
    if time.monotonic() - state["at"] >= 15 and not state["busy"]:
        state["busy"] = True

        def run():
            import httpx
            try:
                ok = good(httpx.get(url, timeout=1.0).status_code)
            except Exception:
                ok = False
            state.update(at=time.monotonic(), ok=ok, busy=False)
        threading.Thread(target=run, daemon=True, name="device-probe").start()
    return state["ok"]


def _face_server_up() -> Optional[bool]:
    """The face server never reports; ask it directly (background, cached 15 s)."""
    import os
    if os.environ.get("DEVICE_PROBES", "1") == "0":   # tests: never touch real hardware
        return None
    from app.core.config import settings
    return _probe(_face_probe, settings.FACE_SERVER_URL.rstrip("/") + "/users", lambda c: c < 500)


def _entry_camera_up() -> bool:
    """The ESP32-CAM answers /status (background, cached 15 s)."""
    import os
    if os.environ.get("DEVICE_PROBES", "1") == "0":   # tests: never touch real hardware
        return False
    from app.core.config import settings
    return bool(_probe(_cam_probe, settings.CAMERA_URL.rstrip("/") + "/status", lambda c: c == 200))


def _derived_state(d: Device, out, now: datetime) -> None:
    """Devices that do not report for themselves get their state from who does."""
    from sqlalchemy.orm import object_session
    from app.models import DeviceType
    comps = d.component_state or {}
    if d.device_type == DeviceType.SECURITY_CAMERA:
        # Two cameras both called "Security camera" read as one: number them from the device id.
        import re
        n = re.search(r"(\d+)$", d.device_uid or "")
        if n and out.name == "Security camera":
            out.name = f"Security camera {int(n.group(1))}"
    if d.device_type == DeviceType.SECURITY_CAMERA and out.state == "ONLINE" and comps.get("source_ok") is False:
        # The heartbeat is the laptop's camera service; it gets no picture. Partly working - not
        # "online", not a dead device either (owner 2026-10-18: show it orange).
        out.state, out.is_online = "DEGRADED", False
        out.state_note = "Camera service running, but no picture from the camera"
    elif d.device_type == DeviceType.ROBOT and out.state == "ONLINE" and comps.get("source") != "SIMULATION" \
            and comps.get("q") is None and comps.get("robot_mode") is None:
        # The heartbeat is the laptop's read-only collector; it has no joint data from the robot.
        out.state, out.is_online = "DEGRADED", False
        out.state_note = "Collector running, but the robot is not connected (no joint data)"
    elif d.device_type == DeviceType.CAMERA and out.state != "ONLINE" and _entry_camera_up():
        out.state, out.is_online = "ONLINE", True
        out.state_note = "Checked by the portal (the door controller is not reporting)"
    elif d.device_type == DeviceType.CAMERA and out.state != "ONLINE":
        db = object_session(d)
        master = db and db.scalar(select(Device).where(
            Device.lab_id == d.lab_id, Device.device_type == DeviceType.MASTER_CONTROLLER))
        cam = (master.component_state or {}).get("camera") if master else None
        if master is not None and is_fresh(master, now) and cam is not None:
            out.state, out.is_online = ("ONLINE", True) if cam else ("OFFLINE", False)
            out.seconds_since_seen = int((now - _utc(master.last_seen_at)).total_seconds())
            out.state_note = "Reported by the door controller"
    elif d.device_type == DeviceType.FACE_SERVER and out.state != "ONLINE":
        up = _face_server_up()
        if up is not None:
            out.state, out.is_online = ("ONLINE", True) if up else ("OFFLINE", False)
            out.state_note = "Checked by the portal" if up else "Not answering on port 5000"


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


# A component is FAULTY only when it keeps reporting False for COMPONENT_FAULT_AFTER_S. The master's
# idle self-test (one fingerprint verifyPassword() / PN532 query) sometimes misses a single reply: the
# fingerprint then flapped "not responding" / "working again" every 10-30 s while it read fingers fine
# (2026-10-18, 10 alarms in 3 min). Its heartbeat comes every 30 s, so a dead part is still reported
# within about a minute. In memory (one backend process); a restart only restarts the 45 s.
COMPONENT_FAULT_AFTER_S = 45
_component_bad_since: dict[tuple[int, str], datetime] = {}


def component_fault_confirmed(device_id: int, key: str, now: Optional[datetime] = None) -> bool:
    if COMPONENT_FAULT_AFTER_S <= 0:
        return True                          # no confirmation wait configured
    since = _component_bad_since.get((device_id, key))
    return since is not None and ((now or datetime.now(timezone.utc)) - since).total_seconds() >= COMPONENT_FAULT_AFTER_S


def effective_components(d: Device, now: Optional[datetime] = None) -> Optional[dict]:
    """The reported components with a not-yet-confirmed False shown as working (see above)."""
    comps = d.component_state
    if not isinstance(comps, dict):
        return comps
    out = dict(comps)
    for key in COMPONENT_LABELS:
        if out.get(key) is False and not component_fault_confirmed(d.id, key, now):
            out[key] = True
    return out


def component_alert_title(device: Device, key: str) -> str:
    return f"{device.name}: {COMPONENT_LABELS[key]} not responding"


def record_component_health(db: Session, device: Device, lab: Lab,
                            components: dict, now: Optional[datetime] = None) -> None:
    now = now or datetime.now(timezone.utc)
    for key, label in COMPONENT_LABELS.items():
        ok = components.get(key)
        if not isinstance(ok, bool):
            continue
        if ok:
            _component_bad_since.pop((device.id, key), None)
        else:
            _component_bad_since.setdefault((device.id, key), now)
            if not component_fault_confirmed(device.id, key, now):
                continue                     # one missed self-test reply is not a fault (yet)
        title = component_alert_title(device, key)
        open_alert = db.scalar(select(Alert).where(
            Alert.device_id == device.id, Alert.is_resolved.is_(False),
            Alert.title == title))
        if not ok and open_alert is None:
            from app.services.alert_grouping import raise_or_group
            raise_or_group(db, lab_id=lab.id, device_id=device.id, severity=AlertSeverity.WARNING,
                           title=title, now=now,
                           detail=f"The door controller of {lab.code} reports that its {label.lower()} "
                                  f"is not responding. Check its wiring and power.")
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
    # Grouped per lab and alarm kind (one incident counting every occurrence); the NOTIFICATION below
    # is unchanged and still goes out on every occurrence - a safety alarm is never muted by grouping.
    from app.services.alert_grouping import raise_or_group
    raise_or_group(db, lab_id=lab.id, device_id=device.id if device else None, severity=severity,
                   title=title, detail=message or title, fp=f"door:{lab.id}:{reason}")
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

```
