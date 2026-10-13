"""
Person re-identification (vision.Appearance): engine choice, fallbacks, and the
2026-10-13 bug - cv2.dnn gave unrelated embeddings once the number of people
in a frame changed. Offline: no camera, portal or database.
"""
import os

import numpy as np
import pytest

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
