"""
Networked equipment (Robotics Lab): robots and PCs on the lab LAN.

A collector (robots, read-only - e.g. tools/collectors/ur5e_rtde.py) or
an agent (PCs, tools/pc_agent) reports each item's state here with a
device key. Each item is a device linked to its asset, so the existing
liveness check and offline alerts cover it too. A state change closes the
open equipment session and opens the next one, linked to the booking in
force in the lab - usage per person and per booking comes from these.

Nothing here commands a robot. For PCs the server answers the agent with
the mode staff set (NORMAL / EXAM / MAINTENANCE / LOCKED) and, in exam
mode, the configured list of prohibited programs; violations are logged
and shown to staff - nothing is decided automatically about a student.

Admin master PC (System 2): from the portal staff can remove access (mode
LOCKED: the agent locks the PC and locks it again if someone unlocks it),
give it back (NORMAL), view the screen while they watch, and send a short
message. The agent polls for all of this; nothing pushes into a PC, and
every action is audited.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, require_admin, require_device, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import (Alert, AlertSeverity, Asset, AuditLog, Booking, BookingStatus,
                        Device, DeviceCommand, DeviceType, EquipmentSession, Lab,
                        PolicyViolation, Role, SensorReading, User)
from app.services import commands as cmds
from app.services import pc_control
from app.services.access import get_device, get_lab_by_code
from app.services.devices import is_fresh, refresh_liveness
from app.services.notifications import notify, staff_ids

router = APIRouter(prefix="/equipment", tags=["equipment"])

STATES = ("RUNNING", "IDLE", "FAULT")
MODES = ("NORMAL", "EXAM", "MAINTENANCE", "LOCKED")
PC_MESSAGE = "PC_MESSAGE"


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
            "is_master_pc": bool(d.is_master_pc),
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
    # LOCKED = access removed: the agent keeps the PC locked until NORMAL.
    mode: Literal["NORMAL", "EXAM", "MAINTENANCE", "LOCKED"]


@router.put("/{device_id}/mode")
def set_mode(device_id: int, req: ModeRequest, db: Session = Depends(get_db),
             staff: User = Depends(require_staff)):
    d = _pc(db, device_id, staff)
    old = d.mode or "NORMAL"
    d.mode = req.mode
    action = ("PC_ACCESS_REMOVED" if req.mode == "LOCKED" else
              "PC_ACCESS_GIVEN" if old == "LOCKED" else "PC_MODE_SET")
    db.add(AuditLog(actor_user_id=staff.id, action=action, entity_type="device",
                    entity_id=str(d.id), detail={"from": old, "to": req.mode,
                                                 "device": d.device_uid}))
    db.commit()
    return {"device_id": d.id, "mode": d.mode}


def _pc(db: Session, device_id: int, user: Optional[User] = None) -> Device:
    d = db.get(Device, device_id)
    if d is None or d.device_type != DeviceType.PC:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PC not found")
    # The lab engineer controls the lab PCs; only an administrator controls
    # the engineer's own master PC.
    if d.is_master_pc and user is not None and user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This is the lab engineer's master PC - administrators only.")
    return d


class MasterRequest(BaseModel):
    is_master: bool


@router.put("/{device_id}/master")
def set_master(device_id: int, req: MasterRequest, db: Session = Depends(get_db),
               admin: User = Depends(require_admin)):
    """Mark (or unmark) a PC as the lab engineer's master PC."""
    d = _pc(db, device_id, admin)
    d.is_master_pc = req.is_master
    db.add(AuditLog(actor_user_id=admin.id, action="PC_MASTER_SET", entity_type="device",
                    entity_id=str(d.id), detail={"device": d.device_uid, "is_master": req.is_master}))
    db.commit()
    return {"device_id": d.id, "is_master_pc": d.is_master_pc}


# ------------------------------------------- admin master PC: agent side ---
@router.get("/pc/poll", tags=["devices"])
def pc_poll(device_uid: str = Query(max_length=64), db: Session = Depends(get_db),
            identity: str = Depends(require_device)):
    """The PC agent asks every ~2 s: mode, whether staff are watching, and
    one waiting message. Cheap on purpose (nothing is written unless a
    message is handed over)."""
    device_scope(identity, device_uid)
    d = get_device(db, device_uid)
    if d is None or d.device_type != DeviceType.PC:
        return {"mode": "NORMAL", "mirror": False, "message": None}
    c = db.scalar(select(DeviceCommand).where(
        DeviceCommand.device_id == d.id, DeviceCommand.command == PC_MESSAGE,
        DeviceCommand.status == "PENDING").order_by(DeviceCommand.created_at))
    message = None
    if c is not None:
        now = datetime.now(timezone.utc)
        if now > _utc(c.expires_at):
            c.status, c.completed_at = "EXPIRED", now
            c.message = "The PC did not take the message in time (agent off)."
        else:
            # Shown the moment it is handed over: nothing else to wait for.
            c.status, c.sent_at, c.completed_at = "DONE", now, now
            c.message = "Shown on the PC."
            message = {"id": c.id, "text": (c.args or {}).get("text", "")}
        cmds.publish_later(db, c)
        db.commit()
        cmds.flush_published(db)
    return {"mode": d.mode or "NORMAL", "mirror": pc_control.is_watched(d.id),
            "message": message}


@router.post("/pc/frame", tags=["devices"], status_code=status.HTTP_204_NO_CONTENT)
async def pc_frame(request: Request, device_uid: str = Query(max_length=64),
                   db: Session = Depends(get_db), identity: str = Depends(require_device)):
    """One JPEG of the PC's screen, accepted only while staff are watching."""
    device_scope(identity, device_uid)
    d = get_device(db, device_uid)
    if d is None or d.device_type != DeviceType.PC:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown PC")
    if not pc_control.is_watched(d.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Nobody is viewing this screen")
    body = await request.body()
    if not body.startswith(b"\xff\xd8") or len(body) > pc_control.MAX_FRAME_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Expected a JPEG under 1.5 MB")
    pc_control.put_frame(d.id, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------- admin master PC: staff side ---
@router.post("/{device_id}/screen/start")
def screen_start(device_id: int, db: Session = Depends(get_db),
                 staff: User = Depends(require_staff)):
    d = _pc(db, device_id, staff)
    pc_control.touch_viewer(d.id)
    db.add(AuditLog(actor_user_id=staff.id, action="PC_SCREEN_VIEWED", entity_type="device",
                    entity_id=str(d.id), detail={"device": d.device_uid}))
    db.commit()
    return {"device_id": d.id, "watching": True}


@router.get("/{device_id}/screen.jpg")
def screen_frame(device_id: int, db: Session = Depends(get_db),
                 staff: User = Depends(require_staff)):
    """Latest frame, or 204 while the agent has not sent one yet."""
    d = _pc(db, device_id, staff)
    pc_control.touch_viewer(d.id)
    jpeg = pc_control.latest_frame(d.id)
    if jpeg is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(content=jpeg, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@router.post("/{device_id}/screen/stop")
def screen_stop(device_id: int, db: Session = Depends(get_db),
                staff: User = Depends(require_staff)):
    d = _pc(db, device_id, staff)
    pc_control.stop_viewer(d.id)
    return {"device_id": d.id, "watching": False}


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


@router.post("/{device_id}/message", status_code=status.HTTP_201_CREATED)
def send_message(device_id: int, req: MessageRequest, db: Session = Depends(get_db),
                 staff: User = Depends(require_staff)):
    d = _pc(db, device_id, staff)
    text = req.text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Write a message first.")
    now = datetime.now(timezone.utc)
    waiting = db.scalar(select(DeviceCommand).where(
        DeviceCommand.device_id == d.id, DeviceCommand.status == "PENDING"))
    if waiting is not None and now <= _utc(waiting.expires_at):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The previous message has not reached this PC yet.")
    if waiting is not None:
        waiting.status, waiting.completed_at = "EXPIRED", now
        waiting.message = "The PC did not take the message in time (agent off)."
    c = DeviceCommand(device_id=d.id, command=PC_MESSAGE, args={"text": text},
                      status="PENDING", requested_by_id=staff.id, created_at=now,
                      expires_at=now + cmds.PICKUP_WINDOW)
    db.add(c)
    db.flush()
    db.add(AuditLog(actor_user_id=staff.id, action="PC_MESSAGE_SENT", entity_type="device",
                    entity_id=str(d.id), detail={"device": d.device_uid, "command_id": c.id,
                                                 "text": text}))
    cmds.publish_later(db, c)
    db.commit()
    cmds.flush_published(db)
    return cmds.out(c)
