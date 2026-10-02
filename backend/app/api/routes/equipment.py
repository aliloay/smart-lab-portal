"""
Networked equipment (Robotics Lab): robots and PCs on the lab LAN.

A collector (robots, read-only - e.g. tools/collectors/ur5e_rtde.py) or
an agent (PCs, tools/pc_agent) reports each item's state here with a
device key. Each item is a device linked to its asset, so the existing
liveness check and offline alerts cover it too. A state change closes the
open equipment session and opens the next one, linked to the booking in
force in the lab - usage per person and per booking comes from these.

Nothing here commands a robot. For PCs the server only answers the agent
with the mode an engineer set (NORMAL / EXAM / MAINTENANCE) and, in exam
mode, the configured list of prohibited programs; violations are logged
and shown to staff - nothing is decided automatically about a student.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, require_device, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import (Alert, AlertSeverity, Asset, AuditLog, Booking, BookingStatus,
                        Device, DeviceType, EquipmentSession, Lab, PolicyViolation,
                        SensorReading, User)
from app.services.access import get_device, get_lab_by_code
from app.services.devices import is_fresh, refresh_liveness
from app.services.notifications import notify, staff_ids

router = APIRouter(prefix="/equipment", tags=["equipment"])

STATES = ("RUNNING", "IDLE", "FAULT")
MODES = ("NORMAL", "EXAM", "MAINTENANCE")


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def _open_session(db: Session, device_id: int) -> Optional[EquipmentSession]:
    return db.scalar(select(EquipmentSession).where(
        EquipmentSession.device_id == device_id, EquipmentSession.ended_at.is_(None)))


def close_offline_sessions(db: Session, now: datetime) -> None:
    """An item that stopped reporting has no current state: end its session."""
    for s in db.scalars(select(EquipmentSession).where(EquipmentSession.ended_at.is_(None))).all():
        d = db.get(Device, s.device_id)
        if d is not None and is_fresh(d, now) is False:
            s.ended_at = d.last_seen_at or now


# ------------------------------------------------- collector / agent ---
class Reading(BaseModel):
    metric: str = Field(pattern=r"^[a-z][a-z0-9_]{1,47}$")
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(default="", max_length=16)


class StateReport(BaseModel):
    device_uid: str = Field(max_length=64)
    lab_id: str = Field(max_length=32)
    kind: Literal["ROBOT", "PC"]
    asset_tag: Optional[str] = Field(default=None, max_length=64)
    state: Literal["RUNNING", "IDLE", "FAULT"]
    # What the source actually exposes (robot mode, program, safety mode,
    # logged-in account...). Stored as reported; nothing is filled in.
    detail: dict[str, Any] = Field(default_factory=dict)
    metrics: list[Reading] = Field(default_factory=list, max_length=20)
    firmware_version: Optional[str] = Field(default=None, max_length=64)


@router.post("/state", tags=["devices"])
def report_state(req: StateReport, db: Session = Depends(get_db),
                 identity: str = Depends(require_device)):
    device_scope(identity, req.device_uid)
    lab = get_lab_by_code(db, req.lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown lab")
    now = datetime.now(timezone.utc)
    dtype = DeviceType.ROBOT if req.kind == "ROBOT" else DeviceType.PC
    d = get_device(db, req.device_uid)
    if d is None:
        d = Device(device_uid=req.device_uid, name=req.asset_tag or req.device_uid,
                   device_type=dtype, lab_id=lab.id)
        db.add(d)
        db.flush()
    if req.asset_tag and d.asset_id is None:
        a = db.scalar(select(Asset).where(Asset.asset_tag == req.asset_tag))
        if a is not None:
            d.asset_id = a.id
    d.last_seen_at, d.is_online = now, True
    d.firmware_version = req.firmware_version or d.firmware_version
    d.component_state = {"state": req.state, **req.detail}

    s = _open_session(db, d.id)
    if s is None or s.state != req.state:
        if s is not None:
            s.ended_at = now
        current = db.scalar(select(Booking).where(
            Booking.lab_id == lab.id, Booking.status == BookingStatus.CONFIRMED,
            Booking.start_time <= now, Booking.end_time > now))
        db.add(EquipmentSession(device_id=d.id, asset_id=d.asset_id, lab_id=lab.id,
                                state=req.state, detail=req.detail or None,
                                user_id=current.user_id if current else None,
                                booking_id=current.id if current else None,
                                started_at=now))
        if req.state == "FAULT":
            db.add(Alert(lab_id=lab.id, device_id=d.id, severity=AlertSeverity.WARNING,
                         title=f"{d.name}: fault reported",
                         detail=str(req.detail)[:500]))
    for m in req.metrics:
        db.add(SensorReading(lab_id=lab.id, device_id=d.id, metric=m.metric,
                             value=m.value, unit=m.unit, recorded_at=now))
    db.commit()
    mode = d.mode or "NORMAL"
    return {"mode": mode,
            "prohibited": settings.exam_prohibited if mode == "EXAM" else []}


class ViolationReport(BaseModel):
    device_uid: str = Field(max_length=64)
    kind: str = Field(max_length=32)
    detail: str = Field(default="", max_length=255)
    os_user: Optional[str] = Field(default=None, max_length=64)


@router.post("/violations", tags=["devices"], status_code=status.HTTP_201_CREATED)
def report_violation(req: ViolationReport, db: Session = Depends(get_db),
                     identity: str = Depends(require_device)):
    device_scope(identity, req.device_uid)
    d = get_device(db, req.device_uid)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown device")
    v = PolicyViolation(device_id=d.id, lab_id=d.lab_id, kind=req.kind, detail=req.detail,
                        os_user=req.os_user)
    db.add(v)
    notify(db, staff_ids(db), "EXAM_VIOLATION", f"Exam policy: {d.name}",
           body=f"{req.kind}: {req.detail}" + (f" (account {req.os_user})" if req.os_user else ""),
           link="/admin/equipment", severity="warning")
    db.commit()
    return {"id": v.id}


# --------------------------------------------------------------- staff ---
def _today_seconds(db: Session, d: Device, state: str, now: datetime) -> int:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total = 0.0
    for s in db.scalars(select(EquipmentSession).where(
            EquipmentSession.device_id == d.id, EquipmentSession.state == state,
            EquipmentSession.started_at < now)).all():
        a = max(_utc(s.started_at), start)
        b = _utc(s.ended_at) if s.ended_at else now
        if b > a:
            total += (b - a).total_seconds()
    return int(total)


@router.get("")
def list_equipment(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    refresh_liveness(db)
    now = datetime.now(timezone.utc)
    close_offline_sessions(db, now)
    db.commit()
    out = []
    for d in db.scalars(select(Device).where(Device.device_type.in_(
            (DeviceType.ROBOT, DeviceType.PC))).order_by(Device.device_uid)).all():
        lab = db.get(Lab, d.lab_id)
        asset = db.get(Asset, d.asset_id) if d.asset_id else None
        s = _open_session(db, d.id)
        who = db.get(User, s.user_id) if s and s.user_id else None
        out.append({
            "device_id": d.id, "device_uid": d.device_uid, "kind": d.device_type.value,
            "name": asset.name if asset else d.name, "asset_tag": asset.asset_tag if asset else None,
            "lab_code": lab.code if lab else None, "online": is_fresh(d, now),
            "last_seen_at": d.last_seen_at, "state": s.state if s else None,
            "since": s.started_at if s else None, "detail": d.component_state or {},
            "user_name": who.full_name if who else None,
            "booking_id": s.booking_id if s else None, "mode": d.mode or "NORMAL",
            "running_today_s": _today_seconds(db, d, "RUNNING", now),
            "open_violations": db.query(PolicyViolation).filter_by(
                device_id=d.id, reviewed=False).count()})
    return out


@router.get("/{device_id}/sessions")
def sessions(device_id: int, days: int = Query(7, ge=1, le=365),
             db: Session = Depends(get_db), _: User = Depends(require_staff)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.scalars(select(EquipmentSession).where(
        EquipmentSession.device_id == device_id, EquipmentSession.started_at >= since)
        .order_by(desc(EquipmentSession.started_at))).all()
    out = []
    for s in rows:
        u = db.get(User, s.user_id) if s.user_id else None
        out.append({"state": s.state, "started_at": s.started_at, "ended_at": s.ended_at,
                    "user_name": u.full_name if u else None, "booking_id": s.booking_id,
                    "detail": s.detail})
    return out


@router.get("/violations")
def list_violations(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    rows = db.scalars(select(PolicyViolation).order_by(desc(PolicyViolation.created_at))
                      .limit(200)).all()
    return [{"id": v.id, "device_uid": db.get(Device, v.device_id).device_uid, "kind": v.kind,
             "detail": v.detail, "os_user": v.os_user, "reviewed": v.reviewed,
             "created_at": v.created_at} for v in rows]


class ModeRequest(BaseModel):
    mode: Literal["NORMAL", "EXAM", "MAINTENANCE"]


@router.put("/{device_id}/mode")
def set_mode(device_id: int, req: ModeRequest, db: Session = Depends(get_db),
             staff: User = Depends(require_staff)):
    d = db.get(Device, device_id)
    if d is None or d.device_type != DeviceType.PC:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PC not found")
    old = d.mode or "NORMAL"
    d.mode = req.mode
    db.add(AuditLog(actor_user_id=staff.id, action="PC_MODE_SET", entity_type="device",
                    entity_id=str(d.id), detail={"from": old, "to": req.mode,
                                                 "device": d.device_uid}))
    db.commit()
    return {"device_id": d.id, "mode": d.mode}
