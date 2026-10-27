"""Advisory safety triage (2026-10-27): one ranked list from camera + robot + door + environment + access records.
Read-only; stale sources never count as current; simulated robots never raise an item."""
from datetime import datetime, timedelta, timezone

from app.models import AccessSession, Device, DeviceType
from tests.conftest import auth_headers


def now():
    return datetime.now(timezone.utc)


def _robot(db, lab, state="MOVING", source="TEACH_PENDANT", uid="UR5E_T"):
    db.add(Device(device_uid=uid, name="UR5e", device_type=DeviceType.ROBOT, lab_id=lab.id, last_seen_at=now(),
                  is_online=True, component_state={"state": state, "source": source, "model": "UR5e"}))


def _cam(db, lab, people, age_s=1, uid="SECCAM_T"):
    db.add(Device(device_uid=uid, name="Cam", device_type=DeviceType.SECURITY_CAMERA, lab_id=lab.id,
                  last_seen_at=now() - timedelta(seconds=age_s), component_state={"people": people, "source_ok": True}))


def _get(client, staff):
    return client.get("/api/safety/triage", headers=auth_headers(client, staff.email)).json()["items"]


def test_moving_robot_with_people_on_camera_is_p1(client, db, lab, staff):
    _robot(db, lab); _cam(db, lab, 2); db.commit()
    items = _get(client, staff)
    assert items[0]["priority"] == 1 and "moving while the camera sees 2" in items[0]["title"]
    assert any(e["source"].startswith("camera") for e in items[0]["evidence"]) and "Advisory only" in items[0]["advisory"]


def test_moving_robot_alone_without_camera_is_unattended_and_unsupervised(client, db, lab, staff):
    _robot(db, lab); _cam(db, lab, 0, age_s=3600); db.commit()        # the camera is stale = not reporting
    keys = {i["key"].split(":", 1)[1] for i in _get(client, staff)}
    assert {"robot-nocam:UR5E_T", "robot-unattended:UR5E_T"} <= keys


def test_simulated_or_idle_robots_raise_nothing(client, db, lab, staff):
    _robot(db, lab, source="SIMULATION", uid="UR5E_SIM"); _robot(db, lab, state="IDLE", uid="UR5E_IDLE"); db.commit()
    assert not [i for i in _get(client, staff) if "robot" in i["key"]]


def test_more_people_on_camera_than_checked_in(client, db, lab, staff, alice):
    _cam(db, lab, 3); db.add(AccessSession(lab_id=lab.id, user_id=alice.id, entry_method="QR")); db.commit()
    it = [i for i in _get(client, staff) if i["key"].endswith("people-mismatch")]
    assert it and it[0]["priority"] == 2 and "3 people on camera but 1 checked in" in it[0]["title"]


def test_door_open_with_nobody_inside_and_students_cannot_read(client, db, lab, staff, alice):
    db.add(Device(device_uid="MASTER_T", name="Door", device_type=DeviceType.MASTER_CONTROLLER, lab_id=lab.id,
                  last_seen_at=now(), door_closed=False)); db.commit()
    assert any(i["key"].endswith("door-open-empty") for i in _get(client, staff))
    assert client.get("/api/safety/triage", headers=auth_headers(client, alice.email)).status_code == 403
