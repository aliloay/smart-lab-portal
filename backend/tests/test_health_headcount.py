"""Lab Health Score (priority H) and the advisory emergency headcount (priority N), 2026-10-26."""
from datetime import datetime, timedelta, timezone

from app.models import AccessSession, Alert, AlertSeverity, AuthMethod, Device, DeviceType
from tests.conftest import auth_headers


def _cam(db, lab, people, seen_ago_s=1, uid="SECCAM_T1"):
    d = Device(device_uid=uid, name=uid, device_type=DeviceType.SECURITY_CAMERA, lab_id=lab.id,
               last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=seen_ago_s), component_state={"people": people})
    db.add(d); db.commit()
    return d


def test_students_cannot_see_either(client, alice, lab):
    h = auth_headers(client, alice.email)
    assert client.get("/api/labs/health", headers=h).status_code == 403
    assert client.get("/api/labs/headcount", headers=h).status_code == 403


def test_unknown_parts_are_left_out_not_counted_healthy(client, staff, lab):
    r = client.get("/api/labs/health", headers=auth_headers(client, staff.email)).json()
    x = next(v for v in r if v["lab_code"] == lab.code)
    assert x["parts"]["environment"]["value"] is None and x["parts"]["devices"]["value"] is None
    assert x["coverage"] < 1 and x["score"] == 100.0 and x["band"] == "GOOD"     # alerts/issues/hazards known: none


def test_alerts_and_offline_devices_lower_the_score(client, db, staff, lab):
    _cam(db, lab, 0, seen_ago_s=3600)                                 # a silent camera
    db.add(Alert(lab_id=lab.id, severity=AlertSeverity.CRITICAL, title="t", detail=""))
    db.commit()
    x = next(v for v in client.get("/api/labs/health", headers=auth_headers(client, staff.email)).json()
             if v["lab_code"] == lab.code)
    assert x["parts"]["devices"]["value"] == 0.0 and x["parts"]["alerts"]["value"] == 0.5
    assert x["score"] < 85 and x["weakest"] == "devices" and "0 of 1" in x["parts"]["devices"]["evidence"]


def test_headcount_compares_door_record_and_cameras_without_summing(client, db, staff, alice, lab):
    db.add(AccessSession(user_id=alice.id, lab_id=lab.id, started_at=datetime.now(timezone.utc), entry_method=AuthMethod.RFID))
    db.commit()
    _cam(db, lab, 3, uid="CAM_A"); _cam(db, lab, 2, uid="CAM_B")
    r = client.get("/api/labs/headcount", headers=auth_headers(client, staff.email)).json()
    x = next(v for v in r if v["lab_code"] == lab.code)
    assert x["door_inside"] == 1 and x["names"][0]["name"] == "Alice"
    assert x["camera_people"] == 3 and "2 more" in x["note"] and "Advisory" in x["advisory"]


def test_headcount_with_cameras_offline_says_door_only(client, db, staff, lab):
    _cam(db, lab, 5, seen_ago_s=3600)
    x = next(v for v in client.get("/api/labs/headcount", headers=auth_headers(client, staff.email)).json()
             if v["lab_code"] == lab.code)
    assert x["camera_people"] is None and "door record only" in x["note"]
