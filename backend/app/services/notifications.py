"""
In-portal notifications.

Every notification is raised by a real state change and addressed to a real
person. Nothing here invents a message to make a bell icon look busy. There
is no email or SMS provider configured, so the portal is the only channel.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (Booking, BookingStatus, Lab, Notification, Role, User)
from app.services.events import queue_message


def notify(db: Session, user_ids: Iterable[int], kind: str, title: str, *,
           body: str = "", link: Optional[str] = None, severity: str = "info",
           issue_id: Optional[int] = None,
           booking_id: Optional[int] = None,
           exclude: Optional[int] = None,
           dedupe_key: Optional[str] = None) -> list[Notification]:
    """
    Stage one notification per recipient. `exclude` drops the person who
    caused the change - nobody needs to be told about their own action.
    With `dedupe_key`, a recipient who already has a notification with that
    key is skipped, so a retried automation run delivers exactly once.
    """
    rows: list[Notification] = []
    already: set[int] = set()
    if dedupe_key:
        already = set(db.scalars(select(Notification.user_id).where(
            Notification.dedupe_key == dedupe_key)).all())
    for uid in dict.fromkeys(user_ids):      # de-duplicate, keep order
        if uid is None or uid == exclude or uid in already:
            continue
        n = Notification(user_id=uid, kind=kind, title=title[:160],
                         body=body[:500], link=link, severity=severity,
                         issue_id=issue_id, booking_id=booking_id,
                         created_at=datetime.now(timezone.utc),
                         dedupe_key=dedupe_key)
        db.add(n)
        rows.append(n)
    if rows:
        db.flush()
        for n in rows:
            queue_message(db, {"type": "notification", "user_id": n.user_id,
                               "notification": serialize(n)})
    return rows


def serialize(n: Notification) -> dict:
    return {
        "id": n.id, "kind": n.kind, "severity": n.severity, "title": n.title,
        "body": n.body, "link": n.link, "issue_id": n.issue_id,
        "booking_id": n.booking_id, "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


def staff_ids(db: Session) -> list[int]:
    return list(db.scalars(select(User.id).where(
        User.role.in_([Role.ADMIN, Role.LAB_STAFF]),
        User.is_active.is_(True))).all())


def admin_ids(db: Session) -> list[int]:
    return list(db.scalars(select(User.id).where(
        User.role == Role.ADMIN, User.is_active.is_(True))).all())


def booking_reminder(db: Session, b: Booking,
                     now: Optional[datetime] = None) -> bool:
    """
    Raise the reminder for one booking, once. Shared by the lazy path below
    and by the automation API, so n8n and the portal can never both send it.
    """
    now = now or datetime.now(timezone.utc)
    exists = db.scalar(select(Notification.id).where(
        Notification.user_id == b.user_id,
        Notification.kind == "BOOKING_REMINDER",
        Notification.booking_id == b.id))
    if exists:
        return False
    lab = db.get(Lab, b.lab_id)
    start = b.start_time if b.start_time.tzinfo else \
        b.start_time.replace(tzinfo=timezone.utc)
    minutes = max(1, int((start - now).total_seconds() // 60))
    return bool(notify(db, [b.user_id], "BOOKING_REMINDER",
                       f"Your booking starts in {minutes} min",
                       body=f"{lab.name if lab else 'Laboratory'} - your access "
                            f"code becomes valid when the window opens.",
                       link=f"/bookings/{b.id}/qr", booking_id=b.id,
                       dedupe_key=f"booking-reminder:{b.id}"))


def ensure_booking_reminders(db: Session, user: User) -> int:
    """
    "Your booking starts in 15 minutes."

    Raised lazily when the person's notifications are read, rather than by a
    scheduler the deployment does not have. It is still a real reminder: it
    only exists once the booking is actually that close, and at most once
    per booking.
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(minutes=settings.BOOKING_REMINDER_MINUTES)
    soon = db.scalars(select(Booking).where(
        Booking.user_id == user.id,
        Booking.status == BookingStatus.CONFIRMED,
        Booking.start_time > now,
        Booking.start_time <= horizon)).all()
    created = sum(1 for b in soon if booking_reminder(db, b, now))
    if created:
        db.commit()
    return created


# Refusals that suggest someone is trying a credential that is not theirs,
# rather than an honest mistake like arriving early.
SECURITY_REASONS = {"IDENTITY_MISMATCH", "UNKNOWN_CREDENTIAL", "TOKEN_UNKNOWN",
                    "WRONG_LAB", "TOKEN_REVOKED"}


def notify_security(db: Session, lab: Optional[Lab], reason: str,
                    detail: str = "") -> None:
    """
    Tell staff and administrators about a security-relevant refusal. At most
    one per laboratory and reason every five minutes, so a burst of attempts
    raises one notification instead of flooding every inbox.
    """
    if reason not in SECURITY_REASONS:
        return
    title = (f"Security event at {lab.code if lab else 'an unknown lab'}: "
             f"{reason.replace('_', ' ').lower()}")
    since = datetime.now(timezone.utc) - timedelta(minutes=5)
    if db.scalar(select(Notification.id).where(
            Notification.kind == "SECURITY_EVENT",
            Notification.title == title[:160],
            Notification.created_at >= since)):
        return
    notify(db, staff_ids(db), "SECURITY_EVENT", title, body=detail,
           link="/admin/access", severity="critical"
           if reason == "IDENTITY_MISMATCH" else "warning")
