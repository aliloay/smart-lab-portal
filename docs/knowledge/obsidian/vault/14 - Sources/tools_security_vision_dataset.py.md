---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/security_vision/dataset.py"
source_hash: "e9129abc5a9e7e66a8b959f267632c015708c6acdf6541cfc0b17707d791fe5b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/dataset.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_test_recorder.py]] - tests
- [[tools_security_vision_security_vision.py]] - imports

```py
"""
Training pictures for teaching the camera to recognise the robots (UR5e,
Fanuc ...): while collecting is ON, a plain frame is saved every interval -
but only when the picture changed enough since the last saved one (a robot
moved, someone walked by), so the set is varied, not 500 copies of one view.

    dataset/images/<DEVICE>_<YYYY-MM-DD_HH-MM-SS>_<n>.jpg

Labelling (a box + class per robot) and training come after; nothing here
decides anything. Files stay on this laptop, never deleted here.
"""
from __future__ import annotations

import glob
import os
import threading
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np


def change(a: np.ndarray, b: np.ndarray) -> float:
    """How different two pictures are: mean absolute difference (0-255) of
    small grey copies - cheap and robust to noise."""
    sa = cv2.cvtColor(cv2.resize(a, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.int16)
    sb = cv2.cvtColor(cv2.resize(b, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.int16)
    return float(np.abs(sa - sb).mean())


class Collector:
    def __init__(self, device: str, folder: str, *, interval_s: float = 2.0,
                 min_change: float = 4.0, max_pictures: int = 1000):
        self.device = device
        self.folder = os.path.join(folder, "images")
        self.interval_s, self.min_change, self.max_pictures = interval_s, min_change, max_pictures
        self._lock = threading.Lock()
        self.on = False
        self.started_by = ""
        self.saved_this_run = 0
        self.skipped_same = 0
        self._last: Optional[np.ndarray] = None
        self._last_t = 0.0
        os.makedirs(self.folder, exist_ok=True)

    def total(self) -> int:
        return len(glob.glob(os.path.join(self.folder, "*.jpg")))

    def status(self) -> dict:
        return {"collecting": self.on, "started_by": self.started_by, "saved_this_run": self.saved_this_run,
                "skipped_unchanged": self.skipped_same, "total": self.total(),
                "interval_s": self.interval_s, "max_pictures": self.max_pictures}

    def start(self, by: str = "") -> dict:
        with self._lock:
            if self.total() >= self.max_pictures:
                return {"ok": False, "error": f"{self.max_pictures} pictures already - label and train first"}
            self.on, self.started_by, self.saved_this_run, self.skipped_same = True, by, 0, 0
            self._last, self._last_t = None, 0.0
            return {"ok": True}

    def stop(self) -> dict:
        with self._lock:
            self.on = False
            return {"ok": True, "saved": self.saved_this_run}

    def offer(self, frame: np.ndarray, now: Optional[float] = None) -> Optional[str]:
        """Called with every new plain frame; saves it when due and different
        enough. Returns the saved file name, or None."""
        now = now or time.time()
        with self._lock:
            if not self.on or now - self._last_t < self.interval_s:
                return None
            self._last_t = now
            if self._last is not None and change(self._last, frame) < self.min_change:
                self.skipped_same += 1
                return None
            if self.total() >= self.max_pictures:
                self.on = False
                return None
            name = f"{self.device}_{datetime.now():%Y-%m-%d_%H-%M-%S}_{self.saved_this_run:04d}.jpg"
            cv2.imwrite(os.path.join(self.folder, name), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            self._last = frame.copy()
            self.saved_this_run += 1
            return name

```
