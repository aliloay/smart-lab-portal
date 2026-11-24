"""Lab 24 Nov 2026: the 5-second RUNNING / IDLE report must not erase a robot's live telemetry."""
from app.models import Device
from sqlalchemy import select


def test_equipment_report_keeps_live_telemetry(client, db, lab, device_headers):
    q = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    assert client.post("/api/robots/telemetry", headers=device_headers, json={
        "device_uid": "UR5E_K", "lab_id": lab.code, "model": "UR5E", "source": "RTDE", "state": "MOVING", "q": q,
        "qd": [0.0] * 6, "joints_moving": [True] * 6, "telemetry_age_ms": 5.0, "rate_hz": 10.0}).status_code == 200
    assert client.post("/api/equipment/state", headers=device_headers, json={
        "device_uid": "UR5E_K", "lab_id": lab.code, "kind": "ROBOT", "state": "RUNNING",
        "detail": {"robot_mode": 7}}).status_code == 200
    db.expire_all()
    cs = db.scalar(select(Device).where(Device.device_uid == "UR5E_K")).component_state
    assert cs["q"] == q and cs["state"] == "MOVING" and cs["equipment_state"] == "RUNNING"


def test_robot_without_telemetry_still_reports_its_state(client, db, lab, device_headers):
    assert client.post("/api/equipment/state", headers=device_headers, json={
        "device_uid": "UR5E_L", "lab_id": lab.code, "kind": "ROBOT", "state": "IDLE"}).status_code == 200
    db.expire_all()
    assert db.scalar(select(Device).where(Device.device_uid == "UR5E_L")).component_state["state"] == "IDLE"
