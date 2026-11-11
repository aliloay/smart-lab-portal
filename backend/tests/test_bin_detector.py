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
    monkeypatch.setattr(bd, "detect", lambda img, *a: {"confidence": 0.8, "box": {"x": 0, "y": 0, "w": 1, "h": 1}})
    monkeypatch.setattr(bd, "extras", lambda: [(SPEC, "rt")])
    monkeypatch.setattr(bd, "_infer_multi", lambda rt, spec, img, *a: [
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


# ---------------------------------------------------------------- Gemini review fixes (2026-11-02) ---
def test_a_box_in_the_padding_never_gets_a_negative_size():
    # 640x480 frame letterboxed: 80 px grey above / below; a box entirely in the bottom bar
    b = bd._box(320, 600, 100, 20, 1.0, 0, 80, (480, 640))
    assert b["w"] >= 0 and b["h"] >= 0 and 0 <= b["y"] <= 1


def test_a_spec_may_list_only_some_classes_of_a_bigger_model():
    out = np.zeros((1, 7, 8400), np.float32)            # 3-class file
    out[0, :4, 5] = (320, 320, 64, 64)
    out[0, 5, 5] = 0.8                                   # class 1 only is listed below
    only_switch = {"classes": [{"index": 1, "name": "network_switch", "conf": 0.5}]}
    hits = bd._parse_multi(out, only_switch, (640, 640), 1.0, 0, 0)
    assert [h["class"] for h in hits] == ["network_switch"]


def test_the_one_class_reader_refuses_a_multi_class_model(monkeypatch):
    class Net:
        def setInput(self, x): pass
        def forward(self): return np.full((1, 7, 8400), 320.0, np.float32)   # would look like huge "scores"
    assert bd._infer(("cv2", Net()), 0.5, np.zeros((480, 640, 3), np.uint8)) is None


def test_detect_all_prepares_the_frame_once(monkeypatch):
    calls = []
    real = bd.letterbox
    monkeypatch.setattr(bd, "letterbox", lambda img: calls.append(1) or real(img))
    monkeypatch.setattr(bd, "_runtime", lambda: None)
    monkeypatch.setattr(bd, "extras", lambda: [({"classes": [{"index": 1, "name": "x"}]}, None)])
    bd.detect_all(np.zeros((480, 640, 3), np.uint8))
    assert calls == [1]


# ---------------------------------------------------------------- lab-wide model (2026-11-02) ---
def test_lab_model_that_answers_the_bin_replaces_the_one_class_bin_model(monkeypatch):
    ran = []
    monkeypatch.setattr(bd, "detect", lambda img, *a: ran.append(1) or {"confidence": 0.9, "box": {"x": 0, "y": 0, "w": 1, "h": 1}})
    lab = {"classes": [{"index": 0, "name": "reusable_bin", "code": bd.CODE}]}
    monkeypatch.setattr(bd, "extras", lambda: [(lab, "rt")])
    monkeypatch.setattr(bd, "_infer_multi", lambda rt, spec, img, *a: [
        {"code": bd.CODE, "class": "reusable_bin", "label": None, "confidence": 0.6, "box": {"x": 0, "y": 0, "w": 0.5, "h": 0.5}}])
    hits = bd.detect_all(np.zeros((480, 640, 3), np.uint8))
    assert ran == [] and [h["confidence"] for h in hits] == [0.6]


def test_two_models_naming_the_same_object_give_one_hit(monkeypatch):
    monkeypatch.setattr(bd, "detect", lambda img, *a: None)
    monkeypatch.setattr(bd, "extras", lambda: [(SPEC, "a"), (SPEC, "b")])
    monkeypatch.setattr(bd, "_infer_multi", lambda rt, spec, img, *a: [
        {"code": "type:network_switch", "class": "network_switch", "label": "Switch",
         "confidence": 0.9 if rt == "b" else 0.55, "box": {"x": 0, "y": 0, "w": 0.2, "h": 0.2}}])
    hits = bd.detect_all(np.zeros((480, 640, 3), np.uint8))
    assert len(hits) == 1 and hits[0]["confidence"] == 0.9


def _hit(code, conf, x, y, w, h):
    return {"code": code, "class": code, "label": code, "confidence": conf, "box": {"x": x, "y": y, "w": w, "h": h}}


def test_two_classes_on_the_same_object_keep_only_the_more_confident(monkeypatch):
    # phone test 2026-11-03: the master node got "Door controller 94%" AND "router 81%" on the same box
    monkeypatch.setattr(bd, "detect", lambda img, *a: None)
    monkeypatch.setattr(bd, "extras", lambda: [(SPEC, "a")])
    monkeypatch.setattr(bd, "_infer_multi", lambda rt, spec, img, *a: [
        _hit("SLAB:D:MASTER_LAB01", 0.94, 0.10, 0.20, 0.60, 0.40),
        _hit("type:network_router", 0.81, 0.12, 0.18, 0.62, 0.45),
        _hit("SLAB:D:ENV_LAB01", 0.90, 0.70, 0.70, 0.20, 0.20)])
    hits = bd.detect_all(np.zeros((480, 640, 3), np.uint8))
    assert [h["code"] for h in hits] == ["SLAB:D:MASTER_LAB01", "SLAB:D:ENV_LAB01"]


def test_similar_box_inside_is_dropped_but_a_small_object_in_front_stays():
    kept = bd._suppress_overlaps([_hit("A", 0.9, 0.0, 0.0, 0.5, 0.5),       # big box
                                  _hit("B", 0.8, 0.02, 0.02, 0.4, 0.45),   # nearly the same box -> same object
                                  _hit("C", 0.7, 0.1, 0.1, 0.1, 0.1),      # small, inside A -> a separate object
                                  _hit("D", 0.6, 0.6, 0.6, 0.3, 0.3)])
    assert [h["code"] for h in kept] == ["A", "C", "D"]


def test_a_class_that_lists_max_instances_reports_every_separate_object():
    """2026-11-11: two lab PCs in one frame were one box. Opt-in per class; overlapping boxes stay one object."""
    pcs = {"file": "x.onnx", "classes": [{"index": 0, "name": "lab_pc", "label": "Lab PC", "conf": 0.5, "max_instances": 3},
                                          {"index": 1, "name": "lab_door", "label": "Door", "conf": 0.5}]}
    out = np.zeros((6, 8400), np.float32)
    out[:4, 0], out[4, 0] = (100, 100, 80, 60), 0.91          # PC one
    out[:4, 1], out[4, 1] = (104, 102, 80, 60), 0.88          # the same PC again (overlaps): not a second object
    out[:4, 2], out[4, 2] = (400, 110, 80, 60), 0.84          # PC two
    out[:4, 3], out[4, 3] = (300, 300, 80, 60), 0.30          # below the threshold
    out[:4, 4], out[5, 4] = (500, 400, 60, 200), 0.90         # the door: one box, as before
    out[:4, 5], out[5, 5] = (100, 400, 60, 200), 0.80         # a second door-like box: not listed for more
    hits = bd._parse_multi(out, pcs, (640, 640), 1.0, 0, 0)
    assert [(h["code"], h["confidence"]) for h in hits] == [("type:lab_pc", 0.91), ("type:lab_pc#2", 0.84),
                                                            ("type:lab_door", 0.9)]
