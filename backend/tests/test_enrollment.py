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


# --------------------------------------------- photos uploaded by staff ---
def _png(color=(200, 150, 120)) -> bytes:
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(b, "PNG")
    return b.getvalue()


@pytest.fixture
def fake_face_server(monkeypatch):
    """/enroll saves a sample unless the photo is all black (no face)."""
    state = {"samples": 0, "trained": 0, "posted": []}

    def get(url, params=None, timeout=None):
        assert url.endswith("/users")
        return _Resp({"users": {"USER7": state["samples"]}, "portraits": ["USER7"]})

    def post(url, params=None, content=None, headers=None, timeout=None):
        if url.endswith("/train"):
            state["trained"] += 1
            return _Resp({"status": "trained"})
        assert url.endswith("/enroll") and params == {"name": "USER7"}
        state["posted"].append(headers["Content-Type"])
        from PIL import Image
        import io
        if Image.open(io.BytesIO(content)).getpixel((1, 1)) == (0, 0, 0):
            return _Resp({"status": "no_face"})
        state["samples"] += 1
        return _Resp({"status": "saved"})

    monkeypatch.setattr(enrollment.httpx, "get", get)
    monkeypatch.setattr(enrollment.httpx, "post", post)
    return state


def _upload(client, h, user, photos):
    return client.post(f"/api/users/{user.id}/face/upload", headers=h,
                       files=[("files", (f"p{i}.png", p, "image/png")) for i, p in enumerate(photos)])


def test_staff_upload_photos_registers_face(client, db, staff, newbie, fake_face_server):
    h = auth_headers(client, staff.email)
    r = _upload(client, h, newbie, [_png(), _png(), _png(), _png((0, 0, 0))])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] == 3 and body["sent"] == 4 and body["face_enrolled"] is True
    assert "1 had no clear face" in body["message"]
    assert fake_face_server["trained"] == 1
    db.refresh(newbie)
    assert newbie.face_enrolled_at is not None
    assert db.query(AuditLog).filter_by(action="FACE_PHOTOS_UPLOADED").count() == 1


def test_too_few_uploaded_photos_do_not_register(client, db, staff, newbie, fake_face_server):
    r = _upload(client, auth_headers(client, staff.email), newbie, [_png()])
    assert r.status_code == 200 and r.json()["face_enrolled"] is False
    db.refresh(newbie)
    assert newbie.face_enrolled_at is None


def test_upload_rejects_non_images_and_students(client, staff, alice, newbie, fake_face_server):
    r = client.post(f"/api/users/{newbie.id}/face/upload", headers=auth_headers(client, staff.email),
                    files=[("files", ("x.png", b"not an image", "image/png"))])
    assert r.status_code == 400 and fake_face_server["posted"] == []
    assert _upload(client, auth_headers(client, alice.email), newbie, [_png()]).status_code == 403
