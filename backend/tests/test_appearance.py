"""Enclosure appearance matching (2026-10-27) on SYNTHETIC box images (random printed patterns, not real enclosure
photos - those come from the owner): a hint only; wrong PROBABLE must be 0; twins are AMBIGUOUS; unrelated = UNKNOWN."""
import json

import pytest

from app.services import appearance

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def box(seed: int) -> "np.ndarray":
    rng = np.random.default_rng(seed)
    img = np.full((420, 620, 3), 235, np.uint8)
    for _ in range(40):
        c = tuple(int(x) for x in rng.integers(0, 200, 3))
        p1, p2 = tuple(int(x) for x in rng.integers(0, 600, 2)), tuple(int(x) for x in rng.integers(0, 400, 2))
        if rng.random() < 0.5:
            cv2.rectangle(img, p1, p2, c, int(rng.integers(1, 5)))
        else:
            cv2.circle(img, p1, int(rng.integers(5, 60)), c, int(rng.integers(1, 4)))
    cv2.putText(img, f"NODE {seed}", (40, 380), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (20, 20, 20), 3)
    return img


def view(img, ang=0.0, scale=1.0, tilt=0.0, light=0):
    h, w = img.shape[:2]
    out = cv2.warpAffine(img, cv2.getRotationMatrix2D((w / 2, h / 2), ang, scale), (w, h), borderValue=(90, 90, 90))
    if tilt:
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[w * tilt, 0], [w - w * tilt, 0], [w, h], [0, h]])
        out = cv2.warpPerspective(out, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(90, 90, 90))
    return np.clip(out.astype(np.int16) + light, 0, 255).astype(np.uint8)


@pytest.fixture
def refs(tmp_path):
    assets = [("SLAB:D:BIN_NODE_1", 1), ("SLAB:D:REUSE_BIN_1", 2), ("SLAB:D:MASTER_LAB01", 3)]
    for code, seed in assets:
        d = tmp_path / code.replace(":", "_"); d.mkdir()
        for i, (a, s, t) in enumerate(((0, 1.0, 0), (12, 0.9, 0.05), (-10, 1.1, 0.08))):
            cv2.imwrite(str(d / f"v{i}.jpg"), view(box(seed), a, s, t))
    (tmp_path / "manifest.json").write_text(json.dumps({"assets": [{"code": c, "class": "node"} for c, _ in assets]}))
    return appearance.Matcher(str(tmp_path)).load()


def test_a_new_view_of_a_box_is_probable_for_that_box(refs):
    r = refs.match(view(box(2), ang=20, scale=0.85, tilt=0.06, light=-25))
    assert r["decision"] == "PROBABLE" and r["best"]["code"] == "SLAB:D:REUSE_BIN_1"
    assert "verify with the asset's QR marker" in r["note"]


def test_something_else_is_unknown(refs):
    assert refs.match(view(box(99)))["decision"] == "UNKNOWN"


def test_two_identical_enclosures_are_ambiguous(tmp_path):
    for code in ("SLAB:D:BIN_A", "SLAB:D:BIN_B"):
        d = tmp_path / code.replace(":", "_"); d.mkdir()
        cv2.imwrite(str(d / "v0.jpg"), box(5))
    (tmp_path / "manifest.json").write_text(json.dumps({"assets": [{"code": "SLAB:D:BIN_A"}, {"code": "SLAB:D:BIN_B"}]}))
    m = appearance.Matcher(str(tmp_path)).load()
    assert m.match(view(box(5), ang=8))["decision"] == "AMBIGUOUS"


def test_leave_one_out_never_names_the_wrong_box(refs):
    ev = appearance.evaluate(refs)
    assert ev["views"] == 9 and ev["wrong"] == 0 and ev["correct"] >= 7


def test_route_without_references_says_scan_the_marker(client, staff, monkeypatch, tmp_path):
    from tests.conftest import auth_headers, image_bytes
    (tmp_path / "manifest.json").write_text('{"assets": []}')
    monkeypatch.setattr(appearance, "_MATCHER", appearance.Matcher(str(tmp_path)).load())
    h = auth_headers(client, staff.email)
    r = client.post("/api/scan/appearance", content=image_bytes(), headers=h).json()
    assert r["decision"] == "UNKNOWN" and "scan the marker" in r["note"]
    assert client.get("/api/scan/appearance/refs", headers=h).json()["assets"] == []


def test_detector_names_the_bin_when_the_matcher_finds_nothing(client, staff, monkeypatch, refs):
    """2026-10-28: far / side views the matcher cannot place go to the trained bin detector."""
    from app.services import bin_detector
    from tests.conftest import auth_headers, image_bytes
    monkeypatch.setattr(appearance, "_MATCHER", refs)
    monkeypatch.setattr(bin_detector, "detect", lambda img: {"confidence": 0.81, "box": {"x": .1, "y": .2, "w": .3, "h": .4}})
    r = client.post("/api/scan/appearance", content=image_bytes(), headers=auth_headers(client, staff.email)).json()
    assert r["decision"] == "PROBABLE" and r["by"] == "detector"
    assert r["best"]["code"] == "SLAB:D:REUSE_BIN_1" and r["best"]["box_kind"] == "detector" and r["best"]["confidence"] == 0.81


def test_no_detection_stays_unknown(client, staff, monkeypatch, refs):
    from app.services import bin_detector
    from tests.conftest import auth_headers, image_bytes
    monkeypatch.setattr(appearance, "_MATCHER", refs)
    monkeypatch.setattr(bin_detector, "detect", lambda img: None)
    r = client.post("/api/scan/appearance", content=image_bytes(), headers=auth_headers(client, staff.email)).json()
    assert r["decision"] == "UNKNOWN" and r.get("by") is None
