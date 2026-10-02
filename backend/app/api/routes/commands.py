"""
Fingerprint enrollment from the portal, through device commands.

Staff press "Enroll fingerprint" on Users & roles. The portal records a
request; the door controller fetches it while idle, prompts the person on
its LCD and the tablet ("place your finger... again"), stores the finger in
slot n of the sensor (USERn), and reports each step back. The portal never
reaches into the controller - see app/services/commands.py.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, require_device, require_staff
from app.db.session import get_db
from app.models import AuditLog, Device, DeviceCommand, DeviceType, User
from app.services import commands as cmds
from app.services import enrolment
from app.services.access import get_device
from app.services.devices import is_fresh

router = APIRouter(tags=["device commands"])

MAX_FINGER_SLOT = 127          # AS608 capacity, as in the firmware


class EnrollRequest(BaseModel):
    # True = overwrite a finger already stored in this slot.
    force: bool = False
    lab_id: Optional[int] = None


def _slot(u: User) -> int:
    m = re.fullmatch(r"USER(\d{1,3})", u.auth_subject or "")
    n = int(m.group(1)) if m else 0
    if not 1 <= n <= MAX_FINGER_SLOT:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Give this person a door identity USERn first, then save.")
    return n


def _controller(db: Session, lab_id: Optional[int]) -> Device:
    q = select(Device).where(Device.device_type == DeviceType.MASTER_CONTROLLER)
    if lab_id is not None:
        q = q.where(Device.lab_id == lab_id)
    now = datetime.now(timezone.utc)
    online = [d for d in db.scalars(q).all() if is_fresh(d, now)]
    if not online:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The door controller is offline. Check it is powered "
                            "and on the lab Wi-Fi, then try again.")
    return online[0]


def _first_name(u: User) -> str:
    first = (u.full_name or "").strip().split(" ")[0].upper()
    return first[:15] or (u.auth_subject or "")


@router.post("/users/{user_id}/fingerprint/enroll")
def request_enrollment(user_id: int, req: EnrollRequest, db: Session = Depends(get_db),
                       staff: User = Depends(require_staff)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    slot = _slot(u)
    device = _controller(db, req.lab_id)
    cmds.expire_stale(db)
    if cmds.active_for_device(db, device.id):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The door controller is busy with another request. "
                            "Wait for it to finish or cancel it.")
    now = datetime.now(timezone.utc)
    c = DeviceCommand(device_id=device.id, command=cmds.ENROLL_FINGERPRINT,
                      args={"slot": slot, "force": req.force,
                            "auth_subject": u.auth_subject,
                            "display_name": _first_name(u)},
                      status="PENDING", target_user_id=u.id,
                      requested_by_id=staff.id, created_at=now,
                      expires_at=now + cmds.PICKUP_WINDOW)
    db.add(c)
    db.flush()
    db.add(AuditLog(actor_user_id=staff.id, action="FINGERPRINT_ENROLL_REQUESTED",
                    entity_type="user", entity_id=str(u.id),
                    detail={"slot": slot, "force": req.force, "command_id": c.id,
                            "device": device.device_uid}))
    cmds.publish_later(db, c)
    db.commit()
    cmds.flush_published(db)
    return cmds.out(c)


@router.get("/device-commands/{command_id}")
def command_status(command_id: int, db: Session = Depends(get_db),
                   _: User = Depends(require_staff)):
    cmds.expire_stale(db)
    db.commit()
    cmds.flush_published(db)
    c = db.get(DeviceCommand, command_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    return cmds.out(c)


@router.post("/device-commands/{command_id}/cancel")
def cancel_command(command_id: int, db: Session = Depends(get_db),
                   staff: User = Depends(require_staff)):
    c = db.get(DeviceCommand, command_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if c.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The door controller has already started it; it ends "
                            "on its own if nobody places a finger.")
    c.status, c.completed_at = "CANCELLED", datetime.now(timezone.utc)
    c.message = "Cancelled by staff."
    db.add(AuditLog(actor_user_id=staff.id, action="DEVICE_COMMAND_CANCELLED",
                    entity_type="device_command", entity_id=str(c.id), detail={}))
    cmds.publish_later(db, c)
    db.commit()
    cmds.flush_published(db)
    return cmds.out(c)


# --------------------------------------------------------- device side ---
@router.get("/access/commands/next", tags=["devices"])
def next_command(device_uid: str = Query(max_length=64), db: Session = Depends(get_db),
                 identity: str = Depends(require_device)):
    """The controller asks, while idle, whether a request is waiting for it."""
    device_scope(identity, device_uid)
    device = get_device(db, device_uid)
    if device is None:
        return {"command": None}
    cmds.expire_stale(db)
    c = db.scalar(select(DeviceCommand).where(
        DeviceCommand.device_id == device.id, DeviceCommand.status == "PENDING")
        .order_by(DeviceCommand.created_at))
    if c is None:
        db.commit()
        cmds.flush_published(db)
        return {"command": None}
    c.status, c.sent_at = "SENT", datetime.now(timezone.utc)
    cmds.publish_later(db, c)
    db.commit()
    cmds.flush_published(db)
    # Flat, so the firmware's small JSON helpers can read it.
    a = c.args or {}
    return {"id": c.id, "command": c.command, "slot": a.get("slot", 0),
            "force": bool(a.get("force")), "auth_subject": a.get("auth_subject", ""),
            "display_name": a.get("display_name", ""),
            # OPEN_LID (reusable bin): the item the person selected.
            "asset_tag": a.get("asset_tag", "")}


class ProgressReport(BaseModel):
    device_uid: str = Field(max_length=64)
    status: Literal["RUNNING", "DONE", "FAILED"]
    step: Optional[str] = Field(default=None, max_length=32)
    message: Optional[str] = Field(default=None, max_length=255)


@router.post("/access/commands/{command_id}/progress", tags=["devices"])
def report_progress(command_id: int, req: ProgressReport, db: Session = Depends(get_db),
                    identity: str = Depends(require_device)):
    device_scope(identity, req.device_uid)
    c = db.get(DeviceCommand, command_id)
    device = get_device(db, req.device_uid)
    if c is None or device is None or c.device_id != device.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such request for this device")
    if c.status in cmds.FINAL:
        return {"status": c.status, "ignored": True}
    now = datetime.now(timezone.utc)
    c.status, c.step = req.status, req.step
    if req.message:
        c.message = req.message
    if req.status in ("DONE", "FAILED"):
        c.completed_at = now
        target = db.get(User, c.target_user_id) if c.target_user_id else None
        if c.command == cmds.ENROLL_FINGERPRINT and target is not None:
            if req.status == "DONE":
                enrolment.mark(db, target, "fingerprint", True)
            db.add(AuditLog(actor_user_id=c.requested_by_id,
                            action="FINGERPRINT_ENROLLED" if req.status == "DONE"
                            else "FINGERPRINT_ENROLL_FAILED",
                            entity_type="user", entity_id=str(target.id),
                            detail={"slot": (c.args or {}).get("slot"),
                                    "command_id": c.id, "step": req.step,
                                    "message": req.message,
                                    "device": device.device_uid}))
    cmds.publish_later(db, c)
    db.commit()
    cmds.flush_published(db)
    return {"status": c.status}
