"""
The authorization tests. This file is the security argument of the project.

Every scenario the specification calls non-negotiable is asserted here:
a QR outside its window, at the wrong laboratory, after cancellation, unknown,
revoked; identity mismatch on the second factor; and one student reaching for
another's booking.
"""
from datetime import timedelta

import pytest

from app.models import (Booking, BookingStatus, DenialReason, QrToken, Role,
                        User)
from app.services.access import validate_qr, validate_rfid
from app.services.booking import (BookingError, active_token, cancel_booking,
                                  create_booking)
from tests.conftest import auth_headers


def make_booking(db, user, lab, start, end, reason="Experiment"):
    return create_booking(db, user, lab, start, end, reason)


# ===========================================================================
# The headline requirement: a QR is only valid inside its own window
# ===========================================================================
def test_qr_invalid_before_window(db, alice, lab, now, hour):
    b = make_booking(db, alice, lab, now + 2 * hour, now + 3 * hour)
    token = active_token(db, b.id)

    res = validate_qr(db, token.token, lab.code)
    assert res.valid is False
    assert res.reason == DenialReason.BOOKING_NOT_STARTED


def test_qr_valid_inside_window(db, alice, lab, now, hour):
    b = make_booking(db, alice, lab, now - timedelta(minutes=15),
                     now + timedelta(minutes=45))
    token = active_token(db, b.id)

    res = validate_qr(db, token.token, lab.code)
    assert res.valid is True
    assert res.user.id == alice.id
    assert res.user.auth_subject == "USER1"
    assert res.booking.id == b.id


def test_qr_invalid_after_window(db, alice, lab, now, hour):
    """
    The booking must be created in the future (creating one in the past is
    rejected), then moved. Editing the stored row is how the passage of time
    is simulated without sleeping through an hour in a test suite.
    """
    b = make_booking(db, alice, lab, now + hour, now + 2 * hour)
    token = active_token(db, b.id)

    b.start_time = now - 3 * hour
    b.end_time = now - 2 * hour
    token.valid_from = b.start_time
    token.valid_until = b.end_time
    db.commit()

    res = validate_qr(db, token.token, lab.code)
    assert res.valid is False
    assert res.reason == DenialReason.BOOKING_EXPIRED


def test_qr_rejected_at_a_different_lab(db, alice, lab, other_lab, now, hour):
    """A credential for one laboratory must not open another, even in window."""
    b = make_booking(db, alice, lab, now - timedelta(minutes=5),
                     now + hour)
    token = active_token(db, b.id)

    assert validate_qr(db, token.token, lab.code).valid is True
    res = validate_qr(db, token.token, other_lab.code)
    assert res.valid is False
    assert res.reason == DenialReason.WRONG_LAB


def test_qr_dead_after_cancellation(db, alice, lab, now, hour):
    """
    Cancelling must kill the credential immediately, not at the end of the
    window. This is the failure the whole booking layer exists to prevent.
    """
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    token = active_token(db, b.id)
    assert validate_qr(db, token.token, lab.code).valid is True

    cancel_booking(db, b, alice)

    res = validate_qr(db, token.token, lab.code)
    assert res.valid is False
    assert res.reason in (DenialReason.TOKEN_REVOKED,
                          DenialReason.BOOKING_CANCELLED)


def test_unknown_token_is_denied(db, lab):
    res = validate_qr(db, "SLB:completely-made-up-token", lab.code)
    assert res.valid is False
    assert res.reason == DenialReason.TOKEN_UNKNOWN


def test_unknown_lab_is_denied(db, alice, lab, now, hour):
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    token = active_token(db, b.id)
    res = validate_qr(db, token.token, "LAB_DOES_NOT_EXIST")
    assert res.valid is False
    assert res.reason == DenialReason.DEVICE_UNKNOWN


def test_inactive_user_is_denied(db, alice, lab, now, hour):
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    token = active_token(db, b.id)
    alice.is_active = False
    db.commit()

    res = validate_qr(db, token.token, lab.code)
    assert res.valid is False
    assert res.reason == DenialReason.USER_INACTIVE


def test_reissuing_revokes_the_previous_token(db, alice, lab, now, hour):
    """
    Re-issuing is how a student invalidates a QR they have already shared.
    The old one must stop working the moment the new one exists.
    """
    from app.services.booking import issue_token_for

    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    old = active_token(db, b.id).token

    issue_token_for(db, b)
    db.commit()
    new = active_token(db, b.id).token
    assert new != old

    assert validate_qr(db, old, lab.code).reason == DenialReason.TOKEN_REVOKED
    assert validate_qr(db, new, lab.code).valid is True


def test_token_carries_no_personal_data(db, alice, lab, now, hour):
    """
    The QR payload must be opaque: nothing in the image identifies the person,
    the laboratory or the booking. Note this checks for IDENTIFIERS, not for
    single digits - a random base64 body will contain '1' almost every time,
    which says nothing about whether the token leaks anything.
    """
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    token = active_token(db, b.id).token

    body = token.split(":", 1)[1]
    lowered = body.lower()
    for leak in ("alice", "user1", "lab_test", alice.email.split("@")[0]):
        assert leak.lower() not in lowered

    # And it must be unguessable: two tokens for the same booking differ
    # completely, so nothing about the booking is encoded in the value.
    from app.services.booking import issue_token_for
    issue_token_for(db, b)
    db.commit()
    second = active_token(db, b.id).token.split(":", 1)[1]
    assert second != body
    assert len(set(body) & set(second)) < len(body)   # not a shared prefix


# ===========================================================================
# Identity binding - step 2 must match step 1
# ===========================================================================
def test_identity_binding_is_what_the_firmware_checks(db, alice, lab, now, hour):
    """
    The backend's job is to return the ONE identity the biometric must match.
    This asserts the contract the firmware relies on: a validated QR yields
    exactly one auth_subject, and it is the booking owner's.
    """
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    token = active_token(db, b.id)

    res = validate_qr(db, token.token, lab.code)
    assert res.valid is True
    assert res.user.auth_subject == "USER1"
    # Bob's face must therefore fail on the device: USER2 != USER1
    assert res.user.auth_subject != "USER2"


def test_api_identity_mismatch_is_recorded(client, db, alice, bob, lab, device,
                                           device_headers, now, hour):
    """
    A mismatch reported by the master must land in the audit trail with the
    right reason - that is what makes test 8 demonstrable after the fact.
    """
    from app.models import AccessEvent, EventType

    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)

    r = client.post("/api/access/deny", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_DENIED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "FACE", "result": "DENIED",
        "reason": "IDENTITY_MISMATCH",
        "message": "QR was USER1 but face matched USER2",
    })
    assert r.status_code == 200

    ev = db.query(AccessEvent).filter(
        AccessEvent.event_type == EventType.ACCESS_DENIED).first()
    assert ev is not None
    assert ev.reason == "IDENTITY_MISMATCH"
    assert ev.lab_id == lab.id


# ===========================================================================
# RFID
# ===========================================================================
def test_rfid_works_without_a_booking_by_default(db, alice, alice_card, lab):
    """
    Preserves the existing local behaviour: the door keeps working exactly as
    it does today unless a lab opts in to requiring bookings.
    """
    assert lab.require_booking_for_rfid is False
    res = validate_rfid(db, "8952FF1F", lab.code)
    assert res.valid is True
    assert res.user.auth_subject == "USER1"


def test_rfid_requires_booking_when_lab_is_configured_to(db, alice, alice_card,
                                                         lab):
    lab.require_booking_for_rfid = True
    db.commit()
    res = validate_rfid(db, "8952FF1F", lab.code)
    assert res.valid is False
    assert res.reason == DenialReason.NO_ACTIVE_BOOKING


def test_rfid_accepted_with_active_booking_when_required(db, alice, alice_card,
                                                         lab, now, hour):
    lab.require_booking_for_rfid = True
    db.commit()
    make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)

    res = validate_rfid(db, "8952FF1F", lab.code)
    assert res.valid is True
    assert res.booking is not None


def test_unknown_card_is_denied(db, lab):
    res = validate_rfid(db, "DEADBEEF", lab.code)
    assert res.valid is False
    assert res.reason == DenialReason.UNKNOWN_CREDENTIAL


# ===========================================================================
# Booking rules
# ===========================================================================
def test_overlapping_bookings_are_rejected(db, alice, bob, lab, now, hour):
    make_booking(db, alice, lab, now + hour, now + 3 * hour)
    with pytest.raises(BookingError) as e:
        make_booking(db, bob, lab, now + 2 * hour, now + 4 * hour)
    assert e.value.code == "CONFLICT"


def test_touching_bookings_are_allowed(db, alice, bob, lab, now, hour):
    """One ending exactly when the next starts is not an overlap."""
    make_booking(db, alice, lab, now + hour, now + 2 * hour)
    b = make_booking(db, bob, lab, now + 2 * hour, now + 3 * hour)
    assert b.status == BookingStatus.CONFIRMED


def test_non_exclusive_lab_allows_concurrent_bookings(db, alice, bob, lab,
                                                      now, hour):
    lab.exclusive_booking = False
    db.commit()
    make_booking(db, alice, lab, now + hour, now + 3 * hour)
    b = make_booking(db, bob, lab, now + hour, now + 3 * hour)
    assert b.id is not None


def test_backwards_window_rejected(db, alice, lab, now, hour):
    with pytest.raises(BookingError) as e:
        make_booking(db, alice, lab, now + 3 * hour, now + hour)
    assert e.value.code == "INVALID_WINDOW"


def test_past_booking_rejected(db, alice, lab, now, hour):
    with pytest.raises(BookingError) as e:
        make_booking(db, alice, lab, now - 3 * hour, now - hour)
    assert e.value.code == "IN_THE_PAST"


def test_overlong_booking_rejected(db, alice, lab, now, hour):
    with pytest.raises(BookingError) as e:
        make_booking(db, alice, lab, now + hour, now + 20 * hour)
    assert e.value.code == "TOO_LONG"


# ===========================================================================
# Role isolation
# ===========================================================================
def test_student_cannot_see_another_students_booking(client, db, alice, bob,
                                                     lab, now, hour):
    b = make_booking(db, alice, lab, now + hour, now + 2 * hour)
    h = auth_headers(client, "bob@test.edu")

    r = client.get(f"/api/bookings/{b.id}", headers=h)
    assert r.status_code == 404      # not 403: existence is itself private


def test_student_cannot_read_another_students_qr(client, db, alice, bob, lab,
                                                 now, hour):
    b = make_booking(db, alice, lab, now + hour, now + 2 * hour)
    h = auth_headers(client, "bob@test.edu")
    assert client.get(f"/api/bookings/{b.id}/qr", headers=h).status_code == 404


def test_student_cannot_cancel_another_students_booking(client, db, alice, bob,
                                                        lab, now, hour):
    b = make_booking(db, alice, lab, now + hour, now + 2 * hour)
    h = auth_headers(client, "bob@test.edu")
    assert client.post(f"/api/bookings/{b.id}/cancel",
                       headers=h).status_code == 404
    db.refresh(b)
    assert b.status != BookingStatus.CANCELLED


def test_student_cannot_create_users(client, alice):
    h = auth_headers(client, "alice@test.edu")
    r = client.post("/api/auth/register", headers=h, json={
        "email": "x@test.edu", "full_name": "X", "password": "Password123"})
    assert r.status_code == 403


def test_student_listing_events_is_scoped_to_themselves(client, db, alice, bob,
                                                       lab, device,
                                                       device_headers,
                                                       now, hour):
    """
    A student asking for the event feed with NO filter must not receive the
    whole building's security log. They get their own slice.

    This replaces an earlier rule that refused students outright. That was
    wrong in a way worth naming: it also broke the "your recent access" panel
    on their own dashboard, so the product silently showed them nothing about
    themselves forever.
    """
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    client.post("/api/access/grant", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_GRANTED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "QR", "result": "GRANTED",
        "message": "Alice entered"})

    h = auth_headers(client, "bob@test.edu")
    r = client.get("/api/access-events", headers=h)
    assert r.status_code == 200
    assert all(e["user_id"] == bob.id for e in r.json())


def test_device_endpoints_reject_a_missing_key(client, lab):
    r = client.post("/api/access/validate-qr",
                    json={"lab_id": lab.code, "qr_token": "SLB:x"})
    assert r.status_code == 401


def test_device_endpoints_reject_a_wrong_key(client, lab):
    r = client.post("/api/access/validate-qr",
                    headers={"X-Device-Key": "not-the-key"},
                    json={"lab_id": lab.code, "qr_token": "SLB:x"})
    assert r.status_code == 401


def test_unauthenticated_cannot_list_bookings(client):
    assert client.get("/api/bookings").status_code == 401


def test_login_does_not_reveal_whether_an_account_exists(client, alice):
    a = client.post("/api/auth/login", json={"email": "alice@test.edu",
                                             "password": "WrongPassword"})
    b = client.post("/api/auth/login", json={"email": "nobody@test.edu",
                                             "password": "WrongPassword"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


# ===========================================================================
# Actual use vs booked intent
# ===========================================================================
def test_real_entry_time_is_recorded_separately_from_the_booking(
        client, db, alice, lab, device, device_headers, now, hour):
    """
    A booking says when someone INTENDED to be there. This asserts the system
    also records when they actually walked in - the two are different
    questions and a room-utilisation study needs both.
    """
    b = make_booking(db, alice, lab, now - timedelta(minutes=16), now + hour)
    assert b.first_entry_at is None
    assert b.entry_count == 0

    r = client.post("/api/access/grant", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_GRANTED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "QR", "result": "GRANTED",
        "message": "Access granted"})
    assert r.status_code == 200

    db.expire_all()
    b = db.get(Booking, b.id)
    assert b.first_entry_at is not None
    assert b.entry_count == 1


def test_first_entry_is_never_overwritten_by_re_entry(
        client, db, alice, lab, device, device_headers, now, hour):
    """
    Walking out and back in must not rewrite history. first_entry_at answers
    'when did they arrive', which happens exactly once.
    """
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    payload = {"lab_id": lab.code, "device_uid": device.device_uid,
               "event_type": "ACCESS_GRANTED", "auth_subject": "USER1",
               "booking_id": b.id, "method": "QR", "result": "GRANTED",
               "message": "Access granted"}

    client.post("/api/access/grant", headers=device_headers, json=payload)
    db.expire_all()
    first = db.get(Booking, b.id).first_entry_at

    client.post("/api/access/grant", headers=device_headers, json=payload)
    db.expire_all()
    b = db.get(Booking, b.id)

    assert b.first_entry_at == first      # unchanged
    assert b.last_entry_at >= first       # moves forward
    assert b.entry_count == 2


def test_api_reports_how_late_the_person_was(
        client, db, alice, lab, device, device_headers, now, hour):
    """The punctuality figure the admin view shows."""
    b = make_booking(db, alice, lab, now - timedelta(minutes=16), now + hour)
    client.post("/api/access/grant", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_GRANTED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "QR", "result": "GRANTED",
        "message": "Access granted"})

    h = auth_headers(client, "alice@test.edu")
    row = client.get(f"/api/bookings/{b.id}", headers=h).json()

    assert row["entry_count"] == 1
    assert row["first_entry_at"] is not None
    # Booked 16 minutes ago, entered now -> ~16 minutes late.
    assert 15 <= row["entry_delay_minutes"] <= 17


def test_a_booking_never_used_reports_no_entry(db, alice, lab, client, now, hour):
    b = make_booking(db, alice, lab, now + hour, now + 2 * hour)
    h = auth_headers(client, "alice@test.edu")
    row = client.get(f"/api/bookings/{b.id}", headers=h).json()
    assert row["first_entry_at"] is None
    assert row["entry_delay_minutes"] is None
    assert row["entry_count"] == 0


# ===========================================================================
# Students may read their OWN access history
# ===========================================================================
def test_student_can_read_their_own_access_events(client, db, alice, lab,
                                                  device, device_headers,
                                                  now, hour):
    """
    The student dashboard shows "your recent access". That panel must work
    without handing a student the whole building's security log.
    """
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    client.post("/api/access/grant", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_GRANTED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "QR", "result": "GRANTED",
        "message": "Access granted"})

    h = auth_headers(client, "alice@test.edu")
    r = client.get(f"/api/access-events?user_id={alice.id}&limit=20", headers=h)
    assert r.status_code == 200, r.text
    assert any(e["event_type"] == "ACCESS_GRANTED" for e in r.json())


def test_student_cannot_read_another_users_access_events(client, db, alice, bob,
                                                         lab, device,
                                                         device_headers,
                                                         now, hour):
    """
    Asking for somebody else's user_id must not return their events. It is
    silently narrowed to the caller rather than refused - a 403 here would
    itself reveal whether that user has any activity.
    """
    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    client.post("/api/access/grant", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_GRANTED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "QR", "result": "GRANTED",
        "message": "Alice entered"})

    h = auth_headers(client, "bob@test.edu")
    r = client.get(f"/api/access-events?user_id={alice.id}&limit=20", headers=h)
    assert r.status_code == 200
    # Bob asked for Alice's events and got only his own - which is none.
    assert all(e["user_id"] == bob.id for e in r.json())
    assert not any("Alice entered" == e["message"] for e in r.json())


def test_staff_still_see_everything(client, db, alice, lab, device,
                                    device_headers, now, hour):
    from app.core.security import hash_password
    from app.models import Role as R, User as U
    staff = U(email="staff@test.edu", full_name="Staff",
              hashed_password=hash_password("Password123"), role=R.LAB_STAFF)
    db.add(staff)
    db.commit()

    b = make_booking(db, alice, lab, now - timedelta(minutes=5), now + hour)
    client.post("/api/access/grant", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_GRANTED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "QR", "result": "GRANTED",
        "message": "Alice entered"})

    h = auth_headers(client, "staff@test.edu")
    r = client.get("/api/access-events?limit=50", headers=h)
    assert r.status_code == 200
    assert any(e["user_id"] == alice.id for e in r.json())
