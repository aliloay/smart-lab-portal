"""Proactive suggestions (services/proactive.py): confirmed vs possible, evidence, de-duplication, no recompute per call."""
from datetime import datetime, timedelta, timezone

from app.models import Device, DeviceType, InventoryBin, SensorReading
from app.services import proactive
from tests.conftest import auth_headers


def test_findings_are_labelled_with_evidence_and_deduplicated(db, lab):
    now = datetime.now(timezone.utc)
    db.add(Device(device_uid="CAM_OFF", name="Camera X", device_type=DeviceType.SECURITY_CAMERA, lab_id=lab.id,
                  last_seen_at=now - timedelta(days=2), is_online=False))
    db.add(InventoryBin(code="BIN-P", lab_id=lab.id, item_name="LEDs", tare_g=100.0, unit_mass_g=1.0,
                        last_mass_g=102.0, last_measured_at=now, reorder_qty=10))
    for i in range(60):                                  # a steady temperature around 23 C, then 39 C now
        db.add(SensorReading(lab_id=lab.id, metric="temperature", value=23.0 + (i % 5) * 0.1, unit="C",
                             recorded_at=now - timedelta(hours=60 - i)))
    db.add(SensorReading(lab_id=lab.id, metric="temperature", value=39.0, unit="C", recorded_at=now))
    db.commit()
    items = proactive.compute(db, now)
    by = {i["key"]: i for i in items}
    assert by["offline:CAM_OFF"]["level"] == "CONFIRMED" and by["offline:CAM_OFF"]["evidence"][0]["at"]
    assert by["low:BIN-P"]["level"] == "CONFIRMED" and "2 left" in by["low:BIN-P"]["title"]
    s = by[f"sensor:{lab.id}:temperature"]
    assert s["level"] == "POSSIBLE" and "39" in s["title"] and "check" in s["suggestion"].lower()
    assert len(by) == len(items)                         # one entry per key
    assert [i["level"] for i in items] == sorted((i["level"] for i in items), key=lambda l: l != "CONFIRMED")


def test_endpoint_is_staff_only_and_cached(client, db, staff, alice, lab, monkeypatch):
    assert client.get("/api/insights/proactive", headers=auth_headers(client, alice.email)).status_code == 403
    proactive._cache.update(fp=None, at=0.0, items=[])
    calls = []
    real = proactive.compute
    monkeypatch.setattr(proactive, "compute", lambda db, now=None: calls.append(1) or real(db, now))
    h = auth_headers(client, staff.email)
    for _ in range(3):
        r = client.get("/api/insights/proactive", headers=h)
        assert r.status_code == 200 and "CONFIRMED" in r.json()["note"]
    assert len(calls) == 1                               # data unchanged: not recomputed per request
