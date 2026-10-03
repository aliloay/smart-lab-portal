"""
Lab PC control from the admin's master PC (System 1): screen view state.

Screen view is pull-based and only while staff watch: the staff page asks
for the latest frame; that marks a viewer; the PC agent sees "mirror" in
its poll reply and uploads a frame about twice a second; when nobody has
asked for VIEWER_TIMEOUT the agent stops on its own. Frames live in memory
only (one per PC, overwritten), never in the database or on disk.

Single backend process (uvicorn without --workers), so a module-level dict
is shared by every request.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

VIEWER_TIMEOUT_S = 6.0      # agent stops uploading this long after the last look
FRAME_MAX_AGE_S = 5.0       # an older frame is not shown (agent stopped / PC off)
MAX_FRAME_BYTES = 1_500_000

_lock = threading.Lock()
_viewers: dict[int, float] = {}                 # device_id -> last time staff looked
_frames: dict[int, tuple[bytes, float]] = {}    # device_id -> (jpeg, received at)


def touch_viewer(device_id: int) -> None:
    with _lock:
        _viewers[device_id] = time.monotonic()


def stop_viewer(device_id: int) -> None:
    with _lock:
        _viewers.pop(device_id, None)
        _frames.pop(device_id, None)


def is_watched(device_id: int) -> bool:
    with _lock:
        t = _viewers.get(device_id)
    return t is not None and time.monotonic() - t < VIEWER_TIMEOUT_S


def put_frame(device_id: int, jpeg: bytes) -> None:
    with _lock:
        _frames[device_id] = (jpeg, time.monotonic())


def latest_frame(device_id: int) -> Optional[bytes]:
    with _lock:
        f = _frames.get(device_id)
    if f is None or time.monotonic() - f[1] > FRAME_MAX_AGE_S:
        return None
    return f[0]


def reset() -> None:
    """Tests only."""
    with _lock:
        _viewers.clear()
        _frames.clear()
