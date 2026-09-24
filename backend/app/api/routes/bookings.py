"""
Bookings and the QR credential page.

Ownership is enforced on every route: a student can only ever see and act on
their own bookings. Staff and admins see everything.
"""
import base64
import io
from datetime import datetime, timezone

import qrcode
from qrcode.constants import ERROR_CORRECT_Q
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_staff
from app.db.session import get_db
from app.models import (AccessSession, Booking, BookingStatus, Lab, Role,
                        User)
from app.schemas import BookingCreate, BookingOut, QrOut, SessionOut
from app.services.booking import (BookingError, active_token, cancel_booking,
                                  confirm_booking, create_booking)

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def _decorate(db: Session, b: Booking) -> BookingOut:
    out = BookingOut.model_validate(b)
    lab = db.get(Lab, b.lab_id)
    user = db.get(User, b.user_id)
    out.lab_name = lab.name if lab else None
    out.lab_code = lab.code if lab else None
    out.lab_category = lab.category if lab else None
    out.user_name = user.full_name if user else None
    out.user_email = user.email if user else None

    # Punctuality, computed rather than stored: derived values go stale the
    # moment either input changes.
    if b.first_entry_at is not None:
        delta = _utc(b.first_entry_at) - _utc(b.start_time)
        out.entry_delay_minutes = int(delta.total_seconds() // 60)

    # An open session means somebody walked in and the door has not registered
    # them leaving. Derived from access_sessions rather than stored on the
    # booking, so it cannot drift out of step with the door's own record.
    out.currently_inside = db.scalar(
        select(AccessSession.id).where(
            AccessSession.booking_id == b.id,
            AccessSession.ended_at.is_(None))) is not None
    return out


def _owned_or_staff(booking: Booking, user: User) -> None:
    if user.role == Role.STUDENT and booking.user_id != user.id:
        # 404 rather than 403: confirming that a booking exists is itself
        # information a student should not have about someone else.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create(req: BookingCreate, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    lab = db.get(Lab, req.lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")
    try:
        booking = create_booking(db, user, lab, req.start_time, req.end_time,
                                 req.reason)
    except BookingError as e:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail={"code": e.code, "message": e.message})
    return _decorate(db, booking)


@router.get("", response_model=list[BookingOut])
def list_bookings(db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    stmt = select(Booking).order_by(desc(Booking.start_time))
    if user.role == Role.STUDENT:
        stmt = stmt.where(Booking.user_id == user.id)
    return [_decorate(db, b) for b in db.scalars(stmt).all()]


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    _owned_or_staff(b, user)
    return _decorate(db, b)


@router.post("/{booking_id}/confirm", response_model=BookingOut)
def confirm(booking_id: int, db: Session = Depends(get_db),
            _: User = Depends(require_staff)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if b.status == BookingStatus.CANCELLED:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Cancelled bookings cannot be confirmed")
    confirm_booking(db, b, issue_token=True)
    db.commit()
    db.refresh(b)
    return _decorate(db, b)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel(booking_id: int, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    _owned_or_staff(b, user)
    cancel_booking(db, b, user)
    db.refresh(b)
    return _decorate(db, b)


@router.get("/{booking_id}/qr", response_model=QrOut)
def booking_qr(booking_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """
    Render the booking's door credential.

    QR settings are chosen for the ESP32-CAM, not for looks: error correction
    level Q (25% recoverable) survives glare and a phone's own pixel grid, and
    box_size 10 with a 4-module quiet zone gives a large, high-contrast target.
    The quiet zone is not decoration - OpenCV's detector needs the white
    margin to find the finder patterns at all.
    """
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    _owned_or_staff(b, user)

    token = active_token(db, b.id)
    if token is None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "No active credential for this booking")

    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q,
                       box_size=10, border=4)
    qr.add_data(token.token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_b64 = base64.b64encode(buf.getvalue()).decode()

    now = datetime.now(timezone.utc)
    currently_valid = (
        b.status == BookingStatus.CONFIRMED
        and token.revoked_at is None
        and _utc(token.valid_from) <= now <= _utc(token.valid_until)
    )

    lab = db.get(Lab, b.lab_id)
    return QrOut(
        booking_id=b.id, token=token.token, qr_png_base64=png_b64,
        valid_from=token.valid_from, valid_until=token.valid_until,
        status=b.status, lab_code=lab.code if lab else "",
        lab_name=lab.name if lab else "",
        is_currently_valid=currently_valid,
    )


@router.get("/{booking_id}/sessions", response_model=list[SessionOut])
def booking_sessions(booking_id: int, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """
    When this booking was ACTUALLY used.

    A booking of 14:00-16:00 with an entry at 14:16 and an exit at 15:02 is
    three different facts, and a laboratory record that only stores the first
    one cannot answer who was in the room when something happened.
    """
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    _owned_or_staff(b, user)

    rows = db.scalars(
        select(AccessSession)
        .where(AccessSession.booking_id == booking_id)
        .order_by(AccessSession.started_at)).all()

    out = []
    for srow in rows:
        item = SessionOut.model_validate(srow)
        u = db.get(User, srow.user_id)
        lab = db.get(Lab, srow.lab_id)
        item.user_name = u.full_name if u else None
        item.lab_code = lab.code if lab else None
        if srow.ended_at is not None:
            item.duration_minutes = int(
                (_utc(srow.ended_at) - _utc(srow.started_at)).total_seconds() // 60)
        out.append(item)
    return out
