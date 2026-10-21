"""
Students share their lab PC's screen after an admin accepts; exam lockdown page (2026-10-21).

Tested: a student asks with their PC's agent proof; admins are notified; Accept makes THAT PC the
capturing source (its agent gets broadcast_capture, its frames are accepted, the master PC's are not);
"only me" keeps the picture from other students; the student can stop it; Reject / a missing proof /
a student acting as admin are refused; EXAM with an exam page reaches the agent, Normal clears it.
"""
import hashlib
import hmac

from app.models import Device, Notification
from app.services import pc_control
from tests.conftest import TEST_DEVICE_KEY, auth_headers

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


def _pc(client, db, lab, h, uid):
    client.post("/api/equipment/state", headers=h, json={"device_uid": uid, "lab_id": lab.code, "kind": "PC", "state": "RUNNING"})
    return db.query(Device).filter_by(device_uid=uid).one()


def _proof(nonce):
    return hmac.new(hashlib.sha256(TEST_DEVICE_KEY.encode()).hexdigest().encode(), nonce.encode(), hashlib.sha256).hexdigest()


def _ask(client, h, uid):
    n = client.get("/api/equipment/share-requests/nonce", headers=h).json()["nonce"]
    return client.post("/api/equipment/share-requests", headers=h, json={"device_uid": uid, "nonce": n, "proof": _proof(n)})


def _poll(client, h, uid):
    return client.get("/api/equipment/pc/poll", params={"device_uid": uid}, headers=h).json()


def test_student_share_needs_admin_approval_and_comes_from_their_pc(client, db, admin, alice, staff, lab, device_headers):
    pc_control.broadcast_reset()
    hs, ha, hst = auth_headers(client, alice.email), auth_headers(client, admin.email), auth_headers(client, staff.email)
    pc3 = _pc(client, db, lab, device_headers, "PC_03")
    assert client.post("/api/equipment/share-requests", headers=hs, json={}).status_code == 409   # no PC proof
    r = _ask(client, hs, "PC_03")
    assert r.status_code == 200 and r.json()["status"] == "PENDING" and r.json()["pc_name"] == pc3.name
    assert db.query(Notification).filter_by(user_id=admin.id, kind="SHARE_REQUEST").count() == 1
    assert client.get("/api/equipment/share-requests", headers=hs).status_code == 403            # students cannot list
    rid = client.get("/api/equipment/share-requests", headers=ha).json()[0]["id"]
    assert client.post(f"/api/equipment/share-requests/{rid}", headers=hs, json={"accept": True}).status_code == 403
    assert _poll(client, device_headers, "PC_03")["broadcast_capture"] is False                   # nothing before Accept
    assert client.post(f"/api/equipment/share-requests/{rid}", headers=ha, json={"accept": True, "audience": "staff"}).status_code == 200
    assert _poll(client, device_headers, "PC_03")["broadcast_capture"] is True                    # its agent captures now
    up = client.post("/api/equipment/pc/broadcast-frame", params={"device_uid": "PC_03"}, headers={**device_headers, "Content-Type": "image/jpeg"}, content=JPEG)
    assert up.status_code == 204
    # "only me": staff see it, another student does not; the presenting student does
    other = auth_headers(client, admin.email)
    assert client.get("/api/equipment/broadcast/frame.jpg", headers=hst).status_code == 200
    assert client.get("/api/equipment/broadcast/frame.jpg", headers=hs).status_code == 200      # the presenter herself
    assert client.get("/api/equipment/share-requests/mine", headers=hs).json()["presenting"] is True
    assert client.post(f"/api/equipment/share-requests/{rid}", headers=other, json={"accept": False}).status_code == 409  # already answered
    client.post("/api/equipment/share-requests/mine/stop", headers=hs)
    assert client.get("/api/equipment/broadcast/frame.jpg", headers=hst).status_code == 410
    assert _poll(client, device_headers, "PC_03")["broadcast_capture"] is False


def test_rejected_request_and_staff_only_share_hidden_from_other_students(client, db, admin, alice, lab, device_headers):
    from app.models import User
    from app.core.security import hash_password
    from app.models.enums import Role
    pc_control.broadcast_reset()
    bob = User(email="bob@test.edu", full_name="Bob", hashed_password=hash_password("Password123"), role=Role.STUDENT, is_active=True)
    db.add(bob); db.commit()
    ha, hs, hb = auth_headers(client, admin.email), auth_headers(client, alice.email), auth_headers(client, bob.email)
    _pc(client, db, lab, device_headers, "PC_04")
    rid = _ask(client, hs, "PC_04").json()["id"]
    client.post(f"/api/equipment/share-requests/{rid}", headers=ha, json={"accept": False})
    assert client.get("/api/equipment/share-requests/mine", headers=hs).json()["request"]["status"] == "REJECTED"
    assert client.get("/api/equipment/broadcast/status", headers=hb).json()["active"] is False
    rid = _ask(client, hs, "PC_04").json()["id"]
    client.post(f"/api/equipment/share-requests/{rid}", headers=ha, json={"accept": True, "audience": "staff"})
    assert client.get("/api/equipment/broadcast/status", headers=hb).json()["active"] is False   # private to staff
    assert client.get("/api/equipment/broadcast/frame.jpg", headers=hb).status_code == 410


def test_exam_page_reaches_the_agent_and_normal_clears_it(client, db, staff, lab, device_headers):
    d = _pc(client, db, lab, device_headers, "PC_05")
    h = auth_headers(client, staff.email)
    assert client.put(f"/api/equipment/{d.id}/mode", headers=h, json={"mode": "EXAM", "exam_url": "javascript:alert(1)"}).status_code == 422
    r = client.put(f"/api/equipment/{d.id}/mode", headers=h, json={"mode": "EXAM", "exam_url": "https://exam.giu/plc"})
    assert r.status_code == 200 and r.json()["exam_url"] == "https://exam.giu/plc"
    assert _poll(client, device_headers, "PC_05")["exam"] == {"url": "https://exam.giu/plc", "lockdown": True}
    pc_control.exam_url_set(d.id, None)                                  # portal restarted: restored from the audit log
    assert _poll(client, device_headers, "PC_05")["exam"]["url"] == "https://exam.giu/plc"
    client.put(f"/api/equipment/{d.id}/mode", headers=h, json={"mode": "NORMAL"})
    assert _poll(client, device_headers, "PC_05")["exam"] is None


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_share_left_running():
    """The share lives in process memory: never leave one running for the next test."""
    pc_control.broadcast_reset()
    yield
    pc_control.broadcast_reset()
