"""Admin surface: events, users, devices, assets, alerts, summary, reports."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_staff
from app.api.routes.labs import DEVICE_STALE_AFTER
from app.db.session import get_db
from app.models import (AccessEvent, AccessResult, AccessSession, Alert, Asset,
                        AssetTransaction, AuthMethod, Booking, BookingStatus,
                        Device, EventType, Lab, RfidCredential, Role, User)
from app.schemas import (AdminSummary, AlertOut, AssetCreate, AssetOut,
                         DeviceCreate, DeviceOut, EventOut, UserOut, UserUpdate)

router = APIRouter(tags=["admin"])


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


# ---------------------------------------------------------------- events ---
@router.get("/access-events", response_model=list[EventOut])
def access_events(
    lab_id: Optional[int] = None,
    user_id: Optional[int] = None,
    event_type: Optional[EventType] = None,
    method: Optional[AuthMethod] = None,
    result: Optional[AccessResult] = None,
    since: Optional[datetime] = None,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
    caller: User = Depends(get_current_user),
):
    """
    The access timeline.

    Staff and admins see everything. A STUDENT may read this too, but only
    their own events - which is what makes the "your recent access" panel on
    the student dashboard work at all.

    The scoping is forced server-side rather than trusted from the query
    string: a student who asks for somebody else's user_id is silently
    narrowed back to themselves instead of being refused, because refusing
    would leak whether that other user has any events.
    """
    is_staff = caller.role in (Role.ADMIN, Role.LAB_STAFF)
    if not is_staff:
        user_id = caller.id

    stmt = select(AccessEvent).order_by(desc(AccessEvent.created_at)).limit(limit)
    if lab_id is not None:
        stmt = stmt.where(AccessEvent.lab_id == lab_id)
    if user_id is not None:
        stmt = stmt.where(AccessEvent.user_id == user_id)
    if event_type is not None:
        stmt = stmt.where(AccessEvent.event_type == event_type)
    if method is not None:
        stmt = stmt.where(AccessEvent.method == method)
    if result is not None:
        stmt = stmt.where(AccessEvent.result == result)
    if since is not None:
        stmt = stmt.where(AccessEvent.created_at >= since)

    out = []
    for e in db.scalars(stmt).all():
        item = EventOut.model_validate(e)
        if e.user_id:
            u = db.get(User, e.user_id)
            item.user_name = u.full_name if u else None
        if e.lab_id:
            lab = db.get(Lab, e.lab_id)
            item.lab_code = lab.code if lab else None
        out.append(item)
    return out


# --------------------------------------------------------------- summary ---
@router.get("/summary", response_model=AdminSummary)
def summary(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    labs = db.scalars(select(Lab)).all()
    confirmed = db.scalars(select(Booking).where(
        Booking.status == BookingStatus.CONFIRMED)).all()

    active = [b for b in confirmed
              if _utc(b.start_time) <= now <= _utc(b.end_time)]
    upcoming = [b for b in confirmed if _utc(b.start_time) > now]

    occupied_lab_ids = {b.lab_id for b in active}
    occupied_lab_ids |= {
        s.lab_id for s in db.scalars(
            select(AccessSession).where(AccessSession.ended_at.is_(None))).all()}

    granted = db.scalar(select(func.count()).select_from(AccessEvent).where(
        AccessEvent.event_type == EventType.ACCESS_GRANTED,
        AccessEvent.created_at >= midnight)) or 0
    denied = db.scalar(select(func.count()).select_from(AccessEvent).where(
        AccessEvent.event_type == EventType.ACCESS_DENIED,
        AccessEvent.created_at >= midnight)) or 0

    devices = db.scalars(select(Device)).all()
    online = sum(1 for d in devices if d.last_seen_at is not None
                 and (now - _utc(d.last_seen_at)) < DEVICE_STALE_AFTER)

    open_alerts = db.scalar(select(func.count()).select_from(Alert).where(
        Alert.is_resolved.is_(False))) or 0

    return AdminSummary(
        total_labs=len(labs), occupied_labs=len(occupied_lab_ids),
        active_bookings=len(active), upcoming_bookings=len(upcoming),
        granted_today=granted, denied_today=denied,
        devices_online=online, devices_total=len(devices),
        open_alerts=open_alerts,
    )


# ----------------------------------------------------------------- users ---
@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return db.scalars(select(User).order_by(User.full_name)).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, req: UserUpdate, db: Session = Depends(get_db),
                _: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(u, k, v)
    db.commit()
    db.refresh(u)
    return u


@router.post("/users/{user_id}/rfid", status_code=status.HTTP_201_CREATED)
def add_rfid(user_id: int, uid_hex: str, label: str = "",
             db: Session = Depends(get_db), _: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    uid = uid_hex.upper().replace(" ", "")
    if db.scalar(select(RfidCredential).where(RfidCredential.uid_hex == uid)):
        raise HTTPException(status.HTTP_409_CONFLICT, "UID already registered")
    cred = RfidCredential(uid_hex=uid, label=label, user_id=u.id)
    db.add(cred)
    db.commit()
    return {"id": cred.id, "uid_hex": cred.uid_hex, "user_id": u.id}


# --------------------------------------------------------------- devices ---
@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db),
                 _: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    devices = db.scalars(select(Device).order_by(Device.name)).all()
    # Recompute liveness on read: a device that stops sending heartbeats never
    # gets a chance to mark itself offline.
    for d in devices:
        d.is_online = (d.last_seen_at is not None
                       and (now - _utc(d.last_seen_at)) < DEVICE_STALE_AFTER)
    return devices


@router.post("/devices", response_model=DeviceOut,
             status_code=status.HTTP_201_CREATED)
def create_device(req: DeviceCreate, db: Session = Depends(get_db),
                  _: User = Depends(require_admin)):
    if db.scalar(select(Device).where(Device.device_uid == req.device_uid)):
        raise HTTPException(status.HTTP_409_CONFLICT, "device_uid exists")
    d = Device(**req.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


# ---------------------------------------------------------------- assets ---
@router.get("/assets", response_model=list[AssetOut])
def list_assets(lab_id: Optional[int] = None, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    stmt = select(Asset).order_by(Asset.name)
    if lab_id is not None:
        stmt = stmt.where(Asset.lab_id == lab_id)
    return db.scalars(stmt).all()


@router.post("/assets", response_model=AssetOut,
             status_code=status.HTTP_201_CREATED)
def create_asset(req: AssetCreate, db: Session = Depends(get_db),
                 _: User = Depends(require_staff)):
    if db.scalar(select(Asset).where(Asset.asset_tag == req.asset_tag)):
        raise HTTPException(status.HTTP_409_CONFLICT, "asset_tag exists")
    a = Asset(**req.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.post("/assets/{asset_id}/checkout", response_model=AssetOut)
def checkout_asset(asset_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    from app.models import AssetStatus
    from app.services.events import log_event

    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    if a.status != AssetStatus.AVAILABLE:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Asset is {a.status.value}")
    a.status = AssetStatus.CHECKED_OUT
    db.add(AssetTransaction(asset_id=a.id, user_id=user.id, lab_id=a.lab_id,
                            action="CHECKOUT"))
    log_event(db, EventType.ASSET_CHECKOUT, lab_id=a.lab_id, user_id=user.id,
              message=f"{user.full_name} checked out {a.name}")
    db.commit()
    db.refresh(a)
    return a


@router.post("/assets/{asset_id}/return", response_model=AssetOut)
def return_asset(asset_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    from app.models import AssetStatus
    from app.services.events import log_event

    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    a.status = AssetStatus.AVAILABLE
    db.add(AssetTransaction(asset_id=a.id, user_id=user.id, lab_id=a.lab_id,
                            action="RETURN"))
    log_event(db, EventType.ASSET_RETURN, lab_id=a.lab_id, user_id=user.id,
              message=f"{user.full_name} returned {a.name}")
    db.commit()
    db.refresh(a)
    return a


# ---------------------------------------------------------------- alerts ---
@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return db.scalars(select(Alert).order_by(desc(Alert.created_at))
                      .limit(200)).all()


@router.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, db: Session = Depends(get_db),
                  _: User = Depends(require_staff)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    a.is_resolved = True
    a.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(a)
    return a


@router.get("/access-events/export")
def export_events(lab_id: Optional[int] = None,
                  since: Optional[datetime] = None,
                  db: Session = Depends(get_db),
                  _: User = Depends(require_staff)):
    """
    CSV of the audit trail, resolved to names rather than foreign keys, so it
    can go straight into a thesis appendix or a spreadsheet.
    """
    import csv
    import io

    from fastapi.responses import StreamingResponse

    stmt = select(AccessEvent).order_by(desc(AccessEvent.created_at)).limit(5000)
    if lab_id is not None:
        stmt = stmt.where(AccessEvent.lab_id == lab_id)
    if since is not None:
        stmt = stmt.where(AccessEvent.created_at >= since)

    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    users = {u.id: u.full_name for u in db.scalars(select(User)).all()}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "lab", "event_type", "person", "method",
                "result", "reason", "message"])
    for e in db.scalars(stmt).all():
        w.writerow([
            e.created_at.isoformat() if e.created_at else "",
            labs.get(e.lab_id, ""),
            e.event_type.value if e.event_type else "",
            users.get(e.user_id, ""),
            e.method.value if e.method else "",
            e.result.value if e.result else "",
            e.reason or "",
            e.message or "",
        ])
    buf.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="access-events-{stamp}.csv"'})


# --------------------------------------------------------------- reports ---
@router.get("/reports/access")
def access_report(days: int = Query(7, le=90), db: Session = Depends(get_db),
                  _: User = Depends(require_staff)):
    """
    Daily grant/deny counts per lab. Real aggregates over real rows - if
    nothing has happened, the series is empty rather than padded.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(AccessEvent.lab_id,
               func.date(AccessEvent.created_at).label("day"),
               AccessEvent.event_type,
               func.count().label("n"))
        .where(AccessEvent.created_at >= since,
               AccessEvent.event_type.in_([EventType.ACCESS_GRANTED,
                                           EventType.ACCESS_DENIED]))
        .group_by(AccessEvent.lab_id, "day", AccessEvent.event_type)
        .order_by("day")).all()

    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    return [{"lab": labs.get(r.lab_id), "day": str(r.day),
             "event": r.event_type.value if hasattr(r.event_type, "value")
             else str(r.event_type),
             "count": r.n} for r in rows]
