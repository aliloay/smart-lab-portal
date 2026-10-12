"""
Detector engine selection (vision.Yolo26Detector): which engine runs, the
fallback order, and that every engine returns the same kind of result.
Offline: no camera, no portal, no database.
"""
import os

import numpy as np
import pytest

import vision

MODEL = os.path.join(os.path.dirname(__file__), "models", "yolo26s.onnx")
needs_model = pytest.mark.skipif(not os.path.isfile(MODEL), reason="yolo26s.onnx not downloaded")


@needs_model
def test_forced_cpu_engine(monkeypatch):
    monkeypatch.setenv("SMARTLAB_DETECTOR", "onnxruntime")
    d = vision.Yolo26Detector(MODEL)
    assert d.engine == "onnxruntime" and d._ov is None and d.sess is not None


@needs_model
def test_openvino_failure_falls_back_to_onnxruntime(monkeypatch):
    import openvino
    monkeypatch.setenv("SMARTLAB_DETECTOR", "openvino")

    def broken(*a, **k):
        raise RuntimeError("simulated OpenVINO failure")
    monkeypatch.setattr(openvino.Core, "compile_model", broken)
    d = vision.Yolo26Detector(MODEL)
    assert d.engine == "onnxruntime"


@needs_model
def test_gpu_unavailable_falls_back(monkeypatch):
    import onnxruntime as ort
    monkeypatch.setenv("SMARTLAB_DETECTOR", "gpu")
    monkeypatch.setattr(ort, "get_available_providers", lambda: ["CPUExecutionProvider"])
    d = vision.Yolo26Detector(MODEL)
    assert d.engine in ("openvino-cpu", "onnxruntime")


@needs_model
@pytest.mark.parametrize("engine", ["onnxruntime", "openvino", "gpu"])
def test_every_engine_handles_empty_and_odd_frames(monkeypatch, engine):
    monkeypatch.setenv("SMARTLAB_DETECTOR", engine)
    d = vision.Yolo26Detector(MODEL, conf=0.35)
    for img in (np.zeros((540, 960, 3), np.uint8),          # black: no people
                np.full((300, 1200, 3), 255, np.uint8),     # very wide
                np.zeros((40, 30, 3), np.uint8)):           # tiny
        out = d.detect(img)
        assert isinstance(out, list)
        for x in out:
            bx, by, bw, bh = x.box
            assert 0 <= bx <= img.shape[1] and 0 <= by <= img.shape[0] and bw >= 0 and bh >= 0


def test_missing_model_raises_clearly():
    with pytest.raises(Exception):
        vision.Yolo26Detector(os.path.join(os.path.dirname(__file__), "models", "does_not_exist_yolo26.onnx"))
