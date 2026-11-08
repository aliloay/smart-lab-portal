"""Usernames (owner, 2026-10-20): sign in with e-mail or username; new accounts need firstname.lastname;
administrators give or change anyone's username at any time."""
from app.core import usernames
from app.models import AuditLog

from .conftest import auth_headers

NEW = {"email": "nour.kamel@example.com", "username": "nour.kamel", "full_name": "Nour Kamel",
       "password": "Lab-Secure#2026"}


def test_suggestion_is_firstname_lastname_without_titles():
    assert usernames.suggest("Dr. Ramy Amir Shawkey Shenouda") == "ramy.shenouda"
    assert usernames.suggest("Nour Ramy") == "nour.ramy"
    assert usernames.suggest("Ali Loay Abozeid") == "ali.abozeid"
    assert usernames.suggest("Eng. Ahmed Hemaly") == "ahmed.hemaly"
    assert usernames.suggest("  Ålia  Nøur ") == "alia.nur"


def test_format_rules():
    assert usernames.normalize(" Ali.Abozeid ") == "ali.abozeid"
    assert usernames.normalize("") is None
    for bad in ("ali", "ali@x.de", "ali..abozeid", ".ali", "ali.", "1ali.b", "ali abozeid", "a." * 40 + "b"):
        try:
            usernames.normalize(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_signup_needs_a_valid_free_username(client):
    assert client.post("/api/auth/signup", json={k: v for k, v in NEW.items() if k != "username"}).status_code == 422
    assert client.post("/api/auth/signup", json={**NEW, "username": "nourkamel"}).status_code == 422
    r = client.post("/api/auth/signup", json={**NEW, "username": "Nour.Kamel"})
    assert r.status_code == 201
    taken = client.post("/api/auth/signup", json={**NEW, "email": "other@example.com"})
    assert taken.status_code == 409 and "taken" in taken.json()["detail"]


def test_sign_in_with_email_or_username(client, alice, db):
    alice.username = "alice.liddell"
    db.commit()
    for ident in ("alice@test.edu", "alice.liddell", "Alice.Liddell", "  alice.liddell "):
        r = client.post("/api/auth/login", json={"email": ident, "password": "Password123"})
        assert r.status_code == 200, (ident, r.text)
    wrong = client.post("/api/auth/login", json={"email": "alice.liddell", "password": "nope-nope"})
    nobody = client.post("/api/auth/login", json={"email": "no.body", "password": "nope-nope"})
    assert wrong.status_code == nobody.status_code == 401
    assert wrong.json()["detail"] == nobody.json()["detail"]                  # no account enumeration


def test_admin_gives_changes_and_removes_usernames(client, db, admin, alice, bob, staff):
    h = auth_headers(client, admin.email)
    r = client.patch(f"/api/users/{alice.id}", headers=h, json={"username": "alice.liddell"})
    assert r.status_code == 200 and r.json()["username"] == "alice.liddell"
    assert client.patch(f"/api/users/{bob.id}", headers=h, json={"username": "alice.liddell"}).status_code == 409
    assert client.patch(f"/api/users/{bob.id}", headers=h, json={"username": "bob"}).status_code == 422
    assert client.patch(f"/api/users/{staff.id}", headers=h, json={"username": "lab.tech"}).json()["username"] == "lab.tech"
    assert client.patch(f"/api/users/{alice.id}", headers=h, json={"username": "alice.l"}).json()["username"] == "alice.l"
    assert client.post("/api/auth/login", json={"email": "alice.l", "password": "Password123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "alice.liddell", "password": "Password123"}).status_code == 401
    assert client.patch(f"/api/users/{alice.id}", headers=h, json={"username": ""}).json()["username"] is None
    # lab staff cannot change usernames (administrators only)
    assert client.patch(f"/api/users/{alice.id}", headers=auth_headers(client, staff.email),
                        json={"username": "x.y"}).status_code == 403
    assert db.query(AuditLog).filter(AuditLog.action.like("USER_%")).count() >= 1


def test_admin_created_account_with_username(client, admin):
    h = auth_headers(client, admin.email)
    r = client.post("/api/auth/register", headers=h, json={**NEW, "role": "LAB_STAFF"})
    assert r.status_code == 201 and r.json()["username"] == "nour.kamel"
    assert client.post("/api/auth/register", headers=h,
                       json={**NEW, "email": "z@example.com"}).status_code == 409
    sug = client.get("/api/auth/username-suggestion", params={"full_name": "Dr. Ramy Shenouda"}).json()
    assert sug == {"username": "ramy.shenouda"}
