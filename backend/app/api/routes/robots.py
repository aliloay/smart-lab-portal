"""
Robots: read-only monitoring (tools/robot_monitor/robot_collector.py feeds it).

Device endpoints (X-Device-Key):
    POST /robots/telemetry   latest state, ~5 a second: joints, velocities,
                             TCP, motion state, telemetry age and rate
    POST /robots/events      motion transitions (MOVEMENT_STARTED/STOPPED,
                             JOINT_MOVED, TELEMETRY_STALE/RESTORED)

Portal endpoints:
    GET  /robots             everyone: availability summary; staff: + joints
    GET  /robots/{id}        staff: full state, home calibration, recent events
    GET  /robots/{id}/events staff
    POST /robots/{id}/home   admin: take HOME from live telemetry (versioned)

Nothing here can command a robot: there is no endpoint that sends anything
to a controller. Context stored with an event (booking in force, who was
inside per the door, what the camera saw at the robot's box) is evidence for
a likely actor - never a statement of who moved it.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, get_current_user, require_admin, require_device, require_staff
from app.db.session import get_db
from app.models import (AuditLog, Booking, BookingStatus, Device, DeviceType, RobotEvent,
                        RobotHomeCalibration, User)
from app.services import robot_fusion
from app.services.access import get_device, get_lab_by_code

router = APIRouter(prefix="/robots", tags=["robots"])

STALE_S = 3.0                      # no telemetry for this long = TELEMETRY_STALE (portal side)
OFFLINE_S = 30.0
_last_push: dict[int, float] = {}  # device id -> last robot_state push (throttle)
PUSH_EVERY_S = 0.2


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _publish(msg: dict) -> None:
    try:
        from app.ws.manager import manager
        manager.publish(msg)
    except Exception:
        pass


def _home(db: Session, device_id: int) -> Optional[RobotHomeCalibration]:
    return db.scalar(select(RobotHomeCalibration).where(RobotHomeCalibration.device_id == device_id)
                     .order_by(desc(RobotHomeCalibration.version)).limit(1))


def home_state(q: Optional[list], cal: Optional[RobotHomeCalibration]) -> dict:
    """HOME / NEAR_HOME / NOT_HOME from per-joint deviation; UNKNOWN without data or calibration."""
    if not q or cal is None or len(q) != len(cal.home_q):
        return {"home": "UNKNOWN", "deviation_deg": None, "calibration_version": cal.version if cal else None}
    dev = [math.degrees(abs(a - b)) for a, b in zip(q, cal.home_q)]
    worst = max(dev)
    tol = cal.tolerance_deg or 1.0
    st = "HOME" if worst <= tol else "NEAR_HOME" if worst <= 5 * tol else "NOT_HOME"
    return {"home": st, "deviation_deg": [round(d, 2) for d in dev], "worst_joint": f"J{dev.index(worst) + 1}",
            "worst_deg": round(worst, 2), "tolerance_deg": tol, "calibration_version": cal.version}


def _context(db: Session, d: Device, now: datetime) -> tuple[Optional[int], dict]:
    """What was true at this moment, as evidence (not a conclusion)."""
    from app.api.routes.security import occupants
    booking = db.scalar(select(Booking).where(
        Booking.lab_id == d.lab_id, Booking.status == BookingStatus.CONFIRMED,
        Booking.start_time <= now, Booking.end_time > now))
    inside = occupants(db, d.lab_id)
    cam = db.scalar(select(Device).where(Device.lab_id == d.lab_id,
                                         Device.device_type == DeviceType.SECURITY_CAMERA).limit(1))
    zone, named, cam_state = None, [], "none"
    if cam is not None:
        from app.services.devices import is_fresh
        cam_state = "online" if is_fresh(cam, now) else "offline"
    # Only a camera that is reporting now is evidence - an old report is not.
    if cam is not None and cam_state == "online" and cam.component_state:
        cs = cam.component_state
        model = ((d.component_state or {}).get("model") or "").lower()
        for z in cs.get("zones", []):
            if model and (model in z.get("name", "").lower() or z.get("name", "").lower() in model):
                zone = {"name": z.get("name"), "status": z.get("status")}     # IN_USE = a person at the robot's box
        named = [{"label": n.get("label"), "name": n.get("name"), "state": n.get("identity_state"),
                  "confidence": n.get("confidence")} for n in cs.get("named", [])]
    holder = db.get(User, booking.user_id) if booking else None
    return (booking.id if booking else None), {
        "booking": {"id": booking.id, "holder": holder.full_name if holder else None} if booking else None,
        "inside_per_door": [o["name"] for o in inside],
        "camera": cam_state, "camera_robot_box": zone, "camera_named": named,
    }


def _severity(kind: str, source: str, booking_id: Optional[int], ctx: dict) -> str:
    """How much attention a robot event needs (configurable later; documented in docs/ROBOTS.md)."""
    if source == "SIMULATION":
        return "INFO"
    if kind == "TELEMETRY_STALE":
        return "WARNING"
    if kind != "MOVEMENT_STARTED":
        return "INFO"
    if booking_id:
        return "NOTICE"                                    # expected: a booking is in force
    if not ctx.get("inside_per_door"):
        return "CRITICAL"                                  # moving, no booking, nobody entered
    return "WARNING"                                       # moving, no booking


def _camera_for(db: Session, d: Device, now: datetime) -> tuple[bool, Optional[dict]]:
    """(camera reporting now, the camera's visual result for this robot's box)."""
    from app.services.devices import is_fresh
    cam = db.scalar(select(Device).where(Device.lab_id == d.lab_id,
                                         Device.device_type == DeviceType.SECURITY_CAMERA).limit(1))
    if cam is None or not is_fresh(cam, now):
        return False, None
    model = ((d.component_state or {}).get("model") or "").lower()
    for z in (cam.component_state or {}).get("zones", []):
        name = (z.get("name") or "").lower()
        if model and (model in name or name in model):
            return True, z.get("visual")
    return True, None


def update_fusion(db: Session, d: Device, now: datetime) -> dict:
    """Recompute telemetry + camera fusion for one robot; record transitions as
    events (abnormal ones only once they have lasted DISAGREE_HOLD_S)."""
    cs = dict(d.component_state or {})
    online, visual = _camera_for(db, d, now)
    t_state = _effective_state(d, now)
    view = robot_fusion.camera_view(visual, online, now.timestamp())
    new = robot_fusion.fuse(t_state, cs.get("source"), view)
    state, since, kind = robot_fusion.transition(cs.get("fusion"), cs.get("fusion_since"), new, now.timestamp())
    reported = cs.get("fusion_reported", False) if state == cs.get("fusion") else False
    late = robot_fusion.held(state, since, reported, now.timestamp())
    seen = _utc(d.last_seen_at)
    ev = robot_fusion.evidence(t_state, cs.get("source"), view, visual, online,
                               (now - seen).total_seconds() if seen else None)
    for k in (kind, late):
        if k:
            booking_id, ctx = _context(db, d, now)
            sev = "WARNING" if k in ("VISUAL_TELEMETRY_DISAGREEMENT", "VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE") else "INFO"
            db.add(RobotEvent(device_id=d.id, lab_id=d.lab_id, kind=k[:32], source="FUSION", occurred_at=now,
                              detail={"fusion": state, "evidence": ev}, booking_id=booking_id, context=ctx,
                              severity=sev))
            if k == late:
                reported = True
    cs.update(fusion=state, fusion_since=since, fusion_reported=reported, fusion_evidence=ev, camera_view=view)
    d.component_state = cs
    return cs


# ------------------------------------------------------------- device side ---
class Telemetry(BaseModel):
    device_uid: str = Field(max_length=64)
    lab_id: str = Field(max_length=32)
    model: str = Field(max_length=32)
    name: str = Field(default="", max_length=64)
    source: str = Field(max_length=16)                     # RTDE / SIMULATION / ...
    state: str = Field(max_length=24)                      # MOVING / STATIONARY / TELEMETRY_STALE / UNKNOWN
    q: Optional[list[float]] = Field(default=None, max_length=12)
    qd: Optional[list[float]] = Field(default=None, max_length=12)
    tcp: Optional[list[float]] = Field(default=None, max_length=6)
    joints_moving: list[bool] = Field(default_factory=list, max_length=12)
    telemetry_age_ms: Optional[float] = None
    rate_hz: float = 0.0
    sent_at: Optional[float] = None                        # collector clock (s)
    extra: dict[str, Any] = Field(default_factory=dict)


@router.post("/telemetry", tags=["devices"])
def telemetry(req: Telemetry, db: Session = Depends(get_db), identity: str = Depends(require_device)):
    device_scope(identity, req.device_uid)
    # NaN / inf cannot be stored (JSONB) and are not joint angles: refuse, never store.
    if any(v is not None and not all(math.isfinite(x) for x in v) for v in (req.q, req.qd, req.tcp)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Telemetry values must be finite numbers")
    lab = get_lab_by_code(db, req.lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown lab")
    now = datetime.now(timezone.utc)
    d = get_device(db, req.device_uid)
    if d is None:
        d = Device(device_uid=req.device_uid, name=req.name or req.device_uid, device_type=DeviceType.ROBOT,
                   lab_id=lab.id)
        db.add(d)
        db.flush()
    prev = d.component_state or {}
    cal = _home(db, d.id)
    h = home_state(req.q, cal)
    extra = {k: v for k, v in list(req.extra.items())[:12] if isinstance(v, (int, float, str, bool, type(None)))}
    d.last_seen_at, d.is_online = now, True
    d.component_state = {"model": req.model, "source": req.source, "state": req.state, "q": req.q, "qd": req.qd,
                         "tcp": req.tcp, "joints_moving": req.joints_moving, "telemetry_age_ms": req.telemetry_age_ms,
                         "rate_hz": req.rate_hz, "extra": extra, **h, "received_at": now.isoformat(),
                         "transport_ms": round((time.time() - req.sent_at) * 1000, 1) if req.sent_at else None}
    # Home left / returned: the portal's own events (it holds the calibration).
    was, is_ = prev.get("home"), h["home"]
    if was in ("HOME", "NEAR_HOME", "NOT_HOME") and is_ in ("HOME", "NOT_HOME") and was != is_ \
            and req.state != "MOVING":
        kind = "HOME_RETURNED" if is_ == "HOME" else "HOME_LEFT"
        booking_id, ctx = _context(db, d, now)
        db.add(RobotEvent(device_id=d.id, lab_id=d.lab_id, kind=kind, source="PORTAL", occurred_at=now,
                          detail={k: h.get(k) for k in ("worst_joint", "worst_deg", "calibration_version")},
                          booking_id=booking_id, context=ctx, severity="INFO",
                          provenance="DEMO_DATA" if req.source == "SIMULATION" else None))
    update_fusion(db, d, now)
    db.commit()
    summary = {"state": req.state, "home": is_, "source": req.source}
    if {k: prev.get(k) for k in summary} != summary:
        _publish({"type": "robot_status", "device_id": d.id, "lab_id": d.lab_id, **summary})
    t = time.monotonic()
    if t - _last_push.get(d.id, 0.0) >= PUSH_EVERY_S:
        _last_push[d.id] = t
        _publish({"type": "robot_state", "device_id": d.id, "lab_id": d.lab_id, "state": req.state,
                  "q": req.q, "qd": req.qd, "joints_moving": req.joints_moving, "home": is_,
                  "source": req.source, "telemetry_age_ms": req.telemetry_age_ms})
    return {"ok": True}


class EventIn(BaseModel):
    kind: str = Field(max_length=32, pattern=r"^[A-Z_]{3,32}$")
    t: float
    joint: Optional[int] = Field(default=None, ge=0, le=11)
    detail: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="RTDE", max_length=16)


class EventsIn(BaseModel):
    device_uid: str = Field(max_length=64)
    events: list[EventIn] = Field(max_length=100)


@router.post("/events", tags=["devices"])
def events(req: EventsIn, db: Session = Depends(get_db), identity: str = Depends(require_device)):
    device_scope(identity, req.device_uid)
    d = get_device(db, req.device_uid)
    if d is None or d.device_type != DeviceType.ROBOT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Send telemetry first")
    now = datetime.now(timezone.utc)
    stored = []
    for e in req.events:
        at = datetime.fromtimestamp(e.t, tz=timezone.utc)
        if abs((at - now).total_seconds()) > 3600:          # an unsynchronised clock: keep arrival time
            at = now
        booking_id, ctx = _context(db, d, at)
        sev = _severity(e.kind, e.source, booking_id, ctx)
        ev = RobotEvent(device_id=d.id, lab_id=d.lab_id, kind=e.kind, joint=e.joint,
                        detail={k: v for k, v in list(e.detail.items())[:20]}, source=e.source,
                        occurred_at=at, booking_id=booking_id, context=ctx, severity=sev,
                        provenance="DEMO_DATA" if e.source == "SIMULATION" else None)
        db.add(ev)
        stored.append((e.kind, sev))
    db.commit()
    for kind, sev in stored:
        if sev in ("WARNING", "CRITICAL"):
            _publish({"type": "staff", "kind": "robot_event", "device_id": d.id, "lab_id": d.lab_id,
                      "event": kind, "severity": sev})
    return {"stored": len(stored)}


# ------------------------------------------------------------- portal side ---
def _effective_state(d: Device, now: datetime) -> str:
    cs = d.component_state or {}
    seen = _utc(d.last_seen_at)
    if seen is None:
        return "UNKNOWN"
    age = (now - seen).total_seconds()
    if age > OFFLINE_S:
        return "OFFLINE"
    if age > STALE_S:
        return "TELEMETRY_STALE"                            # never "stationary" because data stopped
    return cs.get("state") or "UNKNOWN"


def _summary(d: Device, now: datetime, staff: bool) -> dict:
    cs = d.component_state or {}
    seen = _utc(d.last_seen_at)
    out = {"device_id": d.id, "device_uid": d.device_uid, "name": d.name, "lab_id": d.lab_id,
           "model": cs.get("model"), "source": cs.get("source"), "state": _effective_state(d, now),
           "home": cs.get("home", "UNKNOWN"), "last_seen_at": seen,
           "demo": cs.get("source") == "SIMULATION"}
    if staff:
        out.update({k: cs.get(k) for k in ("q", "qd", "tcp", "joints_moving", "telemetry_age_ms", "rate_hz",
                                           "extra", "deviation_deg", "worst_joint", "worst_deg",
                                           "calibration_version", "transport_ms", "fusion", "fusion_evidence",
                                           "camera_view")})
        out["telemetry_age_s"] = round((now - seen).total_seconds(), 1) if seen else None
    return out


@router.get("")
def robots(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    staff = user.role.value in ("ADMIN", "LAB_STAFF")
    return [_summary(d, now, staff) for d in db.scalars(select(Device).where(
        Device.device_type == DeviceType.ROBOT).order_by(Device.lab_id, Device.id)).all()]


def _robot(db: Session, device_id: int) -> Device:
    d = db.get(Device, device_id)
    if d is None or d.device_type != DeviceType.ROBOT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Robot not found")
    return d


def _event_out(e: RobotEvent) -> dict:
    # A movement's recorded path (for 3D replay) is fetched on its own - lists stay small.
    detail = {k: v for k, v in (e.detail or {}).items() if k != "trajectory"} if e.detail else e.detail
    return {"id": e.id, "kind": e.kind, "joint": e.joint, "detail": detail, "source": e.source,
            "has_trajectory": bool(e.detail and e.detail.get("trajectory")),
            "occurred_at": _utc(e.occurred_at), "received_at": _utc(e.received_at), "severity": e.severity,
            "booking_id": e.booking_id, "context": e.context, "provenance": e.provenance}


@router.get("/{device_id}")
def robot(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    d = _robot(db, device_id)
    now = datetime.now(timezone.utc)
    cal = _home(db, d.id)
    since = now - timedelta(hours=24)
    counts = dict(db.execute(select(RobotEvent.kind, func.count(RobotEvent.id)).where(
        RobotEvent.device_id == d.id, RobotEvent.occurred_at >= since).group_by(RobotEvent.kind)).all())
    recent = db.scalars(select(RobotEvent).where(RobotEvent.device_id == d.id)
                        .order_by(desc(RobotEvent.occurred_at)).limit(30)).all()
    return {**_summary(d, now, True),
            "home_calibration": None if cal is None else {
                "version": cal.version, "home_q": cal.home_q, "home_tcp": cal.home_tcp,
                "tolerance_deg": cal.tolerance_deg, "created_at": _utc(cal.created_at), "note": cal.note},
            "last_24h": counts, "events": [_event_out(e) for e in recent]}


@router.get("/{device_id}/events")
def robot_events(device_id: int, limit: int = Query(100, ge=1, le=500), kind: Optional[str] = Query(None, max_length=32),
                 db: Session = Depends(get_db), _: User = Depends(require_staff)):
    d = _robot(db, device_id)
    q = select(RobotEvent).where(RobotEvent.device_id == d.id)
    if kind:
        q = q.where(RobotEvent.kind == kind)
    return [_event_out(e) for e in db.scalars(q.order_by(desc(RobotEvent.occurred_at)).limit(limit)).all()]


@router.get("/{device_id}/movements")
def movements(device_id: int, limit: int = Query(30, ge=1, le=1000), db: Session = Depends(get_db),
              _: User = Depends(require_staff)):
    """Recent completed movements that carry their recorded path (3D replay)."""
    d = _robot(db, device_id)
    rows = db.scalars(select(RobotEvent).where(RobotEvent.device_id == d.id, RobotEvent.kind == "MOVEMENT_STOPPED")
                      .order_by(desc(RobotEvent.occurred_at)).limit(limit * 3)).all()
    return [_event_out(e) for e in rows if e.detail and e.detail.get("trajectory")][:limit]


@router.get("/{device_id}/movements/{event_id}")
def movement(device_id: int, event_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """One movement's recorded joint path: t (s from its start) and q (rad, J1..J6)."""
    d = _robot(db, device_id)
    e = db.get(RobotEvent, event_id)
    if e is None or e.device_id != d.id or not (e.detail and e.detail.get("trajectory")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No recorded path for this movement")
    tr = e.detail["trajectory"]
    return {**_event_out(e), "trajectory": {"t": tr.get("t", []), "q": tr.get("q", [])}}


class HomeIn(BaseModel):
    tolerance_deg: float = Field(default=1.0, gt=0.05, le=10)
    note: str = Field(default="", max_length=255)


@router.post("/{device_id}/home")
def calibrate_home(device_id: int, req: HomeIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """HOME = the pose the robot is in NOW (the engineer put it there). Needs
    fresh telemetry and a still robot. A new version; older ones are kept."""
    d = _robot(db, device_id)
    now = datetime.now(timezone.utc)
    cs = d.component_state or {}
    if _effective_state(d, now) != "STATIONARY" or not cs.get("q"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "HOME can only be taken from live telemetry while the robot is still.")
    prev = _home(db, d.id)
    note = req.note + (" [SIMULATION robot]" if cs.get("source") == "SIMULATION" else "")
    cal = RobotHomeCalibration(device_id=d.id, version=(prev.version + 1) if prev else 1, home_q=cs["q"],
                               home_tcp=cs.get("tcp"), tolerance_deg=req.tolerance_deg, note=note.strip(),
                               created_by_id=admin.id)
    db.add(cal)
    db.add(AuditLog(actor_user_id=admin.id, action="ROBOT_HOME_CALIBRATED", entity_type="device",
                    entity_id=str(d.id), detail={"version": cal.version, "home_q": cal.home_q,
                                                 "tolerance_deg": cal.tolerance_deg}))
    db.commit()
    return {"version": cal.version, "home_q": cal.home_q}


# ---------------------------------------------------------------- control ---
# Home / approved routines / software stop. Enforced here, not in the browser. Every adapter is
# UNAVAILABLE until commissioned (app/services/robot_control.py, docs/ROBOT_CONTROL.md): nothing
# below can send anything to a robot controller.
from app.services import robot_control as rctl  # noqa: E402


def _age_s(d: Device, now: datetime) -> Optional[float]:
    seen = _utc(d.last_seen_at)
    return None if seen is None else (now - seen).total_seconds()


def _fmt_age(s: float) -> str:
    """'2.3 s', '14 min', '5 h', '9 days' - a readable age for the readiness list."""
    return (f"{s:.1f} s" if s < 120 else f"{s / 60:.0f} min" if s < 7200 else
            f"{s / 3600:.0f} h" if s < 172800 else f"{s / 86400:.0f} days")


def _ctl_model(d: Device) -> Optional[str]:
    """Picks the controller adapter. UR5E_01 reports no model, so its uid decides (UR5E_* -> UR)."""
    m = (d.component_state or {}).get("model")
    if m:
        return m
    uid = (d.device_uid or "").upper()
    return "UR5e" if uid.startswith("UR") else "FANUC" if uid.startswith("FANUC") else None


def _moving(cs: dict) -> bool:
    m = cs.get("joints_moving")
    return any(m) if isinstance(m, list) else bool(m)


def _control_out(d: Device, now: datetime) -> dict:
    model = _ctl_model(d)
    ad = rctl.adapter_for(model)
    o = rctl.owner(d.id)
    cs = d.component_state or {}
    age = _age_s(d, now)
    master = None
    fresh = age is not None and age <= rctl.FRESH_S
    q = cs.get("q")
    sim = cs.get("source") == "SIMULATION"           # a simulator record is never physical evidence
    readiness = None
    if ad.name == "UR5e":                          # the UR5e master controls; FANUC has its own adapter
        q_deg = [v * 180 / math.pi for v in q] if q and len(q) == 6 else None
        master = rctl.master_state(d.id, q_deg, _moving(cs), fresh, cs.get("extra") or {}, sim)
        readiness = {"readiness": master["readiness"], "checks": master["checks"], "dependencies": []}
    elif ad.name == "FANUC":
        readiness = rctl.fanuc_readiness(fresh, bool(q) and len(q) == 6, sim)
    if readiness and age is not None:              # say how old, not just "not fresh"
        for c in readiness["checks"]:
            if c["key"] == "telemetry":
                c["detail"] = f"{_fmt_age(age)} old" + ("" if fresh else f" - commands need < {rctl.FRESH_S:g} s")
    return {"device_id": d.id, "model": model, "adapter": ad.name, "controller_mode": ad.controller_mode(),
            "simulated": sim,
            "master": master, "control_mode": rctl.MODE, "readiness": readiness,
            "capabilities": ad.capabilities(), "telemetry_age_s": _age_s(d, now),
            "owner": None if o is None else {"user_id": o.user_id, "name": o.name,
                                             "expires_in_s": round(o.until - time.time())}}


@router.get("/{device_id}/control")
def control_status(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return _control_out(_robot(db, device_id), datetime.now(timezone.utc))


@router.post("/{device_id}/control/request")
def control_request(device_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    d = _robot(db, device_id)
    ok, why, _o = rctl.request_control(d.id, user.id, user.full_name)
    db.add(AuditLog(actor_user_id=user.id, action="ROBOT_CONTROL_REQUEST", entity_type="robot",
                    entity_id=str(d.id), detail={"granted": ok, "reason": why}))
    db.commit()
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, why)
    return {**_control_out(d, datetime.now(timezone.utc)), "message": why}


@router.post("/{device_id}/control/release")
def control_release(device_id: int, force: bool = False, db: Session = Depends(get_db),
                    user: User = Depends(require_staff)):
    d = _robot(db, device_id)
    if force and user.role.value != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an administrator can take back control")
    released = rctl.release_control(d.id, user.id, force=force)
    db.add(AuditLog(actor_user_id=user.id, action="ROBOT_CONTROL_RELEASE", entity_type="robot",
                    entity_id=str(d.id), detail={"released": released, "force": force}))
    db.commit()
    return {**_control_out(d, datetime.now(timezone.utc)), "released": released}


class CommandIn(BaseModel):
    action: str = Field(max_length=16)
    routine: Optional[str] = Field(default=None, max_length=48)
    command_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    confirmed: bool = False


@router.post("/{device_id}/control/command")
def control_command(device_id: int, req: CommandIn, db: Session = Depends(get_db),
                    user: User = Depends(require_staff)):
    d = _robot(db, device_id)
    if req.action in ("home", "routine") and not req.confirmed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A movement needs explicit confirmation")
    now = datetime.now(timezone.utc)
    r = rctl.submit(d.id, _ctl_model(d), user.id, req.action, req.routine,
                    req.command_id, _age_s(d, now))
    db.add(AuditLog(actor_user_id=user.id, action="ROBOT_COMMAND", entity_type="robot", entity_id=str(d.id),
                    detail={"command_id": req.command_id, "action": req.action, "routine": req.routine,
                            "result": r.status, "reason": r.reason}))
    db.commit()
    return r.out()


class StopIn(BaseModel):
    command_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


@router.post("/{device_id}/control/stop")
def control_global_stop(device_id: int, req: StopIn, db: Session = Depends(get_db),
                        user: User = Depends(require_staff)):
    """Global STOP: any staff member, no ownership needed, whoever started the motion. Latches
    until an administrator runs the recovery. A software stop - not a safety-rated E-stop."""
    d = _robot(db, device_id)
    r = rctl.global_stop(d.id, _ctl_model(d), user.full_name, req.command_id)
    db.add(AuditLog(actor_user_id=user.id, action="ROBOT_GLOBAL_STOP", entity_type="robot", entity_id=str(d.id),
                    detail={"command_id": req.command_id, "result": r.status, "reason": r.reason}))
    db.commit()
    return {**r.out(), **_control_out(d, datetime.now(timezone.utc))}


def restore_stop_latches(db: Session) -> list[int]:
    """Called once at start-up (main.lifespan): re-latch every STOP that was never recovered."""
    rows = db.execute(select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.actor_user_id)
                      .where(AuditLog.action.in_(("ROBOT_GLOBAL_STOP", "ROBOT_STOP_RECOVERY")))
                      .order_by(AuditLog.created_at, AuditLog.id)).all()
    events = [{"action": a.action, "device_id": int(a.entity_id), "t": _utc(a.created_at).timestamp(),
               "by": name, "result": (a.detail or {}).get("result"), "cleared": (a.detail or {}).get("cleared")}
              for a, name in rows if a.entity_id and str(a.entity_id).isdigit()]
    return rctl.restore_latches(events)


@router.post("/{device_id}/control/recover")
def control_recover(device_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Deliberate recovery after STOP (administrator, arm reported still). Restarts nothing."""
    d = _robot(db, device_id)
    ok, why = rctl.recover(d.id, _moving(d.component_state or {}))
    db.add(AuditLog(actor_user_id=admin.id, action="ROBOT_STOP_RECOVERY", entity_type="robot", entity_id=str(d.id),
                    detail={"cleared": ok, "reason": why}))
    db.commit()
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, why)
    return {"message": why, **_control_out(d, datetime.now(timezone.utc))}
