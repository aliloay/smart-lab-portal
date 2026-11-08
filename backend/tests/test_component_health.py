"""Door-controller component health (2026-10-18): one missed self-test reply is not a fault.

The master's idle self-test sometimes misses a single fingerprint / PN532 reply; the portal used to
raise "Fingerprint sensor not responding" and "working again" every 10-30 s while the sensor read
fingers fine. A fault now has to last COMPONENT_FAULT_AFTER_S; a dead part is still reported."""
from datetime import datetime, timedelta, timezone

from app.models import AccessEvent, Alert, Device, DeviceType, EventType
from app.services import devices as dv

T0 = datetime(2026, 10, 18, 19, 0, tzinfo=timezone.utc)


def _master(db, lab):
    d = Device(device_uid="MASTER_T", name="Door Controller", device_type=DeviceType.MASTER_CONTROLLER,
               lab_id=lab.id, component_state={"fingerprint": True, "rfid": True, "camera": True})
    db.add(d)
    db.commit()
    dv._component_bad_since.clear()
    return d


def _alerts(db, d):
    return db.query(Alert).filter(Alert.device_id == d.id, Alert.title.like("%Fingerprint%")).all()


def test_a_single_missed_reply_raises_nothing(db, lab):
    d = _master(db, lab)
    dv.record_component_health(db, d, lab, {"fingerprint": False}, now=T0)
    dv.record_component_health(db, d, lab, {"fingerprint": True}, now=T0 + timedelta(seconds=10))
    db.commit()
    assert _alerts(db, d) == []
    assert db.query(AccessEvent).filter(AccessEvent.event_type == EventType.ALARM).count() == 0


def test_a_lasting_fault_is_reported_once_and_cleared(db, lab):
    d = _master(db, lab)
    for s in (0, 30):
        dv.record_component_health(db, d, lab, {"fingerprint": False}, now=T0 + timedelta(seconds=s))
    db.commit()
    assert _alerts(db, d) == []                                  # 30 s: not confirmed yet
    dv.record_component_health(db, d, lab, {"fingerprint": False}, now=T0 + timedelta(seconds=60))
    dv.record_component_health(db, d, lab, {"fingerprint": False}, now=T0 + timedelta(seconds=90))
    db.commit()
    open_ = [a for a in _alerts(db, d) if not a.is_resolved]
    assert len(open_) == 1                                       # one incident, not one per report
    dv.record_component_health(db, d, lab, {"fingerprint": True}, now=T0 + timedelta(seconds=120))
    db.commit()
    assert all(a.is_resolved for a in _alerts(db, d))


def test_pages_show_an_unconfirmed_fault_as_working(db, lab):
    d = _master(db, lab)
    d.component_state = {"fingerprint": False, "rfid": True, "camera": True}
    db.commit()
    dv.record_component_health(db, d, lab, d.component_state, now=T0)
    db.commit()
    assert dv.effective_components(d, T0 + timedelta(seconds=5))["fingerprint"] is True
    assert dv.effective_components(d, T0 + timedelta(seconds=50))["fingerprint"] is False
