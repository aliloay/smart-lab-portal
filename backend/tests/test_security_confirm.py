"""
Staff Confirm on the Security page (2026-11-17), with "Other..." (2026-11-18, owner): a person not registered yet is
typed in, added to the portal as a person the cameras can name (no login) and confirmed in the same step. The camera
service is replaced by a fake; what is checked is what the portal sends it and what it keeps.
"""
import httpx

from app.api.routes import security
from app.models import AuditLog, User
from tests.conftest import auth_headers


def _camera(client, device_headers, lab):
    r = client.get("/api/security/config", headers=device_headers,
                   params={"device_uid": "SECCAM_LAB01", "lab_id": lab.code, "port": 5100})
    return r.json()["device_id"]


def _fake(monkeypatch, ok=True):
    sent = []

    def request(method, url, headers=None, timeout=None, json=None, **kw):
        sent.append(json)
        body = {"ok": True, "track_id": json["track_id"], "label": json["label"],
                "name": json.get("name") or json["label"]} if ok else {"ok": False, "error": "that person is no longer in view"}
        return httpx.Response(200 if ok else 409, json=body)
    monkeypatch.setattr(security.httpx, "request", request)
    return sent


def test_other_adds_a_new_person_and_confirms_them(client, db, lab, admin, device_headers, monkeypatch):
    cid = _camera(client, device_headers, lab)
    sent = _fake(monkeypatch)
    r = client.post(f"/api/security/cameras/{cid}/confirm", headers=auth_headers(client, admin.email),
                    json={"track_id": 7, "label": "", "new_name": "  Omar   Hassan "})
    assert r.status_code == 200, r.text
    u = db.query(User).filter_by(full_name="Omar Hassan").one()
    assert u.auth_subject and u.email.endswith("@camera.smartlab.local") and u.is_active
    assert sent[-1]["label"] == u.auth_subject and sent[-1]["name"] == "Omar Hassan"
    assert db.query(AuditLog).filter_by(action="USER_CREATED", entity_id=str(u.id)).count() == 1
    # typed again (any case): the same person, not a second one
    client.post(f"/api/security/cameras/{cid}/confirm", headers=auth_headers(client, admin.email),
                json={"track_id": 8, "new_name": "omar hassan"})
    assert db.query(User).filter(User.full_name.ilike("omar hassan")).count() == 1


def test_a_refused_confirm_does_not_keep_the_new_person(client, db, lab, admin, device_headers, monkeypatch):
    cid = _camera(client, device_headers, lab)
    _fake(monkeypatch, ok=False)
    r = client.post(f"/api/security/cameras/{cid}/confirm", headers=auth_headers(client, admin.email),
                    json={"track_id": 7, "new_name": "Gone Person"})
    assert r.status_code == 409
    assert db.query(User).filter_by(full_name="Gone Person").count() == 0


def test_confirm_is_admin_only_and_needs_a_choice(client, lab, admin, alice, device_headers, monkeypatch):
    cid = _camera(client, device_headers, lab)
    _fake(monkeypatch)
    assert client.post(f"/api/security/cameras/{cid}/confirm", headers=auth_headers(client, alice.email),
                       json={"track_id": 1, "new_name": "X Y"}).status_code == 403
    assert client.post(f"/api/security/cameras/{cid}/confirm", headers=auth_headers(client, admin.email),
                       json={"track_id": 1}).status_code == 422
