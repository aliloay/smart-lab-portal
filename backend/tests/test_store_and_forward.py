"""
Store and forward (portal-1.2, 2026-11-21): door events the master could not deliver while the portal was unreachable
arrive later with age_ms. They are logged at the real time, marked replayed, and do not open a live occupancy session
or send a stale "access denied" to the person.
"""
from datetime import datetime, timedelta, timezone

from app.models import AccessEvent, AccessSession, EventType, Notification


def _grant(client, headers, lab, subject, age_ms=None):
    body = {"lab_id": lab.code, "device_uid": "MASTER_LAB01", "event_type": "ACCESS_GRANTED",
            "auth_subject": subject, "method": "FINGERPRINT"}
    if age_ms is not None:
        body["age_ms"] = age_ms
    return client.post("/api/access/grant", headers=headers, json=body)


def test_replayed_grant_is_logged_at_the_real_time(client, db, lab, alice, device_headers):
    r = _grant(client, device_headers, lab, alice.auth_subject, age_ms=20 * 60 * 1000)   # 20 min ago
    assert r.status_code == 200, r.text
    ev = db.query(AccessEvent).filter_by(event_type=EventType.ACCESS_GRANTED).one()
    at = ev.created_at if ev.created_at.tzinfo else ev.created_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - at
    assert timedelta(minutes=19) < age < timedelta(minutes=21)
    assert ev.event_metadata["replayed"] is True and ev.event_metadata["delay_s"] == 1200
    # history only: no live "inside the lab" session from a 20-minute-old entry
    assert db.query(AccessSession).count() == 0


def test_live_grant_still_opens_a_session(client, db, lab, alice, device_headers):
    assert _grant(client, device_headers, lab, alice.auth_subject, age_ms=800).status_code == 200
    ev = db.query(AccessEvent).filter_by(event_type=EventType.ACCESS_GRANTED).one()
    assert not (ev.event_metadata or {}).get("replayed")
    assert db.query(AccessSession).count() == 1


def test_replayed_denial_sends_no_stale_notification(client, db, lab, alice, device_headers):
    r = client.post("/api/access/deny", headers=device_headers, json={
        "lab_id": lab.code, "device_uid": "MASTER_LAB01", "event_type": "ACCESS_DENIED",
        "auth_subject": alice.auth_subject, "reason": "WRONG_FINGER", "age_ms": 15 * 60 * 1000})
    assert r.status_code == 200, r.text
    assert db.query(AccessEvent).filter_by(event_type=EventType.ACCESS_DENIED).count() == 1
    assert db.query(Notification).filter_by(user_id=alice.id, kind="ACCESS_DENIED").count() == 0


def test_old_firmware_without_age_is_unchanged(client, db, lab, alice, device_headers):
    assert _grant(client, device_headers, lab, alice.auth_subject).status_code == 200
    assert db.query(AccessSession).count() == 1
