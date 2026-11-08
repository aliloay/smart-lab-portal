"""
Administrators and lab staff manage people's sign-in details.

  * an administrator can change anyone's name, e-mail and password;
  * lab staff can do it for STUDENTS only, and never change a role, the door
    identity or whether an account is active (an administrator's job);
  * the new password works at once, the old one stops; the audit log records
    who changed whose password - never the password itself.
"""
from app.models import AuditLog
from tests.conftest import auth_headers


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password}).status_code


def test_admin_sets_anyones_password(client, db, admin, staff):
    h = auth_headers(client, admin.email)
    r = client.put(f"/api/users/{staff.id}/password", headers=h, json={"new_password": "Bench-Ready#2026"})
    assert r.status_code == 200, r.text
    assert _login(client, staff.email, "Bench-Ready#2026") == 200
    assert _login(client, staff.email, "Password123") == 401
    log = db.query(AuditLog).filter_by(action="USER_PASSWORD_SET", entity_id=str(staff.id)).one()
    assert "Bench-Ready#2026" not in str(log.detail)


def test_staff_manage_students_only(client, db, staff, alice, admin):
    h = auth_headers(client, staff.email)
    assert client.put(f"/api/users/{alice.id}/password", headers=h,
                      json={"new_password": "Student#2026"}).status_code == 200
    assert _login(client, alice.email, "Student#2026") == 200
    r = client.patch(f"/api/users/{alice.id}", headers=h, json={"full_name": "Alice Smith",
                                                                    "email": "alice.smith@test.edu"})
    assert r.status_code == 200 and r.json()["full_name"] == "Alice Smith"
    # Not another staff member or an administrator, and not the admin-only fields.
    assert client.put(f"/api/users/{admin.id}/password", headers=h,
                      json={"new_password": "Hijack#2026"}).status_code == 403
    assert client.patch(f"/api/users/{admin.id}", headers=h, json={"full_name": "x"}).status_code == 403
    assert client.patch(f"/api/users/{alice.id}", headers=h, json={"role": "ADMIN"}).status_code == 403
    assert client.patch(f"/api/users/{alice.id}", headers=h, json={"is_active": False}).status_code == 403


def test_students_cannot_and_short_passwords_are_refused(client, admin, alice, bob):
    assert client.put(f"/api/users/{bob.id}/password", headers=auth_headers(client, alice.email),
                      json={"new_password": "Whatever#2026"}).status_code == 403
    assert client.put(f"/api/users/{bob.id}/password", headers=auth_headers(client, admin.email),
                      json={"new_password": "short"}).status_code == 422
