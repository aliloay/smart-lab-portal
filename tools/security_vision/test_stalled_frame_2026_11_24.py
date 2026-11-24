"""Lab 24 Nov 2026: a frame that FFmpeg hands back after its read timeout is an old buffer, not a live picture."""
import time

import numpy as np

import security_vision as sv


class Cap:
    def __init__(self, delays):
        self.delays = list(delays)

    def read(self):
        d = self.delays.pop(0) if self.delays else 0.0
        time.sleep(d)
        return (True, np.zeros((4, 4, 3), np.uint8)) if d is not None and self.delays else (False, None)


def test_stalled_frame_is_dropped(monkeypatch):
    cam = sv.Camera("rtsp://x/stream", 960, start=False)
    monkeypatch.setattr(sv.Camera, "STALE_S", 0.2)
    monkeypatch.setattr(sv.Camera, "LOST_S", 0.6)
    seen = []
    monkeypatch.setattr(cam, "_store", lambda f, ms=0.0: seen.append(ms))
    cam._stream(Cap([0.0, 0.0, 0.3, 0.3, 0.0]))
    assert len(seen) == 2 and max(seen) < 200
