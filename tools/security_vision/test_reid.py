"""
Person re-identification (vision.Appearance): engine choice, fallbacks, and the
2026-10-13 bug - cv2.dnn gave unrelated embeddings once the number of people
in a frame changed. Offline: no camera, portal or database.
"""
import os

import numpy as np
import pytest
import time as _time
real_sleep = _time.sleep

import vision

REID = os.path.join(os.path.dirname(__file__), "models", "person_reid_youtu_2021nov.onnx")
needs_model = pytest.mark.skipif(not os.path.isfile(REID), reason="re-id model not downloaded")


def _frame(seed=7):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (540, 960, 3), dtype=np.uint8)


BOXES = [(100, 100, 80, 220), (400, 120, 90, 240), (700, 90, 70, 200)]


@needs_model
@pytest.mark.parametrize("engine", ["gpu", "cpu", "opencv"])
def test_same_person_same_embedding_whatever_the_crowd(monkeypatch, engine):
    """The bug: an embedding must not depend on how many people share the frame."""
    monkeypatch.setenv("SMARTLAB_REID", engine)
    a = vision.Appearance(REID)
    f = _frame()
    alone = a.looks(f, BOXES[:1])[0].deep
    crowd = a.looks(f, BOXES)[0].deep
    alone_again = a.looks(f, BOXES[:1])[0].deep
    assert alone is not None and crowd is not None
    assert float(alone @ crowd) > 0.999 and float(alone @ alone_again) > 0.999
    assert abs(float(np.linalg.norm(crowd)) - 1.0) < 1e-4


@needs_model
def test_all_engines_agree(monkeypatch):
    f = _frame(3)
    emb = {}
    for e in ("gpu", "cpu", "opencv"):
        monkeypatch.setenv("SMARTLAB_REID", e)
        emb[e] = [l.deep for l in vision.Appearance(REID).looks(f, BOXES)]
    for e in ("gpu", "opencv"):
        for x, y in zip(emb["cpu"], emb[e]):
            assert float(x @ y) > 0.999, e


@needs_model
def test_gpu_unavailable_falls_back_to_cpu(monkeypatch):
    import onnxruntime as ort
    monkeypatch.setenv("SMARTLAB_REID", "gpu")
    monkeypatch.setattr(ort, "get_available_providers", lambda: ["CPUExecutionProvider"])
    assert vision.Appearance(REID).engine == "onnxruntime-cpu"


@needs_model
def test_failing_engine_keeps_colours_and_tracking(monkeypatch):
    monkeypatch.setenv("SMARTLAB_REID", "cpu")
    a = vision.Appearance(REID)

    def boom(_):
        raise RuntimeError("simulated inference failure")
    a.net = boom
    looks = a.looks(_frame(), BOXES)
    assert len(looks) == 3 and all(l.color is not None and l.deep is None for l in looks)


def test_no_model_and_no_people():
    a = vision.Appearance(None)
    assert a.engine == "colours only" and a.looks(_frame(), []) == []
    assert all(l.deep is None for l in a.looks(_frame(), BOXES))


@needs_model
def test_tiny_boxes_are_skipped(monkeypatch):
    monkeypatch.setenv("SMARTLAB_REID", "cpu")
    looks = vision.Appearance(REID).looks(_frame(), [(10, 10, 5, 8), BOXES[0]])
    assert looks[0].deep is None and looks[1].deep is not None


# --- 2026-10-13 pre-rollout audit: correspondence, crowd changes, failures ---------
class _FakeNet:
    """Deterministic stand-in for the re-id model: the embedding is a fixed random
    projection of the crop, so equal crops give equal embeddings and every output
    can be traced back to its input. Counts calls and batch sizes."""
    def __init__(self, fail_on_call=None):
        self.proj = np.random.default_rng(0).standard_normal((3 * 256 * 128, 768)).astype(np.float32) / 300
        self.calls, self.batches, self.fail_on_call = 0, [], fail_on_call

    def __call__(self, blob):
        self.calls += 1
        self.batches.append(blob.shape[0])
        if self.fail_on_call == self.calls:
            raise RuntimeError("simulated failure for one person")
        return blob.reshape(blob.shape[0], -1) @ self.proj


def _fake_appearance(**kw):
    a = vision.Appearance(None)
    a.net = _FakeNet(**kw)
    return a


def _people_frame():
    """Five clearly different 'people' painted on a frame."""
    f = np.zeros((540, 1200, 3), np.uint8)
    boxes = []
    for k in range(6):
        x = 20 + k * 195
        f[60:420, x:x + 150] = np.random.default_rng(k + 10).integers(0, 255, (360, 150, 3), dtype=np.uint8)
        boxes.append((x, 60, 150, 360))
    return f, boxes


def test_each_embedding_belongs_to_its_own_crop_in_any_order():
    a = _fake_appearance()
    f, boxes = _people_frame()
    ref = {b: a.looks(f, [b])[0].deep for b in boxes}            # each person alone
    for order in (boxes, boxes[::-1], [boxes[3], boxes[0], boxes[5], boxes[1]]):
        for b, look in zip(order, a.looks(f, order)):
            assert float(look.deep @ ref[b]) > 0.9999            # right person, not a neighbour


def test_crowd_grows_and_shrinks_between_frames():
    """1 -> 2 -> 6 -> 3 -> 0 -> 1 people: the same person keeps the same embedding."""
    a = _fake_appearance()
    f, boxes = _people_frame()
    p0 = a.looks(f, [boxes[0]])[0].deep
    for crowd in ([boxes[0], boxes[1]], boxes, [boxes[4], boxes[0], boxes[2]], [], [boxes[0]]):
        looks = a.looks(f, crowd)
        assert len(looks) == len(crowd)
        for b, look in zip(crowd, looks):
            if b == boxes[0]:
                assert float(look.deep @ p0) > 0.9999


def test_one_failed_person_does_not_stop_the_others_or_leave_a_stale_embedding():
    a = _fake_appearance(fail_on_call=2)                          # the 2nd person of the frame fails
    f, boxes = _people_frame()
    looks = a.looks(f, boxes[:3])
    assert looks[0].deep is not None and looks[2].deep is not None
    assert looks[1].deep is None and looks[1].color is not None   # keeps its colours, no stale/other vector
    assert float(looks[0].deep @ looks[2].deep) < 0.99           # 3rd did not get the 2nd's slot


def test_model_runs_one_crop_per_call_and_is_not_reloaded():
    a = _fake_appearance()
    net = a.net
    f, boxes = _people_frame()
    for crowd in (boxes[:1], boxes, boxes[:2]):
        a.looks(f, crowd)
    assert a.net is net                                           # same model object every frame
    assert set(net.batches) == {1} and net.calls == 1 + 6 + 2    # always batch 1


def test_too_small_crops_are_skipped_without_shifting_the_others():
    a = _fake_appearance()
    f, boxes = _people_frame()
    tiny = (5, 5, 4, 6)
    looks = a.looks(f, [boxes[0], tiny, boxes[1]])
    alone1 = a.looks(f, [boxes[1]])[0].deep
    assert looks[1].deep is None and float(looks[2].deep @ alone1) > 0.9999


@needs_model
def test_gpu_session_failure_falls_back_to_cpu(monkeypatch):
    import onnxruntime as ort
    real = ort.InferenceSession

    def no_dml(path, *a, providers=None, **k):
        if providers and any((p[0] if isinstance(p, tuple) else p) == "DmlExecutionProvider" for p in providers):
            raise RuntimeError("simulated DirectML start-up failure")
        return real(path, *a, providers=providers, **k)
    monkeypatch.setenv("SMARTLAB_REID", "gpu")
    monkeypatch.setattr(ort, "InferenceSession", no_dml)
    a = vision.Appearance(REID)
    assert a.engine == "onnxruntime-cpu"
    assert a.looks(_frame(), BOXES[:2])[0].deep is not None


@needs_model
def test_real_model_five_people_matches_one_at_a_time(monkeypatch):
    for engine in ("gpu", "cpu", "opencv"):
        monkeypatch.setenv("SMARTLAB_REID", engine)
        a = vision.Appearance(REID)
        f, boxes = _people_frame()
        crowd = a.looks(f, boxes)
        for b, look in zip(boxes, crowd):
            alone = a.looks(f, [b])[0].deep
            assert float(look.deep @ alone) > 0.999, (engine, b)


@needs_model
def test_busy_start_up_does_not_push_a_fast_gpu_to_the_cpu(monkeypatch):
    # 2026-10-14: launch.bat starts everything at once; the single start-up timing came out > 25 ms
    # and re-id ran on the CPU all session although the GTX 1650 does a crop in ~10 ms.
    import onnxruntime as ort
    if "DmlExecutionProvider" not in ort.get_available_providers():
        pytest.skip("no DirectML on this machine")
    real = ort.InferenceSession

    class SlowAtFirst:
        def __init__(self, s): self.s, self.n = s, 0
        def run(self, *a, **k):
            self.n += 1
            if self.n <= 10:                     # warm-up + the first timing: "busy laptop"
                vision.time.sleep(0.03)
            return self.s.run(*a, **k)
        def __getattr__(self, name): return getattr(self.s, name)

    def wrapped(path, *a, providers=None, **k):
        s = real(path, *a, providers=providers, **k)
        dml = providers and any((p[0] if isinstance(p, tuple) else p) == "DmlExecutionProvider" for p in providers)
        return SlowAtFirst(s) if dml else s
    monkeypatch.setenv("SMARTLAB_REID", "gpu")
    monkeypatch.setenv("SMARTLAB_DML_DEVICES", "2")
    monkeypatch.setattr(ort, "InferenceSession", wrapped)
    monkeypatch.setattr(vision.time, "sleep", lambda s: None if s >= 1 else real_sleep(s))
    a = vision.Appearance(REID)
    assert a.engine.startswith("directml"), a.engine


@needs_model
def test_between_refreshes_only_touching_people_get_the_body_model():
    """Speed (lab 2026-10-14): with 8 people, re-ID ran for everyone every pass. Between full
    refreshes only the people touching someone need it."""
    a = vision.Appearance(REID)
    f = _frame()
    boxes = [(10, 10, 60, 120), (65, 12, 60, 118), (400, 10, 60, 120)]   # 0 and 1 touch, 2 far
    first = a.looks(f, boxes, now=100.0)                                # full refresh
    assert all(l.deep is not None for l in first)
    later = a.looks(f, boxes, now=100.4)                                # within DEEP_EVERY_S
    assert later[0].deep is not None and later[1].deep is not None and later[2].deep is None
    again = a.looks(f, boxes, now=100.0 + vision.Appearance.DEEP_EVERY_S + 0.1)
    assert all(l.deep is not None for l in again)                       # everyone refreshed again
