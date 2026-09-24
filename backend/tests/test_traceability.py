"""
Traceability: occupancy sessions, the booking trace, and the honesty rules
around exit times.

The door reports grant, door opened, door closed. It never reports the person
leaving. These tests pin down that a door closing is never presented as an
exit, and that a full booking-to-door sequence can be reconstructed from the
portal alone.
"""
from datetime import timedelta

from app.models import AccessSession, SessionEndReason
from app.services.booking import active_token, create_booking
from tests.conftest import auth_headers


def post(client, headers, path, **body):
    r = client.post(f"/api/access/{path}", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r


def test_door_closing_does_not_end_the_session(client, db, alice, lab, device,
                                               device_headers, now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    h = device_headers
    post(client, h, "grant", lab_id=lab.code, device_uid=device.device_uid,
         event_type="ACCESS_GRANTED", auth_subject="USER1", booking_id=b.id,
         method="QR")
    post(client, h, "events", lab_id=lab.code, device_uid=device.device_uid,
         event_type="DOOR_OPENED", auth_subject="USER1", booking_id=b.id)
    post(client, h, "events", lab_id=lab.code, device_uid=device.device_uid,
         event_type="DOOR_CLOSED", auth_subject="USER1", booking_id=b.id)

    s = db.query(AccessSession).one()
    db.refresh(s)
    assert s.door_opened_at is not None
    assert s.door_closed_at is not None
    assert s.ended_at is None, "door closing behind the person is not an exit"

    r = client.get(f"/api/bookings/{b.id}",
                   headers=auth_headers(client, alice.email)).json()
    assert r["currently_inside"] is True
    assert r["last_exit_at"] is None
    assert r["time_inside_minutes"] is None


def test_unlock_without_opening_is_not_an_entry(client, db, alice, lab, device,
                                                device_headers, now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    post(client, device_headers, "grant", lab_id=lab.code,
         device_uid=device.device_uid, event_type="ACCESS_GRANTED",
         auth_subject="USER1", booking_id=b.id, method="QR")
    # Hold time elapsed, relocked without the door ever opening.
    post(client, device_headers, "events", lab_id=lab.code,
         device_uid=device.device_uid, event_type="DOOR_CLOSED",
         auth_subject="USER1", booking_id=b.id)
    s = db.query(AccessSession).one()
    db.refresh(s)
    assert s.end_reason == SessionEndReason.DOOR_NOT_OPENED
    assert s.ended_at is not None


def test_only_a_recorded_exit_gives_a_duration(client, db, alice, lab, device,
                                               device_headers, now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    post(client, device_headers, "grant", lab_id=lab.code,
         device_uid=device.device_uid, event_type="ACCESS_GRANTED",
         auth_subject="USER1", booking_id=b.id, method="QR")
    s = db.query(AccessSession).one()
    s.started_at = now - timedelta(minutes=47)
    db.commit()
    post(client, device_headers, "events", lab_id=lab.code,
         device_uid=device.device_uid, event_type="EXIT_RECORDED",
         auth_subject="USER1", booking_id=b.id)

    r = client.get(f"/api/bookings/{b.id}",
                   headers=auth_headers(client, alice.email)).json()
    assert r["currently_inside"] is False
    assert r["last_exit_at"] is not None
    assert r["time_inside_minutes"] in (46, 47)


def test_booking_end_closes_the_session_without_inventing_an_exit(
        client, db, alice, lab, device, device_headers, now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    post(client, device_headers, "grant", lab_id=lab.code,
         device_uid=device.device_uid, event_type="ACCESS_GRANTED",
         auth_subject="USER1", booking_id=b.id, method="QR")
    # The window has since closed.
    b.start_time = now - 3 * hour
    b.end_time = now - hour
    db.commit()

    h = auth_headers(client, alice.email)
    sessions = client.get(f"/api/bookings/{b.id}/sessions", headers=h).json()
    assert sessions[0]["end_reason"] == "BOOKING_ENDED"
    assert sessions[0]["duration_minutes"] is None
    booking = client.get(f"/api/bookings/{b.id}", headers=h).json()
    assert booking["currently_inside"] is False
    assert booking["last_exit_at"] is None


def test_second_entry_supersedes_the_first(client, db, alice, lab, device,
                                           device_headers, now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    for _ in range(2):
        post(client, device_headers, "grant", lab_id=lab.code,
             device_uid=device.device_uid, event_type="ACCESS_GRANTED",
             auth_subject="USER1", booking_id=b.id, method="QR")
    rows = db.query(AccessSession).order_by(AccessSession.id).all()
    assert rows[0].end_reason == SessionEndReason.SUPERSEDED
    assert rows[1].ended_at is None


def test_full_booking_trace(client, db, alice, lab, device, device_headers,
                            now, hour):
    """Booking -> QR -> face -> grant -> door -> exit, reconstructed."""
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour,
                       "Calibration")
    token = active_token(db, b.id).token
    h = device_headers
    uid = device.device_uid

    r = client.post("/api/access/validate-qr", headers=h,
                    json={"lab_id": lab.code, "qr_token": token,
                          "device_uid": uid})
    assert r.json()["valid"] is True
    post(client, h, "events", lab_id=lab.code, device_uid=uid,
         event_type="FACE_ACCEPTED", auth_subject="USER1", booking_id=b.id,
         method="FACE", result="GRANTED", message="Face matched USER1")
    post(client, h, "grant", lab_id=lab.code, device_uid=uid,
         event_type="ACCESS_GRANTED", auth_subject="USER1", booking_id=b.id,
         method="QR")
    post(client, h, "events", lab_id=lab.code, device_uid=uid,
         event_type="DOOR_OPENED", auth_subject="USER1", booking_id=b.id)
    post(client, h, "events", lab_id=lab.code, device_uid=uid,
         event_type="DOOR_CLOSED", auth_subject="USER1", booking_id=b.id)
    post(client, h, "events", lab_id=lab.code, device_uid=uid,
         event_type="EXIT_RECORDED", auth_subject="USER1", booking_id=b.id)

    t = client.get(f"/api/bookings/{b.id}/trace",
                   headers=auth_headers(client, alice.email))
    assert t.status_code == 200, t.text
    t = t.json()
    s = t["summary"]
    assert s["first_factor"] == "QR" and s["qr_result"] == "VALID"
    assert s["first_factor_identity"] == "USER1"
    assert s["second_factor"] == "FACE"
    assert s["second_factor_identity"] == "USER1"
    assert s["result"] == "GRANTED"
    assert s["entry_at"] and s["door_opened_at"] and s["door_closed_at"]
    assert s["exit_recorded"] is True and s["exit_at"]
    assert t["token"]["state"] == "VALID" and t["token"]["use_count"] == 1
    assert t["user"]["auth_subject"] == "USER1"
    assert t["sessions"][0]["second_factor"] == "FACE"

    types = [e["event_type"] for e in t["events"]]
    for expected in ("BOOKING_CREATED", "BOOKING_CONFIRMED", "QR_GENERATED",
                     "QR_VALIDATED", "FACE_ACCEPTED", "ACCESS_GRANTED",
                     "DOOR_OPENED", "DOOR_CLOSED", "EXIT_RECORDED"):
        assert expected in types
    # Chronological, so it reads as the sequence that happened.
    times = [e["created_at"] for e in t["events"]]
    assert times == sorted(times)


def test_denied_attempt_appears_in_trace(client, db, alice, lab, device,
                                         device_headers, now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    post(client, device_headers, "deny", lab_id=lab.code,
         device_uid=device.device_uid, event_type="ACCESS_DENIED",
         auth_subject="USER1", booking_id=b.id, method="FACE",
         result="DENIED", reason="IDENTITY_MISMATCH")
    s = client.get(f"/api/bookings/{b.id}/trace",
                   headers=auth_headers(client, alice.email)).json()["summary"]
    assert s["result"] == "DENIED"
    assert s["denial_reason"] == "IDENTITY_MISMATCH"
    assert s["denials"] == 1


def test_student_cannot_trace_someone_elses_booking(client, db, alice, bob,
                                                    lab, now, hour):
    b = create_booking(db, alice, lab, now + hour, now + 2 * hour, "x")
    r = client.get(f"/api/bookings/{b.id}/trace",
                   headers=auth_headers(client, bob.email))
    assert r.status_code == 404


def test_staff_session_list(client, db, alice, staff, lab, device,
                            device_headers, now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    post(client, device_headers, "grant", lab_id=lab.code,
         device_uid=device.device_uid, event_type="ACCESS_GRANTED",
         auth_subject="USER1", booking_id=b.id, method="QR")
    rows = client.get("/api/access-sessions?open_only=true",
                      headers=auth_headers(client, staff.email)).json()
    assert [r["user_name"] for r in rows] == ["Alice"]
    assert client.get("/api/access-sessions",
                      headers=auth_headers(client, alice.email)).status_code == 403
