"""
System status and configuration.

Status reports only what the API actually knows: whether its own database
answers, how many live sockets it holds, and what the devices last said. It
does not claim a device is healthy that has never reported.
"""
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from app.services.backups import read_status as read_backup_status
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import DeviceType, User
from app.schemas import SystemConfig, SystemStatus
from app.services.devices import is_fresh, refresh_liveness
from app.services.issues import sla_hours
from app.services.storage import get_storage
from app.ws.manager import manager

router = APIRouter(prefix="/system", tags=["system"])

# Internet reachability, cached: checked at most once a minute so a status
# request never waits on it. A TCP connect to a public DNS resolver fails
# within a second when the lab router has no uplink.
_INTERNET_TTL = 60.0
_internet = {"ok": None, "at": 0.0}


def _probe_internet() -> None:
    ok = False
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.create_connection((host, 53), timeout=1.0):
                ok = True
                break
        except OSError:
            continue
    _internet["ok"] = ok


def internet_reachable() -> Optional[bool]:
    """Never waits: the probe runs in a background thread (it used to hold a status request - and
    its database connection - for up to 2 s every minute on the offline lab router)."""
    now = time.monotonic()
    if now - _internet["at"] >= _INTERNET_TTL:
        _internet["at"] = now
        threading.Thread(target=_probe_internet, daemon=True, name="internet-probe").start()
    return _internet["ok"]


@router.get("/status", response_model=SystemStatus)
def system_status(db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    now = datetime.now(timezone.utc)
    devices = refresh_liveness(db) if db_ok else []
    fresh = [is_fresh(d, now) for d in devices]
    controllers = [d for d in devices
                   if d.device_type == DeviceType.MASTER_CONTROLLER]
    seen = [d.last_seen_at for d in devices if d.last_seen_at is not None]
    offline = [d.name or d.device_uid for d in devices
               if d.last_seen_at is not None and not is_fresh(d, now)
               and not d.device_uid.upper().endswith("_SIM")
               and not (d.name or "").startswith("TEST -")]    # retired duplicates (kept for their history)

    return SystemStatus(
        status="HEALTHY" if db_ok else "DEGRADED",
        database=db_ok,
        websocket_clients=manager.count,
        devices_online=sum(1 for f in fresh if f),
        devices_total=len(devices),
        devices_reporting=sum(1 for f in fresh if f is not None),
        controllers_online=sum(1 for d in controllers if is_fresh(d, now)),
        controllers_total=len(controllers),
        offline_devices=sorted(offline),
        last_heartbeat_at=max(seen) if seen else None,
        internet=internet_reachable(),
        backup=read_backup_status(),
        time=now,
    )


@router.get("/config", response_model=SystemConfig)
def system_config(_: User = Depends(require_admin)):
    """Read-only: configuration comes from the environment, not the browser."""
    return SystemConfig(
        environment=settings.ENVIRONMENT,
        booking_auto_approve=settings.BOOKING_AUTO_APPROVE,
        max_booking_hours=settings.MAX_BOOKING_HOURS,
        booking_grace_minutes=settings.BOOKING_GRACE_MINUTES,
        booking_reminder_minutes=settings.BOOKING_REMINDER_MINUTES,
        qr_token_bytes=settings.QR_TOKEN_BYTES,
        access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        device_stale_seconds=settings.DEVICE_STALE_SECONDS,
        max_upload_mb=settings.MAX_UPLOAD_MB,
        max_photos_per_issue=settings.MAX_PHOTOS_PER_ISSUE,
        image_max_dimension=settings.IMAGE_MAX_DIMENSION,
        issue_sla_hours=sla_hours(),
        storage_backend=getattr(get_storage(), "name", "custom"),
    )


class DataModeIn(BaseModel):
    mode: Literal["REAL_OPERATION", "PHYSICAL_TEST", "BENCH_TEST", "SOFTWARE_TEST", "DEMO_DATA",
                  "UNKNOWN_PROVENANCE"]


@router.get("/data-mode")
def get_data_mode(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """The provenance new records get (a RUNNING experiment overrides it)."""
    from app.services import provenance
    mode, exp_id = provenance.current(db)
    return {"mode": mode, "experiment_id": exp_id}


@router.put("/data-mode")
def set_data_mode(req: DataModeIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Administrators only. Affects NEW records only - history keeps its provenance."""
    from app.models import AuditLog
    from app.services import provenance
    before, _ = provenance.current(db)
    provenance.set_setting(db, provenance.MODE_KEY, req.mode)
    db.add(AuditLog(actor_user_id=admin.id, action="DATA_MODE_CHANGED", entity_type="system",
                    entity_id="data_mode", detail={"from": before, "to": req.mode}))
    db.commit()
    provenance.invalidate()
    return {"mode": req.mode}


# ------------------------------------------------------------- services ---
# One answer to "is every part of the lab system up?" (Command Center, System Health page).
# Each entry is checked for real - a background HTTP probe (health_monitor) or the device's last
# heartbeat - never assumed green.
STALE_S = 3600          # a device silent for less than this is STALE; longer = OFFLINE; never = UNKNOWN


def _device_health(db: Session, now: datetime) -> list[dict]:
    from sqlalchemy import func, select
    from app.models import Alert, Device
    from app.services.health_monitor import GUIDANCE
    groups = {DeviceType.MASTER_CONTROLLER: "door", DeviceType.CAMERA: "entry_camera",
              DeviceType.SENSOR_NODE: "environment", DeviceType.SECURITY_CAMERA: "security_camera",
              DeviceType.ROBOT: "robot", DeviceType.PC: "pc"}
    open_alerts = dict(db.execute(select(Alert.device_id, func.count()).where(
        Alert.is_resolved.is_(False), Alert.device_id.is_not(None)).group_by(Alert.device_id)).all())
    out = []
    for d in db.scalars(select(Device).order_by(Device.device_type, Device.name)).all():
        if d.device_type not in groups:
            continue
        fresh = is_fresh(d, now)
        cs = d.component_state or {}
        last = d.last_seen_at
        age = None if last is None else (now - (last if last.tzinfo else last.replace(tzinfo=timezone.utc))).total_seconds()
        state = ("UNKNOWN" if last is None else "ONLINE" if fresh else "STALE" if age is not None and age < STALE_S
                 else "OFFLINE")
        note = None
        if d.device_type == DeviceType.SECURITY_CAMERA and fresh and cs.get("source_ok") is False:
            state, note = "DEGRADED", "camera service running, but no picture from the camera"
        if d.device_type == DeviceType.ROBOT and fresh and not cs.get("q"):
            state, note = "DEGRADED", "collector running, but no joint data from the controller"
        sim = cs.get("source") == "SIMULATION" or d.device_uid.upper().endswith("_SIM")
        if sim:
            if not fresh:
                continue                                # a stopped simulation is not a system fault
            state = "SIMULATION"
        g = groups[d.device_type]
        out.append({"key": f"{g}:{d.id}", "group": g, "name": d.name, "device_id": d.id, "device_uid": d.device_uid,
                    "state": state, "latency_ms": None, "last_seen": last.isoformat() if last else None,
                    "age_s": round(age) if age is not None else None,
                    "detail": note or (f"last report {last.isoformat()}" if last else "has never reported"),
                    "open_alerts": int(open_alerts.get(d.id, 0)),
                    "guidance": GUIDANCE.get(g) if state in ("OFFLINE", "STALE", "DEGRADED") else None})
    return out


@router.get("/services")
def services(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Every part of the lab system. Network services come from the background monitor's cache
    (app/services/health_monitor.py) - this request never waits on a probe."""
    from app.services import health_monitor
    now = datetime.now(timezone.utc)
    out = []
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        out.append({"key": "database", "name": "PostgreSQL", "state": "ONLINE",
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1), "detail": "query answered"})
    except Exception:
        out.append({"key": "database", "name": "PostgreSQL", "state": "OFFLINE", "latency_ms": None,
                    "detail": "no answer", "guidance": health_monitor.GUIDANCE["database"]})
    out.append({"key": "backend", "name": "Backend API", "state": "ONLINE", "latency_ms": None,
                "detail": "answering this request"})
    out.append({"key": "websocket", "name": "Live stream", "state": "ONLINE" if manager.count else "UNKNOWN",
                "latency_ms": None, "detail": f"{manager.count} browser(s) connected"})
    for s in health_monitor.snapshot():
        out.append({**s, "last_check": s["last_check"].isoformat() if s["last_check"] else None,
                    "last_ok": s["last_ok"].isoformat() if s["last_ok"] else None,
                    "failing_since": s["failing_since"].isoformat() if s["failing_since"] else None})
    try:
        out.extend(_device_health(db, now))
    except Exception as e:                              # monitoring must never break the page
        out.append({"key": "devices", "name": "Device states", "state": "UNKNOWN", "latency_ms": None,
                    "detail": f"could not read device states ({e.__class__.__name__})"})
    return {"checked_at": now, "services": out}


@router.get("/health")
def system_health(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """The System Health page: services + devices, data-source freshness, backups, a summary."""
    from app.services.system_analytics import freshness
    body = services(db, _)
    states = [s["state"] for s in body["services"]]
    summary = {k: states.count(k) for k in ("ONLINE", "DEGRADED", "STALE", "OFFLINE", "UNKNOWN", "SIMULATION")}
    try:
        fresh = freshness(db, body["checked_at"])
    except Exception:
        fresh = {}
    return {**body, "summary": summary, "data_sources": fresh, "backup": read_backup_status()}
