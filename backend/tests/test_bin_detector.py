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
