"""
Lab access setup reminder: information only. The door logic never reads
these flags - they only tell a person to get their biometrics registered.
"""
from sqlalchemy import select

from app.models import Notification
from tests.conftest import auth_headers

NEW = {"email": "new@example.com", "full_name": "New Student", "password": "Password123"}


def _titles(db, user_id):
    return [n.title for n in db.scalars(select(Notification).where(
        Notification.user_id == user_id).order_by(Notification.id)).all()]


def test_new_account_is_told_to_confirm_biometrics(client, db, admin):
    token = client.post("/api/auth/signup", json=NEW).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    uid = client.get("/api/auth/me", headers=h).json()["id"]
    assert _titles(db, uid) == ["Action needed: confirm your fingerprint and Face ID"]
    st = client.get("/api/auth/me/access-setup", headers=h).json()
    assert st["complete"] is False and st["pending"] == ["Fingerprint", "Face ID"]
    assert "visit the lab staff" in st["summary"]


def _pending(db, user):
    user.fingerprint_enrolled_at = user.face_enrolled_at = None
    db.commit()


def test_existing_account_reminded_once_on_login(client, db, bob):
    _pending(db, bob)
    for _ in range(3):
        auth_headers(client, bob.email)
    assert _titles(db, bob.id).count(
        "Action needed: confirm your fingerprint and Face ID") == 1


def test_staff_confirm_completes_setup(client, db, admin, alice):
    _pending(db, alice)
    h = auth_headers(client, admin.email)
    r = client.patch(f"/api/users/{alice.id}", headers=h, json={"fingerprint_enrolled": True})
    assert r.status_code == 200 and r.json()["fingerprint_enrolled_at"]
    st = client.get(f"/api/users/{alice.id}/access-setup", headers=h).json()
    assert st["complete"] is False and st["pending"] == ["Face ID"]
    client.patch(f"/api/users/{alice.id}", headers=h, json={"face_enrolled": True})
    st = client.get("/api/auth/me/access-setup",
                    headers=auth_headers(client, alice.email)).json()
    assert st["complete"] is True and st["pending"] == []
    titles = [t for t in _titles(db, alice.id) if "confirmed" in t]
    assert "Fingerprint confirmed" in titles
    assert "Face ID confirmed - lab access setup complete" in titles
    # Undo is possible (e.g. a template was deleted from the sensor).
    r = client.patch(f"/api/users/{alice.id}", headers=h, json={"face_enrolled": False})
    assert r.json()["face_enrolled_at"] is None


def test_complete_or_doorless_accounts_get_no_reminder(client, db, alice, admin):
    auth_headers(client, alice.email)          # enrolled in the fixture
    auth_headers(client, admin.email)          # no door identity: not a door user
    assert _titles(db, admin.id) == []
    assert _titles(db, alice.id) == []


def test_students_cannot_confirm_their_own(client, alice):
    r = client.patch(f"/api/users/{alice.id}", headers=auth_headers(client, alice.email),
                     json={"fingerprint_enrolled": True})
    assert r.status_code == 403
