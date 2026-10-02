"""
Environment monitoring (Robotics Lab, System 1), backend side.

The environment node posts states and values to the existing telemetry
endpoint. Tested: a hazard raises exactly one CRITICAL alert and notifies
staff, clears itself when the node reports it clear, and every value shown
carries an honest quality (never an old value presented as current).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import (Alert, AlertSeverity, Device, DeviceType, Notification,
                        SensorReading)
from tests.conftest import auth_headers


@pytest.fixture
def env_node(db, lab) -> Device:
    d = Device(device_uid="ENV_LAB01", name="Environment node", lab_id=lab.id,
               device_type=DeviceType.SENSOR_NODE, is_online=True,
               last_seen_at=datetime.now(timezone.utc))
    db.add(d)
    db.commit()
    return d


def _post(client, headers, lab, **metrics):
    return client.post("/api/access/telemetry", headers=headers, json={
        "device_uid": "ENV_LAB01", "lab_id": lab.code,
        "readings": [{"metric": k, "value": v, "unit": "state" if k not in
                      ("temperature", "humidity") else ("C" if k == "temperature" else "%")}
                     for k, v in metrics.items()]})


def test_smoke_raises_one_critical_alert_then_clears(client, db, staff, lab, env_node,
                                                     device_headers):
    assert _post(client, device_headers, lab, smoke=1).status_code == 200
    _post(client, device_headers, lab, smoke=1)            # still smoky: no duplicate
    alerts = db.query(Alert).filter_by(lab_id=lab.id, is_resolved=False).all()
    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.CRITICAL
    assert "Smoke" in alerts[0].title
    assert db.query(Notification).filter_by(user_id=staff.id,
                                            kind="ENVIRONMENT_HAZARD").count() == 1

    _post(client, device_headers, lab, smoke=0)
    db.expire_all()
    assert db.query(Alert).filter_by(lab_id=lab.id, is_resolved=False).count() == 0


def test_each_hazard_has_its_own_alert(client, db, lab, env_node, device_headers):
    _post(client, device_headers, lab, flame=1, water_leak=1, emergency=1, smoke=0)
    titles = sorted(a.title for a in db.query(Alert).filter_by(lab_id=lab.id).all())
    assert len(titles) == 3
    assert any("Flame" in t for t in titles) and any("leak" in t for t in titles)


def test_motion_and_values_raise_no_hazard_alert(client, db, lab, env_node, device_headers):
    _post(client, device_headers, lab, motion=1, temperature=24.8, humidity=47.2)
    assert db.query(Alert).filter_by(lab_id=lab.id).count() == 0


def test_environment_qualities(client, db, alice, lab, env_node, device_headers):
    _post(client, device_headers, lab, temperature=24.8, humidity=120)
    old = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(SensorReading(lab_id=lab.id, device_id=env_node.id, metric="smoke",
                         value=0, unit="state", recorded_at=old))
    db.commit()
    h = auth_headers(client, alice.email)
    m = client.get(f"/api/labs/{lab.id}/environment", headers=h).json()["metrics"]
    assert m["temperature"]["quality"] == "VALID" and m["temperature"]["value"] == 24.8
    assert m["humidity"]["quality"] == "OUT_OF_RANGE"
    assert m["smoke"]["quality"] == "STALE"
    assert m["flame"]["quality"] == "MISSING" and m["flame"]["value"] is None

    env_node.last_seen_at = old                          # node stopped reporting
    db.commit()
    m = client.get(f"/api/labs/{lab.id}/environment", headers=h).json()["metrics"]
    assert m["temperature"]["quality"] == "DEVICE_OFFLINE"


def test_monitor_tile_shows_the_hazard(client, db, staff, lab, env_node, device_headers):
    _post(client, device_headers, lab, smoke=1, temperature=23.0)
    body = client.get("/api/monitor", headers=auth_headers(client, staff.email)).json()
    t = next(x for x in body["labs"] if x["lab_id"] == lab.id)
    assert t["hazards"] == ["smoke"] and t["state"] == "ALERT"
    assert t["env_online"] is True and t["environment"]["temperature"]["value"] == 23.0


def test_readiness_warns_on_hazard_and_offline_node(client, db, lab, env_node, device_headers):
    from app.services.automation import lab_readiness
    _post(client, device_headers, lab, smoke=0, temperature=22.0)
    r = lab_readiness(db, lab)
    assert r["environment"] == "ONLINE" and r["environment_hazards"] == []
    _post(client, device_headers, lab, water_leak=1)
    r = lab_readiness(db, lab)
    assert r["level"] == "warning" and r["environment_hazards"] == ["water_leak"]
    assert any("water leak" in w for w in r["warnings"])
    env_node.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()
    r = lab_readiness(db, lab)
    assert r["environment"] == "OFFLINE" and any("offline" in w for w in r["warnings"])


def test_ai_environment_tool_reports_only_stored_data(client, db, lab, env_node, device_headers):
    from app.services.ai import run_tool
    import json
    _post(client, device_headers, lab, temperature=21.0, humidity=40.0)
    _post(client, device_headers, lab, temperature=25.0, flame=1)
    _post(client, device_headers, lab, flame=0)
    out, is_error = run_tool(db, "get_environment", {"lab_code": lab.code, "hours": 24})
    assert not is_error
    d = json.loads(out)
    t = d["values"]["temperature"]
    assert t["count"] == 2 and t["min"] == 21.0 and t["max"] == 25.0 and t["mean"] == 23.0
    assert [e["hazard"] for e in d["hazard_episodes"]] == ["flame"]
    assert d["hazard_episodes"][0]["cleared"] is not None
    bad, _ = run_tool(db, "get_environment", {"lab_code": "NOPE"})
    assert "No laboratory" in bad
