"""
Reconstructing what happened at the door, shared by the booking trace and
the access-session detail. Everything here reads recorded rows; nothing is
inferred that the devices did not report.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (AuthMethod, Device, EventType, Lab, SessionEndReason,
                        User)
from app.schemas import EventOut, TraceSummary


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None         else dt.astimezone(timezone.utc)


# Events that belong on a door timeline.
DOOR_EVENTS = {
    EventType.QR_SCAN, EventType.QR_VALIDATED, EventType.QR_REJECTED,
    EventType.RFID_SCAN, EventType.RFID_ACCEPTED, EventType.RFID_REJECTED,
    EventType.FINGERPRINT_ATTEMPT, EventType.FINGERPRINT_ACCEPTED,
    EventType.FINGERPRINT_REJECTED, EventType.FACE_ATTEMPT,
    EventType.FACE_ACCEPTED, EventType.FACE_REJECTED,
    EventType.IDENTITY_MISMATCH, EventType.ACCESS_GRANTED,
    EventType.ACCESS_DENIED, EventType.DOOR_OPENED, EventType.DOOR_CLOSED,
    EventType.EXIT_RECORDED,
}


def event_out(db: Session, e, lab: Lab | None = None) -> EventOut:
    item = EventOut.model_validate(e)
    if e.user_id:
        u = db.get(User, e.user_id)
        item.user_name = u.full_name if u else None
    if e.device_id:
        d = db.get(Device, e.device_id)
        item.device_name = d.name if d else None
    if lab is None and e.lab_id:
        lab = db.get(Lab, e.lab_id)
    item.lab_code = lab.code if lab else None
    return item


def summarise(db: Session, events: list, sessions: list,
               owner: User) -> TraceSummary:
    s = TraceSummary()
    t = {e.event_type for e in events}
    outcomes = [e for e in events
                if e.event_type in (EventType.ACCESS_GRANTED,
                                    EventType.ACCESS_DENIED)]
    s.attempts = len(outcomes)
    s.denials = sum(1 for e in outcomes
                    if e.event_type == EventType.ACCESS_DENIED)
    if outcomes:
        last = outcomes[-1]
        s.result = "GRANTED" if last.event_type == EventType.ACCESS_GRANTED \
            else "DENIED"
        if s.result == "DENIED":
            s.denial_reason = last.reason

    # Step 1
    if EventType.QR_VALIDATED in t:
        s.first_factor = AuthMethod.QR
        s.qr_result = "VALID"
        s.first_factor_identity = owner.auth_subject
    elif EventType.RFID_ACCEPTED in t:
        s.first_factor = AuthMethod.RFID
        s.first_factor_identity = owner.auth_subject
    rejected = [e for e in events if e.event_type == EventType.QR_REJECTED]
    if rejected and s.qr_result is None:
        s.first_factor = AuthMethod.QR
        s.qr_result = rejected[-1].reason or "REJECTED"

    # Step 2
    bio = [e for e in events if e.event_type in
           (EventType.FACE_ACCEPTED, EventType.FINGERPRINT_ACCEPTED)]
    if bio:
        s.second_factor = (AuthMethod.FACE
                           if bio[-1].event_type == EventType.FACE_ACCEPTED
                           else AuthMethod.FINGERPRINT)
        u = db.get(User, bio[-1].user_id) if bio[-1].user_id else None
        s.second_factor_identity = u.auth_subject if u else None

    # The session the door actually produced.
    entered = [x for x in sessions if x.end_reason !=
               SessionEndReason.DOOR_NOT_OPENED] or sessions
    if entered:
        first = entered[0]
        s.entry_at = first.started_at
        s.door_opened_at = first.door_opened_at
        s.door_closed_at = first.door_closed_at
        s.second_factor = s.second_factor or first.second_factor
        s.first_factor = s.first_factor or first.entry_method
        last = entered[-1]
        s.session_end_reason = last.end_reason
        if last.end_reason == SessionEndReason.EXIT_RECORDED:
            s.exit_recorded = True
            s.exit_at = last.ended_at
            s.duration_minutes = int(
                (_utc(last.ended_at) - _utc(first.started_at))
                .total_seconds() // 60)
    return s
