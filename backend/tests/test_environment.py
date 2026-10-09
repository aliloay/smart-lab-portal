"""
Environment monitoring (Robotics Lab, System 2), backend side.

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
    # No CRITICAL hazard. (Motion in a closed lab is a separate WARNING advisory.)
    assert db.query(Alert).filter_by(lab_id=lab.id, severity=AlertSeverity.CRITICAL).count() == 0


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


def test_hazard_is_pushed_live_and_listed_for_every_user(client, db, alice, lab, env_node,
                                                         device_headers, monkeypatch):
    """A smoke / flame alarm reaches every signed-in page at once (the portal's
    full-screen alarm) and stays listed until the node reports it clear."""
    from app.ws.manager import Client, manager
    sent = []
    monkeypatch.setattr(manager, "publish", lambda m: sent.append(m))

    _post(client, device_headers, lab, flame=1)
    raised = [m for m in sent if m.get("type") == "hazard"]
    assert len(raised) == 1 and raised[0]["state"] == "raised"
    assert raised[0]["metric"] == "flame" and raised[0]["lab_id"] == lab.id
    assert raised[0]["alert_id"] is not None
    # Routed to students too: safety information, not staff-only.
    assert manager._wants(Client(user_id=alice.id, is_staff=False, lab_filter=None), raised[0])

    # A student's page loaded after the alarm started still shows it.
    r = client.get("/api/labs/hazards/active", headers=auth_headers(client, alice.email))
    assert r.status_code == 200
    assert [h["metric"] for h in r.json()] == ["flame"]

    # Reporting the same state again pushes nothing new.
    _post(client, device_headers, lab, flame=1)
    assert len([m for m in sent if m.get("type") == "hazard"]) == 1

    _post(client, device_headers, lab, flame=0)
    cleared = [m for m in sent if m.get("type") == "hazard" and m["state"] == "cleared"]
    assert len(cleared) == 1
    assert client.get("/api/labs/hazards/active", headers=auth_headers(client, alice.email)).json() == []


def test_active_hazards_needs_a_login(client):
    assert client.get("/api/labs/hazards/active").status_code == 401


def test_same_hazard_can_happen_again_after_it_cleared(client, db, lab, env_node, device_headers):
    """Regression (bench 2026-10-05): the second flame in a lab collided with the
    resolved first alert's dedupe key -> HTTP 500 for every post afterwards."""
    for _ in range(3):
        assert _post(client, device_headers, lab, flame=1).status_code == 200
        assert _post(client, device_headers, lab, flame=0).status_code == 200
    alerts = db.query(Alert).filter(Alert.lab_id == lab.id).all()
    assert len(alerts) == 3 and all(a.is_resolved for a in alerts)
    assert _post(client, device_headers, lab, flame=1, temperature=24.0).status_code == 200


def test_offline_alert_once_and_cleared_when_back(client, db, lab, env_node, device_headers):
    """One open offline alert per device, resolved by itself when it reports again."""
    from app.services.devices import refresh_liveness
    env_node.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    refresh_liveness(db)
    env_node.is_online = True            # a second, concurrent refresh sees "online" too
    db.commit()
    refresh_liveness(db)
    open_ = db.query(Alert).filter(Alert.device_id == env_node.id, Alert.is_resolved.is_(False)).all()
    assert len(open_) == 1
    _post(client, device_headers, lab, temperature=24.0)   # reports again
    db.expire_all()
    refresh_liveness(db)
    assert db.query(Alert).filter(Alert.device_id == env_node.id,
                                  Alert.is_resolved.is_(False)).count() == 0


def test_humidity_advisory_once_then_clears_with_hysteresis(client, db, lab, env_node,
                                                            device_headers, monkeypatch):
    from app.ws.manager import Client, manager
    sent = []
    monkeypatch.setattr(manager, "publish", lambda m: sent.append(m))
    warn = lambda: [m for m in sent if m.get("type") == "env_warning"]
    _post(client, device_headers, lab, humidity=82.0)
    _post(client, device_headers, lab, humidity=90.0)         # still high: nothing new
    assert [m["state"] for m in warn()] == ["raised"]
    assert warn()[0]["kind"] == "humidity_high"
    assert not manager._wants(Client(user_id=1, is_staff=False, lab_filter=None), warn()[0])
    _post(client, device_headers, lab, humidity=67.0)         # inside the hysteresis band
    assert len(warn()) == 1
    _post(client, device_headers, lab, humidity=60.0)
    assert [m["state"] for m in warn()] == ["raised", "cleared"]
    _post(client, device_headers, lab, humidity=85.0)         # and it can happen again
    assert [m["state"] for m in warn()] == ["raised", "cleared", "raised"]


def test_motion_start_is_a_quiet_note_not_an_alert(client, db, lab, env_node,
                                                   device_headers, monkeypatch):
    """Motion is normal activity: one note to staff when it starts, never an alert."""
    from app.models import SensorReading
    from app.ws.manager import manager
    sent = []
    monkeypatch.setattr(manager, "publish", lambda m: sent.append(m))
    motion = lambda: [m for m in sent if m.get("kind") == "motion"]
    _post(client, device_headers, lab, motion=1)
    assert len(motion()) == 1
    # the node re-sends motion=1 every 10 s while it lasts: no repeat
    for r in db.query(SensorReading).filter_by(metric="motion").all():
        r.recorded_at -= timedelta(seconds=10)
    db.commit()
    _post(client, device_headers, lab, motion=1)
    assert len(motion()) == 1
    assert db.query(Alert).filter(Alert.lab_id == lab.id).count() == 0


def test_all_labs_environment_in_one_request(client, db, alice, lab, env_node, device_headers):
    """The overview reads every lab with a node in one request, the same data
    as the per-lab endpoint; labs without a node are left out."""
    _post(client, device_headers, lab, temperature=24.5, humidity=40)
    h = auth_headers(client, alice.email)
    rows = client.get("/api/labs/environment/all", headers=h).json()
    assert [r["lab"]["code"] for r in rows] == [lab.code]
    one = client.get(f"/api/labs/{lab.id}/environment", headers=h).json()
    assert rows[0]["env"]["metrics"]["temperature"]["value"] == one["metrics"]["temperature"]["value"] == 24.5


def test_no_full_screen_alarm_from_a_node_that_stopped_reporting(client, db, alice, lab, env_node,
                                                                  device_headers):
    """A flame reading from a node that has since gone silent is not a fire now:
    no page-load alarm; the alert stays open for staff on the Alerts page."""
    from datetime import timedelta
    from app.models import Alert
    _post(client, device_headers, lab, flame=1)
    h = auth_headers(client, alice.email)
    assert len(client.get("/api/labs/hazards/active", headers=h).json()) == 1
    env_node.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()
    assert client.get("/api/labs/hazards/active", headers=h).json() == []
    assert db.query(Alert).filter(Alert.is_resolved.is_(False)).count() >= 1
