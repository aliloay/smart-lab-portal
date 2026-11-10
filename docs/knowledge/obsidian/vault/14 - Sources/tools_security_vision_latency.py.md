---
type: "source-mirror"
source_kind: "source-code"
source_path: "tools/security_vision/latency.py"
source_hash: "e0546a6a69a21a01fad0f82d6a84529dcb72d46464d8f6685f97c1638cbc0c62"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `tools/security_vision/latency.py` - edit the original in the repository, not this note.

Systems: [[SecurityCam (vision)]]

## Related
- [[tools_security_vision_test_load_sampler.py]] - tests
- [[backend_app_api_routes_security.py]] - mentioned by docs
- [[docs_LATENCY.md]] - mentioned by docs
- [[tools_security_vision_security_vision.py]] - imports

```py
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


class _LoadSampler:
    """CPU, memory and graphics-card load, sampled in the background every PERIOD_S.

    Fixed 2026-10-18: process_load() made a NEW psutil.Process on every call, and cpu_percent() of a
    new object is always 0.0 - /metrics said 0 % CPU for weeks. One object, sampled on a fixed period,
    gives real numbers that do not depend on how often /metrics is asked. private_mb (private bytes)
    is what memory growth is judged by: the working set (rss_mb) can be trimmed by Windows.
    GPU: nvidia-smi (whole card - the detector, the re-ID model and anything else on it)."""
    PERIOD_S = 5.0
    GPU_EVERY = 2                      # nvidia-smi every 2nd sample (10 s): it costs ~60 ms of CPU

    def __init__(self):
        self.snapshot: Optional[dict] = None
        self.gpu: Optional[dict] = None
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> bool:
        with self._lock:
            if self._started:
                return True
            try:
                import psutil
            except ImportError:
                return False
            self._proc = psutil.Process()
            self._proc.cpu_percent(None)                 # prime both counters (first reading is 0)
            psutil.cpu_percent(None)
            self._started = True
        threading.Thread(target=self._loop, daemon=True, name="load-sampler").start()
        return True

    def _loop(self):
        n = 0
        while True:
            time.sleep(self.PERIOD_S)
            self.sample(gpu=n % self.GPU_EVERY == 0)
            n += 1

    def sample(self, gpu: bool = False):
        """One reading (CPU since the previous reading of this same object)."""
        import psutil
        with self._lock:
            try:
                mi = self._proc.memory_info()
                self.snapshot = {
                    "cpu_percent": round(self._proc.cpu_percent(None), 1),
                    "rss_mb": round(mi.rss / 1e6),
                    "private_mb": round(getattr(mi, "private", mi.vms) / 1e6),
                    "threads": self._proc.num_threads(),
                    "system_cpu_percent": round(psutil.cpu_percent(None), 1),
                    "system_mem_percent": round(psutil.virtual_memory().percent, 1),
                    "cores": psutil.cpu_count(), "sampled_at": round(time.time(), 1)}
            except Exception:
                pass
        if gpu:
            self.gpu = nvidia_smi()
        return self.snapshot


def nvidia_smi() -> Optional[dict]:
    """Whole-card load from nvidia-smi, or None (not an NVIDIA card / tool missing / timeout)."""
    import subprocess
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,pstate",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip().splitlines()
        name, util, used, total, temp, pstate = [x.strip() for x in out[0].split(",")]
        return {"name": name, "util_percent": float(util), "mem_used_mb": float(used),
                "mem_total_mb": float(total), "temp_c": float(temp), "pstate": pstate,
                "sampled_at": round(time.time(), 1)}
    except Exception:
        return None


_SAMPLER = _LoadSampler()


def process_load() -> Optional[dict]:
    """CPU % (all cores = 100 x cores) and memory of this process (sampled every 5 s), if psutil
    is installed. None until the first sample is taken."""
    if not _SAMPLER.start():
        return None
    return _SAMPLER.snapshot


def gpu_load() -> Optional[dict]:
    _SAMPLER.start()
    return _SAMPLER.gpu

```
