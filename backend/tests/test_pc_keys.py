"""Per-PC keys (2026-11-04, audit P0-A): the flash-drive kit carries an enrollment code instead of the door boards' key;
a PC's own key speaks for that PC only, on the PC endpoints only; running the installer again never makes a second card."""
import hashlib
import hmac

import pytest
from fastapi.routing import APIRoute

from app.api.deps import pc_enroll_code, require_device
from app.api.routes import equipment as eq
from app.core.config import settings
from app.main import app
from app.models import AuditLog, Device, DeviceType
from app.services import agent_bundle, pc_control
from tests.conftest import auth_headers


def enroll(client, uid, lab, code=None):
    return client.post("/api/equipment/pc/enroll", headers={"X-Enroll-Key": code or pc_enroll_code()},
                       json={"device_uid": uid, "lab_id": lab.code})


def own_key(client, uid, lab):
    r = enroll(client, uid, lab)
    assert r.status_code == 200, r.text
    return {"X-Device-Key": r.json()["device_key"]}


def test_running_the_installer_again_keeps_one_card_and_retires_the_old_key(client, db, lab):
    first = own_key(client, "PC_LAB_ONE", lab)
    d = db.query(Device).filter_by(device_uid="PC_LAB_ONE").one()
    d.name = "PC-01"                                       # the name staff gave the card
    db.commit()
    second = own_key(client, "PC_LAB_ONE", lab)
    db.expire_all()
    rows = db.query(Device).filter_by(device_uid="PC_LAB_ONE").all()
    assert len(rows) == 1 and rows[0].name == "PC-01" and rows[0].device_type == DeviceType.PC
    poll = "/api/equipment/pc/poll?device_uid=PC_LAB_ONE"
    assert client.get(poll, headers=second).status_code == 200
    assert client.get(poll, headers=first).status_code == 401
    assert db.query(AuditLog).filter_by(action="PC_ENROLLED").count() == 2


def test_enrollment_is_refused_when_it_should_be(client, db, lab, device_headers, monkeypatch):
    assert enroll(client, "PC_X", lab, code="wrong").status_code == 401
    assert client.post("/api/equipment/pc/enroll", json={"device_uid": "PC_X", "lab_id": lab.code}).status_code == 401
    # The door boards' key is not an enrollment code, and the enrollment code is not a device key.
    assert enroll(client, "PC_X", lab, code=settings.DEVICE_API_KEY).status_code == 401
    assert client.get("/api/equipment/pc/poll?device_uid=PC_X", headers={"X-Device-Key": pc_enroll_code()}).status_code == 401
    assert settings.DEVICE_API_KEY not in pc_enroll_code()
    assert enroll(client, "PC_ADMIN_LAPTOP", lab).status_code == 403
    assert enroll(client, "ESP32_MASTER", lab).status_code == 422          # only PC_... names
    assert client.post("/api/equipment/pc/enroll", headers={"X-Enroll-Key": pc_enroll_code()},
                       json={"device_uid": "PC_X", "lab_id": "NOPE"}).status_code == 404
    db.add(Device(device_uid="PC_ROBOT", name="r", device_type=DeviceType.ROBOT, lab_id=lab.id))
    db.commit()
    assert enroll(client, "PC_ROBOT", lab).status_code == 409
    monkeypatch.setattr(settings, "PC_ENROLL_OPEN", False)
    assert enroll(client, "PC_X", lab).status_code == 401
    assert db.query(Device).filter_by(device_uid="PC_X").count() == 0


def test_one_pc_cannot_speak_for_another(client, db, lab):
    a, _ = own_key(client, "PC_A", lab), own_key(client, "PC_B", lab)
    jpeg = b"\xff\xd8" + b"0" * 100
    assert client.get("/api/equipment/pc/poll?device_uid=PC_A", headers=a).status_code == 200
    forged = [
        client.get("/api/equipment/pc/poll?device_uid=PC_B", headers=a),
        client.get("/api/equipment/pc/wait?device_uid=PC_B&timeout=0.5", headers=a),
        client.post("/api/equipment/pc/frame?device_uid=PC_B", headers=a, content=jpeg),
        client.post("/api/equipment/pc/broadcast-frame?device_uid=PC_B", headers=a, content=jpeg),
        client.post("/api/equipment/state", headers=a, json={"device_uid": "PC_B", "lab_id": lab.code, "kind": "PC", "state": "IDLE"}),
        client.post("/api/equipment/violations", headers=a, json={"device_uid": "PC_B", "kind": "X", "detail": "fake"}),
        client.post("/api/equipment/pc/action-result", headers=a, json={"device_uid": "PC_B", "id": 1, "ok": True}),
    ]
    assert [r.status_code for r in forged] == [403] * len(forged)
    assert client.post("/api/equipment/pc/presence", headers=a, json={"lab_id": lab.code, "pcs": []}).status_code == 403
    assert client.get("/api/equipment/pc/lan-targets", headers=a).status_code == 403


def _device_routes():
    """(full path, route) of every endpoint that takes a device key. FastAPI keeps included routers nested."""
    def uses(dep) -> bool:
        return dep.call is require_device or any(uses(d) for d in dep.dependencies)

    def walk(routes, prefix=""):
        for r in routes:
            if isinstance(r, APIRoute):
                if any(uses(d) for d in r.dependant.dependencies):
                    yield prefix + r.path, r
            elif hasattr(r, "original_router"):
                yield from walk(r.original_router.routes, prefix + (getattr(r.include_context, "prefix", "") or ""))
    return list(walk(app.routes))


def test_a_pc_key_opens_no_door_sensor_robot_or_inventory_endpoint(client, lab):
    """Every device endpoint outside /api/equipment/ in the running app, so a new one cannot be forgotten."""
    a = own_key(client, "PC_A", lab)
    routes = [(p, r) for p, r in _device_routes() if not p.startswith("/api/equipment/")]
    assert len(routes) >= 20, [p for p, _ in routes]
    paths = {p for p, _ in routes}
    assert {"/api/access/heartbeat", "/api/robots/telemetry", "/api/robots/events"} <= paths, sorted(paths)
    for path, r in routes:
        url = path
        for name in r.param_convertors:
            url = url.replace("{" + name + "}", "1")
        res = client.request(sorted(r.methods)[0], url, headers=a, json={})
        assert res.status_code == 403, f"{path}: {res.status_code}"
    # ... and the PC endpoints themselves are all on the list the path rule leaves open.
    assert {"/api/equipment/pc/poll", "/api/equipment/pc/frame"} <= {p for p, _ in _device_routes()}


def test_a_pc_with_its_own_key_is_still_recognised_at_a_master_sign_in(client, db, lab):
    a = own_key(client, "PC_ENG", lab)
    d = db.query(Device).filter_by(device_uid="PC_ENG").one()
    keyed = hashlib.sha256(a["X-Device-Key"].encode()).hexdigest().encode()
    nonce = "ab" * 16
    assert eq._proof_ok(d, nonce, hmac.new(keyed, nonce.encode(), hashlib.sha256).hexdigest())
    assert not eq._proof_ok(d, nonce, hmac.new(b"other", nonce.encode(), hashlib.sha256).hexdigest())


def test_the_update_bundle_needs_a_device_key_and_the_poll_names_it(client, lab, tmp_path, monkeypatch):
    a = own_key(client, "PC_A", lab)
    monkeypatch.setattr(agent_bundle, "path", lambda: str(tmp_path / "none.json"))
    assert client.get("/api/equipment/pc/agent-bundle", headers=a).status_code == 404
    assert client.get("/api/equipment/pc/poll?device_uid=PC_A", headers=a).json()["agent_bundle"] is None
    f = tmp_path / "bundle.json"
    f.write_text('{"manifest": {"seq": 42, "id": "abc", "files": []}, "sig": "1", "files": {}}', encoding="utf-8")
    monkeypatch.setattr(agent_bundle, "path", lambda: str(f))
    assert client.get("/api/equipment/pc/poll?device_uid=PC_A", headers=a).json()["agent_bundle"] == {"seq": 42, "id": "abc"}
    assert client.get("/api/equipment/pc/agent-bundle", headers=a).json()["manifest"]["seq"] == 42
    assert client.get("/api/equipment/pc/agent-bundle").status_code == 401


def test_an_unchanged_share_picture_costs_a_few_bytes(client, lab, staff):
    a = own_key(client, "PC_A", lab)
    pc_control.broadcast_start("Eng", staff.id, "browser")
    try:
        assert pc_control.broadcast_put(b"\xff\xd8one")
        t = client.get("/api/equipment/pc/watch-token", headers=a).json()["token"]
        url = f"/api/equipment/broadcast/watch/frame.jpg?t={t}"
        r = client.get(url)
        assert r.status_code == 200 and r.content == b"\xff\xd8one"
        same = client.get(url, headers={"If-None-Match": r.headers["etag"]})
        assert same.status_code == 304 and same.content == b""
        import time
        time.sleep(0.01)
        assert pc_control.broadcast_put(b"\xff\xd8two")
        assert client.get(url, headers={"If-None-Match": r.headers["etag"]}).content == b"\xff\xd8two"
    finally:
        pc_control.broadcast_stop()


def test_retired_test_cards_stay_in_the_database_but_leave_the_portal(client, db, lab, staff, device_headers):
    h = auth_headers(client, staff.email)
    for uid, name in (("PC_OLD", "TEST - old duplicate"), ("PC_NEW", "PC-07")):
        assert client.post("/api/equipment/state", headers=device_headers, json={
            "device_uid": uid, "lab_id": lab.code, "kind": "PC", "state": "IDLE"}).status_code == 200
        db.query(Device).filter_by(device_uid=uid).one().name = name
    db.commit()
    names = [e["name"] for e in client.get("/api/equipment", headers=h).json()]
    assert "PC-07" in names and "TEST - old duplicate" not in names
    assert db.query(Device).filter_by(device_uid="PC_OLD").count() == 1


@pytest.mark.parametrize("uid", ["PC_GIULAB20-PC4", "PC_ENG", "PC_S2PC136"])
def test_real_pc_names_enroll(client, lab, uid):
    assert enroll(client, uid, lab).status_code == 200


def enroll_as(client, uid, lab, account):
    return client.post("/api/equipment/pc/enroll", headers={"X-Enroll-Key": pc_enroll_code()},
                       json={"device_uid": uid, "lab_id": lab.code, "account": account})


def test_two_windows_accounts_on_one_pc_keep_their_own_keys(client, db, lab):
    a = enroll_as(client, "PC_MULTI", lab, "a" * 32).json()["device_key"]
    b = enroll_as(client, "PC_MULTI", lab, "b" * 32).json()["device_key"]
    assert a != b
    for key in (a, b):
        assert client.get("/api/equipment/pc/poll?device_uid=PC_MULTI", headers={"X-Device-Key": key}).status_code == 200
    assert db.query(Device).filter_by(device_uid="PC_MULTI").count() == 1          # one card for the PC


def test_an_account_enrolling_again_replaces_only_its_own_key(client, lab):
    a1 = enroll_as(client, "PC_MULTI", lab, "a" * 32).json()["device_key"]
    b = enroll_as(client, "PC_MULTI", lab, "b" * 32).json()["device_key"]
    a2 = enroll_as(client, "PC_MULTI", lab, "a" * 32).json()["device_key"]
    url = "/api/equipment/pc/poll?device_uid=PC_MULTI"
    assert client.get(url, headers={"X-Device-Key": a1}).status_code == 401
    assert client.get(url, headers={"X-Device-Key": a2}).status_code == 200
    assert client.get(url, headers={"X-Device-Key": b}).status_code == 200


def test_an_account_key_speaks_only_for_its_pc_and_only_on_pc_endpoints(client, lab):
    a = enroll_as(client, "PC_MULTI", lab, "a" * 32).json()["device_key"]
    enroll_as(client, "PC_OTHER", lab, "a" * 32)
    assert client.get("/api/equipment/pc/poll?device_uid=PC_OTHER", headers={"X-Device-Key": a}).status_code == 403
    assert client.post("/api/devices/heartbeat", headers={"X-Device-Key": a}, json={"device_uid": "PC_MULTI"}).status_code in (403, 404, 422)


def test_a_bad_account_value_is_refused(client, lab):
    assert enroll_as(client, "PC_MULTI", lab, "ali.loay").status_code == 422
