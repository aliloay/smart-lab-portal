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
