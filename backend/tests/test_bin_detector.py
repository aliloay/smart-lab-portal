"""Reusable-bin detector (2026-10-29): letterbox / box mapping with a fake model (the real ONNX file is the owner's,
trained locally - checked against Ultralytics by tools/vision_train/parity_bin.py), threshold, missing model."""
import pytest

from app.services import bin_detector as bd

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")


class FakeSession:
    """Returns one box given in letterboxed 640 px (cx, cy, w, h) with a score; records the input it got."""
    def __init__(self, box, score):
        self.box, self.score, self.seen = box, score, None

    def run(self, _, feeds):
        self.seen = next(iter(feeds.values()))
        out = np.zeros((1, 5, 8400), np.float32)
        out[0, :4, 7] = self.box
        out[0, 4, 7] = self.score
        out[0, 4, 3] = 0.1                       # a weaker candidate elsewhere is ignored
        return [out]


@pytest.fixture
def fake(monkeypatch):
    def use(box, score):
        s = FakeSession(box, score)
        monkeypatch.setattr(bd, "_RT", ("ort", s, "images"))
        monkeypatch.setattr(bd, "_LOADED", True)
        return s
    return use


def test_box_maps_back_through_the_centred_letterbox(fake):
    # 1280 x 960 frame -> scale 0.5 -> 640 x 480 centred: 80 px grey above and below
    s = fake((320, 80 + 240, 320, 240), 0.9)    # a box covering the middle half of the frame
    d = bd.detect(np.zeros((960, 1280, 3), np.uint8))
    assert d["confidence"] == 0.9
    assert d["box"] == pytest.approx({"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}, abs=1e-3)
    assert s.seen.shape == (1, 3, 640, 640) and s.seen.dtype == np.float32
    assert s.seen[0, :, 0, 0] == pytest.approx([114 / 255] * 3)      # padding is training's grey


def test_below_threshold_is_no_bin(fake, monkeypatch):
    monkeypatch.setattr(bd, "CONF", 0.6)
    fake((320, 320, 100, 100), 0.59)
    assert bd.detect(np.zeros((480, 640, 3), np.uint8)) is None


def test_no_model_file_means_no_detector(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "MODEL", str(tmp_path / "missing.onnx"))
    monkeypatch.setattr(bd, "_LOADED", False)
    monkeypatch.setattr(bd, "_RT", None)
    assert not bd.available() and bd.engine() is None
    assert bd.detect(np.zeros((480, 640, 3), np.uint8)) is None


def test_opencv_fallback_layout(monkeypatch):
    class Net:
        def setInput(self, x): self.x = x
        def forward(self):
            out = np.zeros((1, 8400, 5), np.float32)   # transposed layout is accepted too
            out[0, 5] = (320, 320, 640, 640, 0.95)
            return out
    monkeypatch.setattr(bd, "_RT", ("cv2", Net()))
    monkeypatch.setattr(bd, "_LOADED", True)
    d = bd.detect(np.zeros((640, 640, 3), np.uint8))
    assert d["box"] == pytest.approx({"x": 0, "y": 0, "w": 1, "h": 1}, abs=1e-3)


# ---------------------------------------------------------------- one model, several classes (2026-10-30) ---
SPEC = {"file": "all_detector.onnx", "classes": [
    {"index": 1, "name": "network_switch", "label": "Network switch (TP-Link)", "conf": 0.5},
    {"index": 2, "name": "network_router", "label": "Smart Lab router", "conf": 0.5}]}


def test_multi_class_reads_one_score_row_per_class():
    out = np.zeros((1, 7, 8400), np.float32)          # 4 box rows + 3 classes in the file
    out[0, :4, 11] = (320, 320, 320, 320)             # a box in letterboxed 640 px
    out[0, 4, 11] = 0.99                              # class 0 (the bin) - not listed here, ignored
    out[0, 5, 11] = 0.9                               # network_switch
    out[0, 6, 11] = 0.2
    out[0, 5, 12] = 0.1
    hits = bd._parse_multi(out, SPEC, (640, 640), 1.0, 0, 0)
    assert [h["class"] for h in hits] == ["network_switch"]
    assert hits[0]["code"] == "type:network_switch" and hits[0]["confidence"] == 0.9
    assert hits[0]["box"] == pytest.approx({"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}, abs=1e-3)


def test_multi_class_transposed_and_own_thresholds():
    out = np.zeros((8400, 7), np.float32)             # transposed (N, 4+classes) is accepted too
    out[3, :4] = (400, 400, 200, 200)
    out[3, 5] = 0.55                                  # switch, just over its 0.5
    out[3, 6] = 0.45                                  # router, under its 0.5
    hits = bd._parse_multi(out, SPEC, (640, 640), 1.0, 0, 0)
    assert [h["class"] for h in hits] == ["network_switch"]
    assert hits[0]["box"] == pytest.approx({"x": 0.46875, "y": 0.46875, "w": 0.3125, "h": 0.3125}, abs=1e-3)
    # a spec exposing only the router (index 2 of a 3-class file) must still expect 7 rows, not 6
    only_router = {"file": "all_detector.onnx", "classes": [{"index": 2, "name": "network_router", "conf": 0.6}]}
    out2 = np.zeros((1, 7, 8400), np.float32)
    out2[0, :4, 1] = (320, 320, 100, 100)
    out2[0, 6, 1] = 0.59
    assert bd._parse_multi(out2, only_router, (640, 640), 1.0, 0, 0) == []
    assert bd._parse_multi(out2, {**only_router, "classes": [{"index": 2, "name": "network_router", "conf": 0.5}]},
                           (640, 640), 1.0, 0, 0)[0]["code"] == "type:network_router"


def test_detect_all_keeps_every_hit_and_the_bin_stays(monkeypatch):
    monkeypatch.setattr(bd, "detect", lambda img: {"confidence": 0.8, "box": {"x": 0, "y": 0, "w": 1, "h": 1}})
    monkeypatch.setattr(bd, "extras", lambda: [(SPEC, "rt")])
    monkeypatch.setattr(bd, "_infer_multi", lambda rt, spec, img: [
        {"code": "type:network_router", "class": "network_router", "label": "Smart Lab router", "confidence": 0.7,
         "box": {"x": 0, "y": 0, "w": 0.2, "h": 0.2}}])
    hits = bd.detect_all(np.zeros((480, 640, 3), np.uint8))
    assert [h["code"] for h in hits] == [bd.CODE, "type:network_router"]      # most confident first
    assert bd.detect_any(np.zeros((480, 640, 3), np.uint8))["code"] == bd.CODE


def test_detectors_json_lists_more_models(monkeypatch, tmp_path):
    (tmp_path / "detectors.json").write_text('[{"file": "sw.onnx", "class": "network_switch", "conf": 0.5}, '
                                             '{"file": "missing.onnx", "class": "x"}]')
    (tmp_path / "sw.onnx").write_bytes(b"x")
    monkeypatch.setattr(bd, "EXTRA", str(tmp_path / "detectors.json"))
    monkeypatch.setattr(bd, "_EXTRA", None)
    monkeypatch.setattr(bd, "_load", lambda p: "rt" if p.endswith("sw.onnx") else None)
    assert [s["class"] for s, rt in bd.extras()] == ["network_switch"]      # a listed file that is missing is skipped
