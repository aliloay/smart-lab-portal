---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/perfmon.py"
source_hash: "3e3e1dca35837e60983fc3d273b4ebeb497db0c251e3755dc66cb87f758b891b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/perfmon.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_reliability.py]] - imports

```py
"""
Request performance monitor, regression detection and service objectives (2026-10-18).

A tiny middleware records each API request's duration (perf_counter, microseconds of overhead) in a
bounded ring per route template ("GET /api/robots/{device_id}") - nothing is written to the database
per request. From that:

  summary()       p50 / p95 / p99 per route with sample counts (p99 only with >= 100 samples)
  regressions()   the last REGRESS_WINDOW_S compared with the HOUR before it: a route is regressed when
                  current p95 > max(1.5 x baseline p95, baseline p95 + 50 ms) with >= MIN_SAMPLES in
                  both windows; one finding per route per COOLDOWN_S (no alert storm)
  objectives()    measurable service objectives over a stated observation window (since this process
                  started, at most WINDOW_S), with error-budget use; no claim beyond the samples
A saved baseline (admin: "capture baseline") is kept in system_settings and compared on demand -
across deployments, under comparable load only (the note says so).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

RING = 2000                      # samples kept per route
WINDOW_S = 24 * 3600
REGRESS_WINDOW_S = 300
MIN_SAMPLES = 20
COOLDOWN_S = 900
STARTED = time.time()

_lock = threading.Lock()
_data: dict[str, deque] = {}     # route -> deque[(t, ms, status)]
_flagged: dict[str, float] = {}

OBJECTIVES = [
    # (key, description, kind, target)
    ("api_p95_ms", "95 % of ordinary API reads answer within 300 ms", "latency_p95", 300.0),
    ("api_success", "99.5 % of API requests do not fail with a server error", "success", 0.995),
]


MAX_ROUTES = 500


def record(route: str, ms: float, status: int, t: Optional[float] = None) -> None:
    t = t or time.time()
    with _lock:
        d = _data.get(route)
        if d is None:
            if len(_data) >= MAX_ROUTES:
                route = "other"
                d = _data.get(route)
            if d is None:
                d = _data[route] = deque(maxlen=RING)
        d.append((t, ms, status))


def _pct(v: list[float], q: float) -> Optional[float]:
    if not v:
        return None
    v = sorted(v)
    return round(v[min(len(v) - 1, max(0, int(round(q * len(v))) - 1))], 1)


def summary(top: int = 25) -> dict:
    with _lock:
        items = {k: list(d) for k, d in _data.items()}
    rows = []
    for k, d in items.items():
        ms = [x[1] for x in d]
        rows.append({"route": k, "n": len(ms), "p50": _pct(ms, 0.5), "p95": _pct(ms, 0.95),
                     "p99": _pct(ms, 0.99) if len(ms) >= 100 else None,
                     "errors_5xx": sum(1 for x in d if x[2] >= 500)})
    rows.sort(key=lambda r: -(r["p95"] or 0))
    allms = [x[1] for d in items.values() for x in d]
    return {"since_s": round(time.time() - STARTED), "requests": len(allms), "p50": _pct(allms, 0.5),
            "p95": _pct(allms, 0.95), "p99": _pct(allms, 0.99) if len(allms) >= 100 else None, "routes": rows[:top]}


def regressions(now: Optional[float] = None) -> list[dict]:
    now = now or time.time()
    out = []
    with _lock:
        items = {k: list(d) for k, d in _data.items()}
    for k, d in items.items():
        cur = [x[1] for x in d if x[0] >= now - REGRESS_WINDOW_S]
        base = [x[1] for x in d if now - REGRESS_WINDOW_S - 3600 <= x[0] < now - REGRESS_WINDOW_S]
        if len(cur) < MIN_SAMPLES or len(base) < MIN_SAMPLES:
            continue
        c95, b95 = _pct(cur, 0.95), _pct(base, 0.95)
        if c95 > max(1.5 * b95, b95 + 50):
            first = now - _flagged.get(k, 0) > COOLDOWN_S
            if first:
                _flagged[k] = now
            out.append({"route": k, "baseline_p95": b95, "current_p95": c95, "change_pct": round(100 * (c95 - b95) / b95),
                        "samples": {"baseline": len(base), "current": len(cur)}, "new": first,
                        "note": "compared with the hour before on this machine; load may differ"})
    return out


def objectives() -> list[dict]:
    with _lock:
        items = [x for d in _data.values() for x in d]
    out = []
    span = min(time.time() - STARTED, WINDOW_S)
    for key, desc, kind, target in OBJECTIVES:
        if kind == "latency_p95":
            ms = [x[1] for x in items]
            good = sum(1 for m in ms if m <= target)
            ratio = good / len(ms) if ms else None
            out.append({"key": key, "objective": desc, "samples": len(ms), "window_s": round(span),
                        "measured_p95_ms": _pct(ms, 0.95), "within_target_share": None if ratio is None else round(ratio, 4),
                        "met": None if ratio is None else ratio >= 0.95,
                        "error_budget_used": None if ratio is None else round(min(1.0, (1 - ratio) / 0.05), 3)})
        else:
            n = len(items)
            bad = sum(1 for x in items if x[2] >= 500)
            ratio = 1 - bad / n if n else None
            out.append({"key": key, "objective": desc, "samples": n, "window_s": round(span),
                        "measured": None if ratio is None else round(ratio, 5), "met": None if ratio is None else ratio >= target,
                        "error_budget_used": None if ratio is None else round(min(1.0, (bad / n) / (1 - target)), 3)})
    return out


def reset() -> None:                                   # tests
    with _lock:
        _data.clear()
        _flagged.clear()


class TimingMiddleware:
    """Pure ASGI timing (not BaseHTTPMiddleware: that would buffer streamed answers). Records the time
    to the response START per route template; /api only."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return
        t0 = time.perf_counter()

        async def snd(msg):
            if msg["type"] == "http.response.start":
                # the route template from the real path: each path parameter's value -> {name}
                path = scope.get("path", "")
                params = scope.get("path_params") or {}
                for k, v in params.items():
                    path = path.replace(f"/{v}", "/{" + k + "}", 1)
                # no matched route (404 / scanners): one shared key - random URLs must not grow memory
                key = path if scope.get("route") is not None else "unmatched"
                record(f"{scope['method']} {key}", (time.perf_counter() - t0) * 1000, msg["status"])
            await send(msg)
        await self.app(scope, receive, snd)

```
