"""
Occupancy sessions: when somebody was actually inside a laboratory.

The physical door reports three things about an entry: access was granted,
the door opened, the door closed behind the person. It does not report the
person leaving - there is no exit reader. So:

  * the door cycle is recorded ON the session (door_opened_at,
    door_closed_at) and never ends it;
  * a session ends with an observed exit (EXIT_RECORDED), or because the
    booking window closed, or because the door was unlocked and never
    opened, or because the same person entered again;
  * only EXIT_RECORDED is ever presented as an exit time. Every other end
    reason is shown as what it is.

This replaces the earlier rule that the door closing ended the session,
which made every visit look a few seconds long.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (AccessSession, AuthMethod, Booking, SessionEndReason,
                        User)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def open_session(db: Session, *, lab_id: int, user_id: int,
                 booking_id: Optional[int], device_id: Optional[int],
                 method: AuthMethod) -> AccessSession:
    now = datetime.now(timezone.utc)
    # A second entry by the same person closes the first: they cannot be
    # inside twice.
    for s in db.scalars(select(AccessSession).where(
            AccessSession.lab_id == lab_id,
            AccessSession.user_id == user_id,
            AccessSession.ended_at.is_(None))).all():
        s.ended_at = now
        s.end_reason = SessionEndReason.SUPERSEDED
    s = AccessSession(lab_id=lab_id, user_id=user_id, booking_id=booking_id,
                      device_id=device_id, entry_method=method, started_at=now)
    db.add(s)
    return s


def _latest_open(db: Session, lab_id: int,
                 user: Optional[User]) -> Optional[AccessSession]:
    stmt = select(AccessSession).where(AccessSession.lab_id == lab_id,
                                       AccessSession.ended_at.is_(None))
    if user is not None:
        stmt = stmt.where(AccessSession.user_id == user.id)
    return db.scalar(stmt.order_by(AccessSession.started_at.desc()))


def record_door_opened(db: Session, lab_id: int, user: Optional[User]) -> None:
    s = _latest_open(db, lab_id, user)
    if s is not None and s.door_opened_at is None:
        s.door_opened_at = datetime.now(timezone.utc)


def record_door_closed(db: Session, lab_id: int, user: Optional[User]) -> None:
    s = _latest_open(db, lab_id, user)
    if s is None or s.door_closed_at is not None:
        return
    now = datetime.now(timezone.utc)
    if s.door_opened_at is None:
        # Unlocked, then relocked after the hold time without the door ever
        # opening: nobody went in.
        s.ended_at = now
        s.end_reason = SessionEndReason.DOOR_NOT_OPENED
    else:
        s.door_closed_at = now


def record_exit(db: Session, lab_id: int, user: Optional[User]) -> bool:
    if user is None:
        return False
    s = _latest_open(db, lab_id, user)
    if s is None:
        return False
    s.ended_at = datetime.now(timezone.utc)
    s.end_reason = SessionEndReason.EXIT_RECORDED
    return True


def second_factor_seen(db: Session, lab_id: int, user: Optional[User],
                       method: Optional[AuthMethod]) -> None:
    """Attach the biometric that completed step 2 to the open session."""
    if user is None or method not in (AuthMethod.FACE, AuthMethod.FINGERPRINT):
        return
    s = _latest_open(db, lab_id, user)
    if s is not None and s.second_factor is None:
        s.second_factor = method


def close_expired(db: Session) -> int:
    """
    Stop counting sessions whose booking window has closed, and sessions with
    no booking that have outlived the longest possible booking. Commits only
    when something changed.
    """
    now = datetime.now(timezone.utc)
    changed = 0
    open_rows = db.scalars(select(AccessSession).where(
        AccessSession.ended_at.is_(None))).all()
    for s in open_rows:
        if s.booking_id is not None:
            b = db.get(Booking, s.booking_id)
            if b is not None and _utc(b.end_time) < now:
                s.ended_at = max(_utc(b.end_time), _utc(s.started_at))
                s.end_reason = SessionEndReason.BOOKING_ENDED
                changed += 1
                continue
        cutoff = _utc(s.started_at) + timedelta(hours=settings.MAX_BOOKING_HOURS)
        if s.booking_id is None and cutoff < now:
            s.ended_at = cutoff
            s.end_reason = SessionEndReason.NO_EXIT_TIMEOUT
            changed += 1
    if changed:
        db.commit()
    return changed


def duration_minutes(s: AccessSession) -> Optional[int]:
    """Only an observed exit yields a duration inside the room."""
    if s.ended_at is None or s.end_reason != SessionEndReason.EXIT_RECORDED:
        return None
    return int((_utc(s.ended_at) - _utc(s.started_at)).total_seconds() // 60)
