"""
Fingerprint enrollment from the portal, through device commands.

The portal only records a request; the controller fetches it while idle and
reports each step. Tested: who may ask, one request at a time, the device
side (fetch, progress, done), expiry, and that DONE marks the fingerprint
as enrolled with an audit record.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import (AuditLog, Device, DeviceCommand, DeviceType,
                        Notification, Role, User)
from app.core.security import hash_password
from app.services import commands as cmds
from tests.conftest import auth_headers


@pytest.fixture
def master(db, lab) -> Device:
    d = Device(device_uid="MASTER_CMD", name="Master", lab_id=lab.id,
               device_type=DeviceType.MASTER_CONTROLLER, is_online=True,
               last_seen_at=datetime.now(timezone.utc))
    db.add(d)
    db.commit()
    return d


@pytest.fixture
def newbie(db) -> User:
    u = User(email="fp@test.edu", full_name="Ahmed Ali",
             hashed_password=hash_password("Password123"),
             role=Role.STUDENT, auth_subject="USER5")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _ask(client, h, user, **body):
    return client.post(f"/api/users/{user.id}/fingerprint/enroll", headers=h, json=body)


def test_students_cannot_request_enrollment(client, alice, newbie, master):
    assert _ask(client, auth_headers(client, alice.email), newbie).status_code == 403


def test_full_enrollment_flow_marks_fingerprint(client, db, staff, newbie, master,
                                                device_headers):
    h = auth_headers(client, staff.email)
    r = _ask(client, h, newbie)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert r.json()["args"]["slot"] == 5

    # The controller fetches it (once) ...
    nxt = client.get("/api/access/commands/next?device_uid=MASTER_CMD", headers=device_headers).json()
    assert nxt["id"] == cid and nxt["command"] == "ENROLL_FINGERPRINT"
    assert nxt["slot"] == 5 and nxt["force"] is False and nxt["display_name"] == "AHMED"
    again = client.get("/api/access/commands/next?device_uid=MASTER_CMD", headers=device_headers).json()
    assert again == {"command": None}

    # ... reports steps, then success.
    for step in ("PLACE_FINGER", "REMOVE_FINGER", "PLACE_AGAIN"):
        assert client.post(f"/api/access/commands/{cid}/progress", headers=device_headers,
                           json={"device_uid": "MASTER_CMD", "status": "RUNNING",
                                 "step": step}).status_code == 200
    assert client.get(f"/api/device-commands/{cid}", headers=h).json()["step"] == "PLACE_AGAIN"
    client.post(f"/api/access/commands/{cid}/progress", headers=device_headers,
                json={"device_uid": "MASTER_CMD", "status": "DONE", "step": "STORED"})

    db.refresh(newbie)
    assert newbie.fingerprint_enrolled_at is not None
    assert db.query(AuditLog).filter_by(action="FINGERPRINT_ENROLLED").count() == 1
    assert db.query(Notification).filter_by(user_id=newbie.id, kind="ACCESS_SETUP").count() == 1
    assert client.get(f"/api/device-commands/{cid}", headers=h).json()["status"] == "DONE"


def test_failure_does_not_mark_enrolled(client, db, staff, newbie, master, device_headers):
    h = auth_headers(client, staff.email)
    cid = _ask(client, h, newbie).json()["id"]
    client.get("/api/access/commands/next?device_uid=MASTER_CMD", headers=device_headers)
    client.post(f"/api/access/commands/{cid}/progress", headers=device_headers,
                json={"device_uid": "MASTER_CMD", "status": "FAILED",
                      "step": "MISMATCH", "message": "The two scans did not match"})
    db.refresh(newbie)
    assert newbie.fingerprint_enrolled_at is None
    assert db.query(AuditLog).filter_by(action="FINGERPRINT_ENROLL_FAILED").count() == 1


def test_one_request_at_a_time(client, staff, newbie, bob, master):
    h = auth_headers(client, staff.email)
    assert _ask(client, h, newbie).status_code == 200
    assert _ask(client, h, bob).status_code == 409


def test_offline_controller_is_refused(client, db, staff, newbie, master):
    master.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    r = _ask(client, auth_headers(client, staff.email), newbie)
    assert r.status_code == 409 and "offline" in r.json()["detail"]


def test_needs_a_numbered_door_identity(client, db, staff, newbie, master):
    newbie.auth_subject = "STAFF9"
    db.commit()
    assert _ask(client, auth_headers(client, staff.email), newbie).status_code == 409


def test_unfetched_request_expires_and_frees_the_controller(client, db, staff, newbie,
                                                            bob, master):
    h = auth_headers(client, staff.email)
    cid = _ask(client, h, newbie).json()["id"]
    c = db.get(DeviceCommand, cid)
    c.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert client.get(f"/api/device-commands/{cid}", headers=h).json()["status"] == "EXPIRED"
    assert _ask(client, h, bob).status_code == 200


def test_cancel_only_before_the_controller_starts(client, staff, newbie, master, device_headers):
    h = auth_headers(client, staff.email)
    cid = _ask(client, h, newbie).json()["id"]
    assert client.post(f"/api/device-commands/{cid}/cancel", headers=h).json()["status"] == "CANCELLED"
    cid = _ask(client, h, newbie).json()["id"]
    client.get("/api/access/commands/next?device_uid=MASTER_CMD", headers=device_headers)
    assert client.post(f"/api/device-commands/{cid}/cancel", headers=h).status_code == 409


def test_another_device_cannot_report_for_it(client, db, staff, newbie, master, lab,
                                             device_headers):
    other = Device(device_uid="OTHER", name="Other", lab_id=lab.id,
                   device_type=DeviceType.MASTER_CONTROLLER)
    db.add(other)
    db.commit()
    cid = _ask(client, auth_headers(client, staff.email), newbie).json()["id"]
    r = client.post(f"/api/access/commands/{cid}/progress", headers=device_headers,
                    json={"device_uid": "OTHER", "status": "DONE"})
    assert r.status_code == 404


def test_device_key_required(client, staff, newbie, master):
    assert client.get("/api/access/commands/next?device_uid=MASTER_CMD").status_code == 401
