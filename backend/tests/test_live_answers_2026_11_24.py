"""Lab 24 Nov 2026: questions the local model answered wrongly are answered from the live records."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Device, DeviceType
from tests.conftest import auth_headers


def _dev(db, lab, uid, name, typ, age, cs):
    now = datetime.now(timezone.utc)
    db.add(Device(device_uid=uid, name=name, device_type=typ, lab_id=lab.id, is_online=True,
                  last_seen_at=now - timedelta(seconds=age), component_state=cs))
    db.commit()


def _ask(client, user, q):
    r = client.post("/api/ai/ask", headers=auth_headers(client, user.email), json={"question": q})
    assert r.status_code == 200, r.text
    return r.json()


LIVE = {"state": "MOVING", "q": [0.1] * 6, "joints_moving": [True, True] + [False] * 4, "source": "RTDE"}


def test_robot_doing_is_live_and_never_the_simulation(client, db, lab, staff):
    _dev(db, lab, "UR5E_SIM", "UR5e (simulation)", DeviceType.ROBOT, 1, {"state": "MOVING", "source": "SIMULATION"})
    _dev(db, lab, "UR5E_01", "UR5e (physical)", DeviceType.ROBOT, 1, LIVE)
    out = _ask(client, staff, "What is the UR5e doing?")
    assert out["tools_used"] == ["instant:robot_now"]
    assert "UR5e (physical)" in out["answer"] and "moving" in out["answer"] and "2 joints" in out["answer"]


@pytest.mark.parametrize("age,state", [(60, "MOVING"), (1, "TELEMETRY_STALE")])
def test_stale_robot_is_not_called_moving(client, db, lab, staff, age, state):
    _dev(db, lab, "UR5E_01", "UR5e (physical)", DeviceType.ROBOT, age, {**LIVE, "state": state})
    assert "not reporting live" in _ask(client, staff, "What is the UR5e doing?")["answer"]


def test_camera_people_count(client, db, lab, staff):
    _dev(db, lab, "SECCAM_LAB01", "Security camera 1", DeviceType.SECURITY_CAMERA, 1,
         {"activity": [{"text": "a"}, {"text": "b"}]})
    out = _ask(client, staff, "How many people do the cameras see?")
    assert out["tools_used"] == ["instant:camera_people"] and "**2** in view" in out["answer"]


def test_lab_summary_now_but_not_the_weekly_report(client, db, lab, staff):
    lab.name = "Robotics Lab"
    db.commit()
    _dev(db, lab, "UR5E_01", "UR5e (physical)", DeviceType.ROBOT, 1, LIVE)
    out = _ask(client, staff, "Give me a short summary of the robotics lab right now.")
    assert out["tools_used"] == ["instant:lab_now"] and "Open alerts" in out["answer"] and "moving" in out["answer"]
