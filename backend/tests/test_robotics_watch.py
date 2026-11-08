"""
n8n workflows 13-22: the Robotics Lab watch topics. Each returns
deduplicated notification items from stored data; unknown topics 404;
the automation key is required.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.models import (Alert, AlertSeverity, Asset, AssetStatus, Device, DeviceType,
                        EquipmentSession, InventoryBin, InventoryTransaction, PolicyViolation)

KEY = {"X-Automation-Key": "test-automation-key"}


@pytest.fixture(autouse=True)
def _automation(monkeypatch):
    monkeypatch.setattr(settings, "AUTOMATION_API_KEY", "test-automation-key")


def _topic(client, t):
    r = client.get(f"/api/automation/robotics/{t}", headers=KEY)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_topics_report_what_is_stored(client, db, lab):
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=3)
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.CRITICAL, title="Smoke/gas detected",
                 detail="", dedupe_key=f"env:{lab.id}:smoke", created_at=now - timedelta(minutes=10)))
    db.add(Device(device_uid="ENV_X", name="Env", lab_id=lab.id, device_type=DeviceType.SENSOR_NODE,
                  last_seen_at=old))
    b = InventoryBin(code="BIN-T", lab_id=lab.id, item_name="Resistors", tare_g=0, unit_mass_g=1,
                     reorder_qty=50, last_mass_g=10)
    db.add(b)
    db.flush()
    db.add(InventoryTransaction(bin_id=b.id, kind="WITHDRAWAL", delta_mass_g=-5,
                                attribution="NOBODY_INSIDE"))
    db.add(Asset(asset_tag="ARD-1", name="Arduino", lab_id=lab.id, bin_item=True,
                 status=AssetStatus.CHECKED_OUT, checked_out_at=now - timedelta(hours=30)))
    robot = Device(device_uid="UR5E_X", name="UR5e", lab_id=lab.id, device_type=DeviceType.ROBOT,
                   last_seen_at=now)
    pc = Device(device_uid="PC_X", name="PC", lab_id=lab.id, device_type=DeviceType.PC, last_seen_at=old)
    db.add_all([robot, pc])
    db.flush()
    db.add(EquipmentSession(device_id=robot.id, lab_id=lab.id, state="RUNNING", started_at=now))
    db.add(PolicyViolation(device_id=pc.id, lab_id=lab.id, kind="PROHIBITED_PROGRAM", detail="x running"))
    db.commit()

    assert "Still active" in _topic(client, "hazards")[0]["title"]
    assert _topic(client, "env-offline")[0]["title"].startswith("Node offline")
    assert "Reorder Resistors" in _topic(client, "low-stock")[0]["title"]
    assert "nobody inside" in _topic(client, "unattended-stock")[0]["title"]
    assert "ARD-1" in _topic(client, "assets-overdue")[0]["title"]
    assert "without a booking" in _topic(client, "robot-unbooked")[0]["title"]
    assert _topic(client, "pcs-offline")[0]["title"].startswith("PC offline")
    assert "PC_X" in _topic(client, "exam-violations")[0]["title"]
    d = _topic(client, "daily")[0]
    assert "1 consumable withdrawal" in d["body"] and d["dedupe_key"].startswith("robotics:daily:")


def test_unknown_topic_and_key(client):
    assert client.get("/api/automation/robotics/nope", headers=KEY).status_code == 404
    assert client.get("/api/automation/robotics/daily").status_code in (401, 403)
