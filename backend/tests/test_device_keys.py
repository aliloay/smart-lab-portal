"""
Per-device keys: a device given its own key may report only as itself; the
shared key keeps working for the door boards until it is switched off.
"""
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.models import AuditLog, Device, DeviceType
from tests.conftest import auth_headers


@pytest.fixture
def node(db, lab) -> Device:
    d = Device(device_uid="ENV_KEYED", name="Env", lab_id=lab.id,
               device_type=DeviceType.SENSOR_NODE, last_seen_at=datetime.now(timezone.utc))
    db.add(d)
    db.commit()
    return d


def _telemetry(client, key, lab, uid="ENV_KEYED"):
    return client.post("/api/access/telemetry", headers={"X-Device-Key": key}, json={
        "device_uid": uid, "lab_id": lab.code,
        "readings": [{"metric": "temperature", "value": 22.5, "unit": "C"}]})


def test_own_key_reports_only_as_itself(client, db, admin, lab, node):
    r = client.post(f"/api/devices/{node.id}/key", headers=auth_headers(client, admin.email))
    assert r.status_code == 200
    key = r.json()["device_key"]
    db.refresh(node)
    assert node.key_hash and key not in node.key_hash          # only the hash is stored
    assert _telemetry(client, key, lab).status_code == 200
    assert _telemetry(client, key, lab, uid="MASTER_LAB01").status_code == 403
    assert db.query(AuditLog).filter_by(action="DEVICE_KEY_ISSUED").count() == 1


def test_revoked_or_wrong_key_is_refused(client, db, admin, lab, node):
    h = auth_headers(client, admin.email)
    key = client.post(f"/api/devices/{node.id}/key", headers=h).json()["device_key"]
    client.delete(f"/api/devices/{node.id}/key", headers=h)
    assert _telemetry(client, key, lab).status_code == 401
    assert _telemetry(client, "made-up", lab).status_code == 401


def test_shared_key_works_until_switched_off(client, lab, node, device_headers, monkeypatch):
    assert _telemetry(client, device_headers["X-Device-Key"], lab).status_code == 200
    monkeypatch.setattr(settings, "DEVICE_SHARED_KEY", False)
    assert _telemetry(client, device_headers["X-Device-Key"], lab).status_code == 401


def test_only_admins_issue_keys(client, staff, node):
    r = client.post(f"/api/devices/{node.id}/key", headers=auth_headers(client, staff.email))
    assert r.status_code == 403


_DOOR_REPORTS = (
    ("/api/access/validate-qr", {"qr_token": "tok"}),
    ("/api/access/validate-rfid", {"uid_hex": "AABBCCDD"}),
    ("/api/access/events", {"event_type": "DOOR_OPENED"}),
    ("/api/access/grant", {"event_type": "ACCESS_GRANTED"}),
    ("/api/access/deny", {"event_type": "ACCESS_DENIED"}),
)


def test_a_sensor_nodes_own_key_cannot_make_door_reports(client, db, admin, lab, node):
    """2026-11-11 closure audit (SEC-01): not in the master's name, and not in its own name either."""
    key = client.post(f"/api/devices/{node.id}/key", headers=auth_headers(client, admin.email)).json()["device_key"]
    db.add(Device(device_uid="MASTER_LAB01", name="Master", lab_id=lab.id, device_type=DeviceType.MASTER_CONTROLLER))
    db.commit()
    for uid in ("MASTER_LAB01", "ENV_KEYED", None):
        for path, body in _DOOR_REPORTS:
            r = client.post(path, headers={"X-Device-Key": key}, json={**body, "lab_id": lab.code, "device_uid": uid})
            assert r.status_code == 403, (path, uid, r.text)


def test_door_reports_still_work_with_the_shared_key_and_a_masters_own_key(client, db, admin, lab, device_headers):
    m = Device(device_uid="MASTER_KEYED", name="Master", lab_id=lab.id, device_type=DeviceType.MASTER_CONTROLLER)
    db.add(m)
    db.commit()
    own = {"X-Device-Key": client.post(f"/api/devices/{m.id}/key",
                                       headers=auth_headers(client, admin.email)).json()["device_key"]}
    body = {"event_type": "DOOR_OPENED", "lab_id": lab.code, "device_uid": "MASTER_KEYED"}
    assert client.post("/api/access/events", headers=device_headers, json=body).status_code == 200
    assert client.post("/api/access/events", headers=own, json=body).status_code == 200
    assert client.post("/api/access/events", headers=own, json={**body, "device_uid": "OTHER_MASTER"}).status_code == 403
