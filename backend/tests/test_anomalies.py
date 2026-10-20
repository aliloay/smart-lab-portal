"""Anomaly detection (2026-10-17): rules, sensor faults, robust baseline, stale data, no duplicate incidents."""
import random
from datetime import datetime, timedelta, timezone

from app.models import Alert, Device, DeviceType, SensorReading
from app.services import anomalies as an
from tests.conftest import auth_headers


def _node(db, lab, uid="ENV_T"):
    d = Device(device_uid=uid, name=uid, device_type=DeviceType.SENSOR_NODE, lab_id=lab.id)
    db.add(d)
    db.flush()
    return d


def _fill(db, d, lab, metric, now, minutes, value_fn, unit="C"):
    db.add_all([SensorReading(lab_id=lab.id, device_id=d.id, metric=metric, unit=unit, value=value_fn(i),
                              recorded_at=now - timedelta(minutes=minutes - i)) for i in range(minutes)])


def test_baseline_deviation_rule_and_fresh_data(db, lab):
    now = datetime.now(timezone.utc)
    d = _node(db, lab)
    rnd = random.Random(1)
    # 2 days at ~24 C, then the last hour at 31 C (inside the rule range, far outside the baseline)
    _fill(db, d, lab, "temperature", now, 2 * 1440, lambda i: 31.0 if i >= 2 * 1440 - 60 else 24 + rnd.gauss(0, 0.3))
    db.commit()
    r = an.scan(db, now)
    kinds = {(f["metric"], f["kind"]) for f in r["findings"]}
    assert ("temperature", "DEVIATION") in kinds and ("temperature", "OUT_OF_RANGE") not in kinds
    dev = next(f for f in r["findings"] if f["kind"] == "DEVIATION")
    assert "7-day median" in dev["expected"] and dev["source"] == "sensor_readings" and not dev["stale"]
    assert "Not used" in r["ml_status"]


def test_impossible_values_and_out_of_range(db, lab):
    now = datetime.now(timezone.utc)
    d = _node(db, lab)
    _fill(db, d, lab, "humidity", now, 60, lambda i: 120.0 if i == 59 else 80.0, unit="%")
    db.commit()
    kinds = {f["kind"] for f in an.scan(db, now)["findings"]}
    assert {"IMPOSSIBLE_VALUE", "OUT_OF_RANGE"} <= kinds


def test_stale_node_is_reported_as_missing_not_normal(db, lab):
    now = datetime.now(timezone.utc)
    d = _node(db, lab)
    _fill(db, d, lab, "temperature", now - timedelta(days=3), 60, lambda i: 24.0)
    db.commit()
    r = an.scan(db, now)
    f = next(x for x in r["findings"] if x["kind"] == "NO_CURRENT_DATA")
    assert f["stale"] is True and "stopped reporting" in f["explanation"]
    ev = next(x for x in r["evaluated"] if x["metric"] == "temperature")
    assert "insufficient" in ev["baseline"]                       # 60 readings: no statistics claimed


def test_frequent_flame_detections_flag_the_sensor_and_raise_once(client, db, staff, lab):
    now = datetime.now(timezone.utc)
    d = _node(db, lab)
    _fill(db, d, lab, "flame", now, 300, lambda i: 1.0 if i % 5 == 0 else 0.0, unit="state")
    db.commit()
    h = auth_headers(client, staff.email)
    from app.api.routes import analytics
    analytics._anom_cache.update(at=0.0, body=None)
    r = client.get("/api/analytics/anomalies", headers=h).json()
    idx = next(i for i, f in enumerate(r["findings"]) if f["kind"] == "FREQUENT_DETECTIONS")
    a = client.post(f"/api/analytics/anomalies/raise?index={idx}", headers=h).json()
    b = client.post(f"/api/analytics/anomalies/raise?index={idx}", headers=h).json()
    assert a["created"] is True and b["created"] is False and a["incident_id"] == b["incident_id"]
    assert db.query(Alert).filter(Alert.dedupe_key.like("anomaly:%")).count() == 1


def test_one_long_flame_block_is_described_as_concentrated(db, lab):
    """Real pattern from ENV_LAB01 (9 Oct): one continuous ~3 h active block, otherwise quiet."""
    now = datetime.now(timezone.utc)
    d = _node(db, lab)
    # 2 days of readings 1/min; active for 180 min a day ago; the last 24 h quiet
    _fill(db, d, lab, "flame", now, 2 * 1440, lambda i: 1.0 if 600 <= i < 780 else 0.0, unit="state")
    db.commit()
    f = next(x for x in an.scan(db, now)["findings"] if x["kind"] == "HISTORICALLY_FREQUENT")
    assert "1 separate activation(s)" in f["observed"] and "179 min" in f["observed"]
