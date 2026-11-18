"""
Retired "TEST - ..." cards and _SIM robots (Gemini B-06/B-07/B-08/B-23, 2026-11-19): their history stays in the
database, but they are not counted, scored, alerted on, given markers or shown, and the daily summary counts
robot hours only (lab PCs have RUNNING sessions too).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.api.routes import opcua
from app.core.config import settings
from app.models import Device, DeviceType, EquipmentSession
from app.services import health_score, robotics_watch, scan
from tests.conftest import auth_headers


@pytest.fixture
def fleet(db, lab):
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=10)
    devs = {
        "robot": Device(device_uid="UR5E_X", name="UR5e", lab_id=lab.id, device_type=DeviceType.ROBOT,
                        last_seen_at=now, component_state={"robot_mode": "RUNNING", "q": [0] * 6}),
        "sim": Device(device_uid="UR5E_SIM", name="UR5e (simulation)", lab_id=lab.id,
                      device_type=DeviceType.ROBOT, last_seen_at=old, component_state={"source": "SIMULATION"}),
        "pc": Device(device_uid="PC_LIVE", name="PC-02", lab_id=lab.id, device_type=DeviceType.PC, last_seen_at=now),
        "retired": Device(device_uid="PC_01", name="TEST - old HP test PC", lab_id=lab.id,
                          device_type=DeviceType.PC, last_seen_at=old),
    }
    db.add_all(devs.values())
    db.flush()
    db.add(EquipmentSession(device_id=devs["robot"].id, lab_id=lab.id, state="RUNNING",
                            started_at=now - timedelta(hours=1)))
    db.add(EquipmentSession(device_id=devs["pc"].id, lab_id=lab.id, state="RUNNING",
                            started_at=now - timedelta(hours=5)))
    db.commit()
    return devs, now


def test_watch_rules_skip_retired_and_simulated(db, fleet):
    _, now = fleet
    assert robotics_watch.robots(db, now) == []                 # UR5E_SIM is 10 days silent: no alarm
    assert robotics_watch.pcs_offline(db, now) == []            # retired TEST card: no alarm


def test_daily_summary_counts_robot_hours_only(db, fleet):
    _, now = fleet
    body = robotics_watch.daily(db, now)[0]["body"]
    assert "robots ran 1.0 h" in body                           # not 6.0 h (the PC's 5 h was summed before)


def test_summary_health_markers_and_device_list_leave_out_retired(client, db, lab, admin, fleet):
    devs, now = fleet
    h = auth_headers(client, admin.email)
    s = client.get("/api/summary", headers=h).json()
    assert s["devices_total"] == 2 and s["devices_online"] == 2     # robot + live PC
    names = [d["name"] for d in client.get("/api/devices", headers=h).json()]
    assert "TEST - old HP test PC" not in names and "PC-02" in names
    assert "TEST - old HP test PC" in [d["name"] for d in
                                       client.get("/api/devices?include_retired=true", headers=h).json()]
    lab_devs = [d["name"] for d in client.get(f"/api/labs/{lab.id}", headers=h).json()["devices"]]
    assert "TEST - old HP test PC" not in lab_devs
    part = health_score.score_labs(db, now)[0]["parts"]["devices"]
    assert part["evidence"].startswith("2 of 2")
    keys = [m["key"] for m in scan.registry(db)]
    assert "PC_01" not in keys and "UR5E_SIM" not in keys and "PC_LIVE" in keys


def test_opcua_skips_retired_and_uses_the_portal_state(client, db, lab, fleet, monkeypatch):
    monkeypatch.setattr(opcua, "KEY", "k" * 32)
    db.add(Device(device_uid="FACESRV_X", name="Face server", lab_id=lab.id, device_type=DeviceType.FACE_SERVER))
    db.commit()
    d = client.get("/api/opcua/snapshot", headers={"X-OPCUA-Key": "k" * 32}).json()
    devs = {x["uid"]: x for l in d["labs"] for x in l["devices"]}
    assert "PC_01" not in devs
    assert devs["UR5E_X"]["online"] is True
    assert devs["FACESRV_X"]["online"] is None                  # never reported, probes off in tests
