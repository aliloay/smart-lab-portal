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


# ------------------------------------------------ admin master PC (System 2) ---
from app.models import AuditLog, DeviceCommand  # noqa: E402
from app.services import pc_control  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


def _pc(client, db, lab, device_headers):
    pc_control.reset()
    _state(client, device_headers, lab, "RUNNING", uid="PC_01", kind="PC", tag=None)
    return db.query(Device).filter_by(device_uid="PC_01").one()


def _poll(client, device_headers):
    return client.get("/api/equipment/pc/poll", params={"device_uid": "PC_01"},
                      headers=device_headers).json()


def test_remove_and_give_access(client, db, staff, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    h = auth_headers(client, staff.email)
    assert _poll(client, device_headers)["mode"] == "NORMAL"
    assert client.put(f"/api/equipment/{d.id}/mode", headers=h, json={"mode": "LOCKED"}).status_code == 200
    assert _poll(client, device_headers)["mode"] == "LOCKED"
    assert _state(client, device_headers, lab, "RUNNING", uid="PC_01", kind="PC", tag=None).json()["mode"] == "LOCKED"
    client.put(f"/api/equipment/{d.id}/mode", headers=h, json={"mode": "NORMAL"})
    assert _poll(client, device_headers)["mode"] == "NORMAL"
    actions = [a.action for a in db.query(AuditLog).order_by(AuditLog.id).all()]
    assert "PC_ACCESS_REMOVED" in actions and "PC_ACCESS_GIVEN" in actions


def test_screen_view_only_while_staff_watch(client, db, staff, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    h = auth_headers(client, staff.email)
    frame = lambda: client.post("/api/equipment/pc/frame", params={"device_uid": "PC_01"},
                                headers={**device_headers, "Content-Type": "image/jpeg"}, content=JPEG)
    # Nobody watching: the agent is told not to send, and a frame is refused.
    assert _poll(client, device_headers)["mirror"] is False
    assert frame().status_code == 409
    assert client.post(f"/api/equipment/{d.id}/screen/start", headers=h).status_code == 200
    assert _poll(client, device_headers)["mirror"] is True
    assert client.get(f"/api/equipment/{d.id}/screen.jpg", headers=h).status_code == 204  # none yet
    assert frame().status_code == 204
    r = client.get(f"/api/equipment/{d.id}/screen.jpg", headers=h)
    assert r.status_code == 200 and r.content == JPEG and r.headers["content-type"] == "image/jpeg"
    assert db.query(AuditLog).filter_by(action="PC_SCREEN_VIEWED").count() == 1
    client.post(f"/api/equipment/{d.id}/screen/stop", headers=h)
    assert _poll(client, device_headers)["mirror"] is False
    assert frame().status_code == 409


def test_screen_endpoints_are_staff_only(client, db, alice, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    h = auth_headers(client, alice.email)
    assert client.post(f"/api/equipment/{d.id}/screen/start", headers=h).status_code == 403
    assert client.get(f"/api/equipment/{d.id}/screen.jpg", headers=h).status_code == 403
    assert client.post(f"/api/equipment/{d.id}/message", headers=h, json={"text": "hi"}).status_code == 403


def test_message_is_handed_over_once(client, db, staff, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    h = auth_headers(client, staff.email)
    r = client.post(f"/api/equipment/{d.id}/message", headers=h, json={"text": "  Exam starts in 5 min  "})
    assert r.status_code == 201 and r.json()["status"] == "PENDING"
    # A second one waits for the first to be delivered.
    assert client.post(f"/api/equipment/{d.id}/message", headers=h, json={"text": "x"}).status_code == 409
    m = _poll(client, device_headers)["message"]
    assert m["text"] == "Exam starts in 5 min"
    assert _poll(client, device_headers)["message"] is None
    db.expire_all()
    assert db.query(DeviceCommand).one().status == "DONE"
    assert client.post(f"/api/equipment/{d.id}/message", headers=h, json={"text": "x"}).status_code == 201


def test_undelivered_message_expires(client, db, staff, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    h = auth_headers(client, staff.email)
    client.post(f"/api/equipment/{d.id}/message", headers=h, json={"text": "hello"})
    c = db.query(DeviceCommand).one()
    c.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert _poll(client, device_headers)["message"] is None
    db.expire_all()
    assert db.query(DeviceCommand).one().status == "EXPIRED"


def test_pc_controls_reject_a_robot(client, db, staff, lab, device_headers):
    _state(client, device_headers, lab, "IDLE")
    d = db.query(Device).filter_by(device_uid="UR5E_01").one()
    h = auth_headers(client, staff.email)
    assert client.put(f"/api/equipment/{d.id}/mode", headers=h, json={"mode": "LOCKED"}).status_code == 404
    assert client.post(f"/api/equipment/{d.id}/screen/start", headers=h).status_code == 404
