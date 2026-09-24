"""
Booking lifecycle and QR token issuance.

The rule that matters: a token's validity window is copied from the booking
at issue time, and the token is re-checked against the LIVE booking on every
scan. Copying alone would let a cancelled booking keep working; checking the
live booking alone would lose the record of what was issued. Both.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_qr_token
from app.models import (Booking, BookingStatus, EventType, Lab, QrToken, User,
                        AuthMethod)
from app.services.events import log_event
from app.services.notifications import notify


class BookingError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def find_conflicts(db: Session, lab_id: int, start: datetime, end: datetime,
                   exclude_booking_id: Optional[int] = None) -> Sequence[Booking]:
    """
    Overlap test: two intervals overlap when each starts before the other ends.
    Touching endpoints (one ends exactly when the next starts) is NOT a
    conflict, which is why the comparisons are strict.
    """
    stmt = select(Booking).where(
        Booking.lab_id == lab_id,
        Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
        and_(Booking.start_time < end, Booking.end_time > start),
    )
    if exclude_booking_id is not None:
        stmt = stmt.where(Booking.id != exclude_booking_id)
    return db.scalars(stmt).all()


def create_booking(db: Session, user: User, lab: Lab, start: datetime,
                   end: datetime, reason: str,
                   actor: Optional[User] = None) -> Booking:
    start, end = _as_utc(start), _as_utc(end)

    if start >= end:
        raise BookingError("INVALID_WINDOW", "Start time must be before end time.")

    if end <= datetime.now(timezone.utc):
        raise BookingError("IN_THE_PAST", "Booking window is already over.")

    max_delta = timedelta(hours=settings.MAX_BOOKING_HOURS)
    if end - start > max_delta:
        raise BookingError(
            "TOO_LONG",
            f"Maximum booking length is {settings.MAX_BOOKING_HOURS} hours.")

    if not lab.is_active:
        raise BookingError("LAB_INACTIVE", "This laboratory is not bookable.")

    if lab.exclusive_booking:
        conflicts = find_conflicts(db, lab.id, start, end)
        if conflicts:
            c = conflicts[0]
            raise BookingError(
                "CONFLICT",
                f"Laboratory already booked "
                f"{_as_utc(c.start_time):%H:%M}-{_as_utc(c.end_time):%H:%M} "
                f"on {_as_utc(c.start_time):%Y-%m-%d}.")

    booking = Booking(user_id=user.id, lab_id=lab.id, start_time=start,
                      end_time=end, reason=reason,
                      status=BookingStatus.PENDING)
    db.add(booking)
    db.flush()

    on_behalf = actor is not None and actor.id != user.id
    log_event(db, EventType.BOOKING_CREATED, lab_id=lab.id, user_id=user.id,
              booking_id=booking.id, method=AuthMethod.PORTAL,
              message=(f"{actor.full_name} booked {lab.name} for {user.full_name}"
                       if on_behalf else f"{user.full_name} requested {lab.name}"))

    if settings.BOOKING_AUTO_APPROVE:
        confirm_booking(db, booking, issue_token=True)

    db.commit()
    db.refresh(booking)
    return booking


def confirm_booking(db: Session, booking: Booking,
                    issue_token: bool = True) -> Optional[QrToken]:
    booking.status = BookingStatus.CONFIRMED
    log_event(db, EventType.BOOKING_CONFIRMED, lab_id=booking.lab_id,
              user_id=booking.user_id, booking_id=booking.id,
              method=AuthMethod.PORTAL, message="Booking confirmed")
    token = issue_token_for(db, booking) if issue_token else None
    lab = db.get(Lab, booking.lab_id)
    start = _as_utc(booking.start_time)
    notify(db, [booking.user_id], "BOOKING_CONFIRMED",
           f"Booking confirmed - {lab.code if lab else 'laboratory'}",
           body=f"{lab.name if lab else ''}, {start:%d %b %Y}. Your access "
                f"credential is ready.",
           link=f"/bookings/{booking.id}", booking_id=booking.id)
    db.flush()
    return token


def reject_booking(db: Session, booking: Booking, actor: User,
                   reason: str = "") -> None:
    """A pending request refused by staff. Any credential dies with it."""
    now = datetime.now(timezone.utc)
    booking.status = BookingStatus.REJECTED
    for t in db.scalars(select(QrToken).where(
            QrToken.booking_id == booking.id,
            QrToken.revoked_at.is_(None))).all():
        t.revoked_at = now
    log_event(db, EventType.BOOKING_CANCELLED, lab_id=booking.lab_id,
              user_id=booking.user_id, booking_id=booking.id,
              method=AuthMethod.PORTAL,
              message=f"Rejected by {actor.full_name}"
                      + (f": {reason}" if reason else ""))
    lab = db.get(Lab, booking.lab_id)
    notify(db, [booking.user_id], "BOOKING_REJECTED",
           f"Booking request declined - {lab.code if lab else ''}",
           body=reason or "Laboratory staff declined this booking request.",
           link=f"/bookings/{booking.id}", booking_id=booking.id,
           severity="warning", exclude=actor.id)
    db.commit()


def issue_token_for(db: Session, booking: Booking) -> QrToken:
    """
    Issue the door credential. Any previously issued token for this booking is
    revoked first, so there is never more than one live credential per
    booking - re-issuing is therefore also the way to invalidate a QR the
    student has already shared with someone else.
    """
    existing = db.scalars(select(QrToken).where(
        QrToken.booking_id == booking.id,
        QrToken.revoked_at.is_(None))).all()
    now = datetime.now(timezone.utc)
    for t in existing:
        t.revoked_at = now

    token = QrToken(
        token=generate_qr_token(),
        booking_id=booking.id,
        user_id=booking.user_id,
        lab_id=booking.lab_id,
        valid_from=booking.start_time,
        valid_until=booking.end_time,
    )
    db.add(token)
    db.flush()

    log_event(db, EventType.QR_GENERATED, lab_id=booking.lab_id,
              user_id=booking.user_id, booking_id=booking.id,
              method=AuthMethod.PORTAL,
              message="Access token issued",
              metadata={"valid_from": _as_utc(booking.start_time).isoformat(),
                        "valid_until": _as_utc(booking.end_time).isoformat()})
    return token


def cancel_booking(db: Session, booking: Booking, actor: User) -> None:
    """
    Cancelling revokes the credential immediately. Leaving the token live
    would mean a cancelled booking still opened the door until its window
    elapsed, which is the whole failure this system exists to prevent.
    """
    now = datetime.now(timezone.utc)
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = now

    for t in db.scalars(select(QrToken).where(
            QrToken.booking_id == booking.id,
            QrToken.revoked_at.is_(None))).all():
        t.revoked_at = now

    log_event(db, EventType.BOOKING_CANCELLED, lab_id=booking.lab_id,
              user_id=booking.user_id, booking_id=booking.id,
              method=AuthMethod.PORTAL,
              message=f"Cancelled by {actor.full_name}")
    # Somebody else cancelling your booking is news; cancelling your own
    # is not.
    lab = db.get(Lab, booking.lab_id)
    notify(db, [booking.user_id], "BOOKING_CANCELLED",
           f"Booking cancelled - {lab.code if lab else ''}",
           body=f"Cancelled by {actor.full_name}. The access credential has "
                f"been revoked.",
           link=f"/bookings/{booking.id}", booking_id=booking.id,
           severity="warning", exclude=actor.id)
    db.commit()


def active_token(db: Session, booking_id: int) -> Optional[QrToken]:
    return db.scalar(select(QrToken).where(
        QrToken.booking_id == booking_id,
        QrToken.revoked_at.is_(None)).order_by(QrToken.issued_at.desc()))
