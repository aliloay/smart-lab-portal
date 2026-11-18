"""
2026-11-18 (Gemini live audit, P1): powered-off robots showed "online / IDLE". Only a fresh sample (MOVING or
STATIONARY with joint values) is liveness; UNKNOWN / TELEMETRY_STALE mark the robot offline without refreshing
last_seen, keep the last real pose, and an older report never overrides a newer one.
"""
from datetime import datetime, timedelta, timezone

from app.models import Device

HOME = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]


def post(client, h, state, q=HOME, sent_at=None, uid="UR5E_LIVE"):
    body = {"device_uid": uid, "lab_id": "LAB_TEST", "model": "UR5e", "name": "UR5e", "source": "RTDE",
            "state": state, "q": q, "qd": [0.0] * 6 if q else None, "joints_moving": [False] * 6}
    if sent_at is not None:
        body["sent_at"] = sent_at
    return client.post("/api/robots/telemetry", headers=h, json=body)


def dev(db, uid="UR5E_LIVE"):
    db.expire_all()
    return db.query(Device).filter_by(device_uid=uid).one()


def test_fresh_moving_and_stationary_are_online(client, db, lab, device_headers):
    assert post(client, device_headers, "MOVING").status_code == 200
    assert dev(db).is_online
    post(client, device_headers, "STATIONARY")
    d = dev(db)
    assert d.is_online and d.component_state["state"] == "STATIONARY"


def test_unknown_at_startup_is_never_online(client, db, lab, device_headers):
    assert post(client, device_headers, "UNKNOWN", q=None).status_code == 200
    d = dev(db)
    assert not d.is_online and d.last_seen_at is None


def test_stale_after_online_goes_offline_keeps_last_pose_and_time(client, db, lab, device_headers):
    post(client, device_headers, "STATIONARY", sent_at=100.0)
    seen = dev(db).last_seen_at
    d = dev(db); d.last_seen_at = seen - timedelta(seconds=5); db.commit(); seen = dev(db).last_seen_at
    post(client, device_headers, "TELEMETRY_STALE", q=None, sent_at=101.0)
    d = dev(db)
    assert not d.is_online and d.last_seen_at == seen
    assert d.component_state["state"] == "TELEMETRY_STALE" and d.component_state["q"] == HOME
    first_stale = d.component_state["stale_since"]
    post(client, device_headers, "TELEMETRY_STALE", q=None, sent_at=102.0)            # repeated: idempotent
    assert dev(db).component_state["stale_since"] == first_stale and not dev(db).is_online


def test_an_older_stale_report_cannot_override_newer_telemetry(client, db, lab, device_headers):
    post(client, device_headers, "STATIONARY", sent_at=200.0)
    r = post(client, device_headers, "TELEMETRY_STALE", q=None, sent_at=150.0)
    assert r.json().get("ignored") and dev(db).is_online


def test_recovery_needs_a_new_fresh_sample(client, db, lab, device_headers):
    post(client, device_headers, "UNKNOWN", q=None, sent_at=1.0)
    assert not dev(db).is_online
    post(client, device_headers, "STATIONARY", sent_at=2.0)
    d = dev(db)
    assert d.is_online and d.last_seen_at is not None and "stale_since" not in d.component_state
