"""
The ESP32-CAM never calls the portal; the Master polls it and reports "camera" in its heartbeat
(2026-11-20). The entry-camera row follows that report, display only.
"""
from datetime import datetime, timedelta, timezone

from app.models import Device, DeviceType


def _cam(db, lab, online=False):
    cam = Device(device_uid="CAM_LAB01", name="Entry camera", device_type=DeviceType.CAMERA,
                 lab_id=lab.id, is_online=online,
                 last_seen_at=datetime.now(timezone.utc) - timedelta(days=3) if online else None)
    db.add(cam)
    db.commit()
    return cam


def _beat(client, headers, lab, camera):
    return client.post("/api/access/heartbeat", headers=headers, json={
        "device_uid": "MASTER_LAB01", "lab_id": lab.code, "door_closed": True,
        "components": {"rfid": True, "fingerprint": True, "camera": camera, "relay_locked": True}})


def test_master_reporting_camera_ok_marks_entry_camera_seen(client, db, lab, device_headers):
    cam = _cam(db, lab)
    assert _beat(client, device_headers, lab, True).status_code == 200
    db.expire_all()
    cam = db.get(Device, cam.id)
    assert cam.is_online is True and cam.last_seen_at is not None
    assert datetime.now(timezone.utc) - cam.last_seen_at.replace(tzinfo=cam.last_seen_at.tzinfo or timezone.utc) \
        < timedelta(seconds=30)


def test_master_reporting_camera_down_leaves_entry_camera_alone(client, db, lab, device_headers):
    cam = _cam(db, lab, online=True)
    before = db.get(Device, cam.id).last_seen_at
    assert _beat(client, device_headers, lab, False).status_code == 200
    db.expire_all()
    assert db.get(Device, cam.id).last_seen_at == before     # not refreshed: normal timeout takes it offline
