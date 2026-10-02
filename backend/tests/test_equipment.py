"""
Networked equipment (robots, PCs), backend side.

Tested: a collector's report registers the robot against its asset and
opens a session linked to the booking in force; a state change closes it
and opens the next; FAULT raises an alert; metrics are stored; an item
that stops reporting has its session closed; PC exam mode returns the
prohibited list and violations are logged for staff. No robot command
exists anywhere in this API.
"""
from datetime import datetime, timedelta, timezone

from app.models import (Alert, Asset, Booking, BookingStatus, Device, EquipmentSession,
                        Notification, PolicyViolation, SensorReading)
from tests.conftest import auth_headers


def _state(client, headers, lab, state, uid="UR5E_01", kind="ROBOT", tag="UR5E-01", **kw):
    return client.post("/api/equipment/state", headers=headers, json={
        "device_uid": uid, "lab_id": lab.code, "kind": kind, "asset_tag": tag,
        "state": state, **kw})


def test_robot_sessions_follow_state_and_booking(client, db, staff, alice, lab, device_headers):
    db.add(Asset(asset_tag="UR5E-01", name="UR5e", lab_id=lab.id))
    now = datetime.now(timezone.utc)
    b = Booking(user_id=alice.id, lab_id=lab.id, start_time=now - timedelta(hours=1),
                end_time=now + timedelta(hours=1), status=BookingStatus.CONFIRMED)
    db.add(b)
    db.commit()
    r = _state(client, device_headers, lab, "RUNNING", detail={"robot_mode": 7, "program": "pick.urp"},
               metrics=[{"metric": "ur_speed_scaling", "value": 1.0}])
    assert r.status_code == 200 and r.json()["mode"] == "NORMAL"
    d = db.query(Device).filter_by(device_uid="UR5E_01").one()
    assert d.device_type.value == "ROBOT" and d.asset_id is not None
    s = db.query(EquipmentSession).one()
    assert s.state == "RUNNING" and s.user_id == alice.id and s.booking_id == b.id
    assert db.query(SensorReading).filter_by(metric="ur_speed_scaling").count() == 1

    _state(client, device_headers, lab, "RUNNING")            # same state: same session
    _state(client, device_headers, lab, "IDLE")
    db.expire_all()
    rows = db.query(EquipmentSession).order_by(EquipmentSession.id).all()
    assert [x.state for x in rows] == ["RUNNING", "IDLE"] and rows[0].ended_at is not None

    eq = client.get("/api/equipment", headers=auth_headers(client, staff.email)).json()[0]
    assert eq["state"] == "IDLE" and eq["name"] == "UR5e" and eq["user_name"] == "Alice"
    assert eq["online"] is True


def test_fault_raises_an_alert(client, db, lab, device_headers):
    _state(client, device_headers, lab, "FAULT", tag=None, detail={"safety_mode": 3})
    assert db.query(Alert).filter(Alert.title.like("%fault%")).count() == 1


def test_silent_item_has_its_session_closed(client, db, staff, lab, device_headers):
    _state(client, device_headers, lab, "RUNNING", tag=None)
    d = db.query(Device).filter_by(device_uid="UR5E_01").one()
    d.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    eq = client.get("/api/equipment", headers=auth_headers(client, staff.email)).json()[0]
    assert eq["online"] is False and eq["state"] is None
    db.expire_all()
    assert db.query(EquipmentSession).one().ended_at is not None


def test_pc_exam_mode_and_violations(client, db, staff, lab, device_headers):
    _state(client, device_headers, lab, "IDLE", uid="PC_01", kind="PC", tag=None)
    d = db.query(Device).filter_by(device_uid="PC_01").one()
    h = auth_headers(client, staff.email)
    assert client.put(f"/api/equipment/{d.id}/mode", headers=h, json={"mode": "EXAM"}).status_code == 200
    r = _state(client, device_headers, lab, "IDLE", uid="PC_01", kind="PC", tag=None).json()
    assert r["mode"] == "EXAM" and "discord.exe" in r["prohibited"]
    v = client.post("/api/equipment/violations", headers=device_headers, json={
        "device_uid": "PC_01", "kind": "PROHIBITED_PROGRAM", "detail": "discord.exe running",
        "os_user": "student01"})
    assert v.status_code == 201
    assert db.query(PolicyViolation).one().os_user == "student01"
    assert db.query(Notification).filter_by(user_id=staff.id, kind="EXAM_VIOLATION").count() == 1
    assert client.get("/api/equipment/violations", headers=h).json()[0]["kind"] == "PROHIBITED_PROGRAM"


def test_staff_only_and_robots_have_no_mode(client, db, alice, staff, lab, device_headers):
    _state(client, device_headers, lab, "IDLE")
    d = db.query(Device).filter_by(device_uid="UR5E_01").one()
    assert client.get("/api/equipment", headers=auth_headers(client, alice.email)).status_code == 403
    assert client.put(f"/api/equipment/{d.id}/mode", headers=auth_headers(client, staff.email),
                      json={"mode": "EXAM"}).status_code == 404
