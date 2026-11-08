---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/emergency.py"
source_hash: "a9caca8cef63734587f304740e986ae289807e933b9e148d6bf2c94c52170e52"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/emergency.py` - edit the original in the repository, not this note.

Systems: [[Door and access]]

## Related
- [[backend_app_api_routes_automation.py]] - imports
- [[backend_app_api_routes_equipment.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services_safety_triage.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_commands.py]] - imports
- [[backend_app_services_proactive.py]] - imports
- [[backend_app_services_emergency.py]] - imports
- [[backend_app_services_access.py]] - imports
- [[backend_app_services_devices.py]] - imports
- [[backend_app_services_integration.py]] - imports
- [[backend_app_services_notifications.py]] - imports
- [[backend_app_services_environment.py]] - imports

```py
"""
Emergency tab (administrators, behind the emergency password).

    POST /emergency/session            password -> short emergency session
    GET  /emergency/status             every lab's state + controller status
    POST /emergency/labs/{id}          door UNLOCKED (minutes / until normal)
                                       or LOCKDOWN, message on LCD + tablet,
                                       evacuation alarm
    POST /emergency/labs/{id}/normal   everything back to normal
    POST /emergency/pcs                lock / unlock / message all lab PCs
    PUT  /emergency/password           change the emergency password

    GET  /access/emergency             the door controller, every second

This is the one place where the portal can open a door, and it is built for
that: an administrator, the emergency password, a session of a few minutes,
every action audited and announced to all staff. The door controller still
applies it itself and keeps doing so if the network drops.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, get_current_user, require_admin, require_device, require_staff
from app.db.session import get_db
from app.models import AuditLog, Device, DeviceCommand, DeviceType, Lab, LabEmergency, User
from app.services import commands as cmds
from app.services import emergency as em
from app.services.access import get_device
from app.services.devices import is_fresh
from app.services.integration import emit
from app.services.notifications import active_user_ids, notify, staff_ids

router = APIRouter(tags=["emergency"])


def _publish(lab_id: int, alarm: Optional[dict] = None, alarm_was: bool = False,
             lab_code: str = "", state: Optional[dict] = None) -> None:
    """Staff pages refetch; every signed-in page gets the lab's message
    (`emergency_broadcast`); when the evacuation alarm was switched on or off,
    every page also gets the full-screen alarm (`hazard`) message."""
    try:
        from app.ws.manager import manager
        manager.publish({"type": "staff", "kind": "emergency", "lab_id": lab_id})
        if state is not None:
            manager.publish({"type": "emergency_broadcast", **state})
        if alarm is not None:
            manager.publish({"type": "hazard", "state": "raised", **alarm})
        elif alarm_was:
            manager.publish({"type": "hazard", "state": "cleared", "lab_id": lab_id,
                             "lab_code": lab_code, "metric": "evacuation", "label": "evacuation alarm"})
    except Exception:
        pass


def _alarm_view(lab: Lab, e) -> Optional[dict]:
    from app.services.environment import evacuation_alarm
    return evacuation_alarm(lab, e) if e.alarm else None


def require_session(admin: User = Depends(require_admin),
                    x_emergency_token: Optional[str] = Header(default=None)) -> User:
    """An admin who opened the Emergency tab with the password, recently."""
    if em.session_user(x_emergency_token) != admin.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            {"code": "EMERGENCY_LOCKED",
                             "message": "Enter the emergency password to use these controls."})
    return admin


def door_text(text: str) -> str:
    """What the LCD can show: plain printable ASCII, no quotes or backslashes."""
    text = text.replace('"', "'").replace("\\", "/")
    return re.sub(r"[^\x20-\x7E]", "", text).strip()[:96]


# -------------------------------------------------------------- session ---
class SessionRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@router.post("/emergency/session")
def open_session(req: SessionRequest, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    now = datetime.now(timezone.utc)
    if not em.password_configured(db):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "No emergency password is set: add EMERGENCY_PASSWORD to the .env file.")
    if em.recent_failures(db, admin.id, now) >= em.MAX_FAILURES:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many wrong passwords. Try again in 15 minutes.")
    if not em.check_password(db, req.password):
        db.add(AuditLog(actor_user_id=admin.id, action="EMERGENCY_PASSWORD_WRONG",
                        entity_type="emergency", entity_id=None, detail={}))
        db.commit()
        left = em.MAX_FAILURES - em.recent_failures(db, admin.id, now)
        # 403, not 401: a 401 would sign the admin out of the portal.
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Wrong emergency password. {max(left, 0)} tries left.")
    token, exp = em.issue_session(admin.id, now)
    db.add(AuditLog(actor_user_id=admin.id, action="EMERGENCY_OPENED", entity_type="emergency",
                    entity_id=None, detail={"until": exp.isoformat()}))
    db.commit()
    return {"token": token, "expires_at": exp}


# --------------------------------------------------------------- status ---
def _controller(db: Session, lab_id: int) -> Optional[Device]:
    return db.scalar(select(Device).where(Device.lab_id == lab_id,
                                          Device.device_type == DeviceType.MASTER_CONTROLLER))


@router.get("/emergency/status")
def status_all(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    now = datetime.now(timezone.utc)
    labs = []
    for lab in db.scalars(select(Lab).order_by(Lab.code)).all():
        e = em.state(db, lab.id, now)
        c = _controller(db, lab.id)
        comp = (c.component_state or {}) if c else {}
        applied = comp.get("emergency_version")
        by = db.get(User, e.updated_by_id) if e.updated_by_id else None
        labs.append({"lab_id": lab.id, "code": lab.code, "name": lab.name,
                     "has_door": c is not None, "controller_online": is_fresh(c, now) if c else None,
                     "door_closed": c.door_closed if c else None,
                     "lock_released": (comp.get("relay_locked") is False) if c else None,
                     # The controller confirms it is running this exact state.
                     "applied": c is not None and applied is not None and int(applied) >= e.version,
                     "updated_by": by.full_name if by else None, **em.out(e, now)})
    db.commit()
    pcs = db.scalars(select(Device).where(Device.device_type == DeviceType.PC)).all()
    return {"password_set": em.password_configured(db), "labs": labs,
            "pcs": {"total": len(pcs), "locked": sum(1 for d in pcs if d.mode == "LOCKED"),
                    "master": sum(1 for d in pcs if d.is_master_pc)}}


@router.get("/emergency/active")
def active_broadcasts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Every signed-in user (any role): the labs with an emergency message or
    alarm right now - what a page opened after it was set shows and reads aloud."""
    now = datetime.now(timezone.utc)
    out = []
    # Every lab's state in ONE query (kept referenced, so em.state()'s db.get() finds it without a query):
    # 11 separate lookups made this the slowest call of every page (78 ms in a page burst, 2026-10-19).
    _states = db.scalars(select(LabEmergency)).all()  # noqa: F841 - holds the identity map
    for lab in db.scalars(select(Lab).order_by(Lab.code)).all():
        e = em.state(db, lab.id, now)
        if e.message or e.alarm:
            out.append(em.broadcast(lab.code, e))
    db.commit()
    return out


# ---------------------------------------------------------------- labs ---
class LabAction(BaseModel):
    door: Optional[Literal["NORMAL", "UNLOCKED", "LOCKDOWN"]] = None
    # UNLOCKED only: minutes, or None = until "back to normal".
    minutes: Optional[int] = Field(default=None, ge=1, le=720)
    # None = leave the message as it is; "" = clear it.
    message: Optional[str] = Field(default=None, max_length=200)
    message_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    alarm: Optional[bool] = None
    # Read the message aloud (tablet and every portal screen). A new message
    # is read aloud unless this says false; "Clear sound" sends alarm=false,
    # speak=false.
    speak: Optional[bool] = None


def _announce(db: Session, lab: Lab, admin: User, what: str, e=None) -> None:
    notify(db, staff_ids(db), "EMERGENCY", f"{lab.code}: {what}",
           body=f"Set by {admin.full_name} from the Emergency tab.", link="/admin/emergency",
           severity="critical")
    if e is not None:
        # n8n (workflow 23) warns the people inside and checks the door applied it.
        emit(db, "emergency.set", lab_id=lab.id, user_id=admin.id, object_type="lab",
             object_id=lab.id, payload={"lab_code": lab.code, "version": e.version,
                                        "door_mode": e.door_mode, "alarm": e.alarm,
                                        "message": e.message, "active": em.active(e), "what": what})


@router.post("/emergency/labs/{lab_id}")
def act(lab_id: int, req: LabAction, db: Session = Depends(get_db),
        admin: User = Depends(require_session)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")
    now = datetime.now(timezone.utc)
    e = em.state(db, lab.id, now)
    alarm_was = bool(e.alarm)
    new_message = False
    did = []
    if req.door is not None:
        e.door_mode = req.door
        e.door_until = now + timedelta(minutes=req.minutes) if req.door == "UNLOCKED" and req.minutes else None
        did.append({"UNLOCKED": f"door kept OPEN {f'for {req.minutes} min' if req.minutes else 'until back to normal'}",
                    "LOCKDOWN": "LOCKDOWN - no entry", "NORMAL": "door back to normal"}[req.door])
    if req.message is not None:
        e.message = door_text(req.message)
        e.message_until = now + timedelta(minutes=req.message_minutes) if e.message and req.message_minutes else None
        did.append(f'message "{e.message}"' if e.message else "message cleared")
        if e.message:
            e.speak = req.speak if req.speak is not None else True
            new_message = True
    if req.alarm is not None:
        e.alarm = req.alarm
        did.append("evacuation alarm ON" if req.alarm else "alarm off")
    if req.speak is not None and req.message is None:
        e.speak = req.speak
        did.append("message read aloud" if req.speak else "message voice off")
    if not did:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nothing to do")
    e.version += 1
    e.updated_by_id, e.updated_at = admin.id, now
    db.add(AuditLog(actor_user_id=admin.id, action="EMERGENCY_ACTION", entity_type="lab",
                    entity_id=str(lab.id), detail={"lab": lab.code, **req.model_dump(),
                                                   "version": e.version}))
    _announce(db, lab, admin, "; ".join(did), e)
    if new_message:
        # Everyone, not only staff: the people in the lab are the ones it is for.
        others = [u for u in active_user_ids(db) if u not in set(staff_ids(db))]
        notify(db, others, "EMERGENCY", f"{lab.code}: message from the lab administrator",
               body=e.message, link="/", severity="critical")
    db.commit()
    _publish(lab.id, _alarm_view(lab, e), alarm_was, lab.code, em.broadcast(lab.code, e))
    return em.out(e, now)


@router.post("/emergency/labs/{lab_id}/normal")
def back_to_normal(lab_id: int, db: Session = Depends(get_db), admin: User = Depends(require_session)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")
    now = datetime.now(timezone.utc)
    e = em.state(db, lab.id, now)
    alarm_was = bool(e.alarm)
    e.door_mode, e.door_until, e.message, e.message_until, e.alarm = "NORMAL", None, "", None, False
    e.speak = True
    e.version += 1
    e.updated_by_id, e.updated_at = admin.id, now
    db.add(AuditLog(actor_user_id=admin.id, action="EMERGENCY_NORMAL", entity_type="lab",
                    entity_id=str(lab.id), detail={"lab": lab.code, "version": e.version}))
    _announce(db, lab, admin, "back to normal", e)
    db.commit()
    _publish(lab.id, None, alarm_was, lab.code, em.broadcast(lab.code, e))
    return em.out(e, now)


# ----------------------------------------------------------------- PCs ---
class PcAction(BaseModel):
    action: Literal["LOCK", "UNLOCK", "MESSAGE"]
    text: str = Field(default="", max_length=200)
    lab_id: Optional[int] = None
    # The lab engineer's master PC is left alone unless asked.
    include_master: bool = False


@router.post("/emergency/pcs")
def pcs(req: PcAction, db: Session = Depends(get_db), admin: User = Depends(require_session)):
    from app.api.routes.equipment import PC_MESSAGE
    q = select(Device).where(Device.device_type == DeviceType.PC)
    if req.lab_id is not None:
        q = q.where(Device.lab_id == req.lab_id)
    targets = [d for d in db.scalars(q).all() if req.include_master or not d.is_master_pc]
    if req.action == "MESSAGE" and not req.text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Write a message first.")
    now = datetime.now(timezone.utc)
    done = 0
    for d in targets:
        if req.action == "LOCK":
            d.mode = "LOCKED"
        elif req.action == "UNLOCK":
            if d.mode == "LOCKED":
                d.mode = "NORMAL"
        else:
            waiting = db.scalar(select(DeviceCommand).where(
                DeviceCommand.device_id == d.id, DeviceCommand.status == "PENDING"))
            if waiting is not None:
                waiting.status, waiting.completed_at = "CANCELLED", now
                waiting.message = "Replaced by an emergency message."
            db.add(DeviceCommand(device_id=d.id, command=PC_MESSAGE, args={"text": req.text.strip()},
                                 status="PENDING", requested_by_id=admin.id, created_at=now,
                                 expires_at=now + cmds.PICKUP_WINDOW))
        done += 1
    db.add(AuditLog(actor_user_id=admin.id, action=f"EMERGENCY_PCS_{req.action}", entity_type="pc",
                    entity_id=None, detail={**req.model_dump(), "count": done}))
    db.commit()
    return {"done": done}


# ------------------------------------------------------------ password ---
class PasswordChange(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


@router.put("/emergency/password")
def change_password(req: PasswordChange, db: Session = Depends(get_db),
                    admin: User = Depends(require_session)):
    em.set_password(db, req.new_password)
    db.add(AuditLog(actor_user_id=admin.id, action="EMERGENCY_PASSWORD_CHANGED",
                    entity_type="emergency", entity_id=None, detail={}))
    notify(db, staff_ids(db), "EMERGENCY", "Emergency password changed",
           body=f"Changed by {admin.full_name}.", link="/admin/emergency", severity="warning")
    db.commit()
    return {"ok": True}


# -------------------------------------------------------- the controller ---
@router.get("/access/emergency", tags=["devices"])
def for_controller(device_uid: str = Query(max_length=64), db: Session = Depends(get_db),
                   identity: str = Depends(require_device)):
    """Polled every second by the door controller. Read-mostly: it writes
    only when a timed state has just run out."""
    device_scope(identity, device_uid)
    d = get_device(db, device_uid)
    if d is None or d.lab_id is None:
        return {"version": 0, "door": "NORMAL", "remaining_s": 0, "message": "",
                "message_remaining_s": 0, "alarm": False, "speak": False}
    now = datetime.now(timezone.utc)
    e = em.state(db, d.lab_id, now)
    view = em.device_view(e, now)
    db.commit()
    return view


@router.get("/safety/triage")
def safety_triage(lab_id: Optional[int] = None, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Advisory safety triage (services/safety_triage.py): what to look at first, ranked, with evidence and ages.
    Read-only; never actuates anything."""
    from app.services.safety_triage import ADVISORY, triage
    return {"items": triage(db, lab_id=lab_id), "advisory": ADVISORY}


@router.get("/insights/proactive")
def proactive_insights(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Proactive suggestions (services/proactive.py): CONFIRMED findings and POSSIBLE anomalies with evidence and
    timestamps, de-duplicated; recomputed only when the data changed (at most once a minute), not per request."""
    from app.services import proactive
    return proactive.current(db)

```
