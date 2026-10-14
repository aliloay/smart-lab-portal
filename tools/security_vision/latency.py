"""
Stage timing for the camera pipeline (measured, never assumed):

    capture   frame arrival rate and gaps, time spent in read()/decode
    analysis  age of the frame when analysis starts, detector ms, tracking +
              naming ms, zones ms, whole pass ms, frames skipped (the
              latest-frame policy: frames that arrived while a pass was
              running are never analysed - by design, so nothing queues)
    render    age of the frame when the annotated JPEG is made, encode ms
    serve     age of the frame when /frame.jpg is sent

Ages are measured from the moment the frame was RECEIVED from the RTSP
stream. The camera's own encode + network delay (glass to laptop) cannot be
seen in software: measure it with a ms clock in view (docs/LATENCY.md).

Rolling windows (last N samples); p50 / p95 / max. Thread-safe.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional


class Rolling:
    def __init__(self, n: int = 300):
        self.v: deque = deque(maxlen=n)
        self.lock = threading.Lock()

    def add(self, x: float):
        with self.lock:
            self.v.append(float(x))

    def summary(self, nd: int = 1) -> Optional[dict]:
        with self.lock:
            v = sorted(self.v)
        if not v:
            return None
        q = lambda p: v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))]
        return {"p50": round(q(0.5), nd), "p95": round(q(0.95), nd), "max": round(v[-1], nd), "n": len(v)}


class Rate:
    """Events per second over the last window_s."""
    def __init__(self, window_s: float = 10.0):
        self.window_s = window_s
        self.t: deque = deque()
        self.lock = threading.Lock()

    def tick(self, now: Optional[float] = None):
        now = now or time.time()
        with self.lock:
            self.t.append(now)
            while self.t and now - self.t[0] > self.window_s:
                self.t.popleft()

    def per_s(self, now: Optional[float] = None) -> float:
        now = now or time.time()
        with self.lock:
            while self.t and now - self.t[0] > self.window_s:
                self.t.popleft()
            if len(self.t) < 2:
                return 0.0
            return round((len(self.t) - 1) / max(1e-6, self.t[-1] - self.t[0]), 2)


class PipelineMetrics:
    def __init__(self):
        self.started = time.time()
        self.input = Rate()
        self.gap_ms = Rolling()
        self.read_ms = Rolling()
        self.analysis = Rate()
        self.age_at_analysis_ms = Rolling()
        self.detect_ms = Rolling()
        self.track_ms = Rolling()
        self.zones_ms = Rolling()
        self.pass_ms = Rolling()
        self.render = Rate()
        self.age_at_render_ms = Rolling()
        self.encode_ms = Rolling()
        self.age_at_serve_ms = Rolling()
        self.frames_in = 0
        self.frames_analysed = 0
        self.frames_skipped = 0
        self.reconnects = 0
        self.open_failures = 0          # the stream could not be opened at all (camera off / wrong address)
        self._last_seq = None
        self._last_arrival = None
        self.lock = threading.Lock()

    def frame_in(self, now: float, read_ms: float):
        with self.lock:
            self.frames_in += 1
            if self._last_arrival is not None:
                self.gap_ms.add((now - self._last_arrival) * 1000)
            self._last_arrival = now
        self.input.tick(now)
        self.read_ms.add(read_ms)

    def analysed(self, seq: int, age_ms: float, detect_ms: float, track_ms: float, zones_ms: float,
                 pass_ms: float, now: Optional[float] = None):
        with self.lock:
            if self._last_seq is not None and seq > self._last_seq + 1:
                self.frames_skipped += seq - self._last_seq - 1
            self._last_seq = seq
            self.frames_analysed += 1
        self.analysis.tick(now)
        for r, v in ((self.age_at_analysis_ms, age_ms), (self.detect_ms, detect_ms),
                     (self.track_ms, track_ms), (self.zones_ms, zones_ms), (self.pass_ms, pass_ms)):
            r.add(v)

    def summary(self) -> dict:
        return {
            "uptime_s": round(time.time() - self.started),
            "capture": {"fps": self.input.per_s(), "gap_ms": self.gap_ms.summary(),
                        "read_ms": self.read_ms.summary(), "frames": self.frames_in,
                        "reconnects": self.reconnects, "open_failures": self.open_failures},
            "analysis": {"fps": self.analysis.per_s(), "frame_age_ms": self.age_at_analysis_ms.summary(0),
                         "detect_ms": self.detect_ms.summary(0), "track_ms": self.track_ms.summary(1),
                         "zones_ms": self.zones_ms.summary(1), "pass_ms": self.pass_ms.summary(0),
                         "frames": self.frames_analysed, "skipped_latest_frame_policy": self.frames_skipped},
            "render": {"fps": self.render.per_s(), "frame_age_ms": self.age_at_render_ms.summary(0),
                       "encode_ms": self.encode_ms.summary(1)},
            "serve": {"frame_age_ms": self.age_at_serve_ms.summary(0)},
        }


def process_load() -> Optional[dict]:
    """CPU % (all cores = 100 x cores) and memory of this process, if psutil is installed."""
    try:
        import psutil
    except ImportError:
        return None
    p = psutil.Process()
    return {"cpu_percent": p.cpu_percent(interval=None), "rss_mb": round(p.memory_info().rss / 1e6),
            "threads": p.num_threads(), "system_cpu_percent": psutil.cpu_percent(interval=None),
            "cores": psutil.cpu_count()}
