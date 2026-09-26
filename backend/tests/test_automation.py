"""
Automation (n8n) integration: the outbox, the dispatcher, and the API n8n
calls. What must hold:

  - the portal works exactly as before when automation is not configured;
  - an outbox row exists only if the change it describes committed;
  - a failing or absent n8n never affects the request that caused the event;
  - retried automation calls create a notification or alert exactly once;
  - rules (bursts, escalation, readiness) are decided here, not in n8n.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.models import (AccessEvent, Alert, Booking, BookingStatus, Device,
                        DeviceType, EventType, IntegrationEvent, Issue,
                        IssueCategory, IssueSeverity, IssueStatus, Notification,
                        SensorReading)
from app.services import integration

KEY = {"X-Automation-Key": "test-automation-key"}


@pytest.fixture(autouse=True)
def _automation(monkeypatch):
    monkeypatch.setattr(settings, "AUTOMATION_API_KEY", "test-automation-key")
    monkeypatch.setattr(settings, "AUTOMATION_WEBHOOK_BASE", "")


def _booking(db, user, lab, start, hours=1, status=BookingStatus.CONFIRMED):
    b = Booking(user_id=user.id, lab_id=lab.id, start_time=start,
                end_time=start + timedelta(hours=hours), status=status)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def _deny(client, device_headers, lab, reason="BOOKING_NOT_STARTED"):
    return client.post("/api/access/deny", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": "MASTER_LAB01",
        "event_type": "ACCESS_DENIED", "reason": reason, "message": "x"})


# ------------------------------------------------------------------ auth ---
def test_disabled_without_key(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTOMATION_API_KEY", "")
    assert client.get("/api/automation/health", headers=KEY).status_code == 503


def test_rejects_wrong_or_missing_key(client):
    assert client.get("/api/automation/health").status_code == 401
    assert client.get("/api/automation/health",
                      headers={"X-Automation-Key": "nope"}).status_code == 401
    assert client.get("/api/automation/health", headers=KEY).status_code == 200


def test_user_jwt_is_not_an_automation_key(client, alice):
    from tests.conftest import auth_headers
    h = auth_headers(client, alice.email)
    assert client.get("/api/automation/events", headers=h).status_code == 401


# ---------------------------------------------------------------- outbox ---
def test_event_is_recorded_with_the_change(client, db, lab, device_headers):
    _deny(client, device_headers, lab)
    db.expire_all()
    row = db.query(IntegrationEvent).filter_by(event_type="access.denied").one()
    assert row.lab_id == lab.id
    assert len(row.event_id) == 36
    # Not configured to push: recorded for the pull feed, never sent.
    assert row.delivery_status == "SKIPPED"

    feed = client.get("/api/automation/events", headers=KEY).json()
    assert feed["events"][0]["type"] == "access.denied"
    assert feed["events"][0]["event_id"] == row.event_id
    again = client.get(f"/api/automation/events?after={feed['next_after']}",
                       headers=KEY).json()
    assert again["events"] == []


def test_rolled_back_change_leaves_no_event(db, lab):
    from app.services.events import log_event
    log_event(db, EventType.ACCESS_DENIED, lab_id=lab.id)
    db.rollback()
    assert db.query(IntegrationEvent).count() == 0


def test_scan_noise_is_not_an_integration_event(db, lab):
    from app.services.events import log_event
    log_event(db, EventType.QR_SCAN, lab_id=lab.id)
    db.commit()
    assert db.query(IntegrationEvent).count() == 0
    assert db.query(AccessEvent).count() == 1     # the audit log still has it


def test_dispatcher_delivers_retries_and_gives_up(db, lab, monkeypatch):
    monkeypatch.setattr(settings, "AUTOMATION_WEBHOOK_BASE", "http://n8n/webhook")
    monkeypatch.setattr(settings, "AUTOMATION_MAX_ATTEMPTS", 2)
    row = integration.emit(db, "access.denied", lab_id=lab.id)
    db.commit()
    assert row.delivery_status == "PENDING"
    assert integration.webhook_url("access.denied") == \
        "http://n8n/webhook/smartlab-access-denied"

    def down(_):
        raise ConnectionError("n8n unreachable")
    assert integration.deliver_due(db, sender=down) == 0
    db.refresh(row)
    assert row.delivery_status == "PENDING" and row.attempts == 1
    assert "unreachable" in row.last_error

    row.next_attempt_at = datetime.now(timezone.utc)
    db.commit()
    integration.deliver_due(db, sender=down)
    db.refresh(row)
    assert row.delivery_status == "FAILED"          # gave up, nothing else hurt

    assert integration.requeue_failed(db) == 1
    sent = []
    assert integration.deliver_due(db, sender=sent.append) == 1
    db.refresh(row)
    assert row.delivery_status == "DELIVERED" and sent[0].event_id == row.event_id


def test_n8n_down_does_not_affect_the_door_path(client, db, lab, device_headers,
                                                monkeypatch):
    # Configured to push to an address nothing listens on: the device call
    # still succeeds at once, because pushing happens later, elsewhere.
    monkeypatch.setattr(settings, "AUTOMATION_WEBHOOK_BASE", "http://127.0.0.1:9")
    assert _deny(client, device_headers, lab).status_code == 200
    db.expire_all()
    assert db.query(IntegrationEvent).one().delivery_status == "PENDING"


def test_issue_and_session_events(client, db, alice, lab, now):
    from app.services.issues import create_issue
    create_issue(db, alice, lab_id=lab.id, asset_id=None, device_id=None,
                 access_event_id=None, category=IssueCategory.MALFUNCTION,
                 severity=IssueSeverity.HIGH, title="Scope dead",
                 description="No signal on channel 1")
    ev = db.query(IntegrationEvent).filter_by(event_type="issue.created").one()
    assert ev.payload["severity"] == "HIGH"
    assert ev.correlation_id.startswith("issue:")


# --------------------------------------------------------------- idempotent --
def test_notify_is_idempotent(client, db, staff, admin):
    body = {"audience": "staff", "kind": "DAILY_REPORT", "title": "Daily",
            "body": "x", "dedupe_key": "daily-report:2026-09-26",
            "link": "/admin/operations"}
    r1 = client.post("/api/automation/notify", headers=KEY, json=body).json()
    r2 = client.post("/api/automation/notify", headers=KEY, json=body).json()
    assert r1["created"] == 2 and r2["created"] == 0 and r2["duplicate"]
    assert db.query(Notification).filter_by(kind="DAILY_REPORT").count() == 2


def test_notify_rejects_portal_kinds_and_external_links(client, staff):
    base = {"audience": "staff", "title": "t", "dedupe_key": "k-1"}
    assert client.post("/api/automation/notify", headers=KEY, json={
        **base, "kind": "BOOKING_CONFIRMED"}).status_code == 422
    assert client.post("/api/automation/notify", headers=KEY, json={
        **base, "kind": "ANOMALY", "link": "https://evil.example"}).status_code == 422


def test_alert_is_idempotent(client, db, lab):
    body = {"severity": "WARNING", "title": "Denial burst", "lab_id": lab.id,
            "dedupe_key": "denial-burst:1:42"}
    a = client.post("/api/automation/alerts", headers=KEY, json=body).json()
    b = client.post("/api/automation/alerts", headers=KEY, json=body).json()
    assert a["created"] and not b["created"] and a["alert_id"] == b["alert_id"]
    assert db.query(Alert).count() == 1


def test_reminder_shared_with_lazy_path(client, db, alice, lab, now):
    b = _booking(db, alice, lab, now + timedelta(minutes=10))
    assert client.post(f"/api/automation/bookings/{b.id}/remind",
                       headers=KEY).json()["created"] is True
    # The portal's own lazy reminder (on reading notifications) sees it.
    from app.services.notifications import ensure_booking_reminders
    assert ensure_booking_reminders(db, alice) == 0
    assert client.post(f"/api/automation/bookings/{b.id}/remind",
                       headers=KEY).json()["created"] is False
    assert db.query(Notification).filter_by(kind="BOOKING_REMINDER").count() == 1


def test_reminder_not_sent_for_cancelled_booking(client, db, alice, lab, now):
    b = _booking(db, alice, lab, now + timedelta(minutes=10),
                 status=BookingStatus.CANCELLED)
    r = client.post(f"/api/automation/bookings/{b.id}/remind", headers=KEY).json()
    assert r["created"] is False


# ------------------------------------------------------------------- rules --
def test_denial_burst_levels(client, db, lab, device_headers):
    url = f"/api/automation/access/denials?lab_id={lab.id}"
    assert client.get(url, headers=KEY).json()["level"] == "none"
    _deny(client, device_headers, lab)
    one = client.get(url, headers=KEY).json()
    assert one["level"] == "normal" and one["dedupe_key"] is None
    _deny(client, device_headers, lab)
    _deny(client, device_headers, lab, "TOKEN_UNKNOWN")
    burst = client.get(url, headers=KEY).json()
    assert burst["level"] == "warning" and burst["count"] == 3
    assert burst["by_reason"]["BOOKING_NOT_STARTED"] == 2
    assert burst["dedupe_key"].startswith(f"denial-burst:{lab.id}:")


def test_device_escalation_levels(client, db, lab, staff):
    now = datetime.now(timezone.utc)
    for uid, minutes in (("D1", 5), ("D2", 20), ("D3", 90)):
        db.add(Device(device_uid=uid, name=uid, lab_id=lab.id, is_online=True,
                      device_type=DeviceType.MASTER_CONTROLLER,
                      last_seen_at=now - timedelta(minutes=minutes)))
    db.add(Device(device_uid="NEW", name="NEW", lab_id=lab.id,
                  device_type=DeviceType.CAMERA))
    db.commit()
    r = client.get("/api/automation/devices/offline", headers=KEY).json()
    levels = {d["name"]: d["level"] for d in r["offline"]}
    assert levels == {"D1": 1, "D2": 2, "D3": 3}
    assert [d["name"] for d in r["never_reported"]] == ["NEW"]
    assert {d["name"]: d["audience"] for d in r["offline"]}["D3"] == "admins"
    # Reading it also recorded the outages, as the portal would.
    db.expire_all()
    assert db.query(AccessEvent).filter_by(
        event_type=EventType.DEVICE_OFFLINE).count() == 3


def test_readiness_warns_but_never_cancels(client, db, alice, lab, now):
    lab.has_controller = True
    db.add(Issue(reporter_id=alice.id, lab_id=lab.id, title="Fume hood",
                 description="x", category=IssueCategory.SAFETY,
                 severity=IssueSeverity.CRITICAL, status=IssueStatus.OPEN,
                 ticket_number="ISS-1"))
    db.commit()
    b = _booking(db, alice, lab, now + timedelta(minutes=20))
    r = client.get("/api/automation/bookings/upcoming?within_minutes=30",
                   headers=KEY).json()["bookings"][0]
    assert r["readiness"]["level"] == "warning"
    assert r["readiness"]["controller"] == "NOT_REPORTED"
    assert any("Critical issue" in w for w in r["readiness"]["warnings"])
    db.refresh(b)
    assert b.status == BookingStatus.CONFIRMED


def test_sensor_evaluation_is_honest_about_no_data(client, db, lab):
    r = client.get("/api/automation/sensors/evaluate", headers=KEY).json()
    assert r["no_data"] is True and r["breaches"] == []
    db.add(SensorReading(lab_id=lab.id, metric="temperature", value=34.5,
                         unit="C"))
    db.commit()
    r = client.get("/api/automation/sensors/evaluate", headers=KEY).json()
    assert r["breaches"][0]["status"] == "high"


def test_telemetry_ingest(client, db, lab, device_headers):
    r = client.post("/api/access/telemetry", headers=device_headers, json={
        "device_uid": "SENSOR1", "lab_id": lab.code,
        "readings": [{"metric": "temperature", "value": 22.5, "unit": "C"},
                     {"metric": "humidity", "value": 41, "unit": "%"}]})
    assert r.status_code == 200 and r.json()["count"] == 2
    assert client.post("/api/access/telemetry", json={
        "device_uid": "S", "lab_id": lab.code,
        "readings": [{"metric": "t", "value": 1}]}).status_code == 401
    bad = client.post("/api/access/telemetry", headers=device_headers, json={
        "device_uid": "S", "lab_id": lab.code,
        "readings": [{"metric": "Temp; DROP", "value": 1}]})
    assert bad.status_code == 422


def test_reports_count_only_what_happened(client, db, alice, lab, device_headers):
    empty = client.get("/api/automation/reports/daily", headers=KEY).json()
    assert empty["bookings"]["attendance_rate"] is None
    assert "Bookings: none in this period." in empty["lines"]
    _deny(client, device_headers, lab)
    r = client.get("/api/automation/reports/daily", headers=KEY).json()
    assert r["access"]["denied"] == 1
    w = client.get("/api/automation/reports/weekly", headers=KEY).json()
    assert w["kind"] == "weekly" and "previous" in w


def test_post_session_attended_and_missed(client, db, alice, bob, lab, now):
    went = _booking(db, alice, lab, now - timedelta(minutes=70))
    went.first_entry_at = now - timedelta(minutes=65)
    went.entry_count = 1
    _booking(db, bob, lab, now - timedelta(minutes=80))
    db.commit()
    rows = client.get("/api/automation/bookings/ended?minutes=60",
                      headers=KEY).json()["bookings"]
    by_user = {r["user_id"]: r for r in rows}
    assert by_user[alice.id]["attended"] and "exit not recorded" in \
        by_user[alice.id]["body"]
    assert not by_user[bob.id]["attended"]
    assert by_user[bob.id]["title"].startswith("Missed booking")


def test_data_quality_reads_only(client, db, alice, lab, now):
    b = _booking(db, alice, lab, now - timedelta(hours=2),
                 status=BookingStatus.CANCELLED)
    b.first_entry_at = now - timedelta(hours=2)
    db.commit()
    r = client.get("/api/automation/data-quality", headers=KEY).json()
    check = {c["id"]: c for c in r["checks"]}["entry_on_cancelled_booking"]
    assert check["count"] == 1 and check["sample_ids"] == [b.id]
    db.refresh(b)
    assert b.status == BookingStatus.CANCELLED       # untouched


def test_anomaly_rules(client, db, lab, device_headers):
    for _ in range(3):
        _deny(client, device_headers, lab, "TOKEN_UNKNOWN")
    r = client.get("/api/automation/anomalies?hours=1", headers=KEY).json()
    rules = {a["rule"] for a in r["anomalies"]}
    assert "denial_burst" in rules


def test_run_is_recorded(client, db):
    assert client.post("/api/automation/runs", headers=KEY, json={
        "workflow": "daily-report", "status": "success",
        "summary": "sent"}).json()["recorded"]


def test_component_fault_is_not_a_door_alarm(client, db, lab, device_headers):
    client.post("/api/access/heartbeat", headers=device_headers, json={
        "device_uid": "MASTER_LAB01", "lab_id": lab.code, "door_closed": True,
        "components": {"rfid": False, "fingerprint": True, "camera": True}})
    types = {r.event_type for r in db.query(IntegrationEvent).all()}
    assert "device.component_fault" in types and "door.alarm" not in types
