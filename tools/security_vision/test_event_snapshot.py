"""Alert snapshots stay fresh while nobody watches the camera (2026-11-11, Gemini audit FG-02). With the idle render at
1 picture a second, the stored annotated picture can be up to 1 s old; an alert then draws the newest frame itself."""
import threading
import time
import types

import cv2
import numpy as np

import security_vision as sv
from vision import ZoneWatcher


def frame_with(value: int):
    f = np.full((120, 160, 3), value, np.uint8)
    return f


def service(latest_frame, latest_at, stored_jpeg, stored_at):
    s = sv.Service.__new__(sv.Service)                 # no camera, no network, no models
    s.lock = threading.Lock()
    s.tracks, s.cfg, s.door_open = [], {"zones": []}, None
    s.zones = ZoneWatcher()
    s.camera = types.SimpleNamespace(latest=lambda: (latest_frame, latest_at))
    s.jpeg, s.jpeg_at = stored_jpeg, stored_at
    return s


def decoded_mean(jpeg: bytes) -> float:
    return float(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR).mean())


def test_a_stale_stored_picture_is_replaced_by_the_newest_frame():
    now = time.time()
    old = cv2.imencode(".jpg", frame_with(20))[1].tobytes()           # drawn 0.9 s ago (idle render)
    s = service(frame_with(200), now - 0.05, old, now - 0.9)
    jpeg, at = s.snapshot_now(old, now - 0.9, now)
    assert at == now - 0.05 and abs(decoded_mean(jpeg) - 200) < 10   # the new frame, not the old picture


def test_a_fresh_stored_picture_is_used_as_is():
    now = time.time()
    fresh = cv2.imencode(".jpg", frame_with(90))[1].tobytes()
    s = service(frame_with(200), now, fresh, now - 0.1)
    assert s.snapshot_now(fresh, now - 0.1, now) == (fresh, now - 0.1)


def test_no_recent_frame_keeps_the_stored_picture_and_its_age():
    now = time.time()
    old = cv2.imencode(".jpg", frame_with(20))[1].tobytes()
    s = service(frame_with(200), now - 30, old, now - 2)              # camera stalled for 30 s
    assert s.snapshot_now(old, now - 2, now) == (old, now - 2)
    s2 = service(None, 0.0, None, 0.0)                                 # nothing at all yet
    assert s2.snapshot_now(None, 0.0, now) == (None, 0.0)


def test_the_camera_frame_itself_is_never_drawn_on():
    now = time.time()
    f = frame_with(200)
    s = service(f, now, None, 0.0)
    s.cfg = {"zones": [], "door": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.5}}
    s.snapshot_now(None, 0.0, now)
    assert int(f.min()) == 200 and int(f.max()) == 200                # drawing happened on a copy
