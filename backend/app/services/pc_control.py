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
_opts: dict[int, dict] = {}                     # device_id -> viewer's choice: monitor, quality, fps
DEFAULT_OPTS = {"monitor": 0, "quality": 60, "fps": 2.0}
# Change signal for the agents' long-poll (/equipment/pc/wait): a counter per PC plus one for
# everything that concerns every PC (a share starting/stopping). Bumped whenever something the
# agent must act on changes, so an idle agent wakes within ~0.1 s instead of its next 1 s poll.
_versions: dict[int, int] = {}
_global_version = [0]


def signal(device_id: Optional[int] = None) -> None:
    with _lock:
        if device_id is None:
            _global_version[0] += 1
        else:
            _versions[device_id] = _versions.get(device_id, 0) + 1


def version(device_id: int) -> tuple[int, int]:
    with _lock:
        return _global_version[0], _versions.get(device_id, 0)


def touch_viewer(device_id: int, opts: Optional[dict] = None) -> None:
    with _lock:
        t = _viewers.get(device_id)
        newly = t is None or time.monotonic() - t >= VIEWER_TIMEOUT_S
        _viewers[device_id] = time.monotonic()
        changed = opts is not None and _opts.get(device_id) != {**DEFAULT_OPTS, **opts}
        if opts is not None:
            _opts[device_id] = {**DEFAULT_OPTS, **opts}
        if newly or changed:                          # a viewer appeared / changed monitor or quality
            _versions[device_id] = _versions.get(device_id, 0) + 1


def view_opts(device_id: int) -> dict:
    with _lock:
        return dict(_opts.get(device_id, DEFAULT_OPTS))


def stop_viewer(device_id: int) -> None:
    with _lock:
        _viewers.pop(device_id, None)
        _frames.pop(device_id, None)
        _versions[device_id] = _versions.get(device_id, 0) + 1


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
        _broadcast.update(active=False, by=None, by_id=None, source=None, since=None, title="", targets=None)
        _opts.clear()
        _versions.clear()
        _global_version[0] = 0
        _bframe[0], _bframe[1] = None, 0.0


# ------------------------------------------------ admin -> students broadcast ---
# One presentation at a time. Frames come from the admin's browser (screen capture, needs HTTPS)
# or from the agent on the admin's master PC. In memory only, like the screen view.
BROADCAST_FRAME_MAX_AGE_S = 6.0
_broadcast: dict = {"active": False, "by": None, "by_id": None, "source": None, "since": None, "title": "",
                    "targets": None}                   # None = every lab PC; else a list of device ids
_bframe: list = [None, 0.0]                     # [jpeg, received at]


def broadcast_start(by: str, by_id: int, source: str, title: str = "", targets: Optional[list] = None) -> dict:
    with _lock:
        _broadcast.update(active=True, by=by, by_id=by_id, source=source, since=time.time(), title=title[:80],
                          targets=sorted(set(targets)) if targets else None)
        _bframe[0], _bframe[1] = None, 0.0
        _global_version[0] += 1
        return dict(_broadcast)


def broadcast_stop() -> dict:
    with _lock:
        _broadcast.update(active=False, source=None)
        _bframe[0], _bframe[1] = None, 0.0
        _global_version[0] += 1
        return dict(_broadcast)


def broadcast_state() -> dict:
    with _lock:
        s = dict(_broadcast)
        s["has_frame"] = _bframe[0] is not None and time.monotonic() - _bframe[1] < BROADCAST_FRAME_MAX_AGE_S
        return s


def broadcast_put(jpeg: bytes) -> bool:
    with _lock:
        if not _broadcast["active"]:
            return False
        _bframe[0], _bframe[1] = jpeg, time.monotonic()
        return True


def broadcast_frame() -> Optional[bytes]:
    with _lock:
        if not _broadcast["active"] or _bframe[0] is None or time.monotonic() - _bframe[1] > BROADCAST_FRAME_MAX_AGE_S:
            return None
        return _bframe[0]


def broadcast_reset() -> None:
    broadcast_stop()
