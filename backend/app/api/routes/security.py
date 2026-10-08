"""
Security camera: a fixed camera in a lab corner, analysed on the laptop.

tools/security_vision reads the camera (RTSP, e.g. Mercusys MC210, or a
webcam), detects people, follows them, puts names on them from the door
entries, and watches a box around each fixed item (PC, robot). It talks to
the portal with a device key, like every other node:

    GET  /security/config   zones + who is inside per the door (registers it)
    POST /security/state    every ~2 s: people seen, names, zone states
    POST /security/events   something to check, with a snapshot

Staff see the live annotated view (fetched from the service through the
portal, so the stream is never open on the network), draw the boxes, and
acknowledge events. Nothing here locks, unlocks or moves anything; a
camera's opinion is something for staff to check, never a decision.

Privacy: no continuous recording. Frames are shown live only to staff; a
snapshot is kept only with an event, and deleted with it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

import time

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, require_admin, require_device, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import (AccessSession, Alert, AlertSeverity, Asset, AuditLog, Device,
                        DeviceType, Lab, SecurityEvent, SecurityZone, User)
from app.services.access import get_device, get_lab_by_code
from app.services.devices import is_fresh
from app.services.notifications import notify, staff_ids
from app.services.storage import get_storage, new_key

router = APIRouter(prefix="/security", tags=["security camera"])

KINDS = {
    # kind: (severity, title)
    "PERSON_NO_ENTRY": (AlertSeverity.CRITICAL, "Person in the lab with no door entry"),
    "UNIDENTIFIED_PERSON": (AlertSeverity.WARNING, "More people seen than entered at the door"),
    "EQUIPMENT_CHANGED": (AlertSeverity.WARNING, "Equipment moved or missing"),
    "EQUIPMENT_MOTION": (AlertSeverity.WARNING, "Movement at equipment with nobody there"),
    "FACE_MISMATCH": (AlertSeverity.CRITICAL, "Face does not match the door entry (card sharing?)"),
    # The camera's view moved (panned / bumped): boxes re-aligned by the camera...
    "CAMERA_VIEW_MOVED": (AlertSeverity.INFO, "Camera view moved - boxes re-aligned"),
    # ...or it could not match the room confidently: boxes left as they were.
    "CAMERA_VIEW_LOST": (AlertSeverity.WARNING, "Camera view changed - check / redraw the boxes"),
    # The background equipment scan: an item with no box / a named item gone.
    "EQUIPMENT_UNNAMED": (AlertSeverity.INFO, "Equipment found with no box"),
    "EQUIPMENT_NOT_SEEN": (AlertSeverity.WARNING, "Equipment not seen for a while"),
    # A robot box (motion alert off) moving / parking in a new pose: a log, not an alarm.
    "ROBOT_ACTIVITY": (AlertSeverity.INFO, "Robot moved"),
    # A face clearly says someone other than the name the camera holds: the
    # name is NOT switched (identity.py); staff check who it is.
    "PERSON_IDENTITY_CONFLICT": (AlertSeverity.WARNING, "Identity conflict - face does not match the name"),
}
MAX_SNAPSHOT = 2_000_000
# One kept-alive connection pool for live frames: a new TCP connection per
# frame (15 a second per viewer) added a handshake to every picture.
_frames = httpx.Client(timeout=httpx.Timeout(3.0, connect=1.5),
                       limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _zone_out(z: SecurityZone, db: Session) -> dict:
    a = db.get(Asset, z.asset_id) if z.asset_id else None
    return {"id": z.id, "name": z.name, "kind": z.kind, "asset_id": z.asset_id,
            "asset_tag": a.asset_tag if a else None, "x": z.x, "y": z.y, "w": z.w, "h": z.h,
            "alert_on_motion": z.alert_on_motion, "ref_version": z.ref_version}


def occupants(db: Session, lab_id: int) -> list[dict]:
    """Who is inside per the door: open access sessions, oldest first."""
    out = []
    for s in db.scalars(select(AccessSession).where(
            AccessSession.lab_id == lab_id, AccessSession.ended_at.is_(None))
            .order_by(AccessSession.started_at)).all():
        u = db.get(User, s.user_id)
        if u is None:
            continue
        out.append({"auth_subject": u.auth_subject or f"user-{u.id}", "name": u.full_name,
                    "role": u.role.value, "entered_at": _utc(s.started_at).timestamp()})
    return out


# ------------------------------------------------------------ the service ---
@router.get("/config", tags=["devices"])
def config(device_uid: str = Query(max_length=64), lab_id: str = Query(max_length=32),
           port: int = Query(5100, ge=1, le=65535), name: str = Query("Security camera", max_length=64),
           db: Session = Depends(get_db), identity: str = Depends(require_device)):
    device_scope(identity, device_uid)
    lab = get_lab_by_code(db, lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown lab")
    d = get_device(db, device_uid)
    now = datetime.now(timezone.utc)
    if d is None:
        d = Device(device_uid=device_uid, name=name, device_type=DeviceType.SECURITY_CAMERA,
                   lab_id=lab.id)
        db.add(d)
        db.flush()
    d.last_seen_at, d.is_online = now, True
    d.component_state = {**(d.component_state or {}), "port": port}
    zones = db.scalars(select(SecurityZone).where(SecurityZone.device_id == d.id)
                       .order_by(SecurityZone.id)).all()
    db.commit()
    return {"device_id": d.id, "lab_code": lab.code, "lab_name": lab.name,
            "zones": [_zone_out(z, db) for z in zones if z.kind == "EQUIPMENT"],
            "door": next((_zone_out(z, db) for z in zones if z.kind == "DOOR"), None),
            "occupants": occupants(db, lab.id), "server_time": now.timestamp(),
            # Who USERx is, so a face recognised before the door can be named
            # (shown "not entered" until the door confirms the entry).
            "known": [{"auth_subject": u.auth_subject, "name": u.full_name, "role": u.role.value}
                      for u in db.scalars(select(User).where(User.is_active.is_(True),
                                                             User.auth_subject.is_not(None))).all()]}


class RealignedBox(BaseModel):
    id: int
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class RealignReport(BaseModel):
    device_uid: str = Field(max_length=64)
    boxes: list[RealignedBox] = Field(default_factory=list, max_length=200)
    lost: list[int] = Field(default_factory=list, max_length=200)     # left the picture: unchanged
    inliers: int = 0
    shift: float = 0.0                                                 # fraction of the width
    # "view": the camera turned (room matched); "detector": a box nudged onto its item.
    reason: Literal["view", "detector"] = "view"


@router.post("/zones/realign", tags=["devices"])
def realign_zones(req: RealignReport, db: Session = Depends(get_db), identity: str = Depends(require_device)):
    """The camera matched its moved view to the room and reports where each
    box went. Each box is moved and relearns its normal look; boxes that left
    the picture are left as they were. In the audit log (no person: the camera)."""
    device_scope(identity, req.device_uid)
    d = get_device(db, req.device_uid)
    if d is None or d.device_type != DeviceType.SECURITY_CAMERA:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown camera")
    moved = []
    for b in req.boxes:
        z = db.get(SecurityZone, b.id)
        if z is None or z.device_id != d.id:
            continue
        before = (round(z.x, 4), round(z.y, 4), round(z.w, 4), round(z.h, 4))
        z.x, z.y, z.w, z.h = b.x, b.y, min(b.w, 1 - b.x), min(b.h, 1 - b.y)
        z.ref_version += 1
        moved.append({"id": z.id, "name": z.name, "from": before, "to": (b.x, b.y, b.w, b.h)})
    db.add(AuditLog(actor_user_id=None, action="SECURITY_ZONES_REALIGNED", entity_type="device",
                    entity_id=str(d.id), detail={"device": d.device_uid, "moved": moved, "lost": req.lost,
                                                 "inliers": req.inliers, "shift": req.shift,
                                                 "reason": req.reason}))
    db.commit()
    return {"moved": len(moved), "lost": req.lost}


class ZoneStatus(BaseModel):
    id: int
    name: str = ""
    status: str = Field(max_length=16)
    score: float = 0.0
    # Robot boxes: the camera's own motion evidence (tools/security_vision/robotvision.py).
    visual: Optional[dict[str, Any]] = None


class StateReport(BaseModel):
    device_uid: str = Field(max_length=64)
    fps: float = 0.0
    people: int = 0
    named: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    unknown: int = 0
    zones: list[ZoneStatus] = Field(default_factory=list, max_length=100)
    source_ok: bool = True
    door_open: Optional[bool] = None          # from the red door leaf in the door box (None: no door box)
    # Measured pipeline timings (tools/security_vision/latency.py): fps per stage, frame ages.
    metrics: dict[str, Any] = Field(default_factory=dict)


@router.post("/state", tags=["devices"])
def report_state(req: StateReport, db: Session = Depends(get_db),
                 identity: str = Depends(require_device)):
    device_scope(identity, req.device_uid)
    d = get_device(db, req.device_uid)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call /security/config first")
    now = datetime.now(timezone.utc)
    prev = d.component_state or {}
    # What staff see: pushed only when it changes. The service reports every
    # 2 s and every staff page refetches on a push - pushing each report made
    # the whole portal reload every 2 s.
    def seen(s: dict) -> tuple:
        return (s.get("people"), s.get("unknown"), s.get("source_ok"), s.get("door_open"),
                tuple(sorted((n.get("label") or "", n.get("name") or "") for n in s.get("named", []))),
                tuple(sorted((z.get("id"), z.get("status")) for z in s.get("zones", []))))
    was_online = d.is_online
    d.last_seen_at, d.is_online = now, True
    d.component_state = {"port": prev.get("port", 5100),
                         "fps": round(req.fps, 1), "people": req.people, "unknown": req.unknown,
                         "named": req.named[:50], "source_ok": req.source_ok, "door_open": req.door_open,
                         "metrics": {k: v for k, v in list(req.metrics.items())[:30]
                                     if isinstance(v, (int, float, type(None)))},
                         "zones": [z.model_dump() for z in req.zones], "at": now.isoformat()}
    # Robots in this lab: the camera's view of each robot's box feeds the
    # telemetry + camera comparison (robot_fusion) - also when telemetry is gone.
    from app.api.routes.robots import update_fusion
    for r in db.scalars(select(Device).where(Device.lab_id == d.lab_id, Device.device_type == DeviceType.ROBOT)).all():
        update_fusion(db, r, now)
    db.commit()
    if seen(prev) != seen(d.component_state) or not was_online:
        try:
            from app.ws.manager import manager
            manager.publish({"type": "security_state", "device_id": d.id, "lab_id": d.lab_id})
        except Exception:
            pass
    return {"ok": True}


@router.post("/events", tags=["devices"], status_code=status.HTTP_201_CREATED)
async def report_event(meta: str = Form(..., max_length=2000),
                       snapshot: Optional[UploadFile] = File(None),
                       db: Session = Depends(get_db), identity: str = Depends(require_device)):
    try:
        m = json.loads(meta)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "meta must be JSON")
    device_scope(identity, str(m.get("device_uid", "")))
    d = get_device(db, str(m.get("device_uid", "")))
    kind = str(m.get("kind", ""))
    if d is None or kind not in KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown camera or event kind")
    zone = db.get(SecurityZone, int(m["zone_id"])) if m.get("zone_id") else None
    if zone is not None and zone.device_id != d.id:
        zone = None
    key = None
    if snapshot is not None:
        data = await snapshot.read(MAX_SNAPSHOT + 1)
        if data[:2] == b"\xff\xd8" and len(data) <= MAX_SNAPSHOT:
            key, _ = new_key(f"security/{d.id}", "jpg")
            get_storage().put(key, data, "image/jpeg")
    severity, title = KINDS[kind]
    if zone is not None:
        title = f"{title}: {zone.name}"
    detail = str(m.get("detail", ""))[:255]
    ev = SecurityEvent(device_id=d.id, lab_id=d.lab_id, zone_id=zone.id if zone else None,
                       kind=kind, detail=detail, people_seen=int(m.get("people_seen", 0)),
                       people_inside=int(m.get("people_inside", 0)), snapshot_key=key)
    db.add(ev)
    db.flush()
    lab = db.get(Lab, d.lab_id)
    dedupe = f"sec:{d.id}:{kind}:{zone.id if zone else 0}"
    if db.scalar(select(Alert).where(Alert.dedupe_key == dedupe, Alert.is_resolved.is_(False))) is None:
        db.add(Alert(lab_id=d.lab_id, device_id=d.id, severity=severity,
                     title=f"{lab.code if lab else ''}: {title}"[:128], detail=detail,
                     dedupe_key=dedupe))
        notify(db, staff_ids(db), "SECURITY_CAMERA", f"{lab.code if lab else 'Lab'}: {title}",
               body=detail + " Check the snapshot; a camera can be wrong.",
               link="/admin/security", severity="critical" if severity == AlertSeverity.CRITICAL
               else "warning")
    db.commit()
    try:
        from app.ws.manager import manager
        manager.publish({"type": "staff", "kind": "security_event", "event_id": ev.id,
                         "lab_id": d.lab_id})
    except Exception:
        pass
    return {"id": ev.id}


# ------------------------------------------------------------------ staff ---
def _camera(db: Session, device_id: int) -> Device:
    d = db.get(Device, device_id)
    if d is None or d.device_type != DeviceType.SECURITY_CAMERA:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Security camera not found")
    return d


def camera_summary(db: Session, d: Device, now: datetime) -> dict:
    st = d.component_state or {}
    lab = db.get(Lab, d.lab_id)
    online = is_fresh(d, now)
    return {"device_id": d.id, "device_uid": d.device_uid, "name": d.name,
            "lab_id": d.lab_id, "lab_code": lab.code if lab else None,
            "online": online, "last_seen_at": d.last_seen_at,
            "source_ok": st.get("source_ok") if online else None,
            "fps": st.get("fps") if online else None,
            "people": st.get("people") if online else None,
            "unknown": st.get("unknown") if online else None,
            "named": st.get("named", []) if online else [],
            "zones": st.get("zones", []) if online else [],
            "door_open": st.get("door_open") if online else None,
            "metrics": st.get("metrics") if online else None,
            "inside": len(occupants(db, d.lab_id)),
            "open_events": db.query(SecurityEvent).filter_by(
                device_id=d.id, acknowledged_at=None).count()}


@router.get("/cameras")
def cameras(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    now = datetime.now(timezone.utc)
    return [camera_summary(db, d, now) for d in db.scalars(select(Device).where(
        Device.device_type == DeviceType.SECURITY_CAMERA).order_by(Device.lab_id, Device.id)).all()]


def _service_url(d: Device, path: str) -> str:
    port = int((d.component_state or {}).get("port", 5100))
    return f"http://{settings.SECURITY_VISION_HOST}:{port}{path}"


@router.get("/cameras/{device_id}/frame.jpg")
def frame(device_id: int, raw: bool = False, db: Session = Depends(get_db),
          _: User = Depends(require_staff)):
    """The latest frame (annotated, or raw for drawing boxes). 204 = none."""
    d = _camera(db, device_id)
    t0 = time.perf_counter()
    try:
        r = _frames.get(_service_url(d, "/raw.jpg" if raw else "/frame.jpg"),
                        headers={"X-Device-Key": settings.DEVICE_API_KEY})
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The security camera service is not reachable - start it on the laptop.")
    if r.status_code != 200:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    # Timing travels with the frame (docs/LATENCY.md): when the camera service
    # received it, its age when served, and how long this hop took.
    return Response(content=r.content, media_type="image/jpeg", headers={
        "Cache-Control": "no-store",
        "X-Frame-Received-At-Ms": r.headers.get("X-Frame-Received-At-Ms", ""),
        "X-Frame-Age-Ms": r.headers.get("X-Frame-Age-Ms", ""),
        "X-Proxy-Ms": str(round((time.perf_counter() - t0) * 1000, 1)),
        "Access-Control-Expose-Headers": "X-Frame-Received-At-Ms, X-Frame-Age-Ms, X-Proxy-Ms"})


def _overlap(a: dict, b) -> float:
    ax2, ay2, bx2, by2 = a["x"] + a["w"], a["y"] + a["h"], b.x + b.w, b.y + b.h
    iw, ih = max(0.0, min(ax2, bx2) - max(a["x"], b.x)), max(0.0, min(ay2, by2) - max(a["y"], b.y))
    inter = iw * ih
    union = a["w"] * a["h"] + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


@router.get("/cameras/{device_id}/identity")
def identity_evidence(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Why each person in view has (or has not) a name: state, confidence and
    the evidence behind it, plus recent identity decisions. Staff only; names,
    scores and times - never face data."""
    d = _camera(db, device_id)
    try:
        r = httpx.get(_service_url(d, "/identity"), headers={"X-Device-Key": settings.DEVICE_API_KEY},
                      timeout=httpx.Timeout(3.0, connect=1.5))
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The security camera service is not reachable - start it on the laptop.")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The camera service has no identity log (update it).")
    return r.json()


@router.get("/cameras/{device_id}/suggestions")
def suggestions(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Equipment the detector finds in the picture now (monitors, laptops) as
    boxes to add, numbered after the boxes already saved. An item a saved box
    already sits on (overlap > 0.6) is skipped. An item a saved box only
    partly covers - the box is off its item, e.g. after the camera turned -
    is offered as "move that box here" (replaces = its id; staff can pick
    another box or a new one instead). Nothing is saved until staff add them."""
    d = _camera(db, device_id)
    try:
        r = httpx.get(_service_url(d, "/equipment"), headers={"X-Device-Key": settings.DEVICE_API_KEY},
                      timeout=httpx.Timeout(20.0, connect=1.5))
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The security camera service is not reachable - start it on the laptop.")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The camera service could not look for equipment.")
    zones = [z for z in db.scalars(select(SecurityZone).where(SecurityZone.device_id == d.id)).all()
             if z.kind == "EQUIPMENT"]
    names = {z.name for z in zones}
    items = [it for it in r.json().get("items", []) if not any(_overlap(it, z) > 0.6 for z in zones)]
    # Each misplaced box is offered for the one item it overlaps most (best item first).
    claim: dict[int, tuple[float, int]] = {}
    for i, it in enumerate(items):
        for z in zones:
            o = _overlap(it, z)
            if o > 0.05 and o > claim.get(z.id, (0.0, -1))[0]:
                claim[z.id] = (o, i)
    replaces = {i: z for z in zones for (o, i) in [claim.get(z.id, (0.0, -1))] if i >= 0}
    out = []
    for i, it in sorted(enumerate(items), key=lambda p: (round(p[1]["y"], 2), p[1]["x"])):
        z = replaces.get(i)
        if z is not None:
            out.append({**it, "name": z.name, "replaces": z.id})
            continue
        prefix = "PC" if it["kind"] == "Monitor" else it["kind"]
        n = 1
        while f"{prefix}-{n:02d}" in names:
            n += 1
        names.add(f"{prefix}-{n:02d}")
        out.append({**it, "name": f"{prefix}-{n:02d}", "replaces": None})
    return out


class ZoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: Literal["EQUIPMENT", "DOOR"] = "EQUIPMENT"
    asset_id: Optional[int] = None
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0.01, le=1)
    h: float = Field(gt=0.01, le=1)
    alert_on_motion: bool = True


def _check_zone(db: Session, d: Device, req: ZoneIn, zone_id: Optional[int] = None):
    if req.x + req.w > 1.001 or req.y + req.h > 1.001:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The box must be inside the picture")
    if req.asset_id is not None and db.get(Asset, req.asset_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    if req.kind == "DOOR" and db.scalar(select(SecurityZone).where(
            SecurityZone.device_id == d.id, SecurityZone.kind == "DOOR",
            SecurityZone.id != (zone_id or 0))):
        raise HTTPException(status.HTTP_409_CONFLICT, "This camera already has a door area")


@router.get("/cameras/{device_id}/zones")
def list_zones(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    d = _camera(db, device_id)
    return [_zone_out(z, db) for z in db.scalars(select(SecurityZone).where(
        SecurityZone.device_id == d.id).order_by(SecurityZone.id)).all()]


@router.post("/cameras/{device_id}/zones", status_code=status.HTTP_201_CREATED)
def add_zone(device_id: int, req: ZoneIn, db: Session = Depends(get_db),
             staff: User = Depends(require_staff)):
    d = _camera(db, device_id)
    _check_zone(db, d, req)
    z = SecurityZone(device_id=d.id, **req.model_dump())
    db.add(z)
    db.flush()
    db.add(AuditLog(actor_user_id=staff.id, action="SECURITY_ZONE_ADDED", entity_type="security_zone",
                    entity_id=str(z.id), detail={"device": d.device_uid, **req.model_dump()}))
    db.commit()
    return _zone_out(z, db)


@router.put("/cameras/{device_id}/zones/{zone_id}")
def update_zone(device_id: int, zone_id: int, req: ZoneIn, db: Session = Depends(get_db),
                staff: User = Depends(require_staff)):
    d = _camera(db, device_id)
    z = db.get(SecurityZone, zone_id)
    if z is None or z.device_id != d.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")
    _check_zone(db, d, req, zone_id)
    moved = (z.x, z.y, z.w, z.h) != (req.x, req.y, req.w, req.h)
    for k, v in req.model_dump().items():
        setattr(z, k, v)
    if moved:
        z.ref_version += 1              # a different box: learn its normal look again
    db.add(AuditLog(actor_user_id=staff.id, action="SECURITY_ZONE_UPDATED", entity_type="security_zone",
                    entity_id=str(z.id), detail={"device": d.device_uid, **req.model_dump()}))
    db.commit()
    return _zone_out(z, db)


@router.post("/cameras/{device_id}/zones/{zone_id}/accept")
def accept_zone(device_id: int, zone_id: int, db: Session = Depends(get_db),
                staff: User = Depends(require_staff)):
    """The item's new position/look is fine: the camera relearns it."""
    d = _camera(db, device_id)
    z = db.get(SecurityZone, zone_id)
    if z is None or z.device_id != d.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")
    z.ref_version += 1
    db.add(AuditLog(actor_user_id=staff.id, action="SECURITY_ZONE_ACCEPTED",
                    entity_type="security_zone", entity_id=str(z.id), detail={"name": z.name}))
    db.commit()
    return _zone_out(z, db)


@router.delete("/cameras/{device_id}/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(device_id: int, zone_id: int, db: Session = Depends(get_db),
                staff: User = Depends(require_staff)):
    d = _camera(db, device_id)
    z = db.get(SecurityZone, zone_id)
    if z is None or z.device_id != d.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")
    db.add(AuditLog(actor_user_id=staff.id, action="SECURITY_ZONE_DELETED",
                    entity_type="security_zone", entity_id=str(z.id), detail={"name": z.name}))
    db.delete(z)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _event_out(db: Session, e: SecurityEvent) -> dict:
    z = db.get(SecurityZone, e.zone_id) if e.zone_id else None
    lab = db.get(Lab, e.lab_id)
    by = db.get(User, e.acknowledged_by_id) if e.acknowledged_by_id else None
    return {"id": e.id, "device_id": e.device_id, "lab_code": lab.code if lab else None,
            "kind": e.kind, "title": KINDS.get(e.kind, (None, e.kind))[1],
            "zone_name": z.name if z else None, "detail": e.detail,
            "people_seen": e.people_seen, "people_inside": e.people_inside,
            "has_snapshot": bool(e.snapshot_key), "created_at": e.created_at,
            "acknowledged_at": e.acknowledged_at, "acknowledged_by": by.full_name if by else None}


@router.get("/events")
def events(lab_id: Optional[int] = None, open_only: bool = False,
           limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
           _: User = Depends(require_staff)):
    q = select(SecurityEvent).order_by(desc(SecurityEvent.created_at)).limit(limit)
    if lab_id is not None:
        q = q.where(SecurityEvent.lab_id == lab_id)
    if open_only:
        q = q.where(SecurityEvent.acknowledged_at.is_(None))
    return [_event_out(db, e) for e in db.scalars(q).all()]


@router.get("/events/{event_id}/snapshot.jpg")
def event_snapshot(event_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    e = db.get(SecurityEvent, event_id)
    if e is None or not e.snapshot_key or not get_storage().exists(e.snapshot_key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No snapshot")
    return StreamingResponse(get_storage().open(e.snapshot_key), media_type="image/jpeg",
                             headers={"Cache-Control": "private, no-store"})


@router.post("/events/{event_id}/ack")
def acknowledge(event_id: int, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    e = db.get(SecurityEvent, event_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    now = datetime.now(timezone.utc)
    if e.acknowledged_at is None:
        e.acknowledged_at, e.acknowledged_by_id = now, staff.id
        # The alert closes when no event of that kind/zone is left open.
        dedupe = f"sec:{e.device_id}:{e.kind}:{e.zone_id or 0}"
        others = db.query(SecurityEvent).filter(
            SecurityEvent.device_id == e.device_id, SecurityEvent.kind == e.kind,
            SecurityEvent.zone_id.is_(None) if e.zone_id is None else SecurityEvent.zone_id == e.zone_id,
            SecurityEvent.acknowledged_at.is_(None), SecurityEvent.id != e.id).count()
        if not others:
            for a in db.scalars(select(Alert).where(Alert.dedupe_key == dedupe,
                                                    Alert.is_resolved.is_(False))).all():
                a.is_resolved, a.resolved_at = True, now
        db.add(AuditLog(actor_user_id=staff.id, action="SECURITY_EVENT_ACKNOWLEDGED",
                        entity_type="security_event", entity_id=str(e.id), detail={"kind": e.kind}))
        db.commit()
    return _event_out(db, e)


RETENTION_DAYS = 30


def purge_old_snapshots(db: Session, now: Optional[datetime] = None) -> int:
    """Snapshots of acknowledged events older than RETENTION_DAYS are deleted."""
    now = now or datetime.now(timezone.utc)
    n = 0
    for e in db.scalars(select(SecurityEvent).where(
            SecurityEvent.snapshot_key.is_not(None), SecurityEvent.acknowledged_at.is_not(None),
            SecurityEvent.created_at < now - timedelta(days=RETENTION_DAYS))).all():
        try:
            get_storage().delete(e.snapshot_key)
        except OSError:
            pass
        e.snapshot_key = None
        n += 1
    db.commit()
    return n


# ------------------------------------------------------------- recording --
# Video is recorded and kept on the laptop by the camera service (FFmpeg,
# tools/security_vision/recorder.py); the portal only switches it on/off for
# an administrator, lists the files and plays them through a short signed
# link (a <video> tag cannot send the sign-in header). Every start / stop is
# in the audit log. "Delete" (administrators) only moves a file into the
# deleted/ folder on the laptop - recoverable, and in the audit log.
import re as _re
from jose import JWTError, jwt as _jwt

_REC_NAME = _re.compile(r"^[A-Za-z0-9_-]+_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.mp4$")
_LINK_MINUTES = 10


def _service(d: Device, method: str, path: str, **kw) -> httpx.Response:
    try:
        return httpx.request(method, _service_url(d, path), headers={"X-Device-Key": settings.DEVICE_API_KEY},
                             timeout=httpx.Timeout(15.0, connect=1.5), **kw)
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The security camera service is not reachable - start it on the laptop.")


@router.get("/cameras/{device_id}/recording")
def recording_status(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    r = _service(_camera(db, device_id), "GET", "/record/status")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The camera service has no recorder (update it).")
    return r.json()


@router.post("/cameras/{device_id}/recording/{action}")
def recording_switch(device_id: int, action: Literal["start", "stop"], db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    d = _camera(db, device_id)
    r = _service(d, "POST", f"/record/{action}", json={"by": admin.full_name})
    if r.status_code == 404:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The camera service has no recorder (update it).")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not body.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT, body.get("error") or "The recording could not be switched.")
    db.add(AuditLog(actor_user_id=admin.id, action=f"SECURITY_RECORDING_{action.upper()}",
                    entity_type="device", entity_id=str(d.id),
                    detail={"device_uid": d.device_uid, **{k: body.get(k) for k in ("file", "duration_s", "size_bytes")}}))
    db.commit()
    return body


@router.get("/cameras/{device_id}/dataset")
def dataset_status(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Training pictures for the robot detector, kept on the laptop."""
    r = _service(_camera(db, device_id), "GET", "/dataset/status")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The camera service has no collector (update it).")
    return r.json()


@router.post("/cameras/{device_id}/dataset/{action}")
def dataset_switch(device_id: int, action: Literal["start", "stop"], db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    d = _camera(db, device_id)
    r = _service(d, "POST", f"/dataset/{action}", json={"by": admin.full_name})
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not body.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT, body.get("error") or "Could not switch collecting.")
    db.add(AuditLog(actor_user_id=admin.id, action=f"SECURITY_DATASET_{action.upper()}", entity_type="device",
                    entity_id=str(d.id), detail={"device_uid": d.device_uid, **body}))
    db.commit()
    return body


@router.get("/cameras/{device_id}/recordings")
def recordings(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    r = _service(_camera(db, device_id), "GET", "/recordings")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The camera service has no recorder (update it).")
    return r.json()


@router.post("/cameras/{device_id}/recordings/{name}/delete")
def recording_delete(device_id: int, name: str, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    d = _camera(db, device_id)
    if not _REC_NAME.match(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such recording")
    r = _service(d, "POST", f"/recordings/{name}/delete", json={"by": admin.full_name})
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not body.get("ok"):
        raise HTTPException(status.HTTP_409_CONFLICT, body.get("error") or "The recording could not be removed.")
    db.add(AuditLog(actor_user_id=admin.id, action="SECURITY_RECORDING_DELETED", entity_type="device",
                    entity_id=str(d.id), detail={"device_uid": d.device_uid, "file": name,
                                                 "moved_to": "recordings/deleted"}))
    db.commit()
    return body


@router.post("/cameras/{device_id}/recordings/{name}/link")
def recording_link(device_id: int, name: str, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    """A link to play / download one recording, valid for 10 minutes."""
    _camera(db, device_id)
    if not _REC_NAME.match(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such recording")
    exp = datetime.now(timezone.utc) + timedelta(minutes=_LINK_MINUTES)
    token = _jwt.encode({"typ": "recording", "dev": device_id, "name": name, "sub": str(admin.id), "exp": exp},
                        settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"url": f"{settings.API_V1}/security/recordings/play?t={token}", "expires_at": exp}


@router.get("/recordings/play")
def recording_play(t: str = Query(max_length=1024), download: bool = False,
                   range_: Optional[str] = Header(default=None, alias="Range"),
                   db: Session = Depends(get_db)):
    """Streams one recording (with Range, so the player can seek). The signed
    link IS the permission: an administrator asked for it minutes ago."""
    try:
        p = _jwt.decode(t, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This link has expired - open the recording again.")
    if p.get("typ") != "recording" or not _REC_NAME.match(str(p.get("name", ""))):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not a recording link")
    d = _camera(db, int(p["dev"]))
    db.close()                          # the stream may run for minutes; no session held
    client = httpx.Client(timeout=httpx.Timeout(60.0, connect=1.5))
    headers = {"X-Device-Key": settings.DEVICE_API_KEY, **({"Range": range_} if range_ else {})}
    try:
        r = client.send(client.build_request("GET", _service_url(d, f"/recordings/{p['name']}"), headers=headers),
                        stream=True)
    except httpx.HTTPError:
        client.close()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The security camera service is not reachable.")
    if r.status_code not in (200, 206):
        r.close(); client.close()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such recording")
    out = {k: r.headers[k] for k in ("content-type", "content-length", "content-range", "accept-ranges",
                                     "last-modified", "etag") if k in r.headers}
    out["Cache-Control"] = "private, no-store"
    if download:
        out["Content-Disposition"] = f'attachment; filename="{p["name"]}"'

    def body():
        try:
            yield from r.iter_bytes(64 * 1024)
        finally:
            r.close()
            client.close()
    return StreamingResponse(body(), status_code=r.status_code, headers=out)

