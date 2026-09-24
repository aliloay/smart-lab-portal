"""
Portal behaviour added for the final UI: availability, role scoping,
notifications, device liveness, booking on behalf, and the live channel.
"""
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (AccessEvent, Alert, Device, DeviceType, EventType,
                        Notification)
from app.services.booking import create_booking
from tests.conftest import auth_headers


# ===========================================================================
# Availability and privacy
# ===========================================================================
def test_availability_shows_taken_slots_without_identity(client, db, alice,
                                                         bob, lab, now, hour):
    b = create_booking(db, alice, lab, now + hour, now + 3 * hour, "Thesis")
    q = {"start": (now).isoformat(), "end": (now + 24 * hour).isoformat()}

    as_bob = client.get(f"/api/labs/{lab.id}/availability", params=q,
                        headers=auth_headers(client, bob.email)).json()
    assert len(as_bob) == 1
    assert as_bob[0]["user_name"] is None
    assert as_bob[0]["booking_id"] is None
    assert as_bob[0]["is_mine"] is False

    as_alice = client.get(f"/api/labs/{lab.id}/availability", params=q,
                          headers=auth_headers(client, alice.email)).json()
    assert as_alice[0]["is_mine"] is True
    assert as_alice[0]["booking_id"] == b.id


def test_availability_range_is_bounded(client, alice, lab, now):
    q = {"start": now.isoformat(), "end": (now + timedelta(days=90)).isoformat()}
    r = client.get(f"/api/labs/{lab.id}/availability", params=q,
                   headers=auth_headers(client, alice.email))
    assert r.status_code == 422


def test_lab_activity_is_scoped_for_students(client, db, alice, bob, staff,
                                             lab):
    for u in (alice, bob):
        db.add(AccessEvent(event_type=EventType.ACCESS_GRANTED, lab_id=lab.id,
                           user_id=u.id, message=f"granted {u.full_name}"))
    db.commit()
    mine = client.get(f"/api/labs/{lab.id}/activity",
                      headers=auth_headers(client, alice.email)).json()
    assert {e["user_name"] for e in mine} == {"Alice"}
    everyone = client.get(f"/api/labs/{lab.id}/activity",
                          headers=auth_headers(client, staff.email)).json()
    assert {e["user_name"] for e in everyone} == {"Alice", "Bob"}


def test_occupant_names_are_staff_only(client, db, alice, bob, staff, lab,
                                       device, device_headers, now, hour):
    b = create_booking(db, alice, lab, now - timedelta(minutes=5), now + hour, "x")
    client.post("/api/access/grant", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": device.device_uid,
        "event_type": "ACCESS_GRANTED", "auth_subject": "USER1",
        "booking_id": b.id, "method": "QR"})
    as_bob = client.get(f"/api/labs/{lab.id}",
                        headers=auth_headers(client, bob.email)).json()
    assert as_bob["occupants"] == 1 and as_bob["current_users"] == []
    assert as_bob["current_booking"]["user_name"] is None
    as_staff = client.get(f"/api/labs/{lab.id}",
                          headers=auth_headers(client, staff.email)).json()
    assert as_staff["current_users"] == ["Alice"]


def test_labs_overview_one_row_per_lab(client, db, alice, lab, other_lab):
    rows = client.get("/api/labs/overview",
                      headers=auth_headers(client, alice.email)).json()
    assert {r["lab"]["code"] for r in rows} == {lab.code, other_lab.code}
    assert all(r["available_now"] for r in rows)


def test_students_cannot_list_devices(client, alice, staff, device):
    assert client.get("/api/devices",
                      headers=auth_headers(client, alice.email)).status_code == 403
    rows = client.get("/api/devices",
                      headers=auth_headers(client, staff.email)).json()
    assert rows[0]["state"] == "NO_DATA"       # never reported, not "offline"


# ===========================================================================
# Booking on behalf, rejection
# ===========================================================================
def test_staff_can_book_for_a_student(client, db, staff, alice, lab, now, hour):
    r = client.post("/api/bookings", headers=auth_headers(client, staff.email),
                    json={"lab_id": lab.id, "user_id": alice.id,
                          "start_time": (now + hour).isoformat(),
                          "end_time": (now + 2 * hour).isoformat(),
                          "reason": "Supervised session"})
    assert r.status_code == 201, r.text
    assert r.json()["user_id"] == alice.id
    ev = db.query(AccessEvent).filter_by(
        event_type=EventType.BOOKING_CREATED).one()
    assert "for Alice" in ev.message


def test_student_cannot_book_for_someone_else(client, alice, bob, lab, now,
                                              hour):
    r = client.post("/api/bookings", headers=auth_headers(client, alice.email),
                    json={"lab_id": lab.id, "user_id": bob.id,
                          "start_time": (now + hour).isoformat(),
                          "end_time": (now + 2 * hour).isoformat()})
    assert r.status_code == 403


def test_staff_rejects_pending_request(client, db, staff, alice, lab, now,
                                       hour, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "BOOKING_AUTO_APPROVE", False)
    b = create_booking(db, alice, lab, now + hour, now + 2 * hour, "x")
    r = client.post(f"/api/bookings/{b.id}/reject",
                    headers=auth_headers(client, staff.email),
                    json={"note": "Lab reserved for exams"})
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"
    n = db.query(Notification).filter_by(user_id=alice.id,
                                          kind="BOOKING_REJECTED").one()
    assert n.body == "Lab reserved for exams"


# ===========================================================================
# Notifications
# ===========================================================================
def test_booking_confirmation_notifies_owner(client, db, alice, lab, now, hour):
    b = create_booking(db, alice, lab, now + 2 * hour, now + 3 * hour, "x")
    rows = client.get("/api/notifications",
                      headers=auth_headers(client, alice.email)).json()
    assert [n["kind"] for n in rows] == ["BOOKING_CONFIRMED"]
    assert rows[0]["link"] == f"/bookings/{b.id}"


def test_reminder_is_raised_once_when_booking_is_close(client, db, alice, lab,
                                                       now):
    b = create_booking(db, alice, lab, now + timedelta(minutes=10),
                       now + timedelta(minutes=70), "x")
    h = auth_headers(client, alice.email)
    for _ in range(3):
        client.get("/api/notifications", headers=h)
    assert db.query(Notification).filter_by(
        booking_id=b.id, kind="BOOKING_REMINDER").count() == 1


def test_no_reminder_for_distant_booking(client, db, alice, lab, now, hour):
    create_booking(db, alice, lab, now + 5 * hour, now + 6 * hour, "x")
    client.get("/api/notifications", headers=auth_headers(client, alice.email))
    assert db.query(Notification).filter_by(kind="BOOKING_REMINDER").count() == 0


def test_notifications_are_private(client, db, alice, bob, lab, now, hour):
    create_booking(db, alice, lab, now + 2 * hour, now + 3 * hour, "x")
    n = db.query(Notification).filter_by(user_id=alice.id).first()
    bh = auth_headers(client, bob.email)
    assert client.get("/api/notifications", headers=bh).json() == []
    assert client.post(f"/api/notifications/{n.id}/read",
                       headers=bh).status_code == 404


def test_mark_read_and_unread_count(client, db, alice, lab, now, hour):
    create_booking(db, alice, lab, now + 2 * hour, now + 3 * hour, "x")
    h = auth_headers(client, alice.email)
    assert client.get("/api/notifications/unread-count",
                      headers=h).json()["unread"] == 1
    client.post("/api/notifications/read-all", headers=h)
    assert client.get("/api/notifications/unread-count",
                      headers=h).json()["unread"] == 0


def test_denial_notifies_the_person_once(client, db, alice, lab, device,
                                         device_headers):
    for _ in range(2):   # the master reports the same refusal twice
        client.post("/api/access/deny", headers=device_headers, json={
            "lab_id": lab.code, "device_uid": device.device_uid,
            "event_type": "ACCESS_DENIED", "auth_subject": "USER1",
            "method": "QR", "reason": "BOOKING_EXPIRED"})
    rows = db.query(Notification).filter_by(user_id=alice.id,
                                            kind="ACCESS_DENIED").all()
    assert len(rows) == 1
    assert rows[0].body == "The booking window has closed."


# ===========================================================================
# Device liveness
# ===========================================================================
def test_silent_device_goes_offline_once_with_alert(client, db, staff, lab):
    d = Device(device_uid="MASTER_X", name="Door controller",
               device_type=DeviceType.MASTER_CONTROLLER, lab_id=lab.id,
               is_online=True,
               last_seen_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    db.add(d)
    db.commit()
    h = auth_headers(client, staff.email)
    for _ in range(2):
        s = client.get("/api/summary", headers=h).json()
    assert s["devices_online"] == 0
    assert db.query(AccessEvent).filter_by(
        event_type=EventType.DEVICE_OFFLINE).count() == 1
    alert = db.query(Alert).one()
    assert alert.title == "Door controller offline"
    assert db.query(Notification).filter_by(user_id=staff.id,
                                            kind="DEVICE_OFFLINE").count() == 1


def test_heartbeat_brings_device_back_and_resolves_alert(client, db, staff,
                                                         lab, device_headers):
    d = Device(device_uid="MASTER_Y", name="Door controller",
               device_type=DeviceType.MASTER_CONTROLLER, lab_id=lab.id,
               is_online=True,
               last_seen_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    db.add(d)
    db.commit()
    client.get("/api/summary", headers=auth_headers(client, staff.email))
    r = client.post("/api/access/heartbeat", headers=device_headers, json={
        "device_uid": "MASTER_Y", "lab_id": lab.code, "door_closed": True,
        "components": {"rfid": True, "fingerprint": True, "relay_locked": True}})
    assert r.status_code == 200
    db.expire_all()
    assert db.query(Alert).one().is_resolved is True
    dev = db.get(Device, d.id)
    assert dev.component_state == {"rfid": True, "fingerprint": True,
                                   "relay_locked": True}


def test_system_status_reports_only_what_it_knows(client, alice, device):
    s = client.get("/api/system/status",
                   headers=auth_headers(client, alice.email)).json()
    assert s["database"] is True
    assert s["controllers_total"] == 1
    assert s["controllers_online"] == 0
    assert s["devices_reporting"] == 0        # never heard from: no claim


def test_system_config_is_admin_only(client, staff, admin):
    assert client.get("/api/system/config",
                      headers=auth_headers(client, staff.email)).status_code == 403
    cfg = client.get("/api/system/config",
                     headers=auth_headers(client, admin.email)).json()
    assert cfg["storage_backend"] == "local-filesystem"


# ===========================================================================
# Users
# ===========================================================================
def test_admin_cannot_lock_themselves_out(client, admin):
    h = auth_headers(client, admin.email)
    for body in ({"is_active": False}, {"role": "STUDENT"}):
        assert client.patch(f"/api/users/{admin.id}", headers=h,
                            json=body).status_code == 409


def test_auth_subject_must_stay_unique(client, admin, alice, bob):
    r = client.patch(f"/api/users/{bob.id}",
                     headers=auth_headers(client, admin.email),
                     json={"auth_subject": alice.auth_subject})
    assert r.status_code == 409


# ===========================================================================
# The live channel
# ===========================================================================
def test_websocket_requires_a_valid_token():
    from starlette.websockets import WebSocketDisconnect
    with TestClient(app) as c:
        for url in ("/ws/activity", "/ws/activity?token=not-a-jwt"):
            with pytest.raises(WebSocketDisconnect) as exc:
                with c.websocket_connect(url) as ws:
                    ws.receive_text()
            assert exc.value.code == 4401


def test_websocket_scopes_events_by_role(db, alice, bob, staff, lab, device,
                                         device_headers):
    """
    A student's socket carries their own events only; staff get everything.
    Delivery runs on a worker thread and is bounded by a timeout, so a
    broken publisher fails the test instead of hanging it.
    """
    with TestClient(app) as c:
        tok = {u.email: auth_headers(c, u.email)["Authorization"][7:]
               for u in (alice, staff)}
        got: dict[str, list] = {"alice": [], "staff": []}

        def listen(name, token, n):
            with c.websocket_connect(f"/ws/activity?token={token}") as ws:
                ready[name].set()
                while len(got[name]) < n:
                    got[name].append(ws.receive_json())

        ready = {"alice": threading.Event(), "staff": threading.Event()}
        threads = [threading.Thread(target=listen, args=("alice", tok[alice.email], 1),
                                    daemon=True),
                   threading.Thread(target=listen, args=("staff", tok[staff.email], 2),
                                    daemon=True)]
        for t in threads:
            t.start()
        for e in ready.values():
            assert e.wait(5)

        for subject in ("USER2", "USER1"):      # Bob first, then Alice
            c.post("/api/access/deny", headers=device_headers, json={
                "lab_id": lab.code, "device_uid": device.device_uid,
                "event_type": "ACCESS_DENIED", "auth_subject": subject,
                "method": "RFID", "reason": "NO_ACTIVE_BOOKING"})
        for t in threads:
            t.join(10)
            assert not t.is_alive(), "live message was never delivered"

    alice_events = [m for m in got["alice"] if m["type"] == "access_event"]
    assert [m["event"]["user_name"] for m in alice_events] == ["Alice"]
    staff_names = {m["event"]["user_name"] for m in got["staff"]
                   if m["type"] == "access_event"}
    assert staff_names == {"Alice", "Bob"}
