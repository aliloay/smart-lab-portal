"""
Bookings, the QR credential page, and the booking trace.

Ownership is enforced on every route: a student can only ever see and act on
their own bookings. Staff and admins see everything.
"""
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_staff
from app.db.session import get_db
from app.models import (AccessEvent, AccessSession, Booking, BookingStatus,
                        Lab, QrToken, Role, SessionEndReason, User)
from app.schemas import (BookingCreate, BookingOut, BookingTrace, LabOut,
                         NoteBody, QrOut, SessionOut, TokenInfo, UserBrief)
from app.services.booking import (BookingError, active_token, cancel_booking,
                                  confirm_booking, create_booking,
                                  reject_booking)
from app.services.qr import render_qr_png
from app.services.sessions import close_expired, duration_minutes
from app.services.trace import DOOR_EVENTS, event_out, summarise

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def _staff(u: User) -> bool:
    return u.role in (Role.ADMIN, Role.LAB_STAFF)


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

    sessions = db.scalars(select(AccessSession).where(
        AccessSession.booking_id == b.id)).all()
    # An open session means somebody walked in and has not been seen leaving
    # or had the window close on them. Derived from access_sessions rather
    # than stored on the booking, so it cannot drift from the door's record.
    out.currently_inside = any(s.ended_at is None for s in sessions)
    exits = [s for s in sessions
             if s.end_reason == SessionEndReason.EXIT_RECORDED]
    if exits:
        out.last_exit_at = max(s.ended_at for s in exits)
        out.time_inside_minutes = sum(duration_minutes(s) or 0 for s in exits)

    tok = active_token(db, b.id)
    out.qr_active = (tok is not None and b.status == BookingStatus.CONFIRMED
                     and _utc(b.end_time) > datetime.now(timezone.utc))
    return out


def _owned_or_staff(booking: Booking, user: User) -> None:
    if user.role == Role.STUDENT and booking.user_id != user.id:
        # 404 rather than 403: confirming that a booking exists is itself
        # information a student should not have about someone else.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")


def _get(db: Session, booking_id: int, user: User) -> Booking:
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    _owned_or_staff(b, user)
    return b


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create(req: BookingCreate, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    lab = db.get(Lab, req.lab_id)
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")

    owner = user
    if req.user_id is not None and req.user_id != user.id:
        # Booking for somebody else is an administrative act.
        if not _staff(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Only staff can book on behalf of another user")
        owner = db.get(User, req.user_id)
        if owner is None or not owner.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        booking = create_booking(db, owner, lab, req.start_time, req.end_time,
                                 req.reason, actor=user)
    except BookingError as e:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail={"code": e.code, "message": e.message})
    return _decorate(db, booking)


@router.get("", response_model=list[BookingOut])
def list_bookings(lab_id: Optional[int] = None,
                  user_id: Optional[int] = None,
                  status_: Optional[BookingStatus] = Query(None, alias="status"),
                  start: Optional[datetime] = Query(None, alias="from"),
                  end: Optional[datetime] = Query(None, alias="to"),
                  limit: int = Query(500, le=2000),
                  db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    close_expired(db)
    stmt = select(Booking).order_by(desc(Booking.start_time))
    if user.role == Role.STUDENT:
        stmt = stmt.where(Booking.user_id == user.id)
    elif user_id is not None:
        stmt = stmt.where(Booking.user_id == user_id)
    if lab_id is not None:
        stmt = stmt.where(Booking.lab_id == lab_id)
    if status_ is not None:
        stmt = stmt.where(Booking.status == status_)
    if start is not None:
        stmt = stmt.where(Booking.end_time > start)
    if end is not None:
        stmt = stmt.where(Booking.start_time < end)
    return [_decorate(db, b) for b in db.scalars(stmt.limit(limit)).all()]


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return _decorate(db, _get(db, booking_id, user))


@router.post("/{booking_id}/confirm", response_model=BookingOut)
def confirm(booking_id: int, db: Session = Depends(get_db),
            _: User = Depends(require_staff)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if b.status in (BookingStatus.CANCELLED, BookingStatus.REJECTED):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Cancelled or rejected bookings cannot be confirmed")
    confirm_booking(db, b, issue_token=True)
    db.commit()
    db.refresh(b)
    return _decorate(db, b)


@router.post("/{booking_id}/reject", response_model=BookingOut)
def reject(booking_id: int, req: Optional[NoteBody] = None,
           db: Session = Depends(get_db),
           actor: User = Depends(require_staff)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if b.status != BookingStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Only pending requests can be rejected")
    reject_booking(db, b, actor, req.note if req else "")
    db.refresh(b)
    return _decorate(db, b)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel(booking_id: int, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    b = _get(db, booking_id, user)
    if b.status in (BookingStatus.CANCELLED, BookingStatus.REJECTED):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This booking is already cancelled")
    cancel_booking(db, b, user)
    db.refresh(b)
    return _decorate(db, b)


@router.get("/{booking_id}/qr", response_model=QrOut)
def booking_qr(booking_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """
    Render the booking's door credential.

    How it is drawn, and why every issued token is readable by the door, is
    in app/services/qr.py.
    """
    b = _get(db, booking_id, user)

    token = active_token(db, b.id)
    if token is None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "No active credential for this booking")

    png_b64 = base64.b64encode(render_qr_png(token.token)).decode()

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


def _session_out(db: Session, srow: AccessSession) -> SessionOut:
    item = SessionOut.model_validate(srow)
    u = db.get(User, srow.user_id)
    lab = db.get(Lab, srow.lab_id)
    item.user_name = u.full_name if u else None
    item.lab_code = lab.code if lab else None
    item.duration_minutes = duration_minutes(srow)
    return item


@router.get("/{booking_id}/sessions", response_model=list[SessionOut])
def booking_sessions(booking_id: int, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """
    When this booking was ACTUALLY used.

    A booking of 14:00-16:00 with an entry at 14:16 is two different facts,
    and a laboratory record that only stores the first one cannot answer who
    was in the room when something happened.
    """
    _get(db, booking_id, user)
    close_expired(db)
    rows = db.scalars(
        select(AccessSession)
        .where(AccessSession.booking_id == booking_id)
        .order_by(AccessSession.started_at)).all()
    return [_session_out(db, s) for s in rows]




@router.get("/{booking_id}/trace", response_model=BookingTrace)
def booking_trace(booking_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """
    One booking, end to end: the reservation, the credential, every step at
    the door, and the resulting session - the record needed to demonstrate
    the physical flow and to reconstruct it afterwards.
    """
    b = _get(db, booking_id, user)
    close_expired(db)
    owner = db.get(User, b.user_id)
    lab = db.get(Lab, b.lab_id)

    # Events explicitly attached to the booking, plus this person's door
    # events at this lab during the window (a biometric step is sometimes
    # reported without the booking id).
    margin = timedelta(minutes=30)
    events = db.scalars(select(AccessEvent).where(or_(
        AccessEvent.booking_id == b.id,
        and_(AccessEvent.user_id == b.user_id,
             AccessEvent.lab_id == b.lab_id,
             AccessEvent.booking_id.is_(None),
             AccessEvent.event_type.in_(DOOR_EVENTS),
             AccessEvent.created_at >= _utc(b.start_time) - margin,
             AccessEvent.created_at <= _utc(b.end_time) + margin)))
        .order_by(AccessEvent.created_at)).all()

    ev_out = [event_out(db, e, lab) for e in events]

    sessions = db.scalars(select(AccessSession).where(
        AccessSession.booking_id == b.id)
        .order_by(AccessSession.started_at)).all()
    ses_out = [_session_out(db, s) for s in sessions]

    token = db.scalar(select(QrToken).where(QrToken.booking_id == b.id)
                      .order_by(QrToken.issued_at.desc()))
    tok_out = None
    if token is not None:
        now = datetime.now(timezone.utc)
        state = ("REVOKED" if token.revoked_at is not None
                 else "ISSUED" if now < _utc(token.valid_from)
                 else "EXPIRED" if now > _utc(token.valid_until)
                 else "VALID")
        tok_out = TokenInfo(issued_at=token.issued_at,
                            valid_from=token.valid_from,
                            valid_until=token.valid_until,
                            revoked_at=token.revoked_at,
                            last_used_at=token.last_used_at,
                            use_count=token.use_count, state=state)

    return BookingTrace(
        booking=_decorate(db, b),
        user=UserBrief(id=owner.id, full_name=owner.full_name, role=owner.role,
                       auth_subject=owner.auth_subject),
        lab=LabOut.model_validate(lab),
        token=tok_out,
        summary=summarise(db, events, sessions, owner),
        sessions=ses_out,
        events=ev_out,
    )
