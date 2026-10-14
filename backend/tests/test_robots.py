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
    """The only command route is /control/command, and the control code has no way to reach a
    controller: no sockets, HTTP clients, RTDE control or dashboard calls (2026-10-14)."""
    import inspect
    from app.main import app
    from app.services import robot_control
    # app.routes holds the mounted sub-app, not its paths (the old check here was always empty).
    paths = [p for p in app.openapi()["paths"] if "/robots" in p]
    assert len(paths) > 5
    assert not [p for p in paths if set(p.split("/")) & {"move", "jog", "program", "write", "io", "servo"}]
    assert [p for p in paths if "command" in p] == [p for p in paths if p.endswith("/robots/{device_id}/control/command")] and len([p for p in paths if "command" in p]) == 1
    src = inspect.getsource(robot_control)
    for bad in ("import socket", "httpx", "import requests", "RTDEControl", "rtde_control", "urllib", "30002"):
        assert bad not in src, bad
    # The only network code is the UR5e Dashboard client, reached only in live mode (off by default).
    assert robot_control.MODE != "live"
    from app.services import ur_dashboard
    assert set(ur_dashboard.ALLOWED) == {"is in remote control", "robotmode", "safetystatus", "programState",
                                         "get loaded program", "play", "stop"}


# ---------------------------------------------------------------- fusion ---
from app.services import robot_fusion as rf


def test_fusion_table():
    assert rf.fuse("MOVING", "RTDE", "MOVING") == "MOVEMENT_VERIFIED"
    assert rf.fuse("MOVING", "RTDE", "OCCLUDED") == "VISUALLY_OCCLUDED"
    assert rf.fuse("MOVING", "RTDE", "STILL") == "MOVEMENT_TELEMETRY_ONLY"
    assert rf.fuse("STATIONARY", "RTDE", "STILL") == "STATIONARY_VERIFIED"
    assert rf.fuse("STATIONARY", "RTDE", "UNKNOWN") == "STATIONARY"
    assert rf.fuse("STATIONARY", "RTDE", "MOVING") == "VISUAL_ANOMALY"
    assert rf.fuse("TELEMETRY_STALE", "RTDE", "MOVING") == "VISUAL_MOVEMENT_DURING_TELEMETRY_OUTAGE"
    assert rf.fuse("OFFLINE", "RTDE", "UNKNOWN") == "OFFLINE"
    assert rf.fuse("MOVING", "SIMULATION", "MOVING") == "SIMULATION"     # demo never vs the real camera
    # Recent motion within the window counts; an offline camera is no evidence.
    assert rf.camera_view({"state": "STILL", "last_motion_at": 99.0}, True, 100.0) == "MOVING"
    assert rf.camera_view({"state": "MOVING"}, False, 100.0) == "UNKNOWN"


def _camera_state(client, device_headers, visual):
    client.get("/api/security/config", headers=device_headers,
               params={"device_uid": "SECCAM_LAB01", "lab_id": "LAB_TEST"})
    return client.post("/api/security/state", headers=device_headers, json={
        "device_uid": "SECCAM_LAB01", "fps": 3, "people": 0, "unknown": 0,
        "zones": [{"id": 1, "name": "UR5e", "status": "MOTION", "visual": visual}]})


def test_camera_sees_motion_while_telemetry_says_still_raises_disagreement_after_hold(client, db, lab, staff,
                                                                                        device_headers):
    tele(client, device_headers)
    assert _camera_state(client, device_headers, {"state": "MOVING", "moving_share": 0.2}).status_code == 200
    d = db.query(Device).filter_by(device_uid="UR5E_TEST").one()
    db.refresh(d)
    assert d.component_state["fusion"] == "VISUAL_ANOMALY"
    assert db.query(RobotEvent).filter_by(kind="VISUAL_TELEMETRY_DISAGREEMENT").count() == 0   # not yet: held 3 s
    cs = dict(d.component_state)
    cs["fusion_since"] -= 5                                              # it has lasted 5 s
    d.component_state = cs
    db.commit()
    _camera_state(client, device_headers, {"state": "MOVING", "moving_share": 0.2})
    _camera_state(client, device_headers, {"state": "MOVING", "moving_share": 0.2})
    ev = db.query(RobotEvent).filter_by(kind="VISUAL_TELEMETRY_DISAGREEMENT").all()
    assert len(ev) == 1 and ev[0].severity == "WARNING"                  # once, not every report
    body = client.get("/api/robots", headers=auth_headers(client, staff.email)).json()[0]
    assert body["fusion"] == "VISUAL_ANOMALY" and body["fusion_evidence"][0]["source"] == "telemetry"


def test_telemetry_and_camera_agreeing_is_verified(client, db, lab, device_headers):
    _camera_state(client, device_headers, {"state": "MOVING", "moving_share": 0.2})
    tele(client, device_headers, state="MOVING")
    d = db.query(Device).filter_by(device_uid="UR5E_TEST").one()
    assert d.component_state["fusion"] == "MOVEMENT_VERIFIED"
    assert db.query(RobotEvent).filter_by(kind="MOVEMENT_VISUALLY_VERIFIED").count() == 1


def test_a_movement_path_is_stored_and_served_on_its_own(client, db, lab, staff, device_headers):
    tele(client, device_headers)
    now = datetime.now(timezone.utc).timestamp()
    path = {"t": [0.0, 0.1, 0.2], "q": [HOME, HOME, HOME]}
    client.post("/api/robots/events", headers=device_headers, json={"device_uid": "UR5E_TEST", "events": [
        {"kind": "MOVEMENT_STOPPED", "t": now, "detail": {"duration_s": 0.2, "trajectory": path}}]})
    h = auth_headers(client, staff.email)
    rid = db.query(Device).filter_by(device_uid="UR5E_TEST").one().id
    listed = client.get(f"/api/robots/{rid}/events", headers=h).json()
    assert listed[0]["has_trajectory"] and "trajectory" not in listed[0]["detail"]     # lists stay small
    mv = client.get(f"/api/robots/{rid}/movements", headers=h).json()
    one = client.get(f"/api/robots/{rid}/movements/{mv[0]['id']}", headers=h).json()
    assert one["trajectory"]["t"] == [0.0, 0.1, 0.2] and len(one["trajectory"]["q"]) == 3


def test_non_finite_joint_values_are_rejected_not_stored(client, db, lab, staff, device_headers):
    # The collector filters these too; the API must not accept them (JSONB cannot hold NaN).
    body = '{"device_uid": "UR5E_TEST", "lab_id": "LAB_TEST", "model": "UR5e", "source": "RTDE", "state": "STATIONARY",' \
           ' "q": [0, NaN, 0, 0, 0, 0], "qd": [0, 0, 0, 0, 0, 0]}'
    r = client.post("/api/robots/telemetry", headers={**device_headers, "Content-Type": "application/json"}, content=body)
    assert r.status_code == 422
    assert db.query(Device).filter_by(device_uid="UR5E_TEST").first() is None
