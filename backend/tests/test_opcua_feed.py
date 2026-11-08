"""OPC UA feed (2026-10-26): key-protected, read-only, equipment state only - no people's names or PC accounts."""
from datetime import datetime, timezone

from app.api.routes import opcua
from app.models import Device, DeviceType


def test_feed_needs_the_key_and_hides_personal_data(client, db, lab, monkeypatch):
    monkeypatch.setattr(opcua, "KEY", "k" * 32)
    db.add_all([
        Device(device_uid="UR5E_X", name="UR5e", device_type=DeviceType.ROBOT, lab_id=lab.id,
               last_seen_at=datetime.now(timezone.utc),
               component_state={"robot_mode": "RUNNING", "q": [0.0, -1.5708, 0, 0, 0, 0], "secret": "x"}),
        Device(device_uid="PC_X", name="PC-07", device_type=DeviceType.PC, lab_id=lab.id,
               component_state={"state": "RUNNING", "os_user": "alice", "user_name": "Alice"})])
    db.commit()
    assert client.get("/api/opcua/snapshot").status_code == 401
    assert client.get("/api/opcua/snapshot", headers={"X-OPCUA-Key": "wrong"}).status_code == 401
    d = client.get("/api/opcua/snapshot", headers={"X-OPCUA-Key": "k" * 32}).json()
    devs = {x["uid"]: x for l in d["labs"] for x in l["devices"]}
    r = devs["UR5E_X"]["values"]
    assert r["robot_mode"] == "RUNNING" and abs(r["J2_deg"] + 90.0) < 0.01 and "secret" not in r
    assert "os_user" not in devs["PC_X"]["values"] and "user_name" not in devs["PC_X"]["values"]
    assert "alice" not in str(d).lower()


def test_feed_off_without_key(client, monkeypatch):
    monkeypatch.setattr(opcua, "KEY", "")
    assert client.get("/api/opcua/snapshot", headers={"X-OPCUA-Key": ""}).status_code == 503
