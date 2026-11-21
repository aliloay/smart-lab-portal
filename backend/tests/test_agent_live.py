"""
Live one-line answers (2026-11-21, services/agent_live.py). Measured that day with both local models: "how many labs"
came back "1" (11 existed) and "is the consumables bin online" came back "offline" / "no data" while it was online.
These questions now get exact answers from the records, without the model.
"""
from datetime import datetime, timedelta, timezone

from app.models import Device, DeviceType, Lab
from app.services import agent_live
from tests.conftest import auth_headers

NOW = datetime.now(timezone.utc)


def _dev(db, lab, uid, name, typ, seen_s=5, online=True, ip=None, fw=None, cs=None):
    d = Device(device_uid=uid, name=name, device_type=typ, lab_id=lab.id, is_online=online,
               last_seen_at=NOW - timedelta(seconds=seen_s) if seen_s is not None else None,
               ip_address=ip, firmware_version=fw, component_state=cs)
    db.add(d)
    return d


def _ask(client, user, q):
    r = client.post("/api/ai/ask", headers=auth_headers(client, user.email), json={"question": q})
    assert r.status_code == 200, r.text
    return r.json()


def _fleet(db, lab):
    _dev(db, lab, "MASTER_LAB01", "Door Controller (Master ESP32)", DeviceType.MASTER_CONTROLLER, ip="192.168.1.151", fw="portal-1.2")
    _dev(db, lab, "ENV_LAB01", "Environment node", DeviceType.SENSOR_NODE, ip="192.168.1.152", fw="env-0.1.1")
    _dev(db, lab, "BIN_NODE_1", "BIN_NODE_1", DeviceType.SENSOR_NODE, ip="192.168.1.153", fw="bin-0.6")
    _dev(db, lab, "REUSE_BIN_1", "REUSE_BIN_1", DeviceType.SENSOR_NODE, seen_s=4000, online=False, fw="reuse-mod-0.5")
    _dev(db, lab, "CAM_LAB01", "Entry Camera (ESP32-CAM)", DeviceType.CAMERA, ip="192.168.1.150")
    _dev(db, lab, "UR5E_01", "UR5e (physical)", DeviceType.ROBOT, seen_s=90000, online=False)
    _dev(db, lab, "UR5E_SIM", "UR5e (simulation)", DeviceType.ROBOT, seen_s=None, online=False, cs={"source": "SIMULATION"})
    _dev(db, lab, "PC_X4", "PC-02", DeviceType.PC, seen_s=200000, online=False, fw="pc-agent-1.0")
    db.commit()


def test_lab_count_lists_every_active_lab(client, db, staff):
    for i in range(3):
        db.add(Lab(code=f"LAB_Z{i}", name=f"Lab {i}", location="Room 1" if i == 0 else None))
    db.add(Lab(code="LAB_OLD", name="Closed lab", is_active=False))
    db.commit()
    out = _ask(client, staff, "How many labs are there?")
    assert out["instant"] and out["tools_used"] == ["instant:lab_count"]
    assert "**3 labs**" in out["answer"] and "1 more inactive" in out["answer"] and "(Room 1)" in out["answer"]


def test_named_device_by_role_words(client, db, staff, lab):
    _fleet(db, lab)
    a = _ask(client, staff, "Is the consumables bin online?")
    assert a["tools_used"] == ["instant:device_status"]
    assert a["answer"].startswith("BIN_NODE_1: **online**") and "bin-0.6" in a["answer"]
    a = _ask(client, staff, "is the master door controller online")["answer"]
    assert "MASTER_LAB01" in a and "**online**" in a and "192.168.1.151" in a
    assert "**offline**" in _ask(client, staff, "Is the reusable bin working?")["answer"]


def test_which_esp32_handles_a_role(client, db, staff, lab):
    _fleet(db, lab)
    a = _ask(client, staff, "Which ESP32 handles environment monitoring?")["answer"]
    assert a.startswith("That is **ENV_LAB01**") and "environment monitoring" in a


def test_last_seen_and_firmware_questions(client, db, staff, lab):
    _fleet(db, lab)
    assert "PC-02 (PC_X4): **offline**" in _ask(client, staff, "When was PC-02 last seen?")["answer"]
    assert "firmware portal-1.2" in _ask(client, staff, "What firmware is the master running?")["answer"]


def test_real_robot_beats_its_simulation(client, db, staff, lab):
    _fleet(db, lab)
    a = _ask(client, staff, "Is the UR5e online?")["answer"]
    assert "UR5E_01" in a and "UR5E_SIM" not in a


def test_ambiguous_bin_asks_which(client, db, staff, lab):
    _fleet(db, lab)
    a = _ask(client, staff, "Is the bin online?")["answer"]
    assert a.startswith("Which one do you mean?") and "BIN_NODE_1" in a and "REUSE_BIN_1" in a


def test_esp32_boards_together(client, db, staff, lab):
    _fleet(db, lab)
    a = _ask(client, staff, "How many ESP32 boards are online?")
    assert a["tools_used"] == ["instant:esp32_status"]
    assert "**ESP32 boards: 4 of 5 online**" in a["answer"]


def test_ai_model_answer_names_the_configured_model(client, db, staff, monkeypatch):
    from app.services import ai
    monkeypatch.setattr(ai, "model_name", lambda student=False: "qwen2.5:1.5b")
    monkeypatch.setattr(agent_live, "_kb_model", lambda: "qwen3:1.7b")
    a = _ask(client, staff, "What model is the AI assistant using?")
    assert a["tools_used"] == ["instant:ai_model"]
    assert "**qwen2.5:1.5b**" in a["answer"] and "**qwen3:1.7b**" in a["answer"]


def test_health_score_answer(client, db, staff, lab):
    a = _ask(client, staff, "What is the Lab Health Score?")
    assert a["tools_used"] == ["instant:health_score"] and "LAB_TEST" in a["answer"] and "/100" in a["answer"]


def test_existing_intents_keep_priority(client, db, staff, lab):
    _fleet(db, lab)
    assert _ask(client, staff, "Is the door open?")["tools_used"] == ["instant:door_status"]
    assert _ask(client, staff, "Which devices are offline right now?")["tools_used"] == ["instant:offline"]


def test_students_get_no_device_details(client, db, alice, lab):
    _fleet(db, lab)
    assert agent_live.answer(db, "Is the consumables bin online?", False, str, lambda *a, **k: a, lambda r: r) is None
    out = agent_live.answer(db, "How many labs are there?", False, str, lambda t, i, l=None: (t, i), lambda r: "\n".join(r))
    assert out[1] == "lab_count"


def test_find_device_matching_rules(db, lab):
    _fleet(db, lab)
    devs = db.query(Device).all()
    assert agent_live.find_device(devs, "is BIN_NODE_1 up")[0].device_uid == "BIN_NODE_1"
    assert agent_live.find_device(devs, "is pc-02 online")[0].device_uid == "PC_X4"
    assert agent_live.find_device(devs, "is the coffee machine online") == (None, [])
    assert agent_live.find_device(devs, "the esp32-cam status")[0].device_uid == "CAM_LAB01"
