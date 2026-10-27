"""Whole-lab time slider (2026-10-27): the lab at time T from recorded history only - sessions open at T, the last
reading before T with its age, alerts open at T, each robot's last recorded event (no invented pose)."""
from datetime import datetime, timedelta, timezone

from app.models import AccessSession, Alert, AlertSeverity, Device, DeviceType, RobotEvent, SensorReading
from tests.conftest import auth_headers


def test_the_lab_at_a_past_time(client, db, lab, staff, alice):
    now = datetime.now(timezone.utc)
    t = now - timedelta(hours=2)
    db.add_all([AccessSession(lab_id=lab.id, user_id=alice.id, entry_method="QR", started_at=t - timedelta(minutes=30),
                              ended_at=t + timedelta(minutes=30)),
                AccessSession(lab_id=lab.id, user_id=staff.id, entry_method="QR", started_at=t + timedelta(minutes=5)),
                SensorReading(lab_id=lab.id, metric="temperature", value=24.5, unit="C", recorded_at=t - timedelta(minutes=3)),
                SensorReading(lab_id=lab.id, metric="temperature", value=30.0, unit="C", recorded_at=t + timedelta(minutes=3)),
                Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="open then", created_at=t - timedelta(hours=1),
                      resolved_at=t + timedelta(hours=1), is_resolved=True),
                Alert(lab_id=lab.id, severity=AlertSeverity.INFO, title="later", created_at=t + timedelta(minutes=1))])
    r = Device(device_uid="UR5E_T", name="UR5e", device_type=DeviceType.ROBOT, lab_id=lab.id)
    db.add(r); db.commit()
    db.add(RobotEvent(device_id=r.id, lab_id=lab.id, kind="HOME_LEFT", source="PORTAL", occurred_at=t - timedelta(minutes=10)))
    db.commit()
    h = auth_headers(client, staff.email)
    d = client.get(f"/api/labs/{lab.id}/at", params={"t": t.isoformat()}, headers=h).json()
    assert [p["name"] for p in d["people_inside"]] == ["Alice"]                       # staff came in after T
    env = {e["metric"]: e for e in d["environment"]}
    assert env["temperature"]["value"] == 24.5 and 170 <= env["temperature"]["age_s"] <= 190  # not the later 30.0
    assert [a["title"] for a in d["alerts_open"]] == ["open then"]
    assert d["robots"][0]["last_event"] == "HOME_LEFT" and "not stored" in d["robots"][0]["note"]
    assert client.get(f"/api/labs/{lab.id}/at", params={"t": (now + timedelta(days=1)).isoformat()}, headers=h).status_code == 422
    assert client.get(f"/api/labs/{lab.id}/at", params={"t": t.isoformat()}, headers=auth_headers(client, alice.email)).status_code == 403
