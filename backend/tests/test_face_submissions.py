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
    """Saves a sample for each photo unless told how many faces it 'finds'; /identify says
    "a face, nobody else" unless told otherwise; records /train calls."""
    state = {"posts": 0, "usable": None, "down": False, "trains": 0, "identify": None,
             "identify_down": False, "checks": 0}

    def post(url, params=None, content=None, headers=None, timeout=None):
        if state["down"] or (url.endswith("/identify") and state["identify_down"]):
            raise httpx.ConnectError("down")
        if url.endswith("/identify"):
            assert content and headers.get("X-Device-Key")
            state["checks"] += 1
            v = state["identify"]
            return _Resp(v(state["checks"]) if callable(v) else (v or {"face": True, "name": None}))
        if url.endswith("/train"):
            state["trains"] += 1
            return _Resp({"ok": True})
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


def test_photo_count_and_image_checks(client, newbie):
    assert _send(client, newbie, n=3).status_code == 400
    r = _send(client, newbie, data=b"not an image")
    assert r.status_code == 400 and "Photo 1" in r.json()["detail"]


def test_registered_people_may_refresh_their_photos(client, db, alice, face_server):
    """Owner 2026-10-20: the button is there for everyone with a door identity."""
    alice.auth_subject = "USER8"
    db.commit()
    assert _send(client, alice).status_code == 201


def test_photo_without_a_face_is_refused_at_once(client, db, newbie, face_server):
    face_server["identify"] = lambda n: {"face": n != 3, "name": None}
    r = _send(client, newbie)
    assert r.status_code == 400 and r.json()["detail"].startswith("Photo 3: no clear face")
    assert db.query(FaceSubmission).count() == 0              # nothing kept


def test_another_persons_face_is_refused_without_naming_them(client, db, newbie, face_server):
    face_server["identify"] = {"face": True, "name": "USER1"}
    r = _send(client, newbie)
    assert r.status_code == 400
    assert "another registered person" in r.json()["detail"] and "USER1" not in r.json()["detail"]
    face_server["identify"] = {"face": True, "name": "USER8"}  # their own earlier samples: fine
    assert _send(client, newbie).status_code == 201


def test_unchecked_when_face_server_down_and_staff_are_told(client, db, staff, newbie, face_server):
    face_server["identify_down"] = True
    r = _send(client, newbie)
    assert r.status_code == 201 and r.json()["auto_checked"] is False
    n = db.query(Notification).filter_by(user_id=staff.id, kind="FACE_REVIEW").one()
    assert "could not check" in n.body and n.link == f"/admin/users?face={newbie.id}"


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
    assert face_server["posts"] == 5 and face_server["trains"] == 1   # new samples used at once
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
    n = db.query(Notification).filter_by(user_id=newbie.id).filter(
        Notification.title.startswith("Face photos not accepted")).one()
    assert "Sunglasses" in n.body and "come to the lab staff" in n.body
    r = _send(client, newbie)                                 # refused: in person from now on
    assert r.status_code == 409 and "lab staff" in r.json()["detail"]
    me = client.get("/api/auth/me/face-submission", headers=auth_headers(client, newbie.email)).json()
    assert me["status"] == "REJECTED" and me["refused_until_seen"] is True


def test_refusal_lifts_after_enrolment_in_person(client, db, staff, newbie, face_server):
    from datetime import datetime, timedelta, timezone
    sid = _send(client, newbie).json()["id"]
    client.post(f"/api/face-submissions/{sid}/reject", json={"reason": "Not you."},
                headers=auth_headers(client, staff.email))
    newbie.face_enrolled_at = datetime.now(timezone.utc) + timedelta(seconds=1)   # staff, at the door
    db.commit()
    assert _send(client, newbie).status_code == 201


def test_retake_asks_for_new_photos(client, db, staff, newbie, face_server):
    sid = _send(client, newbie).json()["id"]
    r = client.post(f"/api/face-submissions/{sid}/retake", json={"reason": "Too dark."},
                    headers=auth_headers(client, staff.email))
    assert r.status_code == 200 and r.json()["status"] == "RETAKE"
    assert face_server["posts"] == 0
    s = db.get(FaceSubmission, sid)
    db.refresh(s)
    assert not _files_exist(s)
    n = db.query(Notification).filter_by(user_id=newbie.id, title="Please retake your Face ID photos").one()
    assert "Too dark" in n.body
    assert _send(client, newbie).status_code == 201           # may send new ones
    assert db.query(AuditLog).filter_by(action="FACE_PHOTOS_RETAKE").count() == 1


def test_staff_list_of_waiting_submissions(client, staff, newbie, bob, face_server):
    sid = _send(client, newbie).json()["id"]
    r = client.get("/api/face-submissions", headers=auth_headers(client, staff.email))
    assert [x["id"] for x in r.json()] == [sid]
    assert client.get("/api/face-submissions", headers=auth_headers(client, bob.email)).status_code == 403


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
    h = auth_headers(client, bob.email)
    assert client.post(f"/api/face-submissions/{sid}/approve", headers=h).status_code == 403
    assert client.post(f"/api/face-submissions/{sid}/retake", json={"reason": "xxx"},
                       headers=h).status_code == 403


def test_withdraw(client, db, newbie, face_server):
    sid = _send(client, newbie).json()["id"]
    r = client.post("/api/auth/me/face-submission/withdraw", headers=auth_headers(client, newbie.email))
    assert r.json()["status"] == "WITHDRAWN"
    s = db.get(FaceSubmission, sid)
    db.refresh(s)
    assert not _files_exist(s)
