"""Scan the lab (phone camera, 2026-10-26): identification ONLY by marker = the record's own key; the card carries the
authoritative live state with its age and quality; people boxes are a generic class proxied to the camera service."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.api.routes import scan as scan_route
from app.models import Asset, Device, DeviceType, InventoryBin, InventoryMeasurement, SensorReading
from app.services import scan
from tests.conftest import auth_headers, image_bytes


@pytest.fixture
def assets(db, lab):
    now = datetime.now(timezone.utc)
    env = Device(device_uid="ENV_NODE_1", name="Environment node", device_type=DeviceType.SENSOR_NODE, lab_id=lab.id,
                 last_seen_at=now, is_online=True)
    ur = Device(device_uid="UR5E_LAB01", name="UR5e", device_type=DeviceType.ROBOT, lab_id=lab.id, last_seen_at=now,
                is_online=True, component_state={"state": "IDLE", "home": "AT_HOME", "source": "TEACH_PENDANT",
                                                 "q": [0.0, -1.57, 1.57, 0, 1.57, 0]})
    sim = Device(device_uid="UR5E_SIM", name="UR5e simulator", device_type=DeviceType.ROBOT, lab_id=lab.id)
    db.add_all([env, ur, sim]); db.commit()
    db.add_all([SensorReading(lab_id=lab.id, device_id=env.id, metric="temperature", value=23.4, unit="C",
                              recorded_at=now - timedelta(seconds=20)),
                SensorReading(lab_id=lab.id, device_id=env.id, metric="temperature", value=21.0, unit="C",
                              recorded_at=now - timedelta(hours=2)),
                SensorReading(lab_id=lab.id, device_id=env.id, metric="humidity", value=44.0, unit="%",
                              recorded_at=now - timedelta(minutes=30))])
    b = InventoryBin(code="BIN-R10K", lab_id=lab.id, device_id=env.id, item_name="10 kOhm resistors", tare_g=100.0,
                     unit_mass_g=0.2, last_mass_g=106.0, last_measured_at=now, reorder_qty=50)
    raw = InventoryBin(code="BIN-RAW", lab_id=lab.id, item_name="LEDs")               # never calibrated
    a = Asset(asset_tag="ARD-01", name="Arduino Uno #1", lab_id=lab.id, bin_item=True)
    db.add_all([b, raw, a]); db.commit()
    db.add(InventoryMeasurement(bin_id=b.id, mass_g=106.0, recorded_at=now)); db.commit()
    return {"env": env, "ur": ur}


def test_marker_text_is_the_record_key_and_nothing_else_parses():
    assert scan.marker("D", "UR5E_LAB01") == "SLAB:D:UR5E_LAB01"
    assert scan.parse("SLAB:D:UR5E_LAB01") == ("D", "UR5E_LAB01")
    for bad in ("", "SLAB:X:1", "SLAB:D:", "OTHER:D:UR5E", "http://evil", "SLAB:D:" + "x" * 65):
        assert scan.parse(bad) is None


def test_registry_lists_real_assets_and_never_a_simulator(client, staff, assets):
    r = client.get("/api/scan/registry", headers=auth_headers(client, staff.email)).json()
    codes = {a["code"] for a in r["assets"]}
    assert {"SLAB:D:ENV_NODE_1", "SLAB:D:UR5E_LAB01", "SLAB:B:BIN-R10K", "SLAB:B:BIN-RAW", "SLAB:A:ARD-01"} <= codes
    assert "SLAB:D:UR5E_SIM" not in codes


def test_students_cannot_scan(client, alice, assets):
    h = auth_headers(client, alice.email)
    assert client.get("/api/scan/registry", headers=h).status_code == 403
    assert client.get("/api/scan/asset", params={"code": "SLAB:D:UR5E_LAB01"}, headers=h).status_code == 403
    assert client.post("/api/scan/people", content=image_bytes(), headers=h).status_code == 403


def test_sensor_card_has_the_newest_reading_per_metric_with_its_age_and_quality(client, staff, assets):
    c = client.get("/api/scan/asset", params={"code": "SLAB:D:ENV_NODE_1"}, headers=auth_headers(client, staff.email)).json()
    assert c["status"] == "ONLINE" and c["seconds_since_seen"] is not None
    r = {x["metric"]: x for x in c["readings"]}
    assert r["temperature"]["value"] == 23.4 and r["temperature"]["quality"] == "LIVE"       # the newest, not 21.0
    assert r["humidity"]["quality"] == "STALE" and r["humidity"]["age_s"] >= 1700            # 30 min old: stale


def test_robot_card_reports_the_controller_state_never_a_guess(client, staff, assets):
    c = client.get("/api/scan/asset", params={"code": "SLAB:D:UR5E_LAB01"}, headers=auth_headers(client, staff.email)).json()
    facts = {f["label"]: f for f in c["facts"]}
    assert facts["Robot state"]["value"] == "IDLE" and facts["Robot state"]["quality"] == "LIVE"
    assert facts["Driven from"]["value"] == "TEACH_PENDANT"


def test_bin_card_counts_only_when_calibrated(client, staff, assets):
    h = auth_headers(client, staff.email)
    c = client.get("/api/scan/asset", params={"code": "SLAB:B:BIN-R10K"}, headers=h).json()
    assert c["facts"][0]["value"].startswith("30") and "estimate" in c["facts"][0]["value"]
    raw = client.get("/api/scan/asset", params={"code": "SLAB:B:BIN-RAW"}, headers=h).json()
    assert raw["facts"][0]["value"] == "not calibrated - no count" and raw["status"] == "MISSING"


def test_unknown_marker_is_unidentified(client, staff, assets):
    h = auth_headers(client, staff.email)
    assert client.get("/api/scan/asset", params={"code": "SLAB:D:NOT_REAL"}, headers=h).status_code == 404
    assert client.get("/api/scan/asset", params={"code": "WIFI:T:WPA;S:x"}, headers=h).status_code == 404


def test_marker_png_decodes_back_to_the_exact_code(client, staff, assets):
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    r = client.get("/api/scan/marker.png", params={"code": "SLAB:A:ARD-01"}, headers=auth_headers(client, staff.email))
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_GRAYSCALE)
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert text == "SLAB:A:ARD-01"


def test_link_qr_only_for_https_portal_addresses(client, staff):
    h = auth_headers(client, staff.email)
    assert client.get("/api/scan/link.png", params={"url": "https://192.168.1.200/scan"}, headers=h).status_code == 200
    for bad in ("http://192.168.1.200/scan", "https://evil.example/<script>", "javascript:alert(1)"):
        assert client.get("/api/scan/link.png", params={"url": bad}, headers=h).status_code == 422


class FakeVision:
    def __init__(self, status=200, exc=None):
        self.status, self.exc, self.calls = status, exc, []

    def post(self, url, content, headers):
        self.calls.append((url, len(content), headers.get("X-Device-Key") is not None))
        if self.exc:
            raise self.exc
        return httpx.Response(self.status, json={"w": 640, "h": 360, "ms": 14.2, "engine": "directml-gpu1",
                                                 "class": "person",
                                                 "boxes": [{"x": 0.1, "y": 0.2, "w": 0.1, "h": 0.4, "score": 0.81}]})


def _camera(db, lab):
    db.add(Device(device_uid="SECCAM_T", name="Cam", device_type=DeviceType.SECURITY_CAMERA, lab_id=lab.id,
                  component_state={"port": 5101}, last_seen_at=datetime.now(timezone.utc)))
    db.commit()


def test_people_boxes_are_proxied_once_and_never_named(monkeypatch, client, db, lab, staff):
    _camera(db, lab)
    fake = FakeVision()
    monkeypatch.setattr(scan_route, "_detect", fake)
    r = client.post("/api/scan/people", content=image_bytes(), headers=auth_headers(client, staff.email))
    assert r.status_code == 200
    body = r.json()
    assert body["class"] == "person" and "name" not in body["boxes"][0] and body["proxy_ms"] >= 0
    assert fake.calls[0][0].endswith(":5101/detect") and fake.calls[0][2]


def test_busy_detector_means_skip_this_frame_not_queue(monkeypatch, client, db, lab, staff):
    _camera(db, lab)
    monkeypatch.setattr(scan_route, "_detect", FakeVision(status=429))
    assert client.post("/api/scan/people", content=image_bytes(), headers=auth_headers(client, staff.email)).status_code == 429


def test_people_needs_a_jpeg_and_a_reachable_service(monkeypatch, client, db, lab, staff):
    h = auth_headers(client, staff.email)
    assert client.post("/api/scan/people", content=b"not a jpeg", headers=h).status_code == 422
    assert client.post("/api/scan/people", content=image_bytes(), headers=h).status_code == 503       # no camera
    _camera(db, lab)
    monkeypatch.setattr(scan_route, "_detect", FakeVision(exc=httpx.ConnectError("down")))
    r = client.post("/api/scan/people", content=image_bytes(), headers=h)
    assert r.status_code == 503 and "markers still work" in r.json()["detail"]


def test_equipment_with_a_device_shows_the_device_once(client, db, lab, staff, assets):
    a = Asset(asset_tag="RB-001", name="UR5e Collaborative Arm", lab_id=lab.id)
    db.add(a); db.commit()
    assets["ur"].asset_id = a.id; db.commit()
    h = auth_headers(client, staff.email)
    codes = [x["code"] for x in client.get("/api/scan/registry", headers=h).json()["assets"]]
    assert "SLAB:A:RB-001" not in codes and "SLAB:D:UR5E_LAB01" in codes
    c = client.get("/api/scan/asset", params={"code": "SLAB:A:RB-001"}, headers=h).json()
    assert c["kind"] == "device" and c["key"] == "UR5E_LAB01" and c["code"] == "SLAB:A:RB-001"


def test_themed_robot_marker_still_decodes_and_the_sheet_is_a_pdf(client, staff, assets):
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    h = auth_headers(client, staff.email)
    r = client.get("/api/scan/marker.png", params={"code": "SLAB:D:UR5E_LAB01"}, headers=h)
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_GRAYSCALE)
    assert cv2.QRCodeDetector().detectAndDecode(img)[0] == "SLAB:D:UR5E_LAB01"
    pdf = client.get("/api/scan/markers.pdf", params={"kind": "device"}, headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    assert client.get("/api/scan/markers.pdf", params={"kind": "x"}, headers=h).status_code == 422


def test_every_theme_decodes_even_when_printed_small():
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    from app.services import marker_art
    for t in list(marker_art.THEMES) + ["Device", "Measurement"]:
        item = {"code": "SLAB:D:A_LONGER_DEVICE_UID_01", "kind": "device", "name": "x", "type": t}
        img = marker_art.render(item)
        small = np.array(img.resize((img.width // 3, img.height // 3)))[:, :, ::-1]
        assert cv2.QRCodeDetector().detectAndDecode(small)[0] == item["code"], t


class FakeFace:
    def __init__(self, name="USER1", score=0.71, second=0.30, face=True, status=200):
        self.res, self.status, self.calls = {"name": name, "score": score, "second": second, "face": face}, status, 0

    def post(self, url, content, headers):
        self.calls += 1
        assert url.endswith("/identify") and headers.get("X-Device-Key") is not None
        return httpx.Response(self.status, json=self.res)


def test_phone_face_names_only_a_clear_match_with_the_portal_record(monkeypatch, client, db, staff, alice):
    from app.models import AuditLog
    alice.department = "Engineering"; db.commit()
    h = auth_headers(client, staff.email)
    monkeypatch.setattr(scan_route, "_face", FakeFace())
    r = client.post("/api/scan/identify", content=image_bytes(), headers=h).json()
    assert r["known"] and r["person"]["name"] == "Alice" and r["person"]["auth_subject"] == "USER1"
    assert r["person"]["department"] == "Engineering" and r["person"]["inside_by_door"] is False
    assert db.query(AuditLog).filter_by(action="PHONE_FACE_IDENTIFIED").count() == 1
    for weak in (FakeFace(score=0.45, second=0.1), FakeFace(score=0.62, second=0.58), FakeFace(name=None, score=None, face=False)):
        monkeypatch.setattr(scan_route, "_face", weak)
        r = client.post("/api/scan/identify", content=image_bytes(), headers=h).json()
        assert not r["known"] and "person" not in r and r["reason"]
    monkeypatch.setattr(scan_route, "_face", FakeFace(status=429))
    assert client.post("/api/scan/identify", content=image_bytes(), headers=h).status_code == 429


def test_students_cannot_identify_faces(client, alice):
    assert client.post("/api/scan/identify", content=image_bytes(), headers=auth_headers(client, alice.email)).status_code == 403
