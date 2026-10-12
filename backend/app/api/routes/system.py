"""
System status and configuration.

Status reports only what the API actually knows: whether its own database
answers, how many live sockets it holds, and what the devices last said. It
does not claim a device is healthy that has never reported.
"""
import socket
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


def internet_reachable() -> Optional[bool]:
    now = time.monotonic()
    if now - _internet["at"] >= _INTERNET_TTL:
        _internet["at"] = now
        ok = False
        for host in ("1.1.1.1", "8.8.8.8"):
            try:
                with socket.create_connection((host, 53), timeout=1.0):
                    ok = True
                    break
            except OSError:
                continue
        _internet["ok"] = ok
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
               and not d.device_uid.upper().endswith("_SIM")]

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
# One answer to "is every part of the lab system up?" for the Command
# Center. Each entry is checked for real (an HTTP probe with a short timeout,
# or the device's last heartbeat) - never assumed green. Cached a few seconds
# so many open dashboards do not multiply the probes.
_SVC_TTL = 5.0
_svc_cache: dict = {"at": 0.0, "body": None}


def _probe(url: str, timeout: float = 1.2) -> tuple[str, Optional[float], str]:
    import httpx
    t0 = time.perf_counter()
    try:
        r = httpx.get(url, timeout=timeout)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return ("ONLINE" if r.status_code < 500 else "DEGRADED"), ms, f"HTTP {r.status_code}"
    except Exception as e:                                  # unreachable / timeout: OFFLINE, with the reason
        return "OFFLINE", None, e.__class__.__name__


@router.get("/services")
def services(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    now_m = time.monotonic()
    if _svc_cache["body"] is not None and now_m - _svc_cache["at"] < _SVC_TTL:
        return _svc_cache["body"]
    from sqlalchemy import select
    from app.models import Device
    now = datetime.now(timezone.utc)
    out = []
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        out.append({"key": "database", "name": "PostgreSQL", "state": "ONLINE",
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1), "detail": "query answered"})
    except Exception:
        out.append({"key": "database", "name": "PostgreSQL", "state": "OFFLINE", "latency_ms": None,
                    "detail": "no answer"})
    out.append({"key": "backend", "name": "Backend API", "state": "ONLINE", "latency_ms": None,
                "detail": "answering this request"})
    out.append({"key": "websocket", "name": "Live stream", "state": "ONLINE" if manager.count else "UNKNOWN",
                "latency_ms": None, "detail": f"{manager.count} browser(s) connected"})
    face = settings.FACE_SERVER_URL.rstrip("/")
    st, ms, why = _probe(face + "/health")
    out.append({"key": "face", "name": "Face server", "state": st, "latency_ms": ms, "detail": why})
    if settings.OLLAMA_URL:
        st, ms, why = _probe(settings.OLLAMA_URL.rstrip("/") + "/api/tags")
        out.append({"key": "ai", "name": "AI (local model)", "state": st, "latency_ms": ms, "detail": why})
    else:
        out.append({"key": "ai", "name": "AI (local model)", "state": "UNKNOWN", "latency_ms": None,
                    "detail": "not configured"})
    st, ms, why = _probe("http://n8n:5678/healthz")
    out.append({"key": "n8n", "name": "Automation (n8n)", "state": st, "latency_ms": ms, "detail": why})
    groups = {DeviceType.MASTER_CONTROLLER: "door", DeviceType.CAMERA: "entry_camera",
              DeviceType.SENSOR_NODE: "environment", DeviceType.SECURITY_CAMERA: "security_camera",
              DeviceType.ROBOT: "robot", DeviceType.PC: "pc"}
    for d in db.scalars(select(Device).order_by(Device.device_type, Device.name)).all():
        if d.device_type not in groups:
            continue
        fresh = is_fresh(d, now)
        state = "UNKNOWN" if fresh is None else "ONLINE" if fresh else "OFFLINE"
        cs = d.component_state or {}
        if d.device_type == DeviceType.SECURITY_CAMERA and fresh and cs.get("source_ok") is False:
            state = "DEGRADED"                              # service up, camera picture lost
        if d.device_type == DeviceType.ROBOT and cs.get("source") == "SIMULATION":
            if not fresh:
                continue                                # a stopped simulation is not a system fault
            state = "SIMULATION"
        last = d.last_seen_at
        out.append({"key": f"{groups[d.device_type]}:{d.id}", "group": groups[d.device_type],
                    "name": d.name, "device_id": d.id, "state": state, "latency_ms": None,
                    "detail": f"last report {last.isoformat() if last else 'never'}"})
    body = {"checked_at": now, "services": out}
    _svc_cache.update(at=now_m, body=body)
    return body
