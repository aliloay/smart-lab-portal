"""
Access authorization. This module is the security boundary of the whole
system: the ESP32 asks it a question and gets a yes or a no.

Two principles govern everything here.

FAIL CLOSED. Every path that cannot positively establish authorization
returns a denial with a named reason. There is no branch that falls through
to "allow" - not for an unknown token, not for a missing booking, not for a
malformed request.

THE BACKEND NEVER OPENS THE DOOR. It returns an identity; the master decides.
The relay is driven by exactly one line of firmware and no network message
reaches it. A compromised backend can refuse entry, but it cannot grant it
without the biometric second factor passing on the device itself.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (AccessAttempt, AccessResult, AuthMethod, Booking,
                        BookingStatus, DenialReason, Device, EventType, Lab,
                        QrToken, RfidCredential, User)
from app.services.events import log_event


@dataclass
class ValidationResult:
    valid: bool
    reason: Optional[DenialReason] = None
    user: Optional[User] = None
    booking: Optional[Booking] = None
    lab: Optional[Lab] = None
    token: Optional[QrToken] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """
    Postgres returns timezone-aware datetimes, but a value that has been
    round-tripped through a naive source could arrive without tzinfo.
    Comparing naive and aware datetimes raises; treating a naive value as UTC
    is the only safe interpretation here because that is how we store them.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_lab_by_code(db: Session, lab_code: str) -> Optional[Lab]:
    return db.scalar(select(Lab).where(Lab.code == lab_code))


def get_device(db: Session, device_uid: Optional[str]) -> Optional[Device]:
    if not device_uid:
        return None
    return db.scalar(select(Device).where(Device.device_uid == device_uid))


# ---------------------------------------------------------------------------
# QR validation
# ---------------------------------------------------------------------------
def validate_qr(db: Session, token_value: str, lab_code: str,
                device_uid: Optional[str] = None) -> ValidationResult:
    """
    Validate a booking QR token presented at a specific laboratory door.

    Checks run in a deliberate order: cheap identity lookups first, then
    relationship checks, then the time window last. The order matters for the
    audit log - 'WRONG_LAB' is more informative than 'BOOKING_EXPIRED' when
    both are true, because it tells you someone took a credential somewhere
    it was never meant to go.
    """
    lab = get_lab_by_code(db, lab_code)
    device = get_device(db, device_uid)

    # An unknown lab code means the device is misconfigured or lying.
    if lab is None:
        _record(db, None, device, None, None, AuthMethod.QR,
                AccessResult.DENIED, DenialReason.DEVICE_UNKNOWN,
                credential_ref=_ref(token_value))
        db.commit()
        return ValidationResult(False, DenialReason.DEVICE_UNKNOWN)

    token = db.scalar(select(QrToken).where(QrToken.token == token_value))
    if token is None:
        _record(db, lab, device, None, None, AuthMethod.QR,
                AccessResult.DENIED, DenialReason.TOKEN_UNKNOWN,
                credential_ref=_ref(token_value))
        log_event(db, EventType.QR_REJECTED, lab_id=lab.id,
                  device_id=device.id if device else None,
                  method=AuthMethod.QR, result=AccessResult.DENIED,
                  reason=DenialReason.TOKEN_UNKNOWN.value,
                  message="Unknown QR token presented")
        db.commit()
        return ValidationResult(False, DenialReason.TOKEN_UNKNOWN)

    booking = db.get(Booking, token.booking_id)
    user = db.get(User, token.user_id)

    def deny(reason: DenialReason) -> ValidationResult:
        _record(db, lab, device, user, booking, AuthMethod.QR,
                AccessResult.DENIED, reason, credential_ref=_ref(token_value))
        log_event(db, EventType.QR_REJECTED, lab_id=lab.id,
                  user_id=user.id if user else None,
                  booking_id=booking.id if booking else None,
                  device_id=device.id if device else None,
                  method=AuthMethod.QR, result=AccessResult.DENIED,
                  reason=reason.value,
                  message=f"QR rejected: {reason.value}")
        # COMMIT. Without this the attempt row and the QR_REJECTED event are
        # staged and then thrown away when the request ends, so every refused
        # scan would vanish from the audit trail - the one record you most
        # need after an incident.
        db.commit()
        return ValidationResult(False, reason, user=user, booking=booking,
                                lab=lab, token=token)

    if token.revoked_at is not None:
        return deny(DenialReason.TOKEN_REVOKED)

    if booking is None:
        return deny(DenialReason.TOKEN_UNKNOWN)

    # The token is bound to a laboratory. Showing it at another door fails
    # even inside its own time window.
    if token.lab_id != lab.id or booking.lab_id != lab.id:
        return deny(DenialReason.WRONG_LAB)

    if booking.status == BookingStatus.CANCELLED:
        return deny(DenialReason.BOOKING_CANCELLED)

    if booking.status != BookingStatus.CONFIRMED:
        return deny(DenialReason.BOOKING_NOT_CONFIRMED)

    if user is None or not user.is_active:
        return deny(DenialReason.USER_INACTIVE)

    # Time window last. Grace is explicit and configurable rather than a
    # magic number buried in the comparison.
    now = _now()
    grace = timedelta(minutes=settings.BOOKING_GRACE_MINUTES)
    if now < _as_utc(token.valid_from) - grace:
        return deny(DenialReason.BOOKING_NOT_STARTED)
    if now > _as_utc(token.valid_until) + grace:
        return deny(DenialReason.BOOKING_EXPIRED)

    # Accepted. Record the use, but do NOT mark anything as consumed: the
    # token is valid for the whole window, and the door may legitimately be
    # opened more than once during a booking.
    token.last_used_at = now
    token.use_count += 1

    _record(db, lab, device, user, booking, AuthMethod.QR,
            AccessResult.PENDING, None, credential_ref=_ref(token_value))
    log_event(db, EventType.QR_VALIDATED, lab_id=lab.id, user_id=user.id,
              booking_id=booking.id, device_id=device.id if device else None,
              method=AuthMethod.QR, result=AccessResult.PENDING,
              message=f"QR validated for {user.full_name} - awaiting biometric")
    db.commit()
    return ValidationResult(True, None, user=user, booking=booking, lab=lab,
                            token=token)


# ---------------------------------------------------------------------------
# RFID validation
# ---------------------------------------------------------------------------
def validate_rfid(db: Session, uid_hex: str, lab_code: str,
                  device_uid: Optional[str] = None) -> ValidationResult:
    """
    RFID as step 1.

    By default a lab does NOT require a booking for RFID: that preserves the
    existing local behaviour exactly, so the door keeps working the way it
    already does. A lab can opt in with require_booking_for_rfid, which is how
    a restricted lab would be configured.
    """
    lab = get_lab_by_code(db, lab_code)
    device = get_device(db, device_uid)

    if lab is None:
        _record(db, None, device, None, None, AuthMethod.RFID,
                AccessResult.DENIED, DenialReason.DEVICE_UNKNOWN,
                credential_ref=_ref(uid_hex))
        db.commit()
        return ValidationResult(False, DenialReason.DEVICE_UNKNOWN)

    cred = db.scalar(select(RfidCredential)
                     .where(RfidCredential.uid_hex == uid_hex.upper()))

    def deny(reason: DenialReason, user=None, booking=None) -> ValidationResult:
        _record(db, lab, device, user, booking, AuthMethod.RFID,
                AccessResult.DENIED, reason, credential_ref=_ref(uid_hex))
        log_event(db, EventType.RFID_REJECTED, lab_id=lab.id,
                  user_id=user.id if user else None,
                  device_id=device.id if device else None,
                  method=AuthMethod.RFID, result=AccessResult.DENIED,
                  reason=reason.value, message=f"RFID rejected: {reason.value}")
        db.commit()
        return ValidationResult(False, reason, user=user, lab=lab)

    if cred is None or not cred.is_active or cred.revoked_at is not None:
        return deny(DenialReason.UNKNOWN_CREDENTIAL)

    user = db.get(User, cred.user_id)
    if user is None or not user.is_active:
        return deny(DenialReason.USER_INACTIVE, user=user)

    booking = None
    if lab.require_booking_for_rfid:
        booking = _active_booking(db, user.id, lab.id)
        if booking is None:
            return deny(DenialReason.NO_ACTIVE_BOOKING, user=user)
    else:
        # Still attach a booking when one happens to be active, so the event
        # timeline can relate the entry to it.
        booking = _active_booking(db, user.id, lab.id)

    _record(db, lab, device, user, booking, AuthMethod.RFID,
            AccessResult.PENDING, None, credential_ref=_ref(uid_hex))
    log_event(db, EventType.RFID_ACCEPTED, lab_id=lab.id, user_id=user.id,
              booking_id=booking.id if booking else None,
              device_id=device.id if device else None,
              method=AuthMethod.RFID, result=AccessResult.PENDING,
              message=f"RFID accepted for {user.full_name} - awaiting biometric")
    db.commit()
    return ValidationResult(True, None, user=user, booking=booking, lab=lab)


def _active_booking(db: Session, user_id: int, lab_id: int) -> Optional[Booking]:
    now = _now()
    grace = timedelta(minutes=settings.BOOKING_GRACE_MINUTES)
    rows = db.scalars(
        select(Booking).where(
            Booking.user_id == user_id,
            Booking.lab_id == lab_id,
            Booking.status == BookingStatus.CONFIRMED,
        )
    ).all()
    for b in rows:
        if _as_utc(b.start_time) - grace <= now <= _as_utc(b.end_time) + grace:
            return b
    return None


# ---------------------------------------------------------------------------
def _ref(credential: str) -> str:
    """
    A short, non-reversible-enough reference for forensics. Storing the whole
    token would put a working credential in the log table; storing nothing
    would make an incident untraceable. The first 10 characters identify the
    row without being usable on their own.
    """
    return credential[:10] + "..." if len(credential) > 10 else credential


def _record(db: Session, lab, device, user, booking, method: AuthMethod,
            result: AccessResult, reason: Optional[DenialReason],
            credential_ref: Optional[str] = None) -> None:
    db.add(AccessAttempt(
        lab_id=lab.id if lab else None,
        device_id=device.id if device else None,
        user_id=user.id if user else None,
        booking_id=booking.id if booking else None,
        method=method, result=result, denial_reason=reason,
        credential_ref=credential_ref,
    ))
