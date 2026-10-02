"""
Face enrollment from the portal (Users & roles -> Edit user -> Face ID).

The camera and the face server are replaced by fakes: what is tested is the
portal's part - who may do it, what it refuses, and that finishing marks the
person as enrolled and leaves an audit record. No hardware is needed.
"""
import httpx
import pytest

from app.api.routes import enrollment
from app.models import AuditLog, Notification, Role, User
from app.core.security import hash_password
from tests.conftest import auth_headers


class _Resp:
    def __init__(self, body=None, status=200, content=b""):
        self._body, self.status_code, self.content = body, status, content

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=None, response=None)


@pytest.fixture
def newbie(db) -> User:
    u = User(email="new@test.edu", full_name="New Person",
             hashed_password=hash_password("Password123"),
             role=Role.STUDENT, auth_subject="USER7")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def fake_devices(monkeypatch):
    """A camera and face server that remember how many samples USER7 has."""
    state = {"samples": 0, "trained": False, "camera_up": True}

    def get(url, params=None, timeout=None):
        if url.endswith("/users"):
            return _Resp({"users": {"USER7": state["samples"]},
                          "portraits": ["USER7"] if state["samples"] else []})
        if not state["camera_up"]:
            raise httpx.ConnectTimeout("down")
        if url.endswith("/enroll"):
            state["samples"] += 1
            return _Resp({"status": "saved", "samples": state["samples"]})
        if url.endswith("/snapshot"):
            return _Resp(content=b"\xff\xd8jpeg")
        raise AssertionError(url)

    def post(url, timeout=None):
        assert url.endswith("/train")
        state["trained"] = True
        return _Resp({"status": "trained"})

    monkeypatch.setattr(enrollment.httpx, "get", get)
    monkeypatch.setattr(enrollment.httpx, "post", post)
    return state


def test_students_cannot_enroll_faces(client, alice, newbie, fake_devices):
    h = auth_headers(client, alice.email)
    assert client.post(f"/api/users/{newbie.id}/face/capture", headers=h).status_code == 403
    assert client.get("/api/enrollment/camera/snapshot", headers=h).status_code == 403


def test_capture_then_finish_marks_face_enrolled(client, db, staff, newbie, fake_devices):
    h = auth_headers(client, staff.email)
    for _ in range(enrollment.MIN_SAMPLES):
        r = client.post(f"/api/users/{newbie.id}/face/capture", headers=h)
        assert r.status_code == 200 and r.json()["saved"] is True

    st = client.get(f"/api/users/{newbie.id}/face", headers=h).json()
    assert st["samples"] == enrollment.MIN_SAMPLES and st["has_photo"] is True

    r = client.post(f"/api/users/{newbie.id}/face/finish", headers=h)
    assert r.status_code == 200, r.text
    assert fake_devices["trained"] is True
    db.refresh(newbie)
    assert newbie.face_enrolled_at is not None
    assert db.query(AuditLog).filter_by(action="FACE_ENROLLED",
                                        entity_id=str(newbie.id)).count() == 1
    # The person is told their Face ID is confirmed.
    assert db.query(Notification).filter_by(user_id=newbie.id,
                                            kind="ACCESS_SETUP").count() == 1


def test_finish_refuses_too_few_samples(client, db, staff, newbie, fake_devices):
    h = auth_headers(client, staff.email)
    client.post(f"/api/users/{newbie.id}/face/capture", headers=h)
    r = client.post(f"/api/users/{newbie.id}/face/finish", headers=h)
    assert r.status_code == 409
    assert fake_devices["trained"] is False
    db.refresh(newbie)
    assert newbie.face_enrolled_at is None


def test_needs_a_door_identity_first(client, db, staff, newbie, fake_devices):
    newbie.auth_subject = None
    db.commit()
    h = auth_headers(client, staff.email)
    assert client.post(f"/api/users/{newbie.id}/face/capture", headers=h).status_code == 409


def test_camera_offline_is_a_clear_503(client, staff, newbie, fake_devices):
    fake_devices["camera_up"] = False
    h = auth_headers(client, staff.email)
    r = client.post(f"/api/users/{newbie.id}/face/capture", headers=h)
    assert r.status_code == 503
    assert "camera" in r.json()["detail"]
