"""Incidents on alerts (2026-10-17): lifecycle, owners, notes, AI hypothesis label, evidence by time only."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.models import Alert, AlertSeverity, AuditLog, IncidentNote
from tests.conftest import auth_headers


def _alert(db, lab, **kw):
    a = Alert(lab_id=lab.id, severity=kw.pop("severity", AlertSeverity.WARNING), title=kw.pop("title", "Smoke reading"), **kw)
    db.add(a)
    db.commit()
    return a


def test_lifecycle_acknowledge_assign_note_resolve_reopen(client, db, staff, admin, alice, lab):
    a = _alert(db, lab)
    h = auth_headers(client, staff.email)
    act = lambda **b: client.post(f"/api/incidents/{a.id}/actions", headers=h, json=b)
    assert client.get("/api/incidents", headers=auth_headers(client, alice.email)).status_code == 403
    lst = client.get("/api/incidents?state=ACTIVE", headers=h).json()
    assert lst["incidents"][0]["code"] == f"INC-{a.id:06d}" and lst["incidents"][0]["state"] == "OPEN"
    assert act(action="acknowledge").json()["state"] == "ACKNOWLEDGED"
    assert act(action="acknowledge").status_code == 409
    assert act(action="assign", owner_id=alice.id).status_code == 422          # students cannot own incidents
    assert act(action="assign", owner_id=admin.id).json()["owner"] == admin.full_name
    assert act(action="note", text="").status_code == 422
    r = act(action="ai_hypothesis", text="Possibly dust on the smoke sensor").json()
    ai = next(n for n in r["notes"] if n["kind"] == "AI_HYPOTHESIS")
    assert ai["label"].startswith("AI hypothesis")
    assert act(action="resolve", text="ok").status_code == 422                  # needs a real reason
    r = act(action="resolve", text="Sensor cleaned, readings back to 0").json()
    assert r["state"] == "RESOLVED" and r["resolved_by"] == staff.full_name
    assert act(action="reopen", text="came back").json()["state"] == "OPEN"
    assert db.query(IncidentNote).filter_by(alert_id=a.id).count() == 5
    assert db.query(AuditLog).filter(AuditLog.action.like("INCIDENT_%")).count() == 5


def test_auto_resolved_alert_is_resolved_with_a_system_reason(client, db, staff, lab):
    a = _alert(db, lab, is_resolved=True, resolved_at=datetime.now(timezone.utc))
    r = client.get(f"/api/incidents/{a.id}", headers=auth_headers(client, staff.email)).json()
    assert r["state"] == "RESOLVED" and "automatically" in r["resolution"]


def test_unacknowledged_critical_escalates(client, db, staff, lab):
    _alert(db, lab, severity=AlertSeverity.CRITICAL, created_at=datetime.now(timezone.utc) - timedelta(minutes=20))
    r = client.get("/api/incidents", headers=auth_headers(client, staff.email)).json()
    assert r["escalations"] == 1 and r["incidents"][0]["escalate"] is True


def test_related_records_are_by_time_only_and_never_name_a_person_from_timing(client, db, staff, alice, lab):
    now = datetime.now(timezone.utc)
    a = _alert(db, lab, created_at=now)
    db.execute(text("""insert into access_events (event_type, lab_id, user_id, method, result, message, created_at, provenance)
                       values ('ENTRY', :lab, :u, 'RFID', 'GRANTED', 'Access granted', :t, 'SOFTWARE_TEST')"""),
               {"lab": lab.id, "u": alice.id, "t": now - timedelta(minutes=3)})
    db.commit()
    r = client.get(f"/api/incidents/{a.id}", headers=auth_headers(client, staff.email)).json()
    assert "BY TIME ONLY" in r["related_note"]
    door = next(x for x in r["related"] if x["source"] == "door")
    assert door["person"] == alice.full_name                                    # named by the door record itself
    assert alice.full_name not in " ".join(r["facts"])                          # never pinned on the incident
