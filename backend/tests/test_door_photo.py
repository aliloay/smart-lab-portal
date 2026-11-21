"""
Door photo picker (2026-11-21): staff choose which photo the ACCESS GRANTED screen shows; the backend passes the call to
the face server with the device key (the browser never gets it) and audits the choice.
"""
import httpx

from app.api.routes import enrollment
from app.models import AuditLog
from tests.conftest import auth_headers


class _FakeFace:
    def __init__(self):
        self.calls = []

    def request(self, method, url, headers=None, json=None, content=None, timeout=None):
        self.calls.append((method, url, headers, json))
        req = httpx.Request(method, url)
        if url.endswith("/info"):
            return httpx.Response(200, json={"has_photo": True, "source": "enrollment", "candidates": ["900", "400"],
                                             "camera_live": True}, request=req)
        if url.endswith("/choose"):
            if json.get("from") == "camera":
                return httpx.Response(409, json={"error": "no face in front of the door camera"}, request=req)
            return httpx.Response(200, json={"ok": True}, request=req)
        if url.endswith(".jpg"):
            return httpx.Response(200, content=b"\xff\xd8jpeg", request=req)
        return httpx.Response(404, json={"error": "nope"}, request=req)


def _fake(monkeypatch):
    f = _FakeFace()
    monkeypatch.setattr(enrollment, "_face", f)
    return f


def test_info_and_choose_candidate_is_audited(client, db, staff, alice, monkeypatch):
    f = _fake(monkeypatch)
    h = auth_headers(client, staff.email)
    info = client.get(f"/api/users/{alice.id}/door-photo", headers=h).json()
    assert info["candidates"] == ["900", "400"]
    assert f.calls[0][2]["X-Device-Key"]                       # the backend adds the device key
    r = client.post(f"/api/users/{alice.id}/door-photo/choose", headers=h, json={"from": "candidate", "candidate": "400"})
    assert r.status_code == 200, r.text
    assert f.calls[-1][1].endswith(f"/portrait/{alice.auth_subject}/choose")
    assert db.query(AuditLog).filter_by(action="DOOR_PHOTO_CHOSEN").count() == 1


def test_face_server_refusal_is_passed_on(client, staff, alice, monkeypatch):
    _fake(monkeypatch)
    r = client.post(f"/api/users/{alice.id}/door-photo/choose", headers=auth_headers(client, staff.email),
                    json={"from": "camera"})
    assert r.status_code == 409 and "door camera" in r.json()["detail"]


def test_images_stream_and_students_are_refused(client, staff, alice, monkeypatch):
    _fake(monkeypatch)
    r = client.get(f"/api/users/{alice.id}/door-photo/candidate/900.jpg", headers=auth_headers(client, staff.email))
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/users/{alice.id}/door-photo", headers=auth_headers(client, alice.email)).status_code == 403
