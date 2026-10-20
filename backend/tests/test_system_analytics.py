"""System-wide analytics: real tables only, missing sources reported as unavailable (test DB)."""
from datetime import datetime, timedelta, timezone

from app.models import SensorReading
from app.services import system_analytics
from tests.conftest import auth_headers


def test_empty_sources_are_unavailable_not_zero(db):
    d = system_analytics.system(db, 7)
    assert d["door"]["available"] is False
    assert d["environment"]["available"] is False
    assert d["freshness"]["door"]["state"] == "never"


def test_environment_daily_mean_and_freshness(db, lab):
    now = datetime.now(timezone.utc)
    for v in (20.0, 24.0):
        db.add(SensorReading(lab_id=lab.id, metric="temperature", value=v, unit="C", recorded_at=now - timedelta(seconds=30)))
    db.add(SensorReading(lab_id=lab.id, metric="smoke", value=1.0, unit="", recorded_at=now - timedelta(seconds=30)))
    db.commit()
    d = system_analytics.system(db, 2, now=now)
    today = [s for s in d["environment"]["series"] if s["day"] == now.date().isoformat()][0]
    assert today["temperature_avg"] == 22.0 and today["smoke_pos"] == 1
    assert d["freshness"]["environment"]["state"] == "live"
    stale = system_analytics.system(db, 2, now=now + timedelta(hours=2))
    assert stale["freshness"]["environment"]["state"] == "stale"


def test_endpoint_is_staff_only(client, alice, staff):
    assert client.get("/api/analytics/system", headers=auth_headers(client, alice.email)).status_code == 403
    r = client.get("/api/analytics/system?days=7", headers=auth_headers(client, staff.email))
    assert r.status_code == 200 and "freshness" in r.json()
    assert any(k["id"] == "door_denied" for k in client.get("/api/analytics/kpis", headers=auth_headers(client, staff.email)).json())


def test_agent_answers_system_health_from_records(db, staff):
    from app.services import agent
    assert agent.detect("how is the system health?", True) == "system"
    assert agent.detect("what is the temperature", False) is None          # staff only
    a = agent.quick_answer(db, staff, "give me the system status")
    assert a and "Door access: **never**" in a["answer"] and a["link"]["to"] == "/admin/system"
