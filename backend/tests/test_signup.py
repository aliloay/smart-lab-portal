"""Self-service sign-up: always an un-enrolled student, admins notified."""
from sqlalchemy import select

from app.core.config import settings
from app.models import Notification, Role, User

NEW = {"email": "New.Student@Example.com", "full_name": "New Student",
       "password": "Password123", "student_id": "S-9", "department": "EE"}


def test_signup_creates_student_and_logs_in(client, db, admin):
    r = client.post("/api/auth/signup", json=NEW)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["pending_approval"] is False and body["access_token"]
    assert body["role"] == "STUDENT"
    u = db.scalar(select(User).where(User.email == "new.student@example.com"))
    assert u.role == Role.STUDENT and u.auth_subject is None and u.is_active
    me = client.get("/api/auth/me",
                    headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["email"] == "new.student@example.com"
    n = db.scalars(select(Notification).where(
        Notification.user_id == admin.id)).all()
    assert [x.kind for x in n] == ["USER_SIGNUP"]


def test_signup_cannot_choose_role_or_enrolment(client, db):
    r = client.post("/api/auth/signup",
                    json={**NEW, "role": "ADMIN", "auth_subject": "USER9"})
    assert r.status_code == 201
    u = db.scalar(select(User).where(User.email == "new.student@example.com"))
    assert u.role == Role.STUDENT and u.auth_subject is None


def test_signup_duplicate_email(client, alice):
    r = client.post("/api/auth/signup", json={**NEW, "email": alice.email.upper()})
    assert r.status_code == 409


def test_signup_domain_restriction(client, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUP_EMAIL_DOMAINS", "giu-uni.de")
    assert client.get("/api/auth/signup-config").json()["email_domains"] == ["giu-uni.de"]
    assert client.post("/api/auth/signup", json=NEW).status_code == 422
    ok = client.post("/api/auth/signup", json={**NEW, "email": "x.y@giu-uni.de"})
    assert ok.status_code == 201


def test_signup_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUP_ENABLED", False)
    assert client.get("/api/auth/signup-config").json()["enabled"] is False
    assert client.post("/api/auth/signup", json=NEW).status_code == 403


def test_signup_pending_approval_blocks_login(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUP_REQUIRES_APPROVAL", True)
    r = client.post("/api/auth/signup", json=NEW)
    assert r.status_code == 201 and r.json() == {
        "pending_approval": True, "message": r.json()["message"]}
    login = client.post("/api/auth/login",
                        json={"email": NEW["email"], "password": NEW["password"]})
    assert login.status_code == 403


def test_signup_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUPS_PER_IP_PER_HOUR", 2)
    for i in range(2):
        assert client.post("/api/auth/signup",
                           json={**NEW, "email": f"s{i}@example.com"}).status_code == 201
    assert client.post("/api/auth/signup",
                       json={**NEW, "email": "s3@example.com"}).status_code == 429


def test_signup_weak_password(client):
    assert client.post("/api/auth/signup",
                       json={**NEW, "password": "short"}).status_code == 422
