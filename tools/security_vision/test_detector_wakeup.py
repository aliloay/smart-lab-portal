"""The GPU wakes slowly from idle: a slow first timing must not put the detector on the CPU
for the whole session (lab 2026-10-14: openvino-cpu at start-up, 23 ms on the GPU minutes later)."""
import os
import time as _time

import pytest

import vision

MODEL = os.path.join(os.path.dirname(__file__), "models", "yolo26s.onnx")
real_sleep = _time.sleep


@pytest.mark.skipif(not os.path.isfile(MODEL), reason="model not downloaded")
def test_slow_first_timing_still_chooses_the_gpu(monkeypatch):
    import onnxruntime as ort
    if "DmlExecutionProvider" not in ort.get_available_providers():
        pytest.skip("no DirectML on this machine")
    real = ort.InferenceSession

    class SlowAtFirst:
        def __init__(self, s): self.s, self.n = s, 0
        def run(self, *a, **k):
            self.n += 1
            if self.n <= 4:                      # the first warm-up + timed runs: GPU still waking
                real_sleep(0.12)
            return self.s.run(*a, **k)
        def __getattr__(self, name): return getattr(self.s, name)

    def wrapped(path, *a, providers=None, **k):
        s = real(path, *a, providers=providers, **k)
        dml = providers and any((p[0] if isinstance(p, tuple) else p) == "DmlExecutionProvider" for p in providers)
        return SlowAtFirst(s) if dml else s
    monkeypatch.setenv("SMARTLAB_DETECTOR", "gpu")
    monkeypatch.setattr(ort, "InferenceSession", wrapped)
    monkeypatch.setattr(vision.time, "sleep", lambda s: None if s >= 1 else real_sleep(s))
    d = vision.make_detector(MODEL, size=640)
    assert d.engine.startswith("directml"), d.engine
