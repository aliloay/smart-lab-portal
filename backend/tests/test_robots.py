"""
Robots API (read-only monitoring): telemetry, events with context and
severity, role-limited views, stale != stationary, versioned HOME.
"""
import math
from datetime import datetime, timedelta, timezone

from app.models import AuditLog, Device, RobotEvent, RobotHomeCalibration
from tests.conftest import auth_headers

HOME = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]


def tele(client, device_headers, q=HOME, state="STATIONARY", source="RTDE", uid="UR5E_TEST"):
    return client.post("/api/robots/telemetry", headers=device_headers, json={
        "device_uid": uid, "lab_id": "LAB_TEST", "model": "UR5e", "name": "UR5e", "source": source,
        "state": state, "q": q, "qd": [0.0] * 6, "joints_moving": [False] * 6, "telemetry_age_ms": 12,
        "rate_hz": 50.0, "extra": {"robot_mode": 7, "safety_mode": 1}})


def test_telemetry_registers_the_robot_and_staff_see_joints_students_do_not(client, lab, staff, alice,
                                                                           device_headers):
    assert tele(client, device_headers).status_code == 200
    staff_view = client.get("/api/robots", headers=auth_headers(client, staff.email)).json()
    assert staff_view[0]["state"] == "STATIONARY" and staff_view[0]["q"] == HOME
    student_view = client.get("/api/robots", headers=auth_headers(client, alice.email)).json()
    assert student_view[0]["state"] == "STATIONARY" and "q" not in student_view[0]
    rid = staff_view[0]["device_id"]
    assert client.get(f"/api/robots/{rid}", headers=auth_headers(client, alice.email)).status_code == 403


def test_no_telemetry_is_stale_never_stationary(client, db, lab, staff, device_headers):
    tele(client, device_headers)
    d = db.query(Device).filter_by(device_uid="UR5E_TEST").one()
    d.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.commit()
    r = client.get("/api/robots", headers=auth_headers(client, staff.email)).json()
    assert r[0]["state"] == "TELEMETRY_STALE"
    d.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
    assert client.get("/api/robots", headers=auth_headers(client, staff.email)).json()[0]["state"] == "OFFLINE"


def test_events_get_context_and_severity(client, db, lab, device_headers):
    tele(client, device_headers)
    now = datetime.now(timezone.utc).timestamp()
    r = client.post("/api/robots/events", headers=device_headers, json={"device_uid": "UR5E_TEST", "events": [
        {"kind": "MOVEMENT_STARTED", "t": now, "detail": {"joints": ["J4"]}},
        {"kind": "JOINT_MOVED", "t": now + 1, "joint": 3, "detail": {"delta_deg": 12.3}}]})
    assert r.status_code == 200 and r.json() == {"stored": 2}
    start, moved = db.query(RobotEvent).order_by(RobotEvent.id).all()
    # No booking, nobody entered at the door: the strongest level.
    assert start.severity == "CRITICAL" and start.context["booking"] is None
    assert moved.joint == 3 and moved.detail["delta_deg"] == 12.3 and moved.severity == "INFO"


def test_simulated_data_is_demo_data_and_never_alarms(client, db, lab, device_headers):
    tele(client, device_headers, source="SIMULATION", uid="UR5E_SIM")
    client.post("/api/robots/events", headers=device_headers, json={"device_uid": "UR5E_SIM", "events": [
        {"kind": "MOVEMENT_STARTED", "t": datetime.now(timezone.utc).timestamp(), "source": "SIMULATION"}]})
    ev = db.query(RobotEvent).one()
    assert ev.provenance == "DEMO_DATA" and ev.severity == "INFO"


def test_home_is_calibrated_from_live_still_telemetry_and_versioned(client, db, lab, admin, staff, device_headers):
    tele(client, device_headers)
    rid = db.query(Device).filter_by(device_uid="UR5E_TEST").one().id
    assert client.post(f"/api/robots/{rid}/home", headers=auth_headers(client, staff.email),
                       json={}).status_code == 403                      # administrators only
    h = auth_headers(client, admin.email)
    assert client.post(f"/api/robots/{rid}/home", headers=h, json={"tolerance_deg": 1.0}).json()["version"] == 1
    assert client.get(f"/api/robots/{rid}", headers=h).json()["home"] in ("UNKNOWN", "HOME")
    tele(client, device_headers)
    assert client.get(f"/api/robots/{rid}", headers=h).json()["home"] == "HOME"
    away = HOME[:2] + [HOME[2] + math.radians(20)] + HOME[3:]
    tele(client, device_headers, q=away)
    body = client.get(f"/api/robots/{rid}", headers=h).json()
    assert body["home"] == "NOT_HOME" and body["worst_joint"] == "J3"
    assert db.query(RobotEvent).filter_by(kind="HOME_LEFT").count() == 1
    # A moving robot cannot be calibrated; a second calibration is version 2, v1 kept.
    tele(client, device_headers, q=away, state="MOVING")
    assert client.post(f"/api/robots/{rid}/home", headers=h, json={}).status_code == 409
    tele(client, device_headers, q=away)
    assert client.post(f"/api/robots/{rid}/home", headers=h, json={}).json()["version"] == 2
    assert db.query(RobotHomeCalibration).count() == 2
    assert db.query(AuditLog).filter_by(action="ROBOT_HOME_CALIBRATED").count() == 2


def test_no_endpoint_can_send_anything_to_a_robot():
    from app.main import app
    paths = [r.path for r in app.routes if getattr(r, "path", "").startswith("/api/robots")]
    assert not [p for p in paths if any(w in p for w in ("command", "move", "program", "write", "io"))]
