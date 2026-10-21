"""
The admin who signs in IS the master (owner 2026-10-21: "whatever the device, the place, the type of
connection").

Tested: a sign-in from a device without the agent makes the admin master and releases the old master
PC; a sign-in on a lab PC whose agent proves itself (HMAC of the one-time nonce with its key's hash)
makes that PC the master PC and only that one; a wrong proof, a reused nonce or a staff member
changes nothing; staff can see who the master is; the shared lab key also proves a PC.
"""
import hashlib
import hmac

from app.models import AuditLog, Device
from tests.conftest import TEST_DEVICE_KEY, auth_headers


def _pc(client, lab, device_headers, uid):
    client.post("/api/equipment/state", headers=device_headers, json={
        "device_uid": uid, "lab_id": lab.code, "kind": "PC", "state": "RUNNING"})


def _proof(key, nonce):
    return hmac.new(hashlib.sha256(key.encode()).hexdigest().encode(), nonce.encode(), hashlib.sha256).hexdigest()


def _nonce(client, h):
    return client.get("/api/equipment/master/nonce", headers=h).json()["nonce"]


def _masters(db):
    db.expire_all()
    return sorted(d.device_uid for d in db.query(Device).filter_by(is_master_pc=True))


def test_admin_anywhere_is_master_and_old_master_pc_is_released(client, db, admin, lab, device_headers):
    h = auth_headers(client, admin.email)
    _pc(client, lab, device_headers, "PC_ADMIN_LAPTOP")
    d = db.query(Device).filter_by(device_uid="PC_ADMIN_LAPTOP").one()
    client.put(f"/api/equipment/{d.id}/master", headers=h, json={"is_master": True})
    assert _masters(db) == ["PC_ADMIN_LAPTOP"]

    r = client.post("/api/equipment/master/claim", headers=h, json={"device_label": "Android · Chrome"})
    assert r.status_code == 200
    assert r.json()["user_name"] == "Admin" and r.json()["device"] == "Android · Chrome" and r.json()["pc"] is None
    assert _masters(db) == []                               # the admin is on a phone: no lab PC is master
    assert db.query(AuditLog).filter_by(action="MASTER_CLAIMED").count() == 1


def test_agent_proof_makes_that_pc_the_master_pc(client, db, admin, lab, device_headers):
    h = auth_headers(client, admin.email)
    for uid in ("PC_01", "PC_02"):
        _pc(client, lab, device_headers, uid)
    pc1 = db.query(Device).filter_by(device_uid="PC_01").one()
    key = client.post(f"/api/devices/{pc1.id}/key", headers=h).json()["device_key"]
    n = _nonce(client, h)
    r = client.post("/api/equipment/master/claim", headers=h, json={
        "device_label": "Windows · Chrome", "device_uid": "PC_01", "nonce": n, "proof": _proof(key, n)})
    assert r.status_code == 200 and r.json()["pc"] == "PC_01"
    assert _masters(db) == ["PC_01"]
    # the nonce is single-use
    r = client.post("/api/equipment/master/claim", headers=h, json={
        "device_label": "x", "device_uid": "PC_01", "nonce": n, "proof": _proof(key, n)})
    assert r.status_code == 400


def test_wrong_proof_changes_nothing(client, db, admin, lab, device_headers):
    h = auth_headers(client, admin.email)
    _pc(client, lab, device_headers, "PC_02")
    n = _nonce(client, h)
    r = client.post("/api/equipment/master/claim", headers=h, json={
        "device_label": "x", "device_uid": "PC_02", "nonce": n, "proof": _proof("not-the-key", n)})
    assert r.status_code == 403
    assert _masters(db) == []
    assert db.query(AuditLog).filter_by(action="MASTER_CLAIMED").count() == 0


def test_shared_lab_key_also_proves_a_pc(client, db, admin, lab, device_headers):
    h = auth_headers(client, admin.email)
    _pc(client, lab, device_headers, "PC_03")
    n = _nonce(client, h)
    r = client.post("/api/equipment/master/claim", headers=h, json={
        "device_label": "Windows · Chrome", "device_uid": "PC_03", "nonce": n, "proof": _proof(TEST_DEVICE_KEY, n)})
    assert r.status_code == 200 and _masters(db) == ["PC_03"]


def test_staff_cannot_claim_but_can_see_the_master(client, db, admin, staff):
    hs = auth_headers(client, staff.email)
    assert client.get("/api/equipment/master/nonce", headers=hs).status_code == 403
    assert client.post("/api/equipment/master/claim", headers=hs, json={"device_label": "x"}).status_code == 403
    client.post("/api/equipment/master/claim", headers=auth_headers(client, admin.email), json={"device_label": "Windows · Edge"})
    m = client.get("/api/equipment/master", headers=hs).json()
    assert m["user_name"] == "Admin" and m["device"] == "Windows · Edge"
