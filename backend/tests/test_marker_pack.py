"""Owner's marker pack (2026-10-27): only pack files whose payload equals a registered record key are used; the port
of the pack renderer reproduces those files exactly; every served marker decodes to its own record."""
import io
import json
import os
from datetime import datetime, timezone

import pytest

from app.models import Device, DeviceType
from app.services import marker_pack as mp
from tests.conftest import auth_headers

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
from PIL import Image  # noqa: E402


def test_only_verified_pack_payloads_are_used_and_the_rejected_ones_never():
    v = json.load(open(os.path.join(mp.DATA, "verified.json")))
    assert {a["payload"] for a in v["rejected"]} == {"SLAB:D:CONS_BIN_01", "SLAB:D:SEC_NODE_01"}
    assert set(mp.verified()) == {a["payload"] for a in v["verified"]} and not set(mp.verified()) & {a["payload"] for a in v["rejected"]}


@pytest.mark.parametrize("payload,slug,typ", [("SLAB:D:UR5E_01", "ur5e-robot", "Robot"),
                                               ("SLAB:D:MASTER_LAB01", "door-master", "Door controller (master ESP32)"),
                                               ("SLAB:D:CAM_LAB01", "entry-camera", "Entry camera")])
def test_the_port_reproduces_the_pack_file_pixel_for_pixel(payload, slug, typ):
    orig = np.array(Image.open(os.path.join(mp.DATA, f"{slug}.png")).convert("RGB"))
    mine = np.array(mp.render_png(payload, mp.category({"type": typ})))
    assert orig.shape == mine.shape and not (orig != mine).any()
    assert cv2.QRCodeDetector().detectAndDecode(cv2.resize(orig[:, :, ::-1], (480, 480)))[0] == payload


def test_every_category_decodes_and_falls_back_to_plain(monkeypatch):
    for cat in mp.CATS:
        img = mp.render_png(f"SLAB:D:{cat.upper()}_X", cat)
        assert cv2.QRCodeDetector().detectAndDecode(np.array(img.resize((480, 480)))[:, :, ::-1])[0] == f"SLAB:D:{cat.upper()}_X"
    mp.qr_png.cache_clear()
    monkeypatch.setattr(mp, "decodes", lambda img, code: False)
    assert mp.qr_png("SLAB:D:FALLBACK_X", "robot")[1] == "plain"
    mp.qr_png.cache_clear()


def test_routes_serve_svg_and_card_for_the_real_record(client, db, lab, staff):
    db.add(Device(device_uid="UR5E_01", name="UR5e (physical)", device_type=DeviceType.ROBOT, lab_id=lab.id,
                  last_seen_at=datetime.now(timezone.utc)))
    db.commit()
    h = auth_headers(client, staff.email)
    s = client.get("/api/scan/marker.svg", params={"code": "SLAB:D:UR5E_01"}, headers=h)
    assert s.status_code == 200 and s.headers["x-marker-source"] == "pack" and s.headers["x-marker-category"] == "robot"
    assert s.text.startswith("<svg") and "#b84300" in s.text
    card = client.get("/api/scan/marker.png", params={"code": "SLAB:D:UR5E_01"}, headers=h)
    img = cv2.imdecode(np.frombuffer(card.content, np.uint8), cv2.IMREAD_COLOR)
    k = 640 / img.shape[1]
    assert cv2.QRCodeDetector().detectAndDecode(cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA))[0] == "SLAB:D:UR5E_01"
    assert client.get("/api/scan/marker.svg", params={"code": "SLAB:D:SEC_NODE_01"}, headers=h).status_code == 404


def test_markers_page_in_one_response(client, db, lab, staff):
    db.add(Device(device_uid="CAM_LAB01", name="Entry cam", device_type=DeviceType.CAMERA, lab_id=lab.id)); db.commit()
    h = auth_headers(client, staff.email)
    r = client.get("/api/scan/markers.json", headers=h).json()
    m = {x["code"]: x for x in r["markers"]}["SLAB:D:CAM_LAB01"]
    assert m["category"] == "camera" and m["source"] == "pack" and m["img"].startswith("data:image/svg+xml;base64,")
    assert client.get("/api/scan/markers.json", params={"style": "shape"}, headers=h).json()["markers"][0]["img"].startswith("data:image/png")


def test_pdf_prints_the_owner_pictures_and_they_scan():
    """2026-10-27 (owner: 'when downloading the markers, where are the images?'): the PDF uses the asset's picture
    with its QR; the printed card still decodes to the asset's own payload."""
    import cv2
    import numpy as np
    from app.services import marker_pack
    items = [{"code": "SLAB:D:UR5E_01", "name": "UR5e (physical)", "kind": "device", "type": "ROBOT"},
             {"code": "SLAB:D:MASTER_LAB01", "name": "Door Controller", "kind": "device", "type": "DOOR_CONTROLLER"}]
    for it in items:
        card = marker_pack.art_card(it, 1100, 1000)
        assert card is not None
        a = cv2.cvtColor(np.array(card), cv2.COLOR_RGB2BGR)
        assert cv2.QRCodeDetector().detectAndDecode(a)[0] == it["code"], it["code"]
    assert marker_pack.art_card({"code": "SLAB:A:XYZ", "name": "x"}, 500, 500) is None     # no picture -> pack card
    pdf = marker_pack.sheet_pdf(items, style="art")
    assert pdf[:4] == b"%PDF" and len(pdf) > 50_000
