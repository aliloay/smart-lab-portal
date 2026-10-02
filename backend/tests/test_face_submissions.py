"""
Face photos sent by the person, approved by staff (Profile -> Face ID).

Tested: who may send and review, that nothing is enrolled before approval,
that approval sends the photos to the face server and registers Face ID
only with enough usable faces, that rejection tells the person why, and
that the portal deletes its copies of the images after either decision.
The face server is a fake; no camera is needed.
"""
import httpx
import pytest

from app.api.routes import face_submissions as fsub
from app.core.security import hash_password
from app.models import AuditLog, FaceSubmission, Notification, Role, User
from app.services.storage import get_storage
from tests.conftest import auth_headers, image_bytes


@pytest.fixture
def newbie(db) -> User:
    u = User(email="selfie@test.edu", full_name="Sara Self",
             hashed_password=hash_password("Password123"),
             role=Role.STUDENT, auth_subject="USER8")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


class _Resp:
    def __init__(self, body):
        self._b = body
        self.status_code = 200

    def json(self):
        return self._b

    def raise_for_status(self):
        pass


@pytest.fixture
def face_server(monkeypatch):
    """Saves a sample for each photo unless told how many faces it 'finds'."""
    state = {"posts": 0, "usable": None, "down": False}

    def post(url, params=None, content=None, headers=None, timeout=None):
        if state["down"]:
            raise httpx.ConnectError("down")
        assert url.endswith("/enroll") and params["name"] == "USER8" and content
        state["posts"] += 1
        ok = state["usable"] is None or state["posts"] <= state["usable"]
        return _Resp({"status": "saved" if ok else "no face found - try again"})

    monkeypatch.setattr(fsub.httpx, "post", post)
    return state


def _send(client, user, n=5, data=None):
    files = [("files", (f"p{i}.jpg", data or image_bytes(), "image/jpeg")) for i in range(n)]
    return client.post("/api/auth/me/face-submission",
                       headers=auth_headers(client, user.email), files=files)


def _files_exist(s: FaceSubmission) -> bool:
    return any(get_storage().exists(k) for k in (s.photo_keys or []) + (s.thumb_keys or []))


def test_submit_waits_for_review_and_tells_staff(client, db, staff, newbie, face_server):
    r = _send(client, newbie)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "PENDING" and r.json()["photo_count"] == 5
    assert face_server["posts"] == 0                         # nothing enrolled yet
    db.refresh(newbie)
    assert newbie.face_enrolled_at is None
    assert db.query(Notification).filter_by(user_id=staff.id, kind="FACE_REVIEW").count() == 1
    assert _send(client, newbie).status_code == 409          # one at a time


def test_photo_count_and_image_checks(client, newbie, alice):
    assert _send(client, newbie, n=3).status_code == 400
    r = _send(client, newbie, data=b"not an image")
    assert r.status_code == 400 and "Photo 1" in r.json()["detail"]
    assert _send(client, alice).status_code == 409           # Face ID already registered


def test_only_owner_and_staff_see_the_photos(client, staff, newbie, bob):
    sid = _send(client, newbie).json()["id"]
    url = f"/api/face-submissions/{sid}/photos/0"
    assert client.get(url, headers=auth_headers(client, newbie.email)).status_code == 200
    assert client.get(url, headers=auth_headers(client, staff.email)).status_code == 200
    assert client.get(url, headers=auth_headers(client, bob.email)).status_code == 404


def test_approve_enrolls_and_deletes_the_images(client, db, staff, newbie, face_server):
    sid = _send(client, newbie).json()["id"]
    h = auth_headers(client, staff.email)
    assert client.get(f"/api/users/{newbie.id}/face/submission", headers=h).json()["id"] == sid
    r = client.post(f"/api/face-submissions/{sid}/approve", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED" and r.json()["samples_saved"] == 5
    assert face_server["posts"] == 5
    db.refresh(newbie)
    assert newbie.face_enrolled_at is not None
    s = db.get(FaceSubmission, sid)
    db.refresh(s)
    assert not _files_exist(s) and s.photo_keys == []
    assert db.query(AuditLog).filter_by(action="FACE_PHOTOS_APPROVED").count() == 1


def test_too_few_usable_faces_does_not_register(client, db, staff, newbie, face_server):
    face_server["usable"] = 2
    sid = _send(client, newbie).json()["id"]
    r = client.post(f"/api/face-submissions/{sid}/approve",
                    headers=auth_headers(client, staff.email)).json()
    assert r["samples_saved"] == 2 and "Only 2" in r["reason"]
    db.refresh(newbie)
    assert newbie.face_enrolled_at is None


def test_reject_tells_the_person_and_deletes(client, db, staff, newbie, face_server):
    sid = _send(client, newbie).json()["id"]
    r = client.post(f"/api/face-submissions/{sid}/reject", json={"reason": "Sunglasses on."},
                    headers=auth_headers(client, staff.email))
    assert r.json()["status"] == "REJECTED"
    assert face_server["posts"] == 0
    s = db.get(FaceSubmission, sid)
    db.refresh(s)
    assert not _files_exist(s)
    n = db.query(Notification).filter_by(user_id=newbie.id,
                                         title="Face photos not accepted").one()
    assert "Sunglasses" in n.body
    assert _send(client, newbie).status_code == 201          # may send new ones


def test_face_server_down_leaves_it_pending(client, db, staff, newbie, face_server):
    face_server["down"] = True
    sid = _send(client, newbie).json()["id"]
    r = client.post(f"/api/face-submissions/{sid}/approve", headers=auth_headers(client, staff.email))
    assert r.status_code == 503
    s = db.get(FaceSubmission, sid)
    db.refresh(s)
    assert s.status == "PENDING" and _files_exist(s)


def test_students_cannot_review(client, newbie, bob, face_server):
    sid = _send(client, newbie).json()["id"]
    assert client.post(f"/api/face-submissions/{sid}/approve",
                       headers=auth_headers(client, bob.email)).status_code == 403


def test_withdraw(client, db, newbie, face_server):
    sid = _send(client, newbie).json()["id"]
    r = client.post("/api/auth/me/face-submission/withdraw", headers=auth_headers(client, newbie.email))
    assert r.json()["status"] == "WITHDRAWN"
    s = db.get(FaceSubmission, sid)
    db.refresh(s)
    assert not _files_exist(s)
