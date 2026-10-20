"""System Health (2026-10-17): background probes, STALE vs OFFLINE vs UNKNOWN, simulation, guidance."""
from datetime import datetime, timedelta, timezone

from app.models import Device, DeviceType
from app.services import health_monitor as hm
from tests.conftest import auth_headers


def test_probes_run_in_the_background_and_report_reason_and_last_success(monkeypatch):
    hm.reset()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            return True, "HTTP 200"
        raise ConnectionError("refused")
    monkeypatch.setattr(hm, "_checks", {"face": ("Face server", flaky)})
    assert hm.snapshot()[0]["state"] == "UNKNOWN"            # never assumed fine before a check
    hm.check_once()
    s = hm.snapshot()[0]
    assert s["state"] == "ONLINE" and s["last_ok"] is not None and s["guidance"] is None
    hm.check_once()
    s = hm.snapshot()[0]
    assert s["state"] == "OFFLINE" and s["detail"] == "ConnectionError" and s["consecutive_failures"] == 1
    assert s["last_ok"] is not None and "face server" in s["guidance"].lower()


def test_device_states_stale_offline_unknown_and_simulation(client, db, staff, alice, lab):
    now = datetime.now(timezone.utc)
    db.add_all([
        Device(device_uid="ENV_STALE", name="Env stale", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
               last_seen_at=now - timedelta(minutes=10)),
        Device(device_uid="ENV_OLD", name="Env old", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
               last_seen_at=now - timedelta(days=2)),
        Device(device_uid="ENV_NEVER", name="Env never", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id),
        Device(device_uid="UR5E_SIM", name="UR sim", device_type=DeviceType.ROBOT, lab_id=lab.id,
               last_seen_at=now, component_state={"source": "SIMULATION", "q": [0] * 6}),
    ])
    db.commit()
    assert client.get("/api/system/health", headers=auth_headers(client, alice.email)).status_code == 403
    h = client.get("/api/system/health", headers=auth_headers(client, staff.email)).json()
    by = {s.get("device_uid"): s for s in h["services"] if s.get("device_uid")}
    assert by["ENV_STALE"]["state"] == "STALE" and by["ENV_STALE"]["guidance"]
    assert by["ENV_OLD"]["state"] == "OFFLINE"
    assert by["ENV_NEVER"]["state"] == "UNKNOWN" and by["ENV_NEVER"]["detail"] == "has never reported"
    assert by["UR5E_SIM"]["state"] == "SIMULATION"
    assert h["summary"]["STALE"] >= 1 and "data_sources" in h and "backup" in h
    db_row = next(s for s in h["services"] if s["key"] == "database")
    assert db_row["state"] == "ONLINE"


def test_robot_collector_without_joints_is_degraded(client, db, staff, lab):
    db.add(Device(device_uid="UR5E_X", name="UR5e", device_type=DeviceType.ROBOT, lab_id=lab.id,
                  last_seen_at=datetime.now(timezone.utc), component_state={"source": "RTDE"}))
    db.commit()
    h = client.get("/api/system/services", headers=auth_headers(client, staff.email)).json()
    r = next(s for s in h["services"] if s.get("device_uid") == "UR5E_X")
    assert r["state"] == "DEGRADED" and "no joint data" in r["detail"]


def test_liveness_scan_is_throttled_in_production_but_still_returns_devices(db, lab, monkeypatch):
    from app.services import devices as dv
    calls = {"n": 0}
    from app.services import backups
    monkeypatch.setattr(backups, "check", lambda db: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setenv("LIVENESS_THROTTLE_S", "3")
    dv._last_refresh["at"] = 0.0
    db.add(Device(device_uid="ENV_X", name="Env X", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id))
    db.commit()
    a, b = dv.refresh_liveness(db), dv.refresh_liveness(db)
    assert calls["n"] == 1                                       # second call within 3 s skipped the scan
    assert [d.device_uid for d in a] == [d.device_uid for d in b] and any(d.device_uid == "ENV_X" for d in b)
