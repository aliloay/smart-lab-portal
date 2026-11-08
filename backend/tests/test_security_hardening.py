"""
Security hardening (2026-10-08): password rules, Argon2id with bcrypt
upgrade, sign-in throttling and logging, safe 500s, API docs off.
"""
from fastapi import APIRouter
from passlib.hash import bcrypt

from app.core import password_policy
from app.core.security import hash_password, pwd_context
from app.models import AuditLog, User
from tests.conftest import auth_headers


def test_password_rules():
    assert password_policy.problems("Lab-Secure#2026") == []
    assert password_policy.problems("short1A!")                     # too short
    assert password_policy.problems("alllowercaseletters")          # one kind only
    assert "not a common password" in password_policy.problems("Password123")
    assert "not your name or email" in password_policy.problems("Alice#Garden2026", "alice@test.edu")
    assert "not your name or email" in password_policy.problems("Mohamed#2026xy", name="Mohamed Magdy")


def test_new_hashes_are_argon2id_and_old_bcrypt_is_upgraded_at_sign_in(client, db, alice):
    assert hash_password("Lab-Secure#2026").startswith("$argon2id$")
    alice.hashed_password = bcrypt.using(rounds=4).hash("Password123")   # an account from before
    db.commit()
    auth_headers(client, alice.email)
    db.expire_all()
    assert db.get(User, alice.id).hashed_password.startswith("$argon2id$")
    auth_headers(client, alice.email)                                    # still signs in afterwards


def test_admin_cannot_set_a_weak_password_and_signup_refuses_one(client, admin, alice):
    h = auth_headers(client, admin.email)
    r = client.put(f"/api/users/{alice.id}/password", headers=h, json={"new_password": "password123"})
    assert r.status_code == 422 and "common" in r.text
    assert client.put(f"/api/users/{alice.id}/password", headers=h,
                      json={"new_password": "Lab-Secure#2026"}).status_code == 200
    r = client.post("/api/auth/register", headers=h, json={
        "email": "new@test.edu", "full_name": "New Person", "password": "Password123"})
    assert r.status_code == 422


def test_failed_sign_ins_are_logged_then_throttled(client, db, alice):
    for _ in range(8):
        r = client.post("/api/auth/login", json={"email": alice.email, "password": "Wrong-guess#1"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": alice.email, "password": "Password123"})
    assert r.status_code == 429 and "Retry-After" in r.headers          # even the right password waits
    fails = db.query(AuditLog).filter_by(action="LOGIN_FAILED").all()
    assert len(fails) == 8 and all("Wrong" not in str(f.detail) for f in fails)   # never the password
    # Another account from the same machine is not blocked by Alice's count.
    r = client.post("/api/auth/login", json={"email": "nobody@test.edu", "password": "x"})
    assert r.status_code == 401


def test_unexpected_errors_are_generic_outside_and_logged_inside(client, caplog):
    from app.main import app
    router = APIRouter()

    @router.get("/api/__boom")
    def boom():
        raise RuntimeError("secret detail: postgresql://user:pw@db/x")

    app.include_router(router)
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/__boom", headers={"X-Request-ID": "req-12345678"})
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "An unexpected error occurred." and body["error_id"]
    assert "postgresql" not in r.text and "Traceback" not in r.text
    assert r.headers["X-Request-ID"] == "req-12345678"
    assert any(body["error_id"] in rec.getMessage() for rec in caplog.records)


def test_api_docs_are_not_public(client):
    assert client.get("/api/openapi.json").status_code == 404
    assert client.get("/api/docs").status_code == 404
