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


def test_state_filter_is_applied_before_the_row_cap(client, db, staff, lab):
    """2026-11-17: the 500-row cap was applied BEFORE the Python state filter - one older OPEN incident behind 500
    newer resolved ones disappeared from the 'OPEN' view."""
    now = datetime.now(timezone.utc)
    old = _alert(db, lab, title="old open one")
    old.created_at = now - timedelta(days=2)
    for i in range(501):
        a = _alert(db, lab, title=f"newer {i}")
        a.is_resolved = True
        a.resolved_at = now
    db.commit()
    r = client.get("/api/incidents?state=OPEN", headers=auth_headers(client, staff.email)).json()
    assert any(x["title"] == "old open one" for x in r["incidents"])
    assert r["total"] >= 1 and r["truncated"] is False


def test_default_contract_is_unchanged_and_summary_view_is_lean(client, db, staff, lab):
    """2026-11-18: the list is polled every 20 s. view=summary drops the drawer-only fields; the default stays full."""
    _alert(db, lab, detail="long detail text " * 20)
    h = auth_headers(client, staff.email)
    full = client.get("/api/incidents?state=ACTIVE", headers=h).json()
    row = full["incidents"][0]
    for k in ("detail", "resolution", "fingerprint", "acknowledged_by", "owner_id", "source", "title", "state"):
        assert k in row
    assert full["next_cursor"] is None and full["truncated"] is False and full["total"] == 1
    lean = client.get("/api/incidents?state=ACTIVE&view=summary", headers=h).json()
    s = lean["incidents"][0]
    assert "detail" not in s and "resolution" not in s and "fingerprint" not in s
    assert {k: s[k] for k in s} == {k: row[k] for k in s}                     # same values, fewer keys
    assert lean["counts"] == full["counts"] and lean["escalations"] == full["escalations"]


def test_cursor_pages_cover_every_row_once_and_counts_describe_the_whole_view(client, db, staff, lab):
    now = datetime.now(timezone.utc)
    made = []
    for i in range(7):
        a = _alert(db, lab, title=f"page row {i}")
        a.created_at = now - timedelta(minutes=i)
        made.append(a)
    made[3].created_at = made[2].created_at                                  # a tie: id breaks it
    db.commit()
    h = auth_headers(client, staff.email)
    seen, before, pages = [], None, 0
    while True:
        url = "/api/incidents?view=summary&limit=3" + (f"&before={before}" if before else "")
        r = client.get(url, headers=h).json()
        pages += 1
        assert r["total"] == 7 and r["counts"]["OPEN"] == 7                  # whole view on every page
        seen += [x["id"] for x in r["incidents"]]
        before = r["next_cursor"]
        assert r["truncated"] is (before is not None)
        if not before:
            break
    assert pages == 3 and len(seen) == 7 and len(set(seen)) == 7
    assert client.get("/api/incidents?before=not-a-cursor", headers=h).status_code == 422
    assert client.get("/api/incidents?limit=501", headers=h).status_code == 422


def test_sql_state_and_lab_filters_match_the_lifecycle_rules(client, db, staff, lab):
    """state(): resolved <=> is_resolved; an unresolved row whose lifecycle column says RESOLVED reads as OPEN."""
    _alert(db, lab, title="plain open")
    stale = _alert(db, lab, title="stale resolved column")
    db.execute(text("update alerts set state='RESOLVED', is_resolved=false where id=:i"), {"i": stale.id})
    _alert(db, lab, title="really resolved", is_resolved=True, resolved_at=datetime.now(timezone.utc))
    db.commit()
    h = auth_headers(client, staff.email)
    titles = lambda q: sorted(x["title"] for x in client.get(f"/api/incidents{q}", headers=h).json()["incidents"])
    assert titles("?state=OPEN") == ["plain open", "stale resolved column"]
    assert titles("?state=ACTIVE") == ["plain open", "stale resolved column"]
    assert titles("?state=RESOLVED") == ["really resolved"]
    assert len(titles(f"?lab={lab.code}")) == 3 and titles("?lab=NOPE") == []
