"""Sign-up needs approval unless someone turned that off on purpose (2026-11-16 pre-lab hardening)."""
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings, settings
from app.models import Role, User

NEW = {"email": "pending.student@example.com", "username": "pending.student", "full_name": "Pending Student",
       "password": "Lab-Secure#2026", "student_id": "S-7", "department": "EE"}
ROOT = Path(__file__).resolve().parents[1]


def test_omitted_setting_means_approval_required(monkeypatch):
    monkeypatch.delenv("SIGNUP_REQUIRES_APPROVAL", raising=False)
    assert Settings(_env_file=None).SIGNUP_REQUIRES_APPROVAL is True
    assert Settings.model_fields["SIGNUP_REQUIRES_APPROVAL"].default is True


def test_open_signup_needs_an_explicit_false(monkeypatch):
    monkeypatch.setenv("SIGNUP_REQUIRES_APPROVAL", "false")
    assert Settings(_env_file=None).SIGNUP_REQUIRES_APPROVAL is False


def test_with_the_default_a_signup_creates_a_pending_student(client, db):
    assert settings.SIGNUP_REQUIRES_APPROVAL is True          # the test process runs on the shipped default
    r = client.post("/api/auth/signup", json=NEW)
    assert r.status_code == 201 and r.json()["pending_approval"] is True and "access_token" not in r.json()
    u = db.scalar(select(User).where(User.email == NEW["email"]))
    assert u.role == Role.STUDENT and u.is_active is False


def test_a_pending_account_cannot_sign_in_or_reach_protected_routes(client, db):
    client.post("/api/auth/signup", json=NEW)
    login = client.post("/api/auth/login", json={"email": NEW["email"], "password": NEW["password"]})
    assert login.status_code == 403 and "access_token" not in login.text
    assert client.get("/api/auth/me").status_code in (401, 403)             # no token, no data
    assert client.get("/api/labs").status_code in (401, 403)


def test_only_an_administrator_can_approve_and_then_login_works(client, db, admin, alice):
    from tests.conftest import auth_headers
    client.post("/api/auth/signup", json=NEW)
    uid = db.scalar(select(User).where(User.email == NEW["email"])).id
    # a student cannot approve
    assert client.patch(f"/api/users/{uid}", json={"is_active": True},
                        headers=auth_headers(client, alice.email)).status_code in (401, 403)
    assert db.scalar(select(User).where(User.id == uid)).is_active is False
    # an administrator can
    ok = client.patch(f"/api/users/{uid}", json={"is_active": True}, headers=auth_headers(client, admin.email))
    assert ok.status_code == 200
    login = client.post("/api/auth/login", json={"email": NEW["email"], "password": NEW["password"]})
    assert login.status_code == 200 and login.json()["access_token"]


def test_shipped_defaults_agree_everywhere():
    compose = (ROOT.parent / "docker-compose.yml")
    example = (ROOT.parent / ".env.example")
    if compose.exists():                                   # the backend container only mounts ./backend
        assert "SIGNUP_REQUIRES_APPROVAL: ${SIGNUP_REQUIRES_APPROVAL:-true}" in compose.read_text(encoding="utf-8")
    if example.exists():
        assert "SIGNUP_REQUIRES_APPROVAL=true" in example.read_text(encoding="utf-8")
