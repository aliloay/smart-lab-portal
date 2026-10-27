"""Live Smart Lab camera (2026-10-27): the target layer. The camera says WHAT is in view (marker / face ticket);
every value shown or spoken comes from that record, with its age and quality; control requests are refused."""
import math
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.api.routes import scan as scan_route
from app.models import Alert, AlertSeverity, Asset, AssetStatus, AuditLog, Device, DeviceType, InventoryBin, SensorReading
from app.services import live_target
from tests.conftest import auth_headers, image_bytes

Q = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.5]
QD = [0.0, 0.0, 0.1, 0.0, 0.0, 0.0]


def _robot(db, lab, age_s=0.5, source="TEACH_PENDANT", q=Q):
    now = datetime.now(timezone.utc)
    d = Device(device_uid="UR5E_T", name="UR5e (physical)", device_type=DeviceType.ROBOT, lab_id=lab.id,
               last_seen_at=now - timedelta(seconds=age_s), is_online=True,
               component_state={"model": "UR5e", "source": source, "state": "MOVING", "home": "NOT_HOME",
                                "q": q, "qd": QD, "tcp": [0.1, -0.2, 0.3, 0.0, 3.14, 0.0],
                                "extra": {"robot_mode": 7, "safety_mode": 1}, "received_at": now.isoformat()})
    db.add(d); db.commit()
    return d


def _ask(client, h, question, code=None, ticket=None):
    return client.post("/api/scan/ask", json={"question": question, "code": code, "ticket": ticket}, headers=h)


def test_robot_live_block_maps_six_joints_in_degrees_with_velocity(client, db, lab, staff):
    _robot(db, lab)
    c = client.get("/api/scan/asset", params={"code": "SLAB:D:UR5E_T"}, headers=auth_headers(client, staff.email)).json()
    r = c["live"]
    assert r["type"] == "robot" and r["connection"] == "LIVE"
    assert [j["name"] for j in r["joints"]] == ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Wrist 3"]
    assert r["joints"][2]["deg"] == pytest.approx(90.0, abs=0.01) and r["joints"][2]["vel_deg_s"] == pytest.approx(5.73, abs=0.01)
    assert r["joints"][5]["deg"] == pytest.approx(math.degrees(0.5), abs=0.01)
    assert r["tcp"]["x_mm"] == 100.0 and r["robot_mode"] == "RUNNING" and r["safety_mode"] == "NORMAL"


@pytest.mark.parametrize("age,state", [(10, "STALE"), (120, "OFFLINE")])
def test_old_robot_telemetry_is_never_called_live(client, db, lab, staff, age, state):
    _robot(db, lab, age_s=age)
    h = auth_headers(client, staff.email)
    r = _ask(client, h, "Is it connected?", "SLAB:D:UR5E_T").json()
    assert r["live"]["connection"] == state and r["deterministic"]
    assert ("STALE" in r["answer"] if state == "STALE" else "not reporting" in r["answer"])
    assert "is connected" not in r["answer"]


def test_robot_without_telemetry_shows_no_joints(client, db, lab, staff):
    db.add(Device(device_uid="UR5E_NEW", name="UR5e new", device_type=DeviceType.ROBOT, lab_id=lab.id)); db.commit()
    r = _ask(client, auth_headers(client, staff.email), "Tell me more", "SLAB:D:UR5E_NEW").json()
    assert r["live"]["connection"] == "NO_TELEMETRY" and r["live"]["joints"] == [] and "never sent telemetry" in r["answer"]


def test_tell_me_more_and_joint_three_come_from_the_record(client, db, lab, staff):
    _robot(db, lab)
    h = auth_headers(client, staff.email)
    r = _ask(client, h, "Tell me more", "SLAB:D:UR5E_T").json()
    assert r["intent"] == "state" and "Elbow 90°" in r["answer"] and "RUNNING" in r["answer"] and r["ms"] >= 0
    j = _ask(client, h, "What is joint 3 doing?", "SLAB:D:UR5E_T").json()
    assert j["intent"] == "joint" and "Joint 3 (Elbow) is at 90.0 deg" in j["answer"] and "+5.7 deg/s" in j["answer"]
    w = _ask(client, h, "and the wrist 3?", "SLAB:D:UR5E_T").json()
    assert "Joint 6 (Wrist 3)" in w["answer"]
    assert db.query(AuditLog).filter_by(action="SCAN_ASK").count() == 3


def test_simulated_robot_is_labelled_simulation(client, db, lab, staff):
    _robot(db, lab, source="SIMULATION")
    r = _ask(client, auth_headers(client, staff.email), "status?", "SLAB:D:UR5E_T").json()
    assert "SIMULATION" in r["answer"]


@pytest.mark.parametrize("q", ["Move the robot home", "stop", "Please open the door", "can you start it"])
def test_voice_never_controls_anything(monkeypatch, client, db, lab, staff, q):
    _robot(db, lab)
    import app.services.robot_control as rc
    monkeypatch.setattr(rc, "execute", lambda *a, **k: pytest.fail("a control path was called"), raising=False)
    r = _ask(client, auth_headers(client, staff.email), q, "SLAB:D:UR5E_T").json()
    assert r["intent"] == "control" and "monitoring only" in r["answer"]


def test_bin_how_much_is_left_is_an_estimate_only_when_calibrated(client, db, lab, staff):
    now = datetime.now(timezone.utc)
    node = Device(device_uid="BIN_NODE_T", name="BIN_NODE_T", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                  last_seen_at=now, is_online=True)
    db.add(node); db.commit()
    db.add_all([InventoryBin(code="BIN-R", lab_id=lab.id, device_id=node.id, item_name="10 kOhm resistors", tare_g=100.0,
                             unit_mass_g=0.2, last_mass_g=106.0, last_measured_at=now, reorder_qty=50),
                InventoryBin(code="BIN-X", lab_id=lab.id, device_id=node.id, item_name="LEDs")])
    db.commit()
    h = auth_headers(client, staff.email)
    r = _ask(client, h, "How much is left?", "SLAB:D:BIN_NODE_T").json()
    assert r["live"]["type"] == "consumables" and r["intent"] == "stock"
    assert "about 30" in r["answer"] and "estimate from 106.0 g" in r["answer"] and "LOW" in r["answer"]
    assert "LEDs (BIN-X): no count - the scale is not calibrated" in r["answer"]
    single = _ask(client, h, "how many remain", "SLAB:B:BIN-R").json()
    assert "LEDs" not in single["answer"] and "about 30" in single["answer"]


def test_environment_problems_lists_readings_ages_and_open_alerts(client, db, lab, staff):
    now = datetime.now(timezone.utc)
    env = Device(device_uid="ENV_T", name="Environment node", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                 last_seen_at=now, is_online=True)
    db.add(env); db.commit()
    db.add_all([SensorReading(lab_id=lab.id, device_id=env.id, metric="temperature", value=23.4, unit="C", recorded_at=now),
                SensorReading(lab_id=lab.id, device_id=env.id, metric="humidity", value=44.0, unit="%",
                              recorded_at=now - timedelta(minutes=30)),
                Alert(lab_id=lab.id, device_id=env.id, severity=AlertSeverity.WARNING, title="Smoke sensor warming up")])
    db.commit()
    r = _ask(client, auth_headers(client, staff.email), "Is anything wrong?", "SLAB:D:ENV_T").json()
    assert r["live"]["type"] == "environment"
    assert "temperature 23.4 C" in r["answer"] and "humidity 44.0 % (30 min ago, STALE)" in r["answer"]
    assert "1 open alert(s)" in r["answer"] and "Smoke sensor warming up" in r["answer"]


def test_reusable_bin_contents_are_the_record_not_a_look_inside(client, db, lab, staff, alice):
    now = datetime.now(timezone.utc)
    db.add(Device(device_uid="REUSE_T", name="Reusable bin", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                  last_seen_at=now, component_state={"reusable_bin": True}))
    db.add_all([Asset(asset_tag="ARD-1", name="Arduino Uno #1", lab_id=lab.id, bin_item=True),
                Asset(asset_tag="BB-1", name="Breadboard #1", lab_id=lab.id, bin_item=True,
                      status=AssetStatus.CHECKED_OUT, holder_id=alice.id, checked_out_at=now)])
    db.commit()
    r = _ask(client, auth_headers(client, staff.email), "What is inside?", "SLAB:D:REUSE_T").json()
    assert r["live"]["type"] == "reusable_bin"
    assert "1 item(s) available (Arduino Uno #1)" in r["answer"] and "Breadboard #1 - Alice" in r["answer"]
    assert "not a camera look inside" in r["answer"]


class FakeFace:
    def __init__(self, name="USER1", score=0.71, second=0.3):
        self.res = {"name": name, "score": score, "second": second, "face": True}

    def post(self, url, content, headers):
        return httpx.Response(200, json=self.res)


def test_who_is_this_needs_a_server_issued_ticket(monkeypatch, client, db, staff, alice):
    alice.student_id = "20231234"; alice.department = "Mechatronics"; db.commit()
    h = auth_headers(client, staff.email)
    monkeypatch.setattr(scan_route, "_face", FakeFace())
    idf = client.post("/api/scan/identify", content=image_bytes(), headers=h).json()
    assert idf["known"] and idf["person"]["student_id"] == "•••••234" and "email" not in idf["person"]
    r = _ask(client, h, "Who is this?", ticket=idf["ticket"]).json()
    assert r["intent"] == "who" and "USER1 - Alice" in r["answer"] and "Mechatronics" in r["answer"]
    assert _ask(client, h, "Who is this?").json()["answer"].startswith("No enrolled person is identified")
    forged = idf["ticket"].split(".")[0] + ".AAAAAAAAAAAAAAAAAAAAAAAA"
    assert _ask(client, h, "Who is this?", ticket=forged).status_code == 409
    old = live_target.person_ticket(alice.id, 0.7, now_s=1_000)
    assert _ask(client, h, "Who is this?", ticket=old).status_code == 409


def test_unknown_target_and_no_target(client, db, lab, staff, alice):
    h = auth_headers(client, staff.email)
    assert _ask(client, h, "tell me more", "SLAB:D:NOPE").status_code == 404
    r = _ask(client, h, "tell me more").json()
    assert "Nothing is identified in view" in r["answer"]
    assert _ask(client, auth_headers(client, alice.email), "tell me more").status_code == 403


def test_open_questions_go_to_the_model_with_the_live_data_as_context(monkeypatch, client, db, lab, staff):
    _robot(db, lab)
    seen = {}

    def fake_run(db_, user, question, history=None, **k):
        seen["q"], seen["h"] = question, history
        return {"answer": "model answer", "tools_used": [], "model": "fake"}
    import app.api.routes.ai as ai_route
    monkeypatch.setattr(ai_route, "_run", fake_run)
    r = _ask(client, auth_headers(client, staff.email), "Compare that with a typical cycle", "SLAB:D:UR5E_T").json()
    assert r["answer"] == "model answer" and r["deterministic"] is False
    assert "UR5e (physical)" in seen["h"][0]["content"] and '"joints"' in seen["h"][0]["content"]
