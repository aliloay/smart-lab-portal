---
type: "source-mirror"
source_kind: "test-code"
source_path: "tools/security_vision/test_camera_reconnect.py"
source_hash: "28027486cba69ba3ac3c657ef8c216bfd8709a7e622a237568564e83018a1a17"
generated: true
updated: "2026-11-04T00:02:39+02:00"
redactions: ["rtsp-credentials"]
---
> Read-only mirror of `tools/security_vision/test_camera_reconnect.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_security_vision.py]] - tests

```py
"""2026-10-18: the camera reader reconnects with exponential backoff, never hangs on a dead stream,
keeps one connection at a time and reports an honest state. No real camera: a fake capture."""
import threading
import time

import numpy as np

import security_vision as sv


class FakeCap:
    """Delivers `frames` frames, then nothing (a camera that stops sending)."""
    opened = 0
    alive = 0

    def __init__(self, ok=True, frames=5):
        self._ok, self.left = ok, frames
        if ok:
            FakeCap.opened += 1
            FakeCap.alive += 1

    def isOpened(self):
        return self._ok

    def read(self):
        if self.left > 0:
            self.left -= 1
            return True, np.zeros((72, 128, 3), np.uint8)
        return False, None

    def set(self, *a):
        pass

    def release(self):
        if self._ok:
            FakeCap.alive -= 1


def test_backoff_doubles_and_is_capped():
    cam = sv.Camera("rtsp://x", 960, start=False)
    waits = []
    for n in range(1, 9):
        cam.fails_in_row = n
        waits.append(cam.backoff_s())
    assert 0.8 <= waits[0] <= 1.2 and 1.6 <= waits[1] <= 2.4 and 3.2 <= waits[2] <= 4.8
    assert max(waits) <= sv.Camera.BACKOFF_MAX_S * 1.2 and waits[-1] >= sv.Camera.BACKOFF_MAX_S * 0.8


def test_failed_opens_go_reconnecting_then_offline_and_count(monkeypatch):
    cam = sv.Camera("rtsp://x", 960, metrics=sv.PipelineMetrics(), start=False)
    for _ in range(sv.Camera.OFFLINE_AFTER):
        cam._failed_open("could not open the stream")
    st = cam.status()
    assert st["state"] == "OFFLINE" and cam.metrics.open_failures == sv.Camera.OFFLINE_AFTER and not cam.ok
    assert "rtsp" not in st["last_error"]                       # never the address


def test_stream_that_stops_is_ended_quickly_and_reconnected_once(monkeypatch):
    monkeypatch.setattr(sv.Camera, "LOST_S", 0.3)
    monkeypatch.setattr(sv.Camera, "BACKOFF_MIN_S", 0.05)
    FakeCap.opened = FakeCap.alive = 0
    monkeypatch.setattr(sv.Camera, "_open", lambda self: FakeCap(frames=5))
    cam = sv.Camera("rtsp://x", 960, metrics=sv.PipelineMetrics())
    deadline = time.time() + 5
    while time.time() < deadline and cam.metrics.reconnects < 2:
        time.sleep(0.05)
    assert cam.metrics.reconnects >= 2                         # lost, reconnected, lost again
    assert FakeCap.alive <= 1                                  # never two connections at once
    assert cam.seq >= 10                                       # frames came in on each connection


def test_status_reports_stale_when_frames_stop(monkeypatch):
    cam = sv.Camera("rtsp://x", 960, start=False)
    cam._store(np.zeros((72, 128, 3), np.uint8))
    assert cam.status()["state"] == "STREAMING"
    cam.at -= sv.Camera.STALE_S + 0.5
    assert cam.status()["state"] == "STALE"


def test_rtsp_open_sets_ffmpeg_timeouts(monkeypatch):
    seen = {}

    class Rec:
        def __init__(self, *a):
            seen["args"] = a

    monkeypatch.setattr(sv.cv2, "VideoCapture", Rec)
    sv.Camera("[REDACTED:rtsp-credentials]10.0.0.1:554/stream2", 960, start=False)._open()
    args = seen["args"]
    assert args[1] == sv.cv2.CAP_FFMPEG and sv.cv2.CAP_PROP_OPEN_TIMEOUT_MSEC in args[2]
    assert sv.cv2.CAP_PROP_READ_TIMEOUT_MSEC in args[2]

```
