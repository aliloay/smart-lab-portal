"""Acknowledging alerts through the assistant (2026-11-11): staff only, a PROPOSAL the page confirms; Confirm = the
Incidents page's own POST /api/incidents/{id}/actions {action: acknowledge}."""
from app.models import Alert, AlertSeverity
from app.services import agent_actions as aa
from tests.conftest import auth_headers


def _alerts(db, lab):
    a = Alert(lab_id=lab.id, severity=AlertSeverity.WARNING, title="Camera 2: no picture", detail="x")
    b = Alert(lab_id=lab.id, severity=AlertSeverity.CRITICAL, title="Smoke detected", detail="x")
    db.add_all([a, b])
    db.commit()
    return a, b


def test_staff_get_open_alerts_most_severe_first_and_nothing_changes(db, staff, lab):
    a, b = _alerts(db, lab)
    p = aa.propose(db, staff, "acknowledge the alerts")
    assert p["intent"] == "ack_alert" and [x["alert_id"] for x in p["actions"]] == [b.id, a.id]
    db.refresh(a)
    assert a.state == "OPEN" and a.acknowledged_at is None                  # proposed only
    one = aa.propose(db, staff, "please acknowledge the camera alert")
    assert [x["alert_id"] for x in one["actions"]] == [a.id]                 # narrowed by the words


def test_students_cannot_and_questions_do_not_trigger_it(db, alice, staff, lab):
    _alerts(db, lab)
    assert "Only lab staff" in aa.propose(db, alice, "acknowledge the alerts")["answer"]
    assert "actions" not in aa.propose(db, alice, "acknowledge the alerts")
    for q in ("which alerts are open?", "how many alerts are there?"):
        r = aa.propose(db, staff, q)
        assert r is None or r.get("intent") != "ack_alert", q


def test_confirming_uses_the_incident_endpoint_once(client, db, staff, alice, lab):
    a, _ = _alerts(db, lab)
    act = aa.propose(db, staff, f"ack alert {a.id}")["actions"][0]
    url = f"/api/incidents/{act['alert_id']}/actions"
    assert client.post(url, headers=auth_headers(client, alice.email), json={"action": "acknowledge"}).status_code == 403
    assert client.post(url, headers=auth_headers(client, staff.email), json={"action": "acknowledge"}).status_code == 200
    assert client.post(url, headers=auth_headers(client, staff.email), json={"action": "acknowledge"}).status_code == 409
    db.refresh(a)
    assert a.state == "ACKNOWLEDGED"
