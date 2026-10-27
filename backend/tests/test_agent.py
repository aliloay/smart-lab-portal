"""
Smart Lab agent (app.services.agent): instant exact answers, insights with
recommendations, the weekly / monthly management report.

Tested: the questions it recognises (and that students never reach staff
answers); next booking / free labs from the database; answers work with no
AI configured and are audited; repeated alerts, refusals and offline drops
become recommendations; equipment running time; the report endpoint.
"""
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models import (AccessEvent, AccessSession, Alert, AlertSeverity, AuditLog, AuthMethod,
                        Booking, BookingStatus, Device, DeviceType, EquipmentSession, EventType)
from app.services import agent
from tests.conftest import auth_headers


def _booking(db, user, lab, start, hours=2, status=BookingStatus.CONFIRMED):
    b = Booking(user_id=user.id, lab_id=lab.id, start_time=start,
                end_time=start + timedelta(hours=hours), status=status, reason="test")
    db.add(b)
    db.commit()
    return b


def _no_ai(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")


def test_detects_questions_and_keeps_staff_answers_from_students():
    assert agent.detect("What's my next booking?", staff=False) == "next_booking"
    assert agent.detect("which labs are free now", staff=False) == "free_labs"
    assert agent.detect("give me the weekly report", staff=True) == "report_weekly"
    assert agent.detect("monthly usage analysis please", staff=True) == "report_monthly"
    assert agent.detect("which robot was used most?", staff=True) == "equipment"
    assert agent.detect("the same alert keeps happening, what should we fix", staff=True) == "insights"
    assert agent.detect("who is inside the lab", staff=True) == "inside"
    assert agent.detect("give me the weekly report", staff=False) is None
    assert agent.detect("why is the sky blue", staff=True) is None


def test_student_next_booking_is_instant_without_any_ai(client, db, alice, lab, monkeypatch):
    _no_ai(monkeypatch)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    b = _booking(db, alice, lab, start)
    r = client.post("/api/ai/student/ask", headers=auth_headers(client, alice.email),
                    json={"question": "when is my next booking?"})
    assert r.status_code == 200
    out = r.json()
    assert out["instant"] and "LAB_TEST" in out["answer"] and out["link"]["to"] == f"/bookings/{b.id}/qr"
    assert db.query(AuditLog).filter_by(action="AI_INSTANT").count() == 1
    # Not an instant question and no AI: still the readable 503.
    r = client.post("/api/ai/student/ask", headers=auth_headers(client, alice.email),
                    json={"question": "tell me a joke"})
    assert r.status_code == 503


def test_free_labs_leave_out_the_booked_one(db, alice, lab):
    from app.models import Lab
    other = Lab(code="LAB_FREE", name="Free Lab", capacity=4)
    db.add(other)
    db.commit()
    _booking(db, alice, lab, datetime.now(timezone.utc) - timedelta(minutes=30))
    codes = [f["code"] for f in agent.free_labs(db)]
    assert "LAB_FREE" in codes and "LAB_TEST" not in codes


def test_repeated_problems_become_recommendations(db, alice, lab):
    now = datetime.now(timezone.utc)
    for i in range(4):
        db.add(Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="LAB_TEST: door held open",
                     detail="", created_at=now - timedelta(hours=i)))
    for i in range(6):
        db.add(AccessEvent(event_type=EventType.ACCESS_DENIED, lab_id=lab.id, reason="BOOKING_NOT_STARTED",
                           created_at=now - timedelta(hours=i)))
    for i in range(3):
        db.add(AccessEvent(event_type=EventType.ACCESS_DENIED, lab_id=lab.id, user_id=alice.id,
                           reason="BIOMETRIC_FAILED", created_at=now - timedelta(hours=i)))
    db.commit()
    found = agent.insights(db, now - timedelta(days=7), now + timedelta(minutes=1))
    kinds = {i["kind"]: i for i in found}
    assert kinds["ALERT"]["count"] == 4 and "door closer" in kinds["ALERT"]["recommendation"]
    assert kinds["DENIAL"]["reason"] == "BOOKING_NOT_STARTED" and "grace" in kinds["DENIAL"]["recommendation"]
    assert alice.full_name in kinds["PERSON"]["title"] and "Re-enrol" in kinds["PERSON"]["recommendation"]


def test_rare_problems_are_not_flagged(db, lab):
    now = datetime.now(timezone.utc)
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="LAB_TEST: door held open", detail=""))
    db.commit()
    assert agent.insights(db, now - timedelta(days=7), now + timedelta(minutes=1)) == []


def test_equipment_running_time(db, lab):
    now = datetime.now(timezone.utc)
    robot = Device(device_uid="UR5E", name="UR5e", lab_id=lab.id, device_type=DeviceType.ROBOT)
    db.add(robot)
    db.flush()
    db.add(EquipmentSession(device_id=robot.id, lab_id=lab.id, state="RUNNING",
                            started_at=now - timedelta(hours=3), ended_at=now - timedelta(hours=1)))
    db.add(EquipmentSession(device_id=robot.id, lab_id=lab.id, state="FAULT",
                            started_at=now - timedelta(minutes=50), ended_at=now - timedelta(minutes=40)))
    db.commit()
    row = agent.equipment_usage(db, now - timedelta(days=1), now)[0]
    assert row["name"] == "UR5e" and row["running_h"] == 2.0 and row["faults"] == 1


def test_staff_report_and_who_is_inside(client, db, staff, alice, lab, monkeypatch):
    _no_ai(monkeypatch)
    db.add(AccessSession(lab_id=lab.id, user_id=alice.id, entry_method=AuthMethod.QR,
                         started_at=datetime.now(timezone.utc)))
    db.commit()
    h = auth_headers(client, staff.email)
    out = client.post("/api/ai/ask", headers=h, json={"question": "who is inside the labs?"}).json()
    assert out["instant"] and alice.full_name in out["answer"] and "student" in out["answer"]

    out = client.post("/api/ai/ask", headers=h, json={"question": "weekly report"}).json()
    assert out["instant"] and out["link"]["to"] == "/report?period=weekly"

    r = client.get("/api/ai/report?period=monthly", headers=h).json()
    assert r["kind"] == "monthly" and r["span"] == "30 days" and "insights" in r and "equipment" in r
    assert client.get("/api/ai/report", headers=auth_headers(client, alice.email)).status_code == 403


def test_improvement_plan_is_actionable_and_honest_about_evidence(db, lab):
    """Each repeated problem: evidence, likely cause, numbered steps, a check
    that says when it is fixed; the answer says when none of it is proven real use."""
    now = datetime.now(timezone.utc)
    for i in range(3):
        db.add(Alert(lab_id=lab.id, severity=AlertSeverity.CRITICAL, title="Flame indication at LAB_TEST",
                     detail="", created_at=now - timedelta(days=10, hours=i)))
    for i in range(4):
        db.add(Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="LAB_TEST: door held open",
                     detail="", created_at=now - timedelta(hours=i)))
    db.commit()
    found = agent.insights(db, now - timedelta(days=30), now + timedelta(minutes=1))
    assert [i["title"] for i in found][0] == "LAB_TEST: door held open"     # still happening first
    flame = next(i for i in found if "Flame" in i["title"])
    assert not flame["ongoing"] and flame["cause"] and len(flame["steps"]) >= 2 and flame["done_when"]
    text = agent.plan_text(found, 30)
    assert "not seen since" in text and "still happening" in text
    assert "Likely cause:" in text and "Done when:" in text and "1. " in text
    assert "Evidence quality" in text                     # the suite's rows are SOFTWARE_TEST
    assert "**Next single action:** Open the door fully" in text



def test_status_questions_are_answered_from_the_records_not_the_model(client, db, staff, lab, monkeypatch):
    """2026-10-18: 'which robots are online?' went to the language model with the whole snapshot - 48 s on
    the CPU while the camera analysis dropped to 1.7/s. Now an exact answer from the device records."""
    _no_ai(monkeypatch)
    assert agent.detect("Which robots are online?", staff=True) == "robots_status"
    assert agent.detect("are the cameras working?", staff=True) == "cameras_status"
    assert agent.detect("which PCs are online", staff=True) == "pcs_status"
    assert agent.detect("Are there open security alerts?", staff=True) == "alerts_open"
    assert agent.detect("which robot was used most?", staff=True) == "equipment"     # usage stays usage
    assert agent.detect("Which robots are online?", staff=False) is None              # staff only
    now = datetime.now(timezone.utc)
    db.add(Device(device_uid="UR5E_X", name="UR5e", device_type=DeviceType.ROBOT, lab_id=lab.id,
                  last_seen_at=now, component_state={"q": [0.0] * 6}))
    db.add(Device(device_uid="FANUC_SIM_X", name="FANUC sim", device_type=DeviceType.ROBOT, lab_id=lab.id,
                  last_seen_at=now - timedelta(days=3), component_state={"source": "SIMULATION"}))
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.CRITICAL, title="Camera offline", detail=""))
    db.commit()
    h = auth_headers(client, staff.email)
    r = client.post("/api/ai/ask", headers=h, json={"question": "Which robots are online?"}).json()
    assert r["instant"] and r["tools_used"] == ["instant:robots_status"]
    assert "UR5E_X): **online**" in r["answer"] and "FANUC_SIM_X): **offline**" in r["answer"]
    assert "SIMULATION" in r["answer"] and "DRY_RUN" in r["answer"]
    r = client.post("/api/ai/ask", headers=h, json={"question": "any alerts right now?"}).json()
    assert r["tools_used"] == ["instant:alerts_open"] and "1 open alert" in r["answer"] and "Camera offline" in r["answer"]


def test_status_answers_match_the_device_pages_and_environment_and_stock_are_instant(client, db, staff, lab):
    # 2026-10-18 live findings: a robot whose collector runs without the robot was called "online"; a
    # temperature question got the data-source overview; "how many resistors" went to the model (213 s).
    from app.models import InventoryBin, SensorReading
    now = datetime.now(timezone.utc)
    db.add(Device(device_uid="UR5E_Y", name="UR5e (physical)", device_type=DeviceType.ROBOT, lab_id=lab.id,
                  last_seen_at=now, is_online=True, component_state={"state": "IDLE"}))
    db.add(Device(device_uid="ENV_Y", name="Environment node", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                  last_seen_at=now, is_online=True))
    db.add(SensorReading(lab_id=lab.id, metric="temperature", value=26.6, unit="C", recorded_at=now))
    db.add(SensorReading(lab_id=lab.id, metric="smoke", value=0.0, unit="", recorded_at=now))
    db.add(InventoryBin(code="BIN-T", lab_id=lab.id, item_name="10 kOhm resistors", tare_g=100.0,
                        unit_mass_g=0.2, last_mass_g=106.0, last_measured_at=now))
    db.commit()
    h = auth_headers(client, staff.email)
    ask = lambda q: client.post("/api/ai/ask", headers=h, json={"question": q}).json()
    r = ask("Which robots are online?")
    assert "UR5E_Y): **partly working**" in r["answer"] and "not connected" in r["answer"]
    r = ask("What is the temperature in the lab?")
    assert r["tools_used"] == ["instant:environment_now"] and "26.6" in r["answer"] and "Smoke / gas: **none**" in r["answer"]
    r = ask("How many resistors are in the bin?")
    assert r["tools_used"] == ["instant:bins_stock"] and "**30** pieces" in r["answer"]


def test_lab_ready_questions_get_the_instant_free_labs_answer():
    # 2026-10-19: "what lab is ready now" missed the free-labs pattern and waited 212 s for the model.
    for q in ("what lab is ready now", "which lab is free?", "which lab can I use now", "is any lab available"):
        assert agent.detect(q, staff=True) == "free_labs", q
        assert agent.detect(q, staff=False) == "free_labs", q


def test_live_state_questions_do_not_go_to_the_documents_lookup():
    # 2026-10-19: "...which one needs attention first and why" matched "why" and got an unrelated document quote.
    from app.api.routes.ai import _LIVE_Q, _PROJECT_Q
    live = "Compare the robotics lab and the PLC lab and tell me which one needs attention first and why"
    assert _PROJECT_Q.search(live) and _LIVE_Q.search(live)
    doc = "why do we use a relay for the door lock?"
    assert _PROJECT_Q.search(doc) and not _LIVE_Q.search(doc)


def test_new_instant_categories_2026_10_27():
    """Owner 2026-10-27: comparisons, daily summary, low stock, recent activity, today's bookings and 'who is where'
    are answered from the records with no model; a lab-vs-lab comparison is NOT a period comparison."""
    d = lambda q: agent.detect(q, staff=True)
    assert d("Compare door entries granted this week with the week before.") == "compare"
    assert d("how does this month compare to last month") == "compare"
    assert d("Compare the robotics lab and the PLC lab and tell me which one needs attention first") != "compare"
    assert d("give me today's summary") == "report_daily" and d("what happened today") == "report_daily"
    assert d("what is running low?") == "low_stock" and d("which parts should we reorder") == "low_stock"
    assert d("show the recent activity") == "recent_activity" and d("what just happened") == "recent_activity"
    assert d("bookings today") == "bookings_today" and d("who booked") == "bookings_today"
    assert d("which lab is empty") == "empty_labs" and d("who is where") == "empty_labs"
    assert d("which lab is free?") == "free_labs"                       # free = bookings, unchanged
    for q in ("what is running low?", "who is where", "what happened today"):
        assert agent.detect(q, staff=False) is None, q                   # staff only


def test_new_instant_answers_come_from_the_records(client, db, staff, alice, lab):
    from app.models import InventoryBin
    now = datetime.now(timezone.utc)
    db.add(AccessSession(user_id=alice.id, lab_id=lab.id, started_at=now - timedelta(minutes=20),
                         entry_method=AuthMethod.RFID))
    db.add(AccessEvent(event_type=EventType.ACCESS_GRANTED, lab_id=lab.id, user_id=alice.id, created_at=now - timedelta(minutes=20)))
    db.add(InventoryBin(code="BIN-LOW", lab_id=lab.id, item_name="LEDs", tare_g=100.0, unit_mass_g=1.0,
                        last_mass_g=103.0, last_measured_at=now, reorder_qty=10))
    db.commit()
    _booking(db, alice, lab, now + timedelta(minutes=5))
    h = auth_headers(client, staff.email)
    ask = lambda q: client.post("/api/ai/ask", headers=h, json={"question": q}).json()
    r = ask("who is where")
    assert r["tools_used"] == ["instant:empty_labs"] and alice.full_name in r["answer"]
    r = ask("what is running low?")
    assert r["tools_used"] == ["instant:low_stock"] and "LEDs (BIN-LOW): 3 pieces" in r["answer"]
    r = ask("show the recent activity")
    assert r["tools_used"] == ["instant:recent_activity"] and "access granted" in r["answer"]
    r = ask("compare this week with last week")
    assert r["tools_used"] == ["instant:compare"] and "Door entries: **1**" in r["answer"]
    r = ask("give me today's summary")
    assert r["tools_used"] == ["instant:report_daily"] and "Door entries: **1**" in r["answer"]


def test_how_to_improve_a_device_is_instant_from_its_records(client, db, staff, lab):
    """2026-10-27: 'how to make ur5e better' waited for the language model; now that device's own records answer."""
    now = datetime.now(timezone.utc)
    d = Device(device_uid="UR5E_ADV", name="UR5e", device_type=DeviceType.ROBOT, lab_id=lab.id, last_seen_at=now,
               is_online=True, component_state={"q": [0.0] * 6})
    db.add(d); db.commit()
    for _ in range(3):
        db.add(Alert(lab_id=lab.id, device_id=d.id, severity=AlertSeverity.WARNING, title="Robot telemetry stale"))
    db.commit()
    assert agent.detect("how to make ur5e better", staff=True) == "device_advice"
    assert agent.detect("what is wrong with PC-05", staff=True) == "device_advice"
    assert agent.detect("which robot was used most?", staff=True) == "equipment"
    r = client.post("/api/ai/ask", headers=auth_headers(client, staff.email), json={"question": "how to make ur5e better"}).json()
    assert r["instant"] and r["tools_used"] == ["instant:device_advice"]
    assert "UR5E_ADV" in r["answer"] and "Alerts (30 days): 3" in r["answer"] and "What its records suggest" in r["answer"]
