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


# ------------------------------------------------ admin master PC (System 1) ---
from app.models import AuditLog, DeviceCommand, DeviceType  # noqa: E402
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


def test_pc_actions_allowlist_roles_confirmation_and_real_result(client, db, staff, admin, alice, lab, device_headers):
    """2026-10-17: open/close approved apps, lock, log off / restart / shut down - queued, handed to the
    agent once (EXECUTING), finished only by the agent's own result; every step audited."""
    d = _pc(client, db, lab, device_headers)
    hs, ha, hst = auth_headers(client, staff.email), auth_headers(client, admin.email), auth_headers(client, alice.email)
    act = lambda h, **b: client.post(f"/api/equipment/{d.id}/action", headers=h, json=b)
    assert act(hst, action="lock").status_code == 403                                   # students: never
    assert act(hs, action="open_app", app="regedit").status_code == 422                 # not approved
    assert act(hs, action="format_disk").status_code == 422
    assert act(hs, action="restart", confirmed=True).status_code == 403                # admin only
    assert act(ha, action="restart").status_code == 422                                # needs confirmation
    r = act(hs, action="open_app", app="matlab")
    assert r.status_code == 201 and r.json()["status"] == "QUEUED"
    assert act(hs, action="lock").status_code == 409                                   # one at a time
    p = _poll(client, device_headers)
    assert p["action"]["action"] == "open_app" and p["action"]["app"] == "matlab"
    assert _poll(client, device_headers)["action"] is None                             # handed over once
    rows = client.get(f"/api/equipment/{d.id}/actions", headers=hs).json()["actions"]
    assert rows[0]["status"] == "EXECUTING"
    res = client.post("/api/equipment/pc/action-result", headers=device_headers,
                      json={"device_uid": "PC_01", "id": p["action"]["id"], "ok": True, "message": "started matlab.exe"})
    assert res.json()["status"] == "COMPLETED"
    assert db.query(AuditLog).filter_by(action="PC_ACTION_REQUESTED").count() == 1
    assert db.query(AuditLog).filter_by(action="PC_ACTION_RESULT").count() == 1


def test_pc_action_not_taken_is_reported_unreachable(client, db, staff, lab, device_headers):
    from app.models import DeviceCommand
    d = _pc(client, db, lab, device_headers)
    h = auth_headers(client, staff.email)
    client.post(f"/api/equipment/{d.id}/action", headers=h, json={"action": "lock"})
    c = db.query(DeviceCommand).filter_by(command="PC_ACTION").one()
    c.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    rows = client.get(f"/api/equipment/{d.id}/actions", headers=h).json()["actions"]
    assert rows[0]["status"] == "EXPIRED" and "Unreachable" in rows[0]["message"]


def test_admin_shares_screen_from_browser_students_watch_and_pcs_are_told(client, db, staff, admin, alice, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    ha, hs, hst = auth_headers(client, admin.email), auth_headers(client, staff.email), auth_headers(client, alice.email)
    assert client.post("/api/equipment/broadcast/start", headers=hs, json={"source": "browser"}).status_code == 403
    assert _poll(client, device_headers)["broadcast"]["active"] is False
    r = client.post("/api/equipment/broadcast/start", headers=ha, json={"source": "browser", "title": "PLC demo"})
    assert r.status_code == 200 and r.json()["active"] is True
    p = _poll(client, device_headers)
    assert p["broadcast"] == {"active": True, "by": admin.full_name, "title": "PLC demo"} and p["broadcast_capture"] is False
    assert client.get("/api/equipment/broadcast/frame.jpg", headers=hst).status_code == 204       # nothing yet
    up = lambda h: client.post("/api/equipment/broadcast/frame", headers={**h, "Content-Type": "image/jpeg"}, content=JPEG)
    assert up(hs).status_code == 403                                                              # not the presenter
    assert up(ha).status_code == 204
    f = client.get("/api/equipment/broadcast/frame.jpg", headers=hst)                            # a student watches
    assert f.status_code == 200 and f.content == JPEG
    client.post("/api/equipment/broadcast/stop", headers=ha)
    assert client.get("/api/equipment/broadcast/frame.jpg", headers=hst).status_code == 204
    assert _poll(client, device_headers)["broadcast"]["active"] is False
    assert db.query(AuditLog).filter_by(action="PC_BROADCAST_STARTED").count() == 1


def test_master_pc_is_the_share_source_only_when_chosen(client, db, admin, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    ha = auth_headers(client, admin.email)
    assert client.post("/api/equipment/broadcast/start", headers=ha, json={"source": "master_pc"}).status_code == 409
    client.put(f"/api/equipment/{d.id}/master", headers=ha, json={"is_master": True})
    client.post("/api/equipment/broadcast/start", headers=ha, json={"source": "master_pc"})
    p = _poll(client, device_headers)
    assert p["broadcast_capture"] is True and p["broadcast"] is None        # the master PC presents, it is not told to watch
    r = client.post("/api/equipment/pc/broadcast-frame", params={"device_uid": "PC_01"},
                    headers={**device_headers, "Content-Type": "image/jpeg"}, content=JPEG)
    assert r.status_code == 204
    assert client.get("/api/equipment/broadcast/frame.jpg", headers=ha).content == JPEG


def test_targeted_share_reaches_only_the_chosen_pcs(client, db, admin, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    ha = auth_headers(client, admin.email)
    other = Device(device_uid="PC_02", name="PC_02", device_type=DeviceType.PC, lab_id=lab.id)
    db.add(other); db.commit()
    assert client.post("/api/equipment/broadcast/start", headers=ha,
                       json={"source": "browser", "targets": [999999]}).status_code == 422   # not a lab PC
    client.post("/api/equipment/broadcast/start", headers=ha, json={"source": "browser", "targets": [other.id]})
    assert _poll(client, device_headers)["broadcast"]["active"] is False                     # PC_01 not chosen
    client.post("/api/equipment/broadcast/stop", headers=ha)
    client.post("/api/equipment/broadcast/start", headers=ha, json={"source": "browser", "targets": [d.id]})
    assert _poll(client, device_headers)["broadcast"]["active"] is True


def test_viewer_chooses_monitor_quality_and_fps_and_end_is_audited(client, db, staff, lab, device_headers):
    d = _pc(client, db, lab, device_headers)
    h = auth_headers(client, staff.email)
    assert client.post(f"/api/equipment/{d.id}/screen/start", headers=h, json={"monitor": 9}).status_code == 422
    client.post(f"/api/equipment/{d.id}/screen/start", headers=h, json={"monitor": 2, "quality": 80, "fps": 4})
    assert _poll(client, device_headers)["mirror_opts"] == {"monitor": 2, "quality": 80, "fps": 4.0}
    client.post(f"/api/equipment/{d.id}/screen/stop", headers=h)
    assert _poll(client, device_headers)["mirror_opts"] is None
    assert db.query(AuditLog).filter_by(action="PC_SCREEN_VIEW_ENDED").count() == 1


def test_agent_long_poll_wakes_on_change_and_times_out_otherwise(client, db, staff, lab, device_headers):
    """2026-10-17: the idle agent waits on /pc/wait instead of polling every second."""
    import threading
    import time as _t
    from app.services import pc_control
    d = _pc(client, db, lab, device_headers)
    url = "/api/equipment/pc/wait"
    assert client.get(url, params={"device_uid": "PC_01", "timeout": 1}).status_code == 401      # no device key
    t0 = _t.monotonic()
    r = client.get(url, params={"device_uid": "PC_01", "timeout": 1}, headers=device_headers)
    assert r.json() == {"changed": False} and _t.monotonic() - t0 >= 0.9
    threading.Timer(0.3, lambda: pc_control.touch_viewer(d.id, {"monitor": 1, "quality": 60, "fps": 2})).start()
    t0 = _t.monotonic()
    r = client.get(url, params={"device_uid": "PC_01", "timeout": 5}, headers=device_headers)
    assert r.json() == {"changed": True} and _t.monotonic() - t0 < 1.5                         # woke ~0.3 s
    # a share starting wakes every PC; an action for this PC wakes it too
    threading.Timer(0.2, lambda: pc_control.broadcast_start("Admin", 1, "browser")).start()
    assert client.get(url, params={"device_uid": "PC_01", "timeout": 5}, headers=device_headers).json()["changed"] is True
    h = auth_headers(client, staff.email)
    threading.Timer(0.2, lambda: client.post(f"/api/equipment/{d.id}/action", headers=h, json={"action": "lock"})).start()
    assert client.get(url, params={"device_uid": "PC_01", "timeout": 5}, headers=device_headers).json()["changed"] is True
    assert client.get(url, params={"device_uid": "NOPE", "timeout": 1}, headers=device_headers).status_code == 404



def test_pc_identity_and_clock_offset_are_kept(client, db, staff, lab, device_headers):
    """2026-10-18: host name, the PC's own IPs and agent version for the fleet view; the agent's clock
    against the server's at arrival (a PC 90 s behind shows clock_offset_s ~ +90)."""
    import time as _t
    r = _state(client, device_headers, lab, "RUNNING", uid="PC_TEST_9", kind="PC", tag=None,
               firmware_version="pc-agent-0.8",
               detail={"hostname": "LAB-PC-09", "ips": ["192.168.1.59"], "agent_version": "0.8",
                       "agent_time": _t.time() - 90.0})
    assert r.status_code == 200
    d = db.query(Device).filter_by(device_uid="PC_TEST_9").one()
    db.refresh(d)
    cs = d.component_state
    assert cs["hostname"] == "LAB-PC-09" and cs["ips"] == ["192.168.1.59"]
    assert 89.0 <= cs["clock_offset_s"] <= 95.0
    r = _state(client, device_headers, lab, "RUNNING", uid="PC_TEST_9", kind="PC", tag=None,
               detail={"agent_time": "not a number"})
    db.refresh(d)
    assert r.status_code == 200 and "clock_offset_s" not in d.component_state
