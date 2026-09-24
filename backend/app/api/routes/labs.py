"""Laboratories: listing, detail, live status and per-lab activity."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import (AccessEvent, AccessSession, Booking, BookingStatus,
                        Device, DeviceType, Lab, SensorReading, User)
from app.schemas import (EventOut, LabCreate, LabOut, LabStatus,
                         SensorReadingOut)

router = APIRouter(prefix="/labs", tags=["labs"])

# A device that has not been heard from in this long is treated as offline.
DEVICE_STALE_AFTER = timedelta(seconds=90)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


@router.get("", response_model=list[LabOut])
def list_labs(db: Session = Depends(get_db),
              _: User = Depends(get_current_user)):
    return db.scalars(select(Lab).order_by(Lab.code)).all()


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
               _: User = Depends(get_current_user)):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")

    now = datetime.now(timezone.utc)

    current = None
    for b in db.scalars(select(Booking).where(
            Booking.lab_id == lab.id,
            Booking.status == BookingStatus.CONFIRMED)).all():
        if _utc(b.start_time) <= now <= _utc(b.end_time):
            current = b
            break

    next_b = db.scalar(
        select(Booking)
        .where(Booking.lab_id == lab.id,
               Booking.status == BookingStatus.CONFIRMED,
               Booking.start_time > now)
        .order_by(Booking.start_time))

    occupants = db.scalars(
        select(AccessSession).where(AccessSession.lab_id == lab.id,
                                    AccessSession.ended_at.is_(None))).all()
    names = []
    for s in occupants:
        u = db.get(User, s.user_id)
        if u:
            names.append(u.full_name)

    # Device state. None means nothing has reported - the UI shows
    # "No data available" rather than inventing a value.
    controller = db.scalar(select(Device).where(
        Device.lab_id == lab.id,
        Device.device_type == DeviceType.MASTER_CONTROLLER))
    camera = db.scalar(select(Device).where(
        Device.lab_id == lab.id, Device.device_type == DeviceType.CAMERA))

    def online(d: Optional[Device]) -> Optional[bool]:
        if d is None or d.last_seen_at is None:
            return None
        return (now - _utc(d.last_seen_at)) < DEVICE_STALE_AFTER

    return LabStatus(
        lab=LabOut.model_validate(lab),
        occupied=current is not None or bool(names),
        current_booking_id=current.id if current else None,
        current_users=names,
        door_closed=controller.door_closed if controller else None,
        controller_online=online(controller),
        camera_online=online(camera),
        next_booking_at=next_b.start_time if next_b else None,
    )


@router.get("/{lab_id}/activity", response_model=list[EventOut])
def lab_activity(lab_id: int, limit: int = Query(80, le=500),
                 db: Session = Depends(get_db),
                 _: User = Depends(get_current_user)):
    rows = db.scalars(
        select(AccessEvent).where(AccessEvent.lab_id == lab_id)
        .order_by(desc(AccessEvent.created_at)).limit(limit)).all()
    out = []
    for e in rows:
        item = EventOut.model_validate(e)
        if e.user_id:
            u = db.get(User, e.user_id)
            item.user_name = u.full_name if u else None
        out.append(item)
    return out


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
