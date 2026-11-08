"""Editing an account: the name and the sign-in email are separate fields."""
from app.models import User
from tests.conftest import auth_headers


def test_admin_changes_email_and_person_signs_in_with_it(client, db, admin, alice):
    h = auth_headers(client, admin.email)
    r = client.patch(f"/api/users/{alice.id}", headers=h,
                     json={"full_name": "Alice Renamed", "email": "Alice.New@Test.edu"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "alice.new@test.edu" and r.json()["full_name"] == "Alice Renamed"
    assert client.post("/api/auth/login", json={"email": "alice.new@test.edu",
                                                 "password": "Password123"}).status_code == 200


def test_name_change_alone_keeps_email(client, db, admin, alice):
    h = auth_headers(client, admin.email)
    old = alice.email
    assert client.patch(f"/api/users/{alice.id}", headers=h, json={"full_name": "X Y"}).json()["email"] == old


def test_email_must_be_unique_and_valid(client, db, admin, alice, staff):
    h = auth_headers(client, admin.email)
    assert client.patch(f"/api/users/{alice.id}", headers=h,
                        json={"email": staff.email.upper()}).status_code == 409
    assert client.patch(f"/api/users/{alice.id}", headers=h, json={"email": "nope"}).status_code == 422


def test_remove_user_keeps_history_and_revokes_credentials(client, db, admin, alice):
    from app.models import RfidCredential, User
    db.add(RfidCredential(uid_hex="AABBCCDD", user_id=alice.id))
    db.commit()
    h = auth_headers(client, admin.email)
    r = client.post(f"/api/users/{alice.id}/remove", headers=h)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(User, alice.id).is_active is False          # still there: history kept
    assert db.query(RfidCredential).one().revoked_at is not None
    assert client.post(f"/api/users/{admin.id}/remove", headers=h).status_code == 409
