"""Operations Center, lab twin and "my usage" aggregates: real rows only."""
from datetime import timedelta

from app.models import (AccessSession, AuthMethod, Booking, BookingStatus,
                        SensorReading, SessionEndReason)
from tests.conftest import auth_headers


def test_operations_empty_is_empty(client, db, staff, lab):
    h = auth_headers(client, staff.email)
    r = client.get("/api/analytics/operations?days=7", headers=h).json()
    assert r["utilisation"] == []
    assert all(v == 0 for row in r["booked_heatmap"] for v in row)
    assert r["sessions"]["median_minutes"] is None
    assert r["environment"]["has_data"] is False
    assert r["environment"]["message"] == "Awaiting sensor data"
    # Configuration surfaces as booleans, never as secrets.
    assert set(r["automation"]) >= {"api_enabled", "push_enabled", "outbox"}
    assert "AUTOMATION_API_KEY" not in str(r)


def test_operations_is_staff_only(client, alice):
    h = auth_headers(client, alice.email)
    assert client.get("/api/analytics/operations", headers=h).status_code == 403


def test_utilisation_and_durations(client, db, staff, alice, lab, now):
    start = now - timedelta(hours=3)
    b = Booking(user_id=alice.id, lab_id=lab.id, start_time=start,
                end_time=start + timedelta(hours=2),
                status=BookingStatus.CONFIRMED, first_entry_at=start)
    db.add(b)
    db.flush()
    db.add(AccessSession(lab_id=lab.id, user_id=alice.id, booking_id=b.id,
                         entry_method=AuthMethod.QR, started_at=start,
                         ended_at=start + timedelta(minutes=45),
                         end_reason=SessionEndReason.EXIT_RECORDED))
    db.add(AccessSession(lab_id=lab.id, user_id=alice.id, booking_id=b.id,
                         entry_method=AuthMethod.QR, started_at=start,
                         ended_at=start + timedelta(hours=2),
                         end_reason=SessionEndReason.BOOKING_ENDED))
    db.commit()
    h = auth_headers(client, staff.email)
    r = client.get("/api/analytics/operations?days=7", headers=h).json()
    u = r["utilisation"][0]
    assert u["booked_hours"] == 2.0 and u["available_hours"] == 70
    assert sum(sum(row) for row in r["booked_heatmap"]) == 2.0
    # Only the observed exit yields a duration; the other is not guessed.
    assert r["sessions"]["exit_recorded"] == 1
    assert r["sessions"]["median_minutes"] == 45


def test_lab_twin_and_environment(client, db, alice, lab):
    db.add(SensorReading(lab_id=lab.id, metric="temperature", value=23.1,
                         unit="C"))
    db.commit()
    h = auth_headers(client, alice.email)
    r = client.get(f"/api/analytics/labs/{lab.id}", headers=h).json()
    assert r["has_bookings"] is False
    assert len(r["days_strip"]) == 21
    env = r["environment"]
    assert env["has_data"] and env["series"][0]["latest"] == 23.1


def test_my_stats_are_mine_only(client, db, alice, bob, lab, now):
    for user, entered in ((alice, True), (bob, False)):
        db.add(Booking(user_id=user.id, lab_id=lab.id,
                       start_time=now - timedelta(days=1),
                       end_time=now - timedelta(days=1) + timedelta(hours=1),
                       status=BookingStatus.CONFIRMED,
                       first_entry_at=now - timedelta(days=1) if entered else None))
    db.commit()
    r = client.get("/api/analytics/me", headers=auth_headers(client, alice.email)).json()
    assert r["sessions_finished"] == 1 and r["attendance_rate"] == 1.0
    r = client.get("/api/analytics/me", headers=auth_headers(client, bob.email)).json()
    assert r["attendance_rate"] == 0.0
