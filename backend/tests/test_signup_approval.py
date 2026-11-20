"""
Self-signup requires admin approval: the account is inactive, an admin notification is
created, and the admin user list surfaces it as pending_approval so it can be approved
(it must not be hidden like a removed account). 2026-11-20.
"""
from app.models import AuditLog, Notification, User


def _signup(client, email="newbie@giu-uni.de", username="new.bie"):
    return client.post("/api/auth/signup", json={
        "email": email, "username": username, "full_name": "New Bie",
        "password": "Str0ng-Pass-9xQ"})


def test_signup_is_pending_notifies_admin_and_is_listed_for_approval(client, db, admin, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "SIGNUP_ENABLED", True)
    monkeypatch.setattr(settings, "SIGNUP_REQUIRES_APPROVAL", True)

    r = _signup(client)
    assert r.status_code == 201 and r.json()["pending_approval"] is True
    u = db.query(User).filter_by(email="newbie@giu-uni.de").one()
    assert u.is_active is False

    # the admin was notified
    assert db.query(Notification).filter_by(user_id=admin.id, kind="USER_SIGNUP").count() == 1

    # the admin user list shows it as pending (not hidden like a removed account)
    from tests.conftest import auth_headers
    rows = client.get("/api/users", headers=auth_headers(client, admin.email)).json()
    row = next(x for x in rows if x["email"] == "newbie@giu-uni.de")
    assert row["pending_approval"] is True and row["is_active"] is False

    # approve -> active, and no longer pending
    pr = client.patch(f"/api/users/{u.id}", headers=auth_headers(client, admin.email),
                      json={"is_active": True})
    assert pr.status_code == 200
    rows = client.get("/api/users", headers=auth_headers(client, admin.email)).json()
    row = next(x for x in rows if x["email"] == "newbie@giu-uni.de")
    assert row["is_active"] is True and row["pending_approval"] is False


def test_admin_removed_account_is_not_pending(client, db, admin, staff, monkeypatch):
    # a removed (disabled) account must read as Disabled, never Pending approval
    from tests.conftest import auth_headers
    client.post(f"/api/users/{staff.id}/remove", headers=auth_headers(client, admin.email))
    rows = client.get("/api/users", headers=auth_headers(client, admin.email)).json()
    row = next(x for x in rows if x["id"] == staff.id)
    assert row["is_active"] is False and row["pending_approval"] is False
