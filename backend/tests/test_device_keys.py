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
