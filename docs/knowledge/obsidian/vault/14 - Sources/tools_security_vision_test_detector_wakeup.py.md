---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_detector_wakeup.py"
source_hash: "eb86b071c1f49debd84b06a9e782548d1465a0b2bee3f6b922573fc500660931"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/test_detector_wakeup.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_vision.py]] - tests

```py
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
        def __init__(self, s): self.s, self.n, self.out = s, 0, None
        def run(self, *a, **k):
            # Tests the RETRY logic, not the GPU's speed: slow at first, then instant (the first
            # real result reused) - a busy GPU (live camera running) no longer fails the test.
            self.n += 1
            if self.n <= 4:
                real_sleep(0.12 if True else 0.03)
                if self.out is None:
                    self.out = self.s.run(*a, **k)
                return self.out
            return self.out if self.out is not None else self.s.run(*a, **k)
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

```
