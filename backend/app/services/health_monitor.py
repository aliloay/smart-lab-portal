"""
Background service health monitor (2026-10-17).

Network checks (face server, Ollama, n8n, knowledge service, ESP32-CAM, security-camera services)
used to run INSIDE the /system/services request, one after another with 1.2 s timeouts. Here they
run in a daemon thread every CHECK_S, in parallel, and requests only read the cache. Each entry
keeps the last check, the last success, latency, the failure reason and how many checks in a row
failed - so a page can say "offline since 10:42 (ConnectError)" instead of only "offline".

A failing check never raises out of the thread; the portal keeps working without it.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional

CHECK_S = 10.0
TIMEOUT_S = 1.5

# Troubleshooting guidance per check - what to look at first.
GUIDANCE = {
    "face": "Start the face server: launch.bat opens it (firmware/face_server). Port 5000 on this laptop.",
    "ai": "Ollama is not answering: start the Ollama app (tray icon) or run `ollama serve`.",
    "n8n": "n8n container: `docker compose --profile automation up -d n8n` (only when automation is configured).",
    "knowledge": "Knowledge service: launch.bat starts `py tools/knowledge/serve.py` (port 5199, needs config.json).",
    "entry_camera": "ESP32-CAM at the door: check its power and Wi-Fi (CAMERA_URL in .env).",
    "security_camera": "Camera service: tools/security_vision/start_security_vision.bat; check the camera's RTSP address in camera.env.",
    "robot": "Collector: tools/robot_monitor/start_ur5e_monitor.bat or start_fanuc_monitor.bat; check the robot's cable and IP.",
    "pc": "PC agent not reporting: is the PC on and signed in, and pc_agent running in the user session?",
    "door": "Master ESP32: check its power and Wi-Fi; it reports every few seconds.",
    "environment": "Environment node: check its power and Wi-Fi.",
    "database": "PostgreSQL container: `docker compose ps db`; the API cannot work without it.",
}

_lock = threading.Lock()
_state: dict[str, dict] = {}
_checks: dict[str, tuple[str, Callable[[], tuple[bool, str]]]] = {}
_thread: Optional[threading.Thread] = None


def _http(url: str, headers: Optional[dict] = None, ok=lambda c: c < 500) -> Callable[[], tuple[bool, str]]:
    def run() -> tuple[bool, str]:
        import httpx
        r = httpx.get(url, headers=headers or {}, timeout=TIMEOUT_S)
        return ok(r.status_code), f"HTTP {r.status_code}"
    return run


def register_defaults() -> None:
    from app.core.config import settings
    _checks.clear()
    _checks["face"] = ("Face server", _http(settings.FACE_SERVER_URL.rstrip("/") + "/health"))
    if settings.OLLAMA_URL:
        _checks["ai"] = ("AI (local model, Ollama)", _http(settings.OLLAMA_URL.rstrip("/") + "/api/tags"))
    _checks["n8n"] = ("Automation (n8n)", _http("http://n8n:5678/healthz"))
    if settings.KB_SERVICE_KEY:
        _checks["knowledge"] = ("Project knowledge service", _http(settings.KB_SERVICE_URL.rstrip("/") + "/status",
                                                                     {"X-KB-Key": settings.KB_SERVICE_KEY}, lambda c: c == 200))
    _checks["entry_camera"] = ("Door camera (ESP32-CAM)", _http(settings.CAMERA_URL.rstrip("/") + "/status", ok=lambda c: c == 200))


def check_once() -> None:
    def one(key: str):
        name, fn = _checks[key]
        t0 = time.perf_counter()
        try:
            ok, why = fn()
        except Exception as e:                       # unreachable / timeout: the reason is the exception class
            ok, why = False, e.__class__.__name__
        ms = round((time.perf_counter() - t0) * 1000, 1)
        now = datetime.now(timezone.utc)
        with _lock:
            prev = _state.get(key, {})
            fails = 0 if ok else prev.get("consecutive_failures", 0) + 1
            _state[key] = {"key": key, "name": name, "state": "ONLINE" if ok else "OFFLINE",
                           "latency_ms": ms if ok else None, "detail": why, "last_check": now,
                           "last_ok": now if ok else prev.get("last_ok"),
                           "failing_since": None if ok else (prev.get("failing_since") or now),
                           "consecutive_failures": fails, "guidance": None if ok else GUIDANCE.get(key)}
    with ThreadPoolExecutor(max_workers=max(1, len(_checks))) as ex:
        list(ex.map(one, list(_checks)))


def start() -> None:
    global _thread
    if _thread is not None:
        return
    register_defaults()

    def loop():
        while True:
            try:
                check_once()
            except Exception:                        # never let monitoring take anything down
                pass
            time.sleep(CHECK_S)
    _thread = threading.Thread(target=loop, daemon=True, name="health-monitor")
    _thread.start()


def snapshot() -> list[dict]:
    """Cached results; a check that has not run yet is UNKNOWN (never assumed fine)."""
    with _lock:
        out = []
        for key, (name, _fn) in _checks.items():
            s = _state.get(key)
            out.append(dict(s) if s else {"key": key, "name": name, "state": "UNKNOWN", "latency_ms": None,
                                          "detail": "not checked yet", "last_check": None, "last_ok": None,
                                          "failing_since": None, "consecutive_failures": 0, "guidance": None})
        return out


def reset() -> None:                                # tests
    with _lock:
        _state.clear()
