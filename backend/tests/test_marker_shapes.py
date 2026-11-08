"""Asset-shaped QR markers (2026-10-27): the code itself forms the object; every marker must decode to its exact payload
and resolve to the right record; a design that does not read back is served as a plain QR. The independent second
decoder (jsQR) runs in frontend/e2e/qr_decode_jsqr.mjs over the same renders."""
from datetime import datetime, timezone

import pytest

from app.models import Device, DeviceType
from app.services import marker_shapes as ms
from tests.conftest import auth_headers

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
DET = cv2.QRCodeDetector()
TYPES = {"camera": "Entry camera", "door": "Door controller (master ESP32)", "robot": "Robot", "pc": "Lab PC",
         "consumables": "Consumables bin node", "security": "Security camera", "server": "Face server",
         "environment": "Environment node", "reusable": "Reusable-items bin node", "equipment": "Measurement"}


def _read(img) -> str:
    a = np.array(img.convert("RGB"))[:, :, ::-1]
    return DET.detectAndDecode(a)[0]


@pytest.mark.parametrize("cat", sorted(TYPES))
def test_every_category_is_shaped_and_decodes_at_print_and_small_size(cat):
    kind = "asset" if cat == "equipment" else "device"
    item = {"code": f"SLAB:{kind[0].upper()}:{cat.upper()}_TEST_LAB01", "kind": kind, "name": cat, "type": TYPES[cat], "lab_code": "LAB_01"}
    assert ms.category(item) == cat
    img, kind = ms.card(item, 12)
    assert kind == "shape", f"{cat} fell back to plain"
    for scale in (1.0, 0.5, 0.33):
        small = img if scale == 1 else img.resize((int(img.width * scale), int(img.height * scale)))
        assert _read(small) == item["code"], (cat, scale)


def test_a_design_that_does_not_read_back_falls_back_to_a_plain_qr(monkeypatch):
    monkeypatch.setattr(ms, "decodes", lambda img, code: False)
    img, kind = ms.card({"code": "SLAB:D:UR5E_01", "kind": "device", "name": "UR5e", "type": "Robot"}, 12)
    assert kind == "plain" and _read(img) == "SLAB:D:UR5E_01"


def test_served_markers_decode_to_their_own_record(client, db, lab, staff):
    now = datetime.now(timezone.utc)
    db.add_all([Device(device_uid="UR5E_T", name="UR5e", device_type=DeviceType.ROBOT, lab_id=lab.id, last_seen_at=now),
                Device(device_uid="CAM_T", name="Entry cam", device_type=DeviceType.CAMERA, lab_id=lab.id),
                Device(device_uid="DOOR_T", name="Door", device_type=DeviceType.MASTER_CONTROLLER, lab_id=lab.id)])
    db.commit()
    h = auth_headers(client, staff.email)
    for a in client.get("/api/scan/registry", headers=h).json()["assets"]:
        r = client.get("/api/scan/marker.png", params={"code": a["code"]}, headers=h)
        assert r.status_code == 200
        img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
        k = 640 / img.shape[1]                                  # the phone page analyses a 640-px-wide frame
        text = DET.detectAndDecode(cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA))[0]
        assert text == a["code"]
        card = client.get("/api/scan/asset", params={"code": text}, headers=h).json()
        assert card["key"] == a["key"]
    pdf = client.get("/api/scan/markers.pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
