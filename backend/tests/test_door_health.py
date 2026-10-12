"""
Door alarms (reed switch) and component health reported by the master.

What staff must see without watching a serial monitor: a forced door, a
door left open, and a reader or sensor that stopped answering - each as an
alert and a notification, and each cleared when it is no longer true.
"""
from app.models import AccessEvent, Alert, AlertSeverity, EventType, Notification


def _heartbeat(client, headers, lab, **components):
    return client.post("/api/access/heartbeat", headers=headers, json={
        "device_uid": "MASTER_LAB01", "lab_id": lab.code, "door_closed": True,
        "components": {"rfid": True, "fingerprint": True, "camera": True,
                       "relay_locked": True, **components}})


def _event(client, headers, lab, event_type, reason=None, message=""):
    body = {"lab_id": lab.code, "device_uid": "MASTER_LAB01",
            "event_type": event_type, "message": message}
    if reason:
        body["reason"] = reason
    return client.post("/api/access/events", headers=headers, json=body)


def test_component_fault_raises_one_alert_and_clears(client, db, staff, lab,
                                                     device_headers):
    assert _heartbeat(client, device_headers, lab).status_code == 200
    assert db.query(Alert).count() == 0

    # RFID stops answering: one alert, one notification...
    _heartbeat(client, device_headers, lab, rfid=False)
    # ...and repeating the report (every 30 s) does not duplicate either.
    _heartbeat(client, device_headers, lab, rfid=False)
    db.expire_all()
    alerts = db.query(Alert).all()
    assert len(alerts) == 1
    assert "RFID reader" in alerts[0].title
    assert alerts[0].is_resolved is False
    assert alerts[0].severity == AlertSeverity.WARNING
    assert db.query(Notification).filter_by(user_id=staff.id,
                                            kind="DEVICE_FAULT").count() == 1

    # It comes back: the alert resolves itself.
    _heartbeat(client, device_headers, lab, rfid=True)
    db.expire_all()
    assert db.query(Alert).one().is_resolved is True


def test_each_component_is_tracked_separately(client, db, staff, lab,
                                              device_headers):
    _heartbeat(client, device_headers, lab, fingerprint=False, camera=False)
    db.expire_all()
    titles = sorted(a.title for a in db.query(Alert).all())
    assert len(titles) == 2
    assert any("Fingerprint sensor" in t for t in titles)
    assert any("Camera" in t for t in titles)

    _heartbeat(client, device_headers, lab, camera=True, fingerprint=False)
    db.expire_all()
    open_titles = [a.title for a in db.query(Alert).filter_by(is_resolved=False)]
    assert len(open_titles) == 1 and "Fingerprint sensor" in open_titles[0]


def test_first_heartbeat_with_a_fault_is_reported(client, db, staff, lab,
                                                  device_headers):
    # A controller that boots with a dead reader must not wait for a
    # healthy->faulty transition that will never come.
    _heartbeat(client, device_headers, lab, rfid=False)
    db.expire_all()
    assert db.query(Alert).filter_by(is_resolved=False).count() == 1


def test_forced_entry_is_a_critical_alert_that_stays_open(client, db, staff,
                                                          lab, device_headers):
    r = _event(client, device_headers, lab, "ALARM", "FORCED_ENTRY",
               "Door opened while locked - no access had been granted")
    assert r.status_code == 200
    db.expire_all()
    alert = db.query(Alert).one()
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.title == f"Forced entry at {lab.code}"
    assert db.query(Notification).filter_by(user_id=staff.id,
                                            kind="SECURITY_EVENT").count() == 1
    assert db.query(AccessEvent).filter_by(event_type=EventType.ALARM,
                                           reason="FORCED_ENTRY").count() == 1

    # Closing the door does not make a forced entry go away: staff decide.
    _event(client, device_headers, lab, "DOOR_CLOSED",
           message="Door closed after forced entry")
    db.expire_all()
    assert db.query(Alert).one().is_resolved is False


def test_door_held_open_resolves_when_closed(client, db, staff, lab,
                                             device_headers):
    _event(client, device_headers, lab, "ALARM", "DOOR_HELD_OPEN",
           "Door open for more than 30 s")
    db.expire_all()
    alert = db.query(Alert).one()
    assert alert.severity == AlertSeverity.WARNING
    assert alert.is_resolved is False

    _event(client, device_headers, lab, "DOOR_CLOSED",
           message="Door closed - relocked")
    db.expire_all()
    assert db.query(Alert).one().is_resolved is True


def test_other_alarm_reasons_do_not_create_door_alerts(client, db, staff, lab,
                                                       device_headers):
    _event(client, device_headers, lab, "ALARM", "SOMETHING_ELSE", "x")
    db.expire_all()
    assert db.query(Alert).count() == 0


def test_door_or_lock_change_pushes_live_refresh(client, lab, device_headers,
                                                 monkeypatch):
    """Open pages refetch the door at once instead of waiting for their poll."""
    from app.ws.manager import manager
    sent = []
    monkeypatch.setattr(manager, "publish", sent.append)

    def beat(door_closed=True, relay_locked=True):
        return client.post("/api/access/heartbeat", headers=device_headers, json={
            "device_uid": "MASTER_LAB01", "lab_id": lab.code,
            "door_closed": door_closed,
            "components": {"rfid": True, "fingerprint": True, "camera": True,
                           "relay_locked": relay_locked}})

    beat()
    sent.clear()
    beat()                                   # nothing changed: no push
    assert sent == []
    beat(door_closed=False)                  # door opened
    beat(door_closed=False, relay_locked=False)   # lock released
    assert sent == [{"type": "door_state", "lab_id": lab.id}] * 2


def test_entry_camera_online_when_it_answers_without_the_door(db, lab, monkeypatch):
    """Audit 2026-10-12: the ESP32-CAM showed 'no data' while answering, because
    its state came only from the (offline) door controller."""
    from app.models import Device, DeviceType
    from app.services import devices as dv
    cam = Device(device_uid="CAM_T", name="cam", lab_id=lab.id, device_type=DeviceType.CAMERA)
    db.add(cam); db.commit()
    monkeypatch.setattr(dv, "_entry_camera_up", lambda: True)
    assert dv.device_out(cam).state == "ONLINE"
    monkeypatch.setattr(dv, "_entry_camera_up", lambda: False)
    assert dv.device_out(cam).state == "NO_DATA"
