"""
RFID card enrollment from the portal, through device commands.

Same path as a finger: staff ask, the door controller fetches the request
while idle, the person taps their card, and the controller reports the
card's UID. Tested: who may ask, the device side, that DONE records the card
as the person's one active card (a new card replaces the old one), that a
failure records nothing, and that removal revokes it.
"""
from datetime import datetime, timezone

import pytest

from app.models import AuditLog, Device, DeviceType, RfidCredential, Role, User
from app.core.security import hash_password
from tests.conftest import auth_headers


@pytest.fixture
def master(db, lab) -> Device:
    d = Device(device_uid="MASTER_CARD", name="Master", lab_id=lab.id,
               device_type=DeviceType.MASTER_CONTROLLER, is_online=True,
               last_seen_at=datetime.now(timezone.utc))
    db.add(d)
    db.commit()
    return d


@pytest.fixture
def person(db) -> User:
    u = User(email="card@test.edu", full_name="Mohamed Magdy",
             hashed_password=hash_password("Password123"), role=Role.STUDENT,
             auth_subject="USER4")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _run(client, h, device_headers, person, path, status="DONE", step="STORED", uid=None):
    r = client.post(f"/api/users/{person.id}/rfid/{path}", headers=h, json={})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    nxt = client.get("/api/access/commands/next?device_uid=MASTER_CARD", headers=device_headers).json()
    assert nxt["id"] == cid and nxt["slot"] == 4 and nxt["display_name"] == "MOHAMED"
    body = {"device_uid": "MASTER_CARD", "status": status, "step": step}
    if uid:
        body["uid"] = uid
    assert client.post(f"/api/access/commands/{cid}/progress", headers=device_headers,
                       json=body).status_code == 200
    return nxt


def _cards(client, h, person):
    return [c["uid_hex"] for c in client.get(f"/api/users/{person.id}/rfid", headers=h).json()]


def test_students_cannot_enroll_cards(client, alice, person, master):
    h = auth_headers(client, alice.email)
    assert client.post(f"/api/users/{person.id}/rfid/enroll", headers=h, json={}).status_code == 403
    assert client.get(f"/api/users/{person.id}/rfid", headers=h).status_code == 403


def test_card_enrollment_records_the_card(client, db, staff, person, master, device_headers):
    h = auth_headers(client, staff.email)
    nxt = _run(client, h, device_headers, person, "enroll", uid="04:A1:B2:C3")
    assert nxt["command"] == "ENROLL_RFID"
    assert _cards(client, h, person) == ["04A1B2C3"]
    assert db.query(AuditLog).filter_by(action="RFID_ENROLLED").count() == 1

    # A new card replaces the old one: one active card per person.
    _run(client, h, device_headers, person, "enroll", uid="DE:AD:BE:EF")
    assert _cards(client, h, person) == ["DEADBEEF"]
    old = db.query(RfidCredential).filter_by(uid_hex="04A1B2C3").one()
    db.refresh(old)
    assert old.is_active is False and old.revoked_at is not None


def test_failed_card_enrollment_records_nothing(client, db, staff, person, master, device_headers):
    h = auth_headers(client, staff.email)
    _run(client, h, device_headers, person, "enroll", status="FAILED", step="CARD_IN_USE",
         uid="04:A1:B2:C3")
    assert _cards(client, h, person) == []
    assert db.query(AuditLog).filter_by(action="RFID_ENROLL_FAILED").count() == 1


def test_card_removal_revokes(client, db, staff, person, master, device_headers):
    h = auth_headers(client, staff.email)
    _run(client, h, device_headers, person, "enroll", uid="04:A1:B2:C3")
    nxt = _run(client, h, device_headers, person, "remove", step="REMOVED", uid="04:A1:B2:C3")
    assert nxt["command"] == "REMOVE_RFID"
    assert _cards(client, h, person) == []
    assert db.query(AuditLog).filter_by(action="RFID_REMOVED").count() == 1


def test_card_needs_a_door_identity(client, db, staff, master):
    u = User(email="noid@test.edu", full_name="No Id", hashed_password=hash_password("Password123"),
             role=Role.STUDENT)
    db.add(u)
    db.commit()
    r = client.post(f"/api/users/{u.id}/rfid/enroll", headers=auth_headers(client, staff.email), json={})
    assert r.status_code == 409
