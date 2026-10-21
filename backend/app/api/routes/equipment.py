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

Admin master PC (System 1): from the portal staff can remove access (mode
LOCKED: the agent locks the PC and locks it again if someone unlocks it),
give it back (NORMAL), view the screen while they watch, and send a short
message. The agent polls for all of this; nothing pushes into a PC, and
every action is audited.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, get_current_user, require_admin, require_device, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import (Alert, AlertSeverity, Asset, AuditLog, Booking, BookingStatus,
                        Device, DeviceCommand, DeviceType, EquipmentSession, Lab,
                        PolicyViolation, Role, SensorReading, User)
from app.services import commands as cmds
from app.services import lan_presence


def _pc_changed(device_id: Optional[int] = None) -> None:
    """Live hint to staff pages: a lab PC changed - they refetch at once instead of on a 10 s timer."""
    try:
        from app.ws.manager import manager
        manager.publish({"type": "pc_state", "device_id": device_id})
    except Exception:
        pass


def _share_changed() -> None:
    try:
        from app.ws.manager import manager
        manager.publish({"type": "share_state"})
    except Exception:
        pass
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


def _agent_stopped_check(db: Session, d: Device, lab: Lab, prev: dict, now_detail: dict) -> None:
    """Lab PCs run the agent invisibly, re-started every minute by a scheduled task (2026-10-21), so a
    student who kills it gets it back - and staff are told: a new agent run (agent_started changed)
    on the SAME Windows boot (boot_time unchanged) means the agent was stopped, not the PC restarted."""
    a0, a1 = prev.get("agent_started"), now_detail.get("agent_started")
    b0, b1 = prev.get("boot_time"), now_detail.get("boot_time")
    if d.device_type != DeviceType.PC or not a0 or not a1 or a0 == a1 or b0 is None or b0 != b1:
        return
    who = prev.get("os_user") or "nobody"
    lan = lan_presence.get(d.device_uid)
    title = f"{d.name}: PC agent was stopped and restarted while {who} was signed in"
    detail = {"device": d.device_uid, "os_user": prev.get("os_user"), "previous_run": a0, "new_run": a1,
              "on_lan": lan["present"] if lan else None}
    db.add(Alert(lab_id=lab.id, device_id=d.id, severity=AlertSeverity.WARNING, title=title,
                 detail=str(detail)[:500]))
    db.add(AuditLog(actor_user_id=None, action="PC_AGENT_RESTARTED", entity_type="device",
                    entity_id=str(d.id), detail=detail))
    notify(db, staff_ids(db), "PC_AGENT_STOPPED", title,
           body="The agent is back (it restarts by itself within a minute). Someone may have ended it in Task Manager.",
           link="/admin/equipment", severity="warning")


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
    prev = d.component_state or {}
    was_fresh = is_fresh(d, now)
    d.last_seen_at, d.is_online = now, True
    d.firmware_version = req.firmware_version or d.firmware_version
    d.component_state = {"state": req.state, **req.detail}
    _agent_stopped_check(db, d, lab, prev, req.detail)
    # The agent's own clock vs this server's at arrival (2026-10-18 clock check): the difference
    # includes the network delay (milliseconds here), so only seconds matter.
    at = req.detail.get("agent_time")
    if isinstance(at, (int, float)) and not isinstance(at, bool):
        d.component_state["clock_offset_s"] = round(now.timestamp() - float(at), 2)

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
    if d.device_type == DeviceType.PC and (not was_fresh or prev.get("state") != req.state
                                            or prev.get("os_user") != req.detail.get("os_user")
                                            or prev.get("ips") != req.detail.get("ips")):
        _pc_changed(d.id)
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
            "lan": lan_presence.get(d.device_uid, now) if d.device_type == DeviceType.PC else None,
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
    # EXAM with an exam page = lockdown: the agent closes other programs and opens only this page in a
    # kiosk Chrome window (2026-10-21). Without it EXAM only reports prohibited programs (as before).
    exam_url: Optional[str] = Field(default=None, max_length=300, pattern=r"^https?://\S+$")


@router.put("/{device_id}/mode")
def set_mode(device_id: int, req: ModeRequest, db: Session = Depends(get_db),
             staff: User = Depends(require_staff)):
    d = _pc(db, device_id, staff)
    old = d.mode or "NORMAL"
    d.mode = req.mode
    action = ("PC_ACCESS_REMOVED" if req.mode == "LOCKED" else
              "PC_ACCESS_GIVEN" if old == "LOCKED" else "PC_MODE_SET")
    url = req.exam_url if req.mode == "EXAM" else None
    pc_control.exam_url_set(d.id, url)
    db.add(AuditLog(actor_user_id=staff.id, action=action, entity_type="device",
                    entity_id=str(d.id), detail={"from": old, "to": req.mode,
                                                 "device": d.device_uid, "exam_url": url}))
    db.commit()
    pc_control.signal(d.id)                        # the agent's long-poll wakes and applies it
    _pc_changed(d.id)
    return {"device_id": d.id, "mode": d.mode, "exam_url": url}


def _exam_url_for(db: Session, d: Device) -> Optional[str]:
    """The exam page while the PC is in EXAM (memory; after a portal restart: the last mode change)."""
    if (d.mode or "NORMAL") != "EXAM":
        return None
    u = pc_control.exam_url(d.id)
    if u is None:
        a = db.scalar(select(AuditLog).where(AuditLog.entity_type == "device", AuditLog.entity_id == str(d.id),
                                             AuditLog.action == "PC_MODE_SET").order_by(desc(AuditLog.id)).limit(1))
        u = (a.detail or {}).get("exam_url") if a else None
        if u:
            pc_control.exam_url_set(d.id, u)
    return u


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


# ---------------------------------------------- the admin who signs in IS the master (2026-10-21) ---
# Owner: "whenever an admin signs in, whatever the device, the place, the type of connection - he IS
# the master". The master is the admin, not a fixed PC: from any browser they share their screen and
# view / control every lab PC. If that browser runs on a lab PC with the agent, the agent proves which
# PC it is (HMAC of a one-time nonce with its key's hash - the portal keeps only that hash), and that
# PC becomes the master PC (protected from staff control; "Share from master PC"); the previous master
# PC is released. On a device without the agent (own laptop, phone, Wi-Fi) no lab PC is master.
# Docker Desktop hides the client address (every request arrives from 172.18.0.1), so the IP cannot
# identify the device - hence the agent's proof.
_master_nonces: dict[str, tuple[int, float]] = {}       # nonce -> (admin user id, expires monotonic)
MASTER_NONCE_S = 60.0


@router.get("/master/nonce")
def master_nonce(admin: User = Depends(require_admin)):
    import secrets
    now = time.monotonic()
    for k in [k for k, (_, exp) in _master_nonces.items() if exp < now]:
        _master_nonces.pop(k, None)
    n = secrets.token_hex(16)
    _master_nonces[n] = (admin.id, now + MASTER_NONCE_S)
    return {"nonce": n}


class MasterClaim(BaseModel):
    device_label: str = Field(max_length=120)
    device_uid: Optional[str] = Field(default=None, max_length=64)
    nonce: Optional[str] = Field(default=None, max_length=64)
    proof: Optional[str] = Field(default=None, max_length=128)


def _proof_ok(d: Device, nonce: str, proof: str) -> bool:
    import hashlib
    import hmac as _hmac
    from app.api.deps import hash_device_key
    hashes = [h for h in (d.key_hash, hash_device_key(settings.DEVICE_API_KEY) if settings.DEVICE_SHARED_KEY else None) if h]
    return any(_hmac.compare_digest(_hmac.new(h.encode(), nonce.encode(), hashlib.sha256).hexdigest(), proof)
               for h in hashes)


@router.post("/master/claim")
def master_claim(req: MasterClaim, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Called by the web app right after an admin signs in. The admin becomes the master; the lab PC
    they sit at becomes the master PC only with a valid agent proof."""
    pc: Optional[Device] = None
    if req.device_uid and req.nonce and req.proof:
        owner = _master_nonces.pop(req.nonce, None)
        if owner is None or owner[0] != admin.id or owner[1] < time.monotonic():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sign-in check expired - sign in again")
        d = get_device(db, req.device_uid)
        if d is None or d.device_type != DeviceType.PC or not _proof_ok(d, req.nonce, req.proof):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This PC could not prove which PC it is")
        pc = d
    changed = []
    for d in db.scalars(select(Device).where(Device.device_type == DeviceType.PC)).all():
        want = pc is not None and d.id == pc.id
        if bool(d.is_master_pc) != want:
            d.is_master_pc = want
            changed.append(d.id)
    db.add(AuditLog(actor_user_id=admin.id, action="MASTER_CLAIMED", entity_type="user",
                    entity_id=str(admin.id), detail={"admin": admin.full_name, "device": req.device_label,
                                                     "pc": pc.device_uid if pc else None}))
    db.commit()
    for i in changed:
        pc_control.signal(i)
    _pc_changed(None)
    return _master_out(db)


def _master_out(db: Session) -> dict:
    a = db.scalar(select(AuditLog).where(AuditLog.action == "MASTER_CLAIMED")
                  .order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(1))
    if a is None:
        return {"user_name": None, "device": None, "pc": None, "pc_name": None, "since": None}
    pc = get_device(db, a.detail.get("pc")) if a.detail.get("pc") else None
    return {"user_name": a.detail.get("admin"), "device": a.detail.get("device"),
            "pc": pc.device_uid if pc else None, "pc_name": pc.name if pc else None, "since": a.created_at}


@router.get("/master")
def current_master(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Who the master is now: the admin who signed in last, their device, and their lab PC (if any)."""
    return _master_out(db)


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
    pc_control.signal(d.id)
    _pc_changed(d.id)
    return {"device_id": d.id, "is_master_pc": d.is_master_pc}


# ------------------------------------------- admin master PC: agent side ---
class LanSeen(BaseModel):
    device_uid: str = Field(max_length=64)
    asset_tag: Optional[str] = Field(default=None, max_length=64)
    present: bool
    ip: Optional[str] = Field(default=None, max_length=45)
    mac: Optional[str] = Field(default=None, max_length=17)
    via: Literal["ping", "arp", "none"] = "none"


class LanPresenceReport(BaseModel):
    lab_id: str = Field(max_length=32)
    pcs: list[LanSeen] = Field(max_length=64)


@router.post("/pc/presence", tags=["devices"])
def report_lan_presence(req: LanPresenceReport, db: Session = Depends(get_db),
                        identity: str = Depends(require_device)):
    """tools/lan_presence (on the lab laptop): which lab PCs answer on the LAN right now, by MAC
    address - no agent needed on the PC. One PC's own key must not speak for the others, so only
    the lab's shared device key is accepted. A PC seen for the first time gets its device row
    (like the agent's first report); connects / disconnects are audited."""
    from app.api.deps import SHARED
    if identity != SHARED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "LAN presence needs the lab's shared device key")
    lab = get_lab_by_code(db, req.lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown lab")
    now = datetime.now(timezone.utc)
    changes = 0
    for pc in req.pcs:
        d = get_device(db, pc.device_uid)
        if d is None:
            if not pc.present:
                continue                            # never seen and absent: nothing to show yet
            d = Device(device_uid=pc.device_uid, name=pc.asset_tag or pc.device_uid,
                       device_type=DeviceType.PC, lab_id=lab.id)
            db.add(d)
            db.flush()
        if d.device_type != DeviceType.PC:
            continue
        if pc.asset_tag and d.asset_id is None:
            a = db.scalar(select(Asset).where(Asset.asset_tag == pc.asset_tag))
            if a is not None:
                d.asset_id = a.id
        changed = lan_presence.update(d.device_uid, pc.present, pc.ip, pc.mac, pc.via, now)
        if changed is not None:
            changes += 1
            db.add(AuditLog(actor_user_id=None, action="PC_LAN_CONNECTED" if changed else "PC_LAN_DISCONNECTED",
                            entity_type="device", entity_id=str(d.id),
                            detail={"device": d.device_uid, "ip": pc.ip, "mac": pc.mac, "via": pc.via}))
    db.commit()
    if changes:
        _pc_changed(None)
    return {"ok": True, "changes": changes}


@router.get("/pc/lan-targets", tags=["devices"])
def lan_targets(db: Session = Depends(get_db), identity: str = Depends(require_device)):
    """For tools/lan_presence: every lab PC whose agent has reported its MAC address(es), so a new PC
    is checked on the LAN without anyone typing its MAC (2026-10-21). Shared lab key only."""
    from app.api.deps import SHARED
    if identity != SHARED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "LAN targets need the lab's shared device key")
    out = []
    for d in db.scalars(select(Device).where(Device.device_type == DeviceType.PC)).all():
        macs = [m for m in (d.component_state or {}).get("macs") or [] if isinstance(m, str) and len(m) == 17]
        if macs:
            a = db.get(Asset, d.asset_id) if d.asset_id else None
            out.append({"device_uid": d.device_uid, "asset_tag": a.asset_tag if a else d.name,
                        "macs": macs, "ips": (d.component_state or {}).get("ips") or []})
    return out


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
            who = db.get(User, c.requested_by_id) if c.requested_by_id else None
            message = {"id": c.id, "text": (c.args or {}).get("text", ""), "from": who.full_name if who else None}
        cmds.publish_later(db, c)
        db.commit()
        cmds.flush_published(db)
    b = pc_control.broadcast_state()
    capture = bool(b["active"] and ((b["source"] == "master_pc" and d.is_master_pc)
                                    or (b["source"] == "pc" and b.get("device_id") == d.id)))
    return {"mode": d.mode or "NORMAL", "mirror": pc_control.is_watched(d.id),
            "exam": {"url": u, "lockdown": True} if (u := _exam_url_for(db, d)) else None,
            "message": message, "action": _hand_over_action(db, d),
            # Presenting: students' PCs open the portal's /share page; the master PC uploads frames
            # when the admin chose it as the source.
            "broadcast": {"active": b["active"] and (b["targets"] is None or d.id in b["targets"]),
                          "by": b["by"], "title": b["title"]}
                         if not d.is_master_pc and not capture and b.get("audience", "all") == "all" else None,
            "mirror_opts": pc_control.view_opts(d.id) if pc_control.is_watched(d.id) else None,
            "broadcast_capture": capture}


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
class ViewOpts(BaseModel):
    monitor: int = Field(default=0, ge=0, le=7)          # 0 = all screens side by side, 1.. = one monitor
    quality: int = Field(default=60, ge=20, le=90)       # JPEG quality
    fps: float = Field(default=2.0, ge=0.5, le=5.0)


@router.post("/{device_id}/screen/start")
def screen_start(device_id: int, opts: Optional[ViewOpts] = None, db: Session = Depends(get_db),
                 staff: User = Depends(require_staff)):
    d = _pc(db, device_id, staff)
    pc_control.touch_viewer(d.id, (opts or ViewOpts()).model_dump())
    db.add(AuditLog(actor_user_id=staff.id, action="PC_SCREEN_VIEWED", entity_type="device",
                    entity_id=str(d.id), detail={"device": d.device_uid, **(opts or ViewOpts()).model_dump()}))
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
    db.add(AuditLog(actor_user_id=staff.id, action="PC_SCREEN_VIEW_ENDED", entity_type="device",
                    entity_id=str(d.id), detail={"device": d.device_uid}))
    db.commit()
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
        DeviceCommand.device_id == d.id, DeviceCommand.command == PC_MESSAGE,
        DeviceCommand.status == "PENDING"))
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
    pc_control.signal(d.id)
    return cmds.out(c)


# ------------------------------------------------ PC actions (allowlisted) ---
# Staff ask; the agent on the PC carries the action out and reports the real result.
# QUEUED (PENDING) -> EXECUTING (SENT) -> COMPLETED (DONE) | FAILED ; not fetched in time -> EXPIRED
# (= the PC was unreachable). App names are KEYS: the agent maps each key to a program it has
# configured itself, so the portal can never start an arbitrary program.
PC_ACTION = "PC_ACTION"
PC_APPS = ("proteus", "matlab", "arduino_ide", "vscode", "browser", "notepad", "tia_portal", "polyscope_sim")
PC_ACTIONS = {"open_app": "staff", "close_app": "staff", "lock": "staff",
              "logoff": "admin", "restart": "admin", "shutdown": "admin"}
_DISRUPTIVE = ("close_app", "logoff", "restart", "shutdown")    # may lose unsaved work: confirmation


class PcActionRequest(BaseModel):
    action: str = Field(max_length=16)
    app: Optional[str] = Field(default=None, max_length=32)
    confirmed: bool = False


def _hand_over_action(db: Session, d: Device) -> Optional[dict]:
    now = datetime.now(timezone.utc)
    c = db.scalar(select(DeviceCommand).where(
        DeviceCommand.device_id == d.id, DeviceCommand.command == PC_ACTION,
        DeviceCommand.status == "PENDING").order_by(DeviceCommand.created_at))
    if c is None:
        return None
    if now > _utc(c.expires_at):
        c.status, c.completed_at = "EXPIRED", now
        c.message = "Unreachable: the PC agent did not take the action in time."
        db.commit()
        return None
    c.status, c.sent_at, c.message = "SENT", now, "Executing on the PC"
    db.commit()
    return {"id": c.id, **(c.args or {})}


@router.post("/{device_id}/action", status_code=status.HTTP_201_CREATED)
def pc_action(device_id: int, req: PcActionRequest, db: Session = Depends(get_db),
              staff: User = Depends(require_staff)):
    d = _pc(db, device_id, staff)
    need = PC_ACTIONS.get(req.action)
    if need is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown action {req.action!r}")
    if need == "admin" and staff.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an administrator can log off, restart or shut down a PC.")
    if req.action in ("open_app", "close_app") and req.app not in PC_APPS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That application is not on the approved list.")
    if req.action in _DISRUPTIVE and not req.confirmed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "This can close the user's programs and lose unsaved work - confirm it first.")
    now = datetime.now(timezone.utc)
    busy = db.scalar(select(DeviceCommand).where(
        DeviceCommand.device_id == d.id, DeviceCommand.command == PC_ACTION,
        DeviceCommand.status.in_(("PENDING", "SENT"))))
    if busy is not None and now <= _utc(busy.expires_at):
        raise HTTPException(status.HTTP_409_CONFLICT, "Another action for this PC is still in progress.")
    if busy is not None:
        busy.status, busy.completed_at = "EXPIRED", now
        busy.message = "Unreachable: no result from the PC agent."
    args = {"action": req.action, **({"app": req.app} if req.app else {})}
    c = DeviceCommand(device_id=d.id, command=PC_ACTION, args=args, status="PENDING",
                      requested_by_id=staff.id, created_at=now, expires_at=now + timedelta(seconds=60),
                      message="Queued - waiting for the PC agent")
    db.add(c)
    db.flush()
    db.add(AuditLog(actor_user_id=staff.id, action="PC_ACTION_REQUESTED", entity_type="device",
                    entity_id=str(d.id), detail={"device": d.device_uid, "command_id": c.id, **args}))
    db.commit()
    pc_control.signal(d.id)
    return _action_out(c)


def _action_out(c: DeviceCommand) -> dict:
    label = {"PENDING": "QUEUED", "SENT": "EXECUTING", "DONE": "COMPLETED"}.get(c.status, c.status)
    return {"id": c.id, "status": label, "message": c.message, **(c.args or {}),
            "created_at": c.created_at, "completed_at": c.completed_at}


@router.get("/{device_id}/actions")
def pc_actions(device_id: int, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    d = _pc(db, device_id, staff)
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(DeviceCommand).where(DeviceCommand.device_id == d.id, DeviceCommand.command == PC_ACTION)
                      .order_by(DeviceCommand.created_at.desc()).limit(10)).all()
    for c in rows:                              # executing but never answered: timed out
        if c.status in ("PENDING", "SENT") and now > _utc(c.expires_at):
            c.status, c.completed_at = "EXPIRED", now
            c.message = "Timed out: no result from the PC agent." if c.sent_at else "Unreachable: the PC agent did not take it."
    db.commit()
    return {"apps": list(PC_APPS), "actions": [_action_out(c) for c in rows]}


class PcActionResult(BaseModel):
    device_uid: str = Field(max_length=64)
    id: int
    ok: bool
    message: str = Field(default="", max_length=200)


@router.post("/pc/action-result", tags=["devices"])
def pc_action_result(req: PcActionResult, db: Session = Depends(get_db), identity: str = Depends(require_device)):
    device_scope(identity, req.device_uid)
    d = get_device(db, req.device_uid)
    c = db.get(DeviceCommand, req.id)
    if d is None or c is None or c.device_id != d.id or c.command != PC_ACTION:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown action")
    if c.status != "SENT":
        return _action_out(c)
    now = datetime.now(timezone.utc)
    c.status, c.completed_at = ("DONE" if req.ok else "FAILED"), now
    c.message = (req.message or ("Done" if req.ok else "Failed on the PC"))[:200]
    db.add(AuditLog(actor_user_id=c.requested_by_id, action="PC_ACTION_RESULT", entity_type="device",
                    entity_id=str(d.id), detail={"device": d.device_uid, "command_id": c.id, "ok": req.ok,
                                                 "message": c.message, **(c.args or {})}))
    db.commit()
    _pc_changed(d.id)
    return _action_out(c)


# ------------------------------------------- admin screen -> students (share) ---
class BroadcastStart(BaseModel):
    source: str = Field(pattern=r"^(browser|master_pc)$")
    title: str = Field(default="", max_length=80)
    targets: Optional[list[int]] = Field(default=None, max_length=200)   # None = every lab PC


@router.post("/broadcast/start")
def broadcast_start(req: BroadcastStart, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Admin shares their screen with the students' PCs (and anyone signed in on /share)."""
    if req.source == "master_pc" and db.scalar(select(Device.id).where(
            Device.device_type == DeviceType.PC, Device.is_master_pc.is_(True))) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No master PC is set - mark the admin PC as master PC first.")
    if req.targets is not None:
        ok = set(db.scalars(select(Device.id).where(Device.id.in_(req.targets), Device.device_type == DeviceType.PC)).all())
        if not req.targets or ok != set(req.targets):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Targets must be registered lab PCs.")
    st = pc_control.broadcast_start(admin.full_name, admin.id, req.source, req.title, req.targets)
    db.add(AuditLog(actor_user_id=admin.id, action="PC_BROADCAST_STARTED", entity_type="broadcast",
                    entity_id="screen", detail={"source": req.source, "title": req.title, "targets": req.targets or "all"}))
    db.commit()
    _share_changed()
    return st


@router.post("/broadcast/stop")
def broadcast_stop(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    was = pc_control.broadcast_state()["active"]
    st = pc_control.broadcast_stop()
    if was:                                       # idempotent: a second Stop is not audited again
        db.add(AuditLog(actor_user_id=admin.id, action="PC_BROADCAST_STOPPED", entity_type="broadcast", entity_id="screen"))
        db.commit()
    _share_changed()
    return st


@router.get("/broadcast/status")
def broadcast_status(viewer: User = Depends(get_current_user)):
    st = pc_control.broadcast_state()
    if st.get("audience") == "staff" and viewer.role not in (Role.ADMIN, Role.LAB_STAFF) and viewer.id != st.get("by_id"):
        return {**st, "active": False, "by": None, "title": ""}  # private to staff: others see nothing
    return st


# ---------------------------------- a student asks to share; an admin accepts (2026-10-21) ---
class ShareAsk(BaseModel):
    device_uid: Optional[str] = Field(default=None, max_length=64)
    nonce: Optional[str] = Field(default=None, max_length=64)
    proof: Optional[str] = Field(default=None, max_length=128)


def _admin_ids(db: Session) -> list[int]:
    return list(db.scalars(select(User.id).where(User.role == Role.ADMIN, User.is_active.is_(True))).all())


@router.get("/share-requests/nonce")
def share_nonce(user: User = Depends(get_current_user)):
    """One-time nonce for the PC proof (as at the admin's sign-in): which lab PC the student sits at."""
    import secrets
    now = time.monotonic()
    n = secrets.token_hex(16)
    _master_nonces[n] = (user.id, now + MASTER_NONCE_S)
    return {"nonce": n}


@router.post("/share-requests")
def share_ask(req: ShareAsk, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A student asks to share their lab PC's screen. Only a PC whose agent proves itself can present
    (its agent captures - the lab PCs' browsers run on plain http, where a page may not capture)."""
    if not (req.device_uid and req.nonce and req.proof):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Sharing works from a lab PC with the Smart Lab agent - this device could not be recognised.")
    owner = _master_nonces.pop(req.nonce, None)
    if owner is None or owner[0] != user.id or owner[1] < time.monotonic():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The check expired - try again")
    d = get_device(db, req.device_uid)
    if d is None or d.device_type != DeviceType.PC or not _proof_ok(d, req.nonce, req.proof):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This PC could not prove which PC it is")
    r = pc_control.share_request_add(user.id, user.full_name, d.id, d.name)
    db.add(AuditLog(actor_user_id=user.id, action="SHARE_REQUESTED", entity_type="device", entity_id=str(d.id),
                    detail={"device": d.device_uid, "request": r["id"]}))
    notify(db, _admin_ids(db), "SHARE_REQUEST", f"{user.full_name} asks to share {d.name}'s screen",
           body="Accept or reject on Lab equipment - Robots & PCs.", link="/admin/equipment?tab=noncons",
           severity="warning")
    db.commit()
    _share_changed()
    return r


@router.get("/share-requests/mine")
def share_mine(user: User = Depends(get_current_user)):
    r = pc_control.share_request_of(user.id)
    st = pc_control.broadcast_state()
    return {"request": r, "presenting": bool(st["active"] and st.get("by_id") == user.id and st["source"] == "pc")}


@router.get("/share-requests")
def share_list(_: User = Depends(require_admin)):
    return pc_control.share_requests()


class ShareDecision(BaseModel):
    accept: bool
    audience: Literal["all", "staff"] = "all"          # everyone (all lab PCs + /share) or only staff


@router.post("/share-requests/{req_id}")
def share_decide(req_id: int, body: ShareDecision, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    r = pc_control.share_request_set(req_id, "ACCEPTED" if body.accept else "REJECTED")
    if r is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This request was already answered or has expired")
    st = None
    if body.accept:
        st = pc_control.broadcast_start(r["name"], r["user_id"], "pc", f"{r['pc_name']}", None,
                                        device_id=r["device_id"], audience=body.audience)
        pc_control.signal(r["device_id"])                         # the student's agent starts capturing now
    db.add(AuditLog(actor_user_id=admin.id, action="SHARE_ACCEPTED" if body.accept else "SHARE_REJECTED",
                    entity_type="device", entity_id=str(r["device_id"]),
                    detail={"student": r["name"], "request": req_id, "audience": body.audience}))
    notify(db, [r["user_id"]], "SHARE_ANSWER",
           "Your screen is being shared" if body.accept else "Your share request was declined",
           link="/share", severity="info")
    db.commit()
    _share_changed()
    return {"request": r, "broadcast": st}


@router.post("/share-requests/mine/stop")
def share_stop_mine(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The presenting student ends their own share."""
    st = pc_control.broadcast_state()
    if not (st["active"] and st.get("by_id") == user.id and st["source"] == "pc"):
        return st
    st = pc_control.broadcast_stop()
    db.add(AuditLog(actor_user_id=user.id, action="PC_BROADCAST_STOPPED", entity_type="broadcast", entity_id="screen"))
    db.commit()
    _share_changed()
    return st


@router.post("/broadcast/frame", status_code=status.HTTP_204_NO_CONTENT)
async def broadcast_frame_from_browser(request: Request, admin: User = Depends(require_admin)):
    """A frame captured in the presenting admin's browser."""
    st = pc_control.broadcast_state()
    if not st["active"] or st["source"] != "browser" or st["by_id"] != admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You are not presenting from this browser")
    body = await request.body()
    if not body.startswith(b"\xff\xd8") or len(body) > pc_control.MAX_FRAME_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Expected a JPEG under 1.5 MB")
    pc_control.broadcast_put(body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/pc/broadcast-frame", tags=["devices"], status_code=status.HTTP_204_NO_CONTENT)
async def broadcast_frame_from_master(request: Request, device_uid: str = Query(max_length=64),
                                      db: Session = Depends(get_db), identity: str = Depends(require_device)):
    """A frame from the PC that presents: the admin's master PC, or a student's PC an admin accepted."""
    device_scope(identity, device_uid)
    d = get_device(db, device_uid)
    st = pc_control.broadcast_state()
    ok = d is not None and st["active"] and ((st["source"] == "master_pc" and d.is_master_pc)
                                             or (st["source"] == "pc" and st.get("device_id") == d.id))
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, "Not presenting from this PC")
    body = await request.body()
    if not body.startswith(b"\xff\xd8") or len(body) > pc_control.MAX_FRAME_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Expected a JPEG under 1.5 MB")
    pc_control.broadcast_put(body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/broadcast/frame.jpg")
def broadcast_frame(viewer: User = Depends(get_current_user)):
    """Latest presented frame for anyone signed in (students watch on /share); 204 = none yet,
    410 = sharing has ENDED (the viewer clears the picture at once instead of showing the last frame
    until its next status check - "stop does not stop immediately", 2026-10-21)."""
    st = pc_control.broadcast_state()
    if st.get("audience") == "staff" and viewer.role not in (Role.ADMIN, Role.LAB_STAFF) and viewer.id != st.get("by_id"):
        return Response(status_code=status.HTTP_410_GONE)          # not shown to the other students
    jpeg = pc_control.broadcast_frame()
    if jpeg is None:
        if not pc_control.broadcast_state()["active"]:
            return Response(status_code=status.HTTP_410_GONE)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(content=jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ------------------------------------------------ agent long-poll (2026-10-17) ---
_uid_ids: dict[str, int] = {}


def _pc_id_for(device_uid: str) -> Optional[int]:
    if device_uid in _uid_ids:
        return _uid_ids[device_uid]
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        d = get_device(db, device_uid)
        if d is None or d.device_type != DeviceType.PC:
            return None
        _uid_ids[device_uid] = d.id
        return d.id
    finally:
        db.close()


@router.get("/pc/wait", tags=["devices"])
async def pc_wait(device_uid: str = Query(max_length=64), timeout: float = Query(20.0, ge=0.5, le=30.0),
                  identity: str = Depends(require_device)):
    """The idle PC agent waits here instead of polling every second: answers {"changed": true} as soon
    as something for this PC changes (a viewer opens or changes monitor/quality, a share starts or stops,
    an action / message / mode / master change), else {"changed": false} after `timeout`. Memory only -
    no database work and no worker thread while waiting; the agent then calls /pc/poll as before."""
    import asyncio
    from fastapi.concurrency import run_in_threadpool
    device_scope(identity, device_uid)
    did = await run_in_threadpool(_pc_id_for, device_uid)
    if did is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown PC")
    start = pc_control.version(did)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pc_control.version(did) != start:
            return {"changed": True}
        await asyncio.sleep(0.05)
    return {"changed": False}
