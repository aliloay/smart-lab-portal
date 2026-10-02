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
    assert t["state"] == "OK"


def test_critical_alert_puts_the_lab_first_in_alert_state(client, db, staff, lab):
    _master(db, lab)
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.CRITICAL,
                 title="Forced entry", detail=""))
    db.commit()
    body = client.get("/api/monitor", headers=auth_headers(client, staff.email)).json()
    assert body["labs"][0]["lab_id"] == lab.id
    assert body["labs"][0]["state"] == "ALERT"
    assert body["labs"][0]["alerts"][0]["title"] == "Forced entry"


def test_faulty_component_is_a_warning(client, db, staff, lab):
    _master(db, lab, rfid=False)
    t = _tile(client, auth_headers(client, staff.email), lab)
    assert t["state"] == "WARN" and t["faults"] == ["RFID reader"]


def test_never_reported_values_stay_null(client, db, staff, lab):
    t = _tile(client, auth_headers(client, staff.email), lab)
    assert t["has_door"] is False
    assert t["door_closed"] is None and t["locked"] is None
    assert t["environment"] == {}
