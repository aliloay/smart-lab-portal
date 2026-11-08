"""Alert grouping (2026-10-18): one incident per continuing condition, occurrences counted, reopen when
the condition returns, distinct conditions kept apart, safety notifications on every occurrence,
lifecycle MITIGATED, escalation on repeats, quality analytics, and the security-event regression
(a resolved camera alert no longer makes the next event fail)."""
import json
from datetime import datetime, timedelta, timezone

from app.models import Alert, AlertSeverity, AuditLog, Device, IncidentNote, Notification
from app.services import alert_grouping as ag
from tests.conftest import auth_headers

T0 = (datetime.now(timezone.utc) - timedelta(hours=6)).replace(microsecond=0)


def _raise(db, lab, title="Camera offline", device_id=None, minutes=0, sev=AlertSeverity.WARNING, **kw):
    a, outcome = ag.raise_or_group(db, lab_id=lab.id, device_id=device_id, severity=sev, title=title,
                                   detail="d", now=T0 + timedelta(minutes=minutes), **kw)
    db.commit()
    return a, outcome


def test_same_condition_is_one_incident_with_occurrences(db, lab):
    a1, o1 = _raise(db, lab)
    a2, o2 = _raise(db, lab, minutes=1)
    a3, o3 = _raise(db, lab, minutes=2)
    assert (o1, o2, o3) == ("created", "grouped", "grouped") and a1.id == a2.id == a3.id
    db.refresh(a1)
    assert a1.occurrences == 3 and a1.last_seen_at.replace(tzinfo=timezone.utc) == T0 + timedelta(minutes=2)
    assert db.query(Alert).count() == 1


def test_distinct_conditions_stay_distinct(db, lab):
    a, _ = _raise(db, lab, title="Camera offline")
    b, _ = _raise(db, lab, title="Smoke detected")
    c, _ = _raise(db, lab, title="Camera offline", device_id=None, fp="other-device")
    assert len({a.id, b.id, c.id}) == 3


def test_condition_returning_soon_reopens_later_starts_a_new_incident(db, lab):
    a, _ = _raise(db, lab)
    a.is_resolved, a.state, a.resolved_at, a.resolution = True, "RESOLVED", T0 + timedelta(minutes=5), "cable fixed"
    db.commit()
    b, o = _raise(db, lab, minutes=20)                               # 15 min after resolution
    assert o == "reopened" and b.id == a.id and b.reopened_count == 1 and not b.is_resolved and b.occurrences == 2
    note = db.query(IncidentNote).filter_by(alert_id=a.id).one()
    assert "cable fixed" in note.text                                 # the previous resolution is kept
    b.is_resolved, b.state, b.resolved_at = True, "RESOLVED", T0 + timedelta(minutes=25)
    db.commit()
    c, o = _raise(db, lab, minutes=90)                               # 65 min later: a new incident
    assert o == "created" and c.id != a.id


def test_same_report_delivered_twice_is_counted_once(db, lab):
    _raise(db, lab, dedupe_s=5)
    a, o = _raise(db, lab, dedupe_s=5)                               # same moment (concurrent refresh)
    assert o == "duplicate" and a.occurrences == 1


def test_a_more_severe_occurrence_raises_the_incident(db, lab):
    a, _ = _raise(db, lab, sev=AlertSeverity.WARNING)
    b, _ = _raise(db, lab, minutes=1, sev=AlertSeverity.CRITICAL)
    assert b.id == a.id and b.severity == AlertSeverity.CRITICAL
    assert "raised from WARNING to CRITICAL" in db.query(IncidentNote).filter_by(alert_id=a.id).one().text


def test_forced_entry_is_grouped_but_notified_every_time(db, lab, staff):
    from app.services.devices import record_door_alarm
    record_door_alarm(db, lab, None, "FORCED_ENTRY", "door opened without a grant")
    db.commit()
    record_door_alarm(db, lab, None, "FORCED_ENTRY", "door opened without a grant")
    db.commit()
    alerts = db.query(Alert).filter(Alert.fingerprint == f"door:{lab.id}:FORCED_ENTRY").all()
    assert len(alerts) == 1 and alerts[0].occurrences == 2 and alerts[0].severity == AlertSeverity.CRITICAL
    assert db.query(Notification).filter_by(user_id=staff.id, kind="SECURITY_EVENT").count() == 2


def test_resolved_camera_alert_does_not_break_the_next_event(client, db, lab, staff, device_headers):
    """Before 2026-10-18 the unique dedupe_key of a resolved camera alert made the next event of the same
    box fail with HTTP 500 (event and snapshot lost). Now the incident reopens and the event is stored."""
    from tests.test_security import _event, _register
    cid = _register(client, device_headers, lab)["device_id"]
    h = auth_headers(client, staff.email)
    z = client.post(f"/api/security/cameras/{cid}/zones", headers=h,
                    json={"name": "PC-09", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}).json()
    assert _event(client, device_headers, zone_id=z["id"]).status_code == 201
    inc = db.query(Alert).filter(Alert.fingerprint.like("sec:%")).one()
    r = client.post(f"/api/incidents/{inc.id}/actions", headers=h, json={"action": "resolve", "text": "checked, ok"})
    assert r.json()["state"] == "RESOLVED"
    assert _event(client, device_headers, zone_id=z["id"]).status_code == 201      # was HTTP 500
    db.refresh(inc)
    assert not inc.is_resolved and inc.reopened_count == 1
    assert db.query(Alert).filter(Alert.fingerprint.like("sec:%")).count() == 1


def test_mitigated_state_and_acknowledging_never_changes_the_device(client, db, lab, staff):
    d = Device(device_uid="CAM_T", name="Cam T", lab_id=lab.id, is_online=False)
    from app.models import DeviceType
    d.device_type = DeviceType.SECURITY_CAMERA
    db.add(d)
    db.commit()
    a, _ = _raise(db, lab, title="Cam T offline", device_id=d.id)
    h = auth_headers(client, staff.email)
    act = lambda **b: client.post(f"/api/incidents/{a.id}/actions", headers=h, json=b)
    assert act(action="acknowledge").json()["state"] == "ACKNOWLEDGED"
    assert act(action="mitigate", text="").status_code == 422
    r = act(action="mitigate", text="switched the live view to camera 2").json()
    assert r["state"] == "MITIGATED" and r["occurrences"] == 1
    assert client.get("/api/incidents?state=MITIGATED", headers=h).json()["counts"]["MITIGATED"] == 1
    db.refresh(d)
    assert d.is_online is False                                      # the incident is not the device
    assert db.query(AuditLog).filter_by(action="INCIDENT_MITIGATE").count() == 1


def test_escalation_on_repeats_and_quality_analytics(client, db, lab, staff, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "INCIDENT_ESCALATE_OCCURRENCES", 3)
    monkeypatch.setattr(settings, "INCIDENT_ESCALATE_WARNING_MIN", 10 ** 6)     # isolate the repeat rule
    for i in range(4):
        _raise(db, lab, title="Flame sensor flicker", minutes=i)
    _raise(db, lab, title="Door held open")
    h = auth_headers(client, staff.email)
    rows = client.get("/api/incidents?days=30", headers=h).json()["incidents"]
    flick = next(r for r in rows if r["title"] == "Flame sensor flicker")
    assert flick["occurrences"] == 4 and flick["escalate"] and "repeated 4 times" in flick["escalation_reason"]
    q = client.get("/api/incidents/quality?days=30", headers=h).json()
    assert q["incidents"] == 2 and q["reports"] == 5 and q["grouped_share"] == 0.6
    assert q["top_conditions"][0]["title"] == "Flame sensor flicker" and q["top_conditions"][0]["reports"] == 4



def test_offline_incident_clears_when_the_device_reports_through_its_own_route(client, db, lab, staff, device_headers):
    """PC agents / collectors / camera services set is_online themselves; their offline incident used to
    stay OPEN while they reported (2026-10-18). A fresh report now clears it on the next liveness refresh."""
    from app.services.devices import refresh_liveness
    from datetime import datetime as _dt, timezone as _tz
    d = Device(device_uid="PC_X", name="LAB-PC-X", lab_id=lab.id, is_online=True, last_seen_at=_dt.now(_tz.utc))
    from app.models import DeviceType
    d.device_type = DeviceType.PC
    db.add(d)
    db.commit()
    a = Alert(lab_id=lab.id, device_id=d.id, severity=AlertSeverity.WARNING, title="LAB-PC-X offline")
    other = Alert(lab_id=lab.id, device_id=d.id, severity=AlertSeverity.WARNING, title="LAB-PC-X disk almost full")
    db.add_all([a, other])
    db.commit()
    refresh_liveness(db)
    db.refresh(a)
    db.refresh(other)
    assert a.is_resolved and a.state == "RESOLVED" and not other.is_resolved



def test_camera_without_picture_becomes_one_incident_and_clears_with_frames(db, lab, monkeypatch):
    from datetime import datetime as _dt, timezone as _tz
    from app.models import DeviceType
    from app.services import devices as dv
    monkeypatch.setattr(dv, "NO_PICTURE_S", 0)
    monkeypatch.setenv("LIVENESS_THROTTLE_S", "0")
    d = Device(device_uid="SECCAM_T", name="Cam T", lab_id=lab.id, is_online=True, last_seen_at=_dt.now(_tz.utc),
               component_state={"source_ok": False})
    d.device_type = DeviceType.SECURITY_CAMERA
    db.add(d)
    db.commit()
    dv.refresh_liveness(db)
    dv.refresh_liveness(db)                                   # still no picture: the same incident, not counted twice
    alerts = db.query(Alert).filter_by(device_id=d.id, title="Cam T: no picture from the camera").all()
    assert len(alerts) == 1 and not alerts[0].is_resolved and alerts[0].occurrences == 1
    d.component_state = {"source_ok": True}
    d.last_seen_at = _dt.now(_tz.utc)
    db.commit()
    dv.refresh_liveness(db)
    db.refresh(alerts[0])
    assert alerts[0].is_resolved


def test_resolving_by_flag_also_closes_the_lifecycle_state(db, lab):
    # 2026-10-18 live finding: a device coming back set is_resolved but left state OPEN, so the
    # Incidents page still listed "BIN_NODE_1 offline" as open. Any resolve must close the state too.
    a, _ = _raise(db, lab, title="Bin offline")
    a.is_resolved, a.resolved_at = True, T0 + timedelta(minutes=1)
    db.commit()
    db.refresh(a)
    assert a.state == "RESOLVED"
    reopened, outcome = _raise(db, lab, title="Bin offline", minutes=5)
    assert outcome == "reopened" and reopened.state == "OPEN" and reopened.is_resolved is False
