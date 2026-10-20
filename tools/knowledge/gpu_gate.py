"""
Camera-first GPU admission for the two assistants (owner, 2026-10-20) - ONE decision for both.

The GTX 1650 belongs to the security cameras. Measured 2026-10-19 13:38 with both cameras live:
an assistant answering on the GPU cut camera 1 from 7.0 to ~5 analyses/s, while on the CPU both
cameras stayed at 7.0. So the rule is simple and conservative:

  * any camera ANALYSING (stream LIVE or analysis rate > 0.5/s)  -> CPU, at once
  * a camera service that answers with something unexpected, or times out -> CPU (unknown = not safe)
  * all cameras idle (stream not live, rate 0) or their services not running (connection refused)
    for IDLE_S in a row, and enough free GPU memory                -> GPU
  * back to the GPU at most once per MIN_GPU_GAP_S after a switch to the CPU (no reload storms:
    every switch makes Ollama reload the model with the other num_gpu)

Limits, said plainly: an answer already running on the GPU when a camera comes live is not
pre-empted - it finishes (GPU answers take ~3 s; Ollama's own request timeout bounds it). The
model may also stay resident in GPU memory (idle, no compute) until the next answer reloads it
on the CPU; the cameras use ~0.6 of 4 GB, so that memory is not what they compete for.

The knowledge service (serve.py, 127.0.0.1:5199) owns the decision and serves it at /gpu-gate;
the portal backend asks there, so both assistants always pick the same device. If the portal
cannot reach it, it uses the CPU.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request

CAMERA_PORTS = (5100, 5101)          # tools/security_vision: camera 1, camera 2 (127.0.0.1 only)
IDLE_S = 120                         # cameras idle this long before the GPU is offered
MIN_GPU_GAP_S = 300                  # after a switch to the CPU, wait at least this long to go back
NEED_FREE_MB = 1800                  # qwen2.5:1.5b on the GPU ~1.3 GB + margin
LIVE_FPS = 0.5
CACHE_S = 5.0


def device_key(repo: str) -> str:
    """The cameras' /metrics need the device key: DEVICE_API_KEY from the environment or the repo .env."""
    k = os.environ.get("DEVICE_API_KEY", "")
    if k:
        return k
    try:
        for line in open(os.path.join(repo, ".env"), encoding="utf-8"):
            if line.startswith("DEVICE_API_KEY="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def camera_state(port: int, key: str, timeout: float = 1.5) -> dict:
    """{"port", "state": "live"|"idle"|"down"|"unknown", "fps", "gpu_free_mb"}; never raises."""
    out = {"port": port, "state": "unknown", "fps": None, "gpu_free_mb": None}
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/metrics", headers={"X-Device-Key": key})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            m = json.loads(r.read())
    except urllib.error.URLError as e:
        refused = isinstance(e.reason, ConnectionRefusedError) or "refused" in str(e.reason).lower()
        out["state"] = "down" if refused else "unknown"          # not running = not using the GPU
        return out
    except (OSError, ValueError, socket.timeout):
        return out
    fps = float((m.get("analysis") or {}).get("fps") or 0.0)
    live = (m.get("stream") or {}).get("state") == "LIVE" or fps > LIVE_FPS
    g = m.get("gpu") or {}
    free = (g["mem_total_mb"] - g["mem_used_mb"]) if g.get("mem_total_mb") and g.get("mem_used_mb") is not None else None
    out.update(state="live" if live else "idle", fps=round(fps, 2), gpu_free_mb=free)
    return out


class Gate:
    """The decision with its memory (hysteresis). `decide` is pure given `now` and the camera states."""

    def __init__(self) -> None:
        self.mode = "cpu"
        self.idle_since: float | None = None
        self.last_cpu_switch = -1e9
        self.reason = "start: CPU until the cameras are seen idle"
        self.changed_at = 0.0

    def decide(self, now: float, cams: list[dict]) -> str:
        busy = [c for c in cams if c["state"] in ("live", "unknown")]
        if busy:
            self.idle_since = None
            if self.mode != "cpu":
                self.mode, self.last_cpu_switch, self.changed_at = "cpu", now, now
            self.reason = "camera " + ", ".join(f"{c['port']} {c['state']}" for c in busy) + " - cameras first"
            return self.mode
        if self.idle_since is None:
            self.idle_since = now
        frees = [c["gpu_free_mb"] for c in cams if c.get("gpu_free_mb") is not None]
        if frees and min(frees) < NEED_FREE_MB:
            self.reason = f"cameras idle, but only {min(frees):.0f} MB GPU memory free"
            if self.mode != "cpu":
                self.mode, self.last_cpu_switch, self.changed_at = "cpu", now, now
            return self.mode
        if self.mode == "gpu":
            self.reason = "cameras idle"
            return self.mode
        idle_for, gap = now - self.idle_since, now - self.last_cpu_switch
        if idle_for >= IDLE_S and gap >= MIN_GPU_GAP_S:
            self.mode, self.changed_at, self.reason = "gpu", now, f"cameras idle for {idle_for:.0f} s"
        else:
            wait = max(IDLE_S - idle_for, MIN_GPU_GAP_S - gap)
            self.reason = f"cameras idle; GPU offered in {wait:.0f} s if they stay idle"
        return self.mode


_GATE, _LOCK = Gate(), threading.Lock()
_LAST: dict = {"at": 0.0, "body": None}


def current(repo: str, now: float | None = None) -> dict:
    """The shared decision (cached CACHE_S): {"device": "gpu"|"cpu", "reason", "cameras", "since"}."""
    with _LOCK:
        t = time.time() if now is None else now
        if _LAST["body"] is not None and t - _LAST["at"] < CACHE_S:
            return _LAST["body"]
        key = device_key(repo)
        cams = [camera_state(p, key) for p in CAMERA_PORTS]
        mode = _GATE.decide(t, cams)
        body = {"device": mode, "reason": _GATE.reason, "cameras": cams,
                "since": _GATE.changed_at or None, "checked_at": t}
        _LAST.update(at=t, body=body)
        return body


def use_gpu(cfg: dict) -> bool:
    """For this service's own LLM calls. llm_gpu_policy: "cpu" (default, as before) | "auto" (this gate)."""
    if cfg.get("llm_gpu_policy", "cpu") != "auto":
        return not cfg.get("llm_on_cpu", True)
    return current(os.path.abspath(cfg.get("repo_abs") or os.path.join(os.path.dirname(__file__), "..", "..")))["device"] == "gpu"
