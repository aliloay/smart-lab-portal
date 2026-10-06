"""
The wall screen (/api/monitor): one tile per lab with door, lock, who is
inside, active alerts and the last door event. Staff only - it names people.
"""
from datetime import datetime, timezone

from app.models import (AccessSession, Alert, AlertSeverity, AuthMethod,
                        Device, DeviceType)
from tests.conftest import auth_headers


def _master(db, lab, door_closed=True, locked=True, **components):
    d = Device(device_uid="MASTER_MON", name="Master", lab_id=lab.id,
               device_type=DeviceType.MASTER_CONTROLLER, is_online=True,
               last_seen_at=datetime.now(timezone.utc), door_closed=door_closed,
               component_state={"rfid": True, "fingerprint": True,
                                "camera": True, "relay_locked": locked,
                                **components})
    db.add(d)
    db.commit()
    return d


def _tile(client, headers, lab):
    r = client.get("/api/monitor", headers=headers)
    assert r.status_code == 200, r.text
    return next(t for t in r.json()["labs"] if t["lab_id"] == lab.id)


def test_students_cannot_see_the_wall_screen(client, alice):
    r = client.get("/api/monitor", headers=auth_headers(client, alice.email))
    assert r.status_code == 403


def test_tile_shows_door_lock_and_who_is_inside(client, db, staff, alice, lab):
    _master(db, lab, door_closed=False, locked=False)
    db.add(AccessSession(lab_id=lab.id, user_id=alice.id,
                         entry_method=AuthMethod.QR,
                         started_at=datetime.now(timezone.utc)))
    db.commit()
    t = _tile(client, auth_headers(client, staff.email), lab)
    assert t["door_closed"] is False and t["locked"] is False
    assert [p["name"] for p in t["people"]] == ["Alice"]
    assert t["people_by_role"] == {"STUDENT": 1} and t["in_use"] is True
    assert t["state"] == "OK"


def test_critical_alert_puts_the_lab_in_alert_state(client, db, staff, lab):
    _master(db, lab)
    for _ in range(3):
        db.add(Alert(lab_id=lab.id, severity=AlertSeverity.CRITICAL,
                     title="Forced entry", detail=""))
    db.commit()
    t = _tile(client, auth_headers(client, staff.email), lab)
    assert t["state"] == "ALERT"
    # Repeats are one line with a count, not three lines.
    assert t["alerts"] == [{"severity": "CRITICAL", "title": "Forced entry",
                            "at": t["alerts"][0]["at"], "count": 3}]
    assert t["alert_count"] == 3


def test_faulty_component_is_a_warning(client, db, staff, lab):
    _master(db, lab, rfid=False)
    t = _tile(client, auth_headers(client, staff.email), lab)
    assert t["state"] == "WARN" and t["faults"] == ["RFID reader"]


def test_never_reported_values_stay_null(client, db, staff, lab):
    t = _tile(client, auth_headers(client, staff.email), lab)
    assert t["has_door"] is False
    assert t["door_closed"] is None and t["locked"] is None
    assert t["environment"] == {} and t["in_use"] is False and t["people_by_role"] == {}


def test_internet_is_reported_apart_and_never_degrades_status(client, alice, monkeypatch):
    """Offline-first: no uplink is 'internet offline', not an unhealthy system."""
    from app.api.routes import system

    def no_uplink(*a, **k):
        raise OSError("no route")

    monkeypatch.setattr(system.socket, "create_connection", no_uplink)
    monkeypatch.setitem(system._internet, "at", 0.0)
    monkeypatch.setattr(system.time, "monotonic", lambda: 10_000.0)
    s = client.get("/api/system/status", headers=auth_headers(client, alice.email)).json()
    assert s["internet"] is False
    assert s["status"] == "HEALTHY" and s["database"] is True


def test_wall_screen_query_count_does_not_grow_with_labs(client, db, staff, lab):
    """The wall screen fetches every lab in a few batched queries: ~15 queries
    per lab made it take ~0.5 s with 11 labs. Adding labs must not add queries."""
    from sqlalchemy import event
    from app.db.session import engine
    from app.models import Lab
    h = auth_headers(client, staff.email)
    client.get("/api/monitor", headers=h)
    count = [0]
    listen = lambda *a: count.__setitem__(0, count[0] + 1)
    event.listen(engine, "before_cursor_execute", listen)
    try:
        client.get("/api/monitor", headers=h)
        few = count[0]
        for i in range(8):
            db.add(Lab(code=f"LAB_Q{i}", name=f"Query lab {i}", is_active=True))
        db.commit()
        client.get("/api/monitor", headers=h)     # a new lab's emergency row is created once
        count[0] = 0
        r = client.get("/api/monitor", headers=h)
        many = count[0]
    finally:
        event.remove(engine, "before_cursor_execute", listen)
    assert r.status_code == 200 and len(r.json()["labs"]) == 9
    assert many <= few + 2, (few, many)


def test_operations_sparkline_is_small_but_keeps_the_count_and_peaks(db, lab):
    from datetime import timedelta
    from app.models import SensorReading
    from app.services import analytics
    now = datetime.now(timezone.utc)
    for i in range(600):
        db.add(SensorReading(lab_id=lab.id, metric="temperature", value=20 + (i % 10), unit="C",
                             recorded_at=now - timedelta(seconds=600 - i)))
        db.add(SensorReading(lab_id=lab.id, metric="smoke", value=1 if i == 300 else 0, unit="state",
                             recorded_at=now - timedelta(seconds=600 - i)))
    db.commit()
    s = {x["metric"]: x for x in analytics.environment(db, lab.id)["series"]}
    assert s["temperature"]["count"] == 600 and len(s["temperature"]["points"]) == 120
    assert s["temperature"]["latest"] == 29                      # the real last reading
    assert max(p["v"] for p in s["smoke"]["points"]) == 1        # a 1-sample alarm survives
