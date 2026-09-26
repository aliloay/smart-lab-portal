"""
Device-facing endpoints. These are what the ESP32 master calls.

Note what is absent: there is no endpoint that opens a door. /grant and /deny
RECORD an outcome the master has already decided. The relay is driven by one
line of firmware and no HTTP request can reach it.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_device
from app.db.session import get_db
from app.models import (AccessEvent, AccessResult, AuthMethod, Booking, Device,
                        DeviceType, EventType, Notification, User)
from app.schemas import (DeviceEventRequest, HeartbeatRequest,
                         ValidateQrRequest, ValidateResponse,
                         ValidateRfidRequest)
from app.services import sessions
from app.services.access import get_device, get_lab_by_code, validate_qr, validate_rfid
from app.services.devices import (record_component_health, record_door_alarm,
                                  resolve_held_open, resolve_offline_alerts)
from app.services.events import log_event
from app.services.notifications import notify, notify_security
from app.ui_text import denial_sentence

router = APIRouter(prefix="/access", tags=["access (device)"])

# Biometric outcomes that complete step 2 on the master.
_SECOND_FACTOR = {EventType.FACE_ACCEPTED: AuthMethod.FACE,
                  EventType.FINGERPRINT_ACCEPTED: AuthMethod.FINGERPRINT}


def _user_by_subject(db: Session, subject: str | None) -> User | None:
    if not subject:
        return None
    return db.scalar(select(User).where(User.auth_subject == subject))


@router.post("/validate-qr", response_model=ValidateResponse)
def validate_qr_endpoint(req: ValidateQrRequest,
                         db: Session = Depends(get_db),
                         _: str = Depends(require_device)):
    """
    Step 1 for a booking QR.

    Returns the canonical identity on success. The master then requires a
    biometric that matches THIS identity before it unlocks anything.
    """
    res = validate_qr(db, req.qr_token, req.lab_id, req.device_uid)

    if not res.valid:
        return ValidateResponse(valid=False,
                                reason=res.reason.value if res.reason else "DENIED")

    return ValidateResponse(
        valid=True,
        user_id=res.user.id,
        auth_subject=res.user.auth_subject,
        display_name=res.user.full_name,
        booking_id=res.booking.id,
        lab_id=res.lab.code,
        valid_from=res.token.valid_from,
        valid_until=res.token.valid_until,
    )


@router.post("/validate-rfid", response_model=ValidateResponse)
def validate_rfid_endpoint(req: ValidateRfidRequest,
                           db: Session = Depends(get_db),
                           _: str = Depends(require_device)):
    res = validate_rfid(db, req.uid_hex, req.lab_id, req.device_uid)
    if not res.valid:
        return ValidateResponse(valid=False,
                                reason=res.reason.value if res.reason else "DENIED")
    return ValidateResponse(
        valid=True,
        user_id=res.user.id,
        auth_subject=res.user.auth_subject,
        display_name=res.user.full_name,
        booking_id=res.booking.id if res.booking else None,
        lab_id=res.lab.code,
    )


@router.post("/events")
def post_event(req: DeviceEventRequest, db: Session = Depends(get_db),
               _: str = Depends(require_device)):
    """
    Generic event sink for the master: biometric attempts, door transitions,
    identity mismatches, exits. The master fires these and does not wait on
    them, so a slow or absent portal never delays the door.
    """
    lab = get_lab_by_code(db, req.lab_id)
    device = get_device(db, req.device_uid)
    user = _user_by_subject(db, req.auth_subject)

    log_event(db, req.event_type,
              lab_id=lab.id if lab else None,
              user_id=user.id if user else None,
              booking_id=req.booking_id,
              device_id=device.id if device else None,
              method=req.method, result=req.result, reason=req.reason,
              message=req.message or req.event_type.value,
              metadata=req.metadata)

    if req.event_type == EventType.IDENTITY_MISMATCH:
        notify_security(db, lab, "IDENTITY_MISMATCH",
                        req.message or "The biometric did not match step 1.")

    # Door alarms from the reed switch: forced entry, door held open.
    if req.event_type == EventType.ALARM and lab is not None and req.reason:
        record_door_alarm(db, lab, device, req.reason, req.message)

    if lab is not None:
        # The door cycle is recorded on the session; it does not end it.
        if req.event_type == EventType.DOOR_OPENED:
            sessions.record_door_opened(db, lab.id, user)
        elif req.event_type == EventType.DOOR_CLOSED:
            sessions.record_door_closed(db, lab.id, user)
            resolve_held_open(db, lab)
        elif req.event_type == EventType.EXIT_RECORDED:
            sessions.record_exit(db, lab.id, user)
        elif req.event_type in _SECOND_FACTOR:
            sessions.second_factor_seen(db, lab.id, user,
                                        _SECOND_FACTOR[req.event_type])

    db.commit()
    return {"status": "recorded"}


@router.post("/grant")
def record_grant(req: DeviceEventRequest, db: Session = Depends(get_db),
                 _: str = Depends(require_device)):
    """
    The master reports that it HAS granted access. This opens an occupancy
    session; it does not authorize anything.
    """
    lab = get_lab_by_code(db, req.lab_id)
    device = get_device(db, req.device_uid)
    user = _user_by_subject(db, req.auth_subject)

    log_event(db, EventType.ACCESS_GRANTED,
              lab_id=lab.id if lab else None,
              user_id=user.id if user else None,
              booking_id=req.booking_id,
              device_id=device.id if device else None,
              method=req.method, result=AccessResult.GRANTED,
              message=req.message or "Access granted at door")

    if lab is not None and user is not None:
        s = sessions.open_session(db, lab_id=lab.id, user_id=user.id,
                                  booking_id=req.booking_id,
                                  device_id=device.id if device else None,
                                  method=req.method or AuthMethod.RFID)
        # The biometric that completed step 2 was reported just before the
        # grant; carry it onto the session that the grant opens.
        recent = datetime.now(timezone.utc) - timedelta(minutes=2)
        bio = db.scalar(
            select(AccessEvent)
            .where(AccessEvent.lab_id == lab.id,
                   AccessEvent.user_id == user.id,
                   AccessEvent.event_type.in_(list(_SECOND_FACTOR)),
                   AccessEvent.created_at >= recent)
            .order_by(AccessEvent.created_at.desc()))
        if bio is not None:
            s.second_factor = _SECOND_FACTOR[bio.event_type]

    # Stamp the REAL entry time on the booking. first_entry_at is written
    # once and never overwritten - it is the answer to "when did they
    # actually turn up", which is not the same question as "when does the
    # booking start". last_entry_at moves on every re-entry.
    if req.booking_id:
        booking = db.get(Booking, req.booking_id)
        if booking is not None:
            now = datetime.now(timezone.utc)
            if booking.first_entry_at is None:
                booking.first_entry_at = now
            booking.last_entry_at = now
            booking.entry_count += 1

    db.commit()
    return {"status": "recorded"}


@router.post("/deny")
def record_deny(req: DeviceEventRequest, db: Session = Depends(get_db),
                _: str = Depends(require_device)):
    lab = get_lab_by_code(db, req.lab_id)
    device = get_device(db, req.device_uid)
    user = _user_by_subject(db, req.auth_subject)

    log_event(db, EventType.ACCESS_DENIED,
              lab_id=lab.id if lab else None,
              user_id=user.id if user else None,
              booking_id=req.booking_id,
              device_id=device.id if device else None,
              method=req.method, result=AccessResult.DENIED,
              reason=req.reason,
              message=req.message or f"Access denied: {req.reason}")

    if req.reason:
        notify_security(db, lab, req.reason, req.message or "")

    # Tell the person, once. The master can report the same refusal from two
    # places in quick succession; a minute of de-duplication keeps that to a
    # single notification.
    if user is not None:
        recent = datetime.now(timezone.utc) - timedelta(minutes=1)
        already = db.scalar(select(Notification.id).where(
            Notification.user_id == user.id,
            Notification.kind == "ACCESS_DENIED",
            Notification.created_at >= recent))
        if not already:
            where = lab.code if lab else req.lab_id
            notify(db, [user.id], "ACCESS_DENIED",
                   f"Access denied at {where}",
                   body=denial_sentence(req.reason) or "Entry was refused.",
                   link=f"/bookings/{req.booking_id}" if req.booking_id else "/bookings",
                   severity="warning", booking_id=req.booking_id)
    db.commit()
    return {"status": "recorded"}


@router.post("/heartbeat", tags=["devices"])
def heartbeat(req: HeartbeatRequest, db: Session = Depends(get_db),
              _: str = Depends(require_device)):
    """
    Device liveness and door state. Auto-registers an unknown device against
    its lab so a freshly flashed board appears in the admin view without
    manual setup.
    """
    lab = get_lab_by_code(db, req.lab_id)
    if lab is None:
        return {"status": "unknown_lab"}

    device = get_device(db, req.device_uid)
    was_online = device.is_online if device else False

    if device is None:
        device = Device(device_uid=req.device_uid, name=req.device_uid,
                        device_type=req.device_type or DeviceType.MASTER_CONTROLLER,
                        lab_id=lab.id)
        db.add(device)
        db.flush()

    device.ip_address = req.ip_address or device.ip_address
    device.firmware_version = req.firmware_version or device.firmware_version
    device.last_seen_at = datetime.now(timezone.utc)
    device.is_online = True
    if req.door_closed is not None:
        device.door_closed = req.door_closed
    if req.components is not None:
        device.component_state = req.components
        record_component_health(db, device, lab, req.components)

    if not was_online:
        log_event(db, EventType.DEVICE_ONLINE, lab_id=lab.id,
                  device_id=device.id, message=f"{device.name} online")
        resolve_offline_alerts(db, device)
    db.commit()
    return {"status": "ok", "lab": lab.code, "device_id": device.id}
