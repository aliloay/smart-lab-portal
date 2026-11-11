"""Live activity lines (2026-11-11): camera -> /security/state -> camera list and the assistant's instant answer."""
from datetime import datetime, timezone

from app.models import Device, DeviceType
from tests.conftest import auth_headers

LINES = [{"track_id": 3, "label": "USER1", "who": "Ali ?", "colour": "green", "posture": "standing",
          "near": "UR5e", "named": True, "text": "Ali ? (green top) - standing - most likely at UR5e"},
         {"track_id": 9, "label": None, "who": "Person 9", "colour": "blue", "posture": "bending or crouching",
          "near": None, "named": False, "text": "Person 9 (blue top) - bending or crouching", "extra": "dropped"}]


def _camera(db, lab):
    d = Device(device_uid="SECCAM_T", name="Camera T", lab_id=lab.id, device_type=DeviceType.SECURITY_CAMERA,
               last_seen_at=datetime.now(timezone.utc), component_state={"port": 5100})
    db.add(d)
    db.commit()
    return d


def test_activity_travels_to_the_camera_list_and_the_instant_answer(client, db, lab, staff, device_headers):
    _camera(db, lab)
    r = client.post("/api/security/state", headers=device_headers,
                    json={"device_uid": "SECCAM_T", "fps": 9, "people": 2, "named": [], "unknown": 2,
                          "activity": LINES})
    assert r.status_code == 200, r.text
    h = auth_headers(client, staff.email)
    cam = next(c for c in client.get("/api/security/cameras", headers=h).json() if c["device_uid"] == "SECCAM_T")
    assert [a["text"] for a in cam["activity"]] == [LINES[0]["text"], LINES[1]["text"]]
    assert "extra" not in cam["activity"][1]                         # only the known fields are kept
    ans = client.post("/api/ai/ask", headers=h, json={"question": "what is everyone doing right now?"}).json()
    assert ans["instant"] is True and "most likely at UR5e" in ans["answer"] and "Person 9" in ans["answer"]


def test_activity_is_bounded_and_students_cannot_read_the_cameras(client, db, lab, alice, device_headers):
    _camera(db, lab)
    many = [{"track_id": i, "text": "x" * 400} for i in range(21)]
    assert client.post("/api/security/state", headers=device_headers,
                       json={"device_uid": "SECCAM_T", "activity": many}).status_code == 422     # at most 20 lines
    assert client.get("/api/security/cameras", headers=auth_headers(client, alice.email)).status_code == 403
