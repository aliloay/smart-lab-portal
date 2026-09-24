"""Laboratories: listing, detail, live status and per-lab activity."""
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import (AccessEvent, AccessSession, Asset, Booking,
                        BookingStatus, Device, DeviceType, Issue, IssueSeverity,
                        Lab, Role, SensorReading, User)
from app.schemas import (BookingSlot, EventOut, LabCreate, LabIssueBrief,
                         LabOut, LabOverview, LabStatus, SensorReadingOut)
from app.services.devices import device_out, is_fresh, refresh_liveness
from app.services.issues import ACTIVE
from app.services.sessions import close_expired

router = APIRouter(prefix="/labs", tags=["labs"])

# Kept for backwards compatibility with anything importing it.
DEVICE_STALE_AFTER = timedelta(seconds=90)

_HIGH = (IssueSeverity.HIGH, IssueSeverity.CRITICAL)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def _staff(u: User) -> bool:
    return u.role in (Role.ADMIN, Role.LAB_STAFF)


def _slot(db: Session, b: Booking, viewer: User) -> BookingSlot:
    mine = b.user_id == viewer.id
    name = None
    if _staff(viewer) or mine:
        u = db.get(User, b.user_id)
        name = u.full_name if u else None
    return BookingSlot(booking_id=b.id if (_staff(viewer) or mine) else None,
                       start_time=b.start_time, end_time=b.end_time,
                       status=b.status, is_mine=mine, user_name=name)


@router.get("", response_model=list[LabOut])
def list_labs(db: Session = Depends(get_db),
              _: User = Depends(get_current_user)):
    return db.scalars(select(Lab).order_by(Lab.code)).all()


@router.get("/overview", response_model=list[LabOverview])
def labs_overview(db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    """
    Everything the laboratory catalogue shows, in one request, computed from
    live rows: occupancy from open sessions, availability from the booking
    table, controller state from heartbeats, issue counts from reports.
    """
    close_expired(db)
    devices = refresh_liveness(db)
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    labs = db.scalars(select(Lab).order_by(Lab.code)).all()
    bookings = db.scalars(select(Booking).where(
        Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.PENDING]),
        Booking.end_time > day_start)).all()
    sessions = db.scalars(select(AccessSession).where(
        AccessSession.ended_at.is_(None))).all()
    issues = db.scalars(select(Issue).where(Issue.status.in_(ACTIVE))).all()

    occupants = Counter(s.lab_id for s in sessions)
    open_issues = Counter(i.lab_id for i in issues)
    high = Counter(i.lab_id for i in issues if i.severity in _HIGH)

    out = []
    for lab in labs:
        lb = [b for b in bookings if b.lab_id == lab.id]
        active = any(_utc(b.start_time) <= now < _utc(b.end_time)
                     and b.status == BookingStatus.CONFIRMED for b in lb)
        future = sorted((b for b in lb if _utc(b.start_time) > now
                         and b.status == BookingStatus.CONFIRMED),
                        key=lambda b: b.start_time)
        today = sum(1 for b in lb if _utc(b.start_time) < day_end
                    and _utc(b.end_time) > day_start)
        controller = next((d for d in devices if d.lab_id == lab.id and
                           d.device_type == DeviceType.MASTER_CONTROLLER), None)
        out.append(LabOverview(
            lab=LabOut.model_validate(lab),
            occupied=active or occupants[lab.id] > 0,
            occupants=occupants[lab.id],
            available_now=lab.is_active and not active,
            controller_online=is_fresh(controller, now) if controller else None,
            door_closed=controller.door_closed if controller else None,
            next_booking_at=future[0].start_time if future else None,
            bookings_today=today,
            open_issues=open_issues[lab.id],
            high_priority_issues=high[lab.id],
        ))
    return out


@router.post("", response_model=LabOut, status_code=status.HTTP_201_CREATED)
def create_lab(req: LabCreate, db: Session = Depends(get_db),
               _: User = Depends(require_admin)):
    if db.scalar(select(Lab).where(Lab.code == req.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Lab code already exists")
    lab = Lab(**req.model_dump())
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab


@router.get("/{lab_id}", response_model=LabStatus)
def lab_detail(lab_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")

    close_expired(db)
    refresh_liveness(db)
    now = datetime.now(timezone.utc)

    confirmed = db.scalars(select(Booking).where(
        Booking.lab_id == lab.id,
        Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.PENDING]),
        Booking.end_time > now).order_by(Booking.start_time)).all()
    current = next((b for b in confirmed
                    if b.status == BookingStatus.CONFIRMED
                    and _utc(b.start_time) <= now <= _utc(b.end_time)), None)
    upcoming = [b for b in confirmed if _utc(b.start_time) > now][:6]
    next_b = next((b for b in upcoming
                   if b.status == BookingStatus.CONFIRMED), None)

    occupants = db.scalars(
        select(AccessSession).where(AccessSession.lab_id == lab.id,
                                    AccessSession.ended_at.is_(None))).all()
    # Who is inside is personal data: staff see names, everyone else a count.
    names = []
    if _staff(user):
        for s in occupants:
            u = db.get(User, s.user_id)
            if u:
                names.append(u.full_name)

    devices = db.scalars(select(Device).where(Device.lab_id == lab.id)
                         .order_by(Device.device_type)).all()
    controller = next((d for d in devices
                       if d.device_type == DeviceType.MASTER_CONTROLLER), None)
    camera = next((d for d in devices if d.device_type == DeviceType.CAMERA), None)

    issues = db.scalars(select(Issue).where(
        Issue.lab_id == lab.id, Issue.status.in_(ACTIVE))
        .order_by(desc(Issue.created_at))).all()

    return LabStatus(
        lab=LabOut.model_validate(lab),
        occupied=current is not None or bool(occupants),
        occupants=len(occupants),
        current_booking_id=current.id if current and (
            _staff(user) or current.user_id == user.id) else None,
        current_users=names,
        door_closed=controller.door_closed if controller else None,
        controller_online=is_fresh(controller, now) if controller else None,
        camera_online=is_fresh(camera, now) if camera else None,
        next_booking_at=next_b.start_time if next_b else None,
        current_booking=_slot(db, current, user) if current else None,
        upcoming=[_slot(db, b, user) for b in upcoming],
        devices=[device_out(d, lab.code, now) for d in devices],
        open_issues=len(issues),
        high_priority_issues=sum(1 for i in issues if i.severity in _HIGH),
        recent_issues=[_brief(db, i, user) for i in issues[:5]],
    )


def _brief(db: Session, i: Issue, viewer: User) -> LabIssueBrief:
    asset = db.get(Asset, i.asset_id) if i.asset_id else None
    return LabIssueBrief(id=i.id, ticket_number=i.ticket_number, title=i.title,
                         category=i.category, severity=i.severity,
                         status=i.status, asset_name=asset.name if asset else None,
                         created_at=i.created_at,
                         is_mine=i.reporter_id == viewer.id)


@router.get("/{lab_id}/availability", response_model=list[BookingSlot])
def lab_availability(lab_id: int, start: datetime, end: datetime,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """
    Reserved intervals in [start, end), for the booking picker.

    A student must see that 14:00-16:00 is taken without learning by whom -
    so identity is returned only for the caller's own bookings or to staff.
    Before this endpoint the picker read the student's own booking list,
    which never contains anyone else's reservation, so taken hours showed as
    free until the server refused the booking.
    """
    if db.get(Lab, lab_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")
    start, end = _utc(start), _utc(end)
    if end <= start or end - start > timedelta(days=31):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Range must be positive and at most 31 days")
    rows = db.scalars(select(Booking).where(
        Booking.lab_id == lab_id,
        Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.PENDING]),
        Booking.start_time < end, Booking.end_time > start)
        .order_by(Booking.start_time)).all()
    return [_slot(db, b, user) for b in rows]


@router.get("/{lab_id}/activity", response_model=list[EventOut])
def lab_activity(lab_id: int, limit: int = Query(80, le=500),
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """
    The lab's event timeline. Staff see all of it; a student sees only their
    own events here, the same rule /access-events applies - the lab page is
    not a way around it.
    """
    stmt = select(AccessEvent).where(AccessEvent.lab_id == lab_id)
    if not _staff(user):
        stmt = stmt.where(AccessEvent.user_id == user.id)
    rows = db.scalars(stmt.order_by(desc(AccessEvent.created_at))
                      .limit(limit)).all()
    lab = db.get(Lab, lab_id)
    out = []
    for e in rows:
        item = EventOut.model_validate(e)
        if e.user_id:
            u = db.get(User, e.user_id)
            item.user_name = u.full_name if u else None
        if e.device_id:
            d = db.get(Device, e.device_id)
            item.device_name = d.name if d else None
        item.lab_code = lab.code if lab else None
        out.append(item)
    return out


@router.get("/{lab_id}/issues", response_model=list[LabIssueBrief])
def lab_issues(lab_id: int, active: bool = True,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """Open problems in a lab: titles and states, never who reported them."""
    stmt = select(Issue).where(Issue.lab_id == lab_id)
    if active:
        stmt = stmt.where(Issue.status.in_(ACTIVE))
    rows = db.scalars(stmt.order_by(desc(Issue.created_at)).limit(50)).all()
    return [_brief(db, i, user) for i in rows]


@router.get("/{lab_id}/sensors", response_model=list[SensorReadingOut])
def lab_sensors(lab_id: int, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    """
    Returns whatever real readings exist - which is an empty list until a
    sensor node is actually deployed. Nothing here fabricates values.
    """
    return db.scalars(
        select(SensorReading).where(SensorReading.lab_id == lab_id)
        .order_by(desc(SensorReading.recorded_at)).limit(200)).all()
