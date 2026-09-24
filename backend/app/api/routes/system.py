"""
System status and configuration.

Status reports only what the API actually knows: whether its own database
answers, how many live sockets it holds, and what the devices last said. It
does not claim a device is healthy that has never reported.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models import DeviceType, User
from app.schemas import SystemConfig, SystemStatus
from app.services.devices import is_fresh, refresh_liveness
from app.services.issues import sla_hours
from app.services.storage import get_storage
from app.ws.manager import manager

router = APIRouter(prefix="/system", tags=["system"])


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

    return SystemStatus(
        status="HEALTHY" if db_ok else "DEGRADED",
        database=db_ok,
        websocket_clients=manager.count,
        devices_online=sum(1 for f in fresh if f),
        devices_total=len(devices),
        devices_reporting=sum(1 for f in fresh if f is not None),
        controllers_online=sum(1 for d in controllers if is_fresh(d, now)),
        controllers_total=len(controllers),
        last_heartbeat_at=max(seen) if seen else None,
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
