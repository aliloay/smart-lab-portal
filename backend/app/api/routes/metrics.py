"""Measurements, device diagnosis and the event timeline (read only, staff)."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.core.ttl import cached
from app.db.session import get_db
from app.models import Device, User
from app.services import metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/registry")
def registry(_: User = Depends(require_staff)):
    return [{"name": k, **v} for k, v in metrics.REGISTRY.items()]


@router.get("/latest")
def latest(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return cached("metrics.latest", 20, lambda: metrics.latest(db))


@router.get("/history")
def history(device_id: int, metric: str = Query(max_length=48), period: Literal["24h", "7d", "30d", "90d"] = "7d",
            db: Session = Depends(get_db), _: User = Depends(require_staff)):
    if metric not in metrics.REGISTRY:
        raise HTTPException(404, "Unknown metric")
    if db.get(Device, device_id) is None:
        raise HTTPException(404, "Unknown device")
    return cached(f"metrics.history.{device_id}.{metric}.{period}", 20,
                  lambda: metrics.history(db, device_id, metric, period))


@router.get("/coverage")
def coverage(days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return cached(f"metrics.coverage.{days}", 60, lambda: metrics.coverage(db, days))


@router.get("/diagnose/{device_id}")
def diagnose(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    d = db.get(Device, device_id)
    if d is None:
        raise HTTPException(404, "Unknown device")
    return metrics.diagnose(db, d)


@router.get("/timeline")
def timeline(hours: int = Query(24, ge=1, le=720),
             kinds: str = Query("alert,robot,maintenance,pc,door,automation", max_length=80),
             db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return metrics.timeline(db, hours, set(kinds.split(",")))
