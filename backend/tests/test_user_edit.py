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
