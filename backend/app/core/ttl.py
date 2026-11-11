"""
Short shared caches for heavy, identical-for-everyone reads (2026-10-27 load ramp: at 50 concurrent sessions the
single backend process queued every request behind the same wall-screen / analytics computations, page p95 1.7 s).

cached(key, ttl_s, fn): the result of fn() is shared for ttl_s seconds. Concurrent callers of the same key wait for
ONE computation instead of each running it (a per-key lock). Only for staff-wide views whose content does not depend
on who asks; the TTLs are below each page's own refresh interval, so nothing on screen gets older than it already was.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable

_store: dict[str, tuple[float, Any]] = {}
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


OFF = os.environ.get("TTL_CACHE", "1") == "0"          # tests set TTL_CACHE=0: every read is fresh


def cached(key: str, ttl_s: float, fn: Callable[[], Any]) -> Any:
    if OFF:
        return fn()
    hit = _store.get(key)
    if hit and time.monotonic() - hit[0] < ttl_s:
        return hit[1]
    with _guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        hit = _store.get(key)
        if hit and time.monotonic() - hit[0] < ttl_s:
            return hit[1]
        val = fn()
        _store[key] = (time.monotonic(), val)
        return val


def clear() -> None:
    _store.clear()


# Posts that change nothing a cached view shows (frames, questions): they must not empty the caches all day.
_READ_LIKE = ("/api/scan/", "/api/ai/", "/api/voice/", "/api/knowledge/", "/api/uiperf", "/api/search",
              "/api/equipment/broadcast/frame", "/api/auth/ws-ticket")


class ClearOnWrite:
    """2026-11-11: the dashboard summary and the lab catalogue are now cached for 2-3 s. A person who has just
    changed something (booked, resolved an issue, edited a device) must see it on the very next read, so a
    signed-in user's write empties the caches when it starts and again when it ends. Device reports (X-Device-Key,
    several a second) do not: what they change shows up when the short cache runs out, as it did within the
    pages' own refresh interval before. Pure ASGI: nothing is buffered, streamed responses pass through."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS")
                or scope["path"].startswith(_READ_LIKE)
                or not any(k == b"authorization" for k, _ in scope["headers"])):
            await self.app(scope, receive, send)
            return
        clear()
        try:
            await self.app(scope, receive, send)
        finally:
            clear()
