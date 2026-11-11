"""
Failure throttling for sign-in (and other abuse-prone endpoints).

Counts FAILURES in a sliding window, per key: the account (email) and the
client address are counted separately, so neither guessing many passwords for
one account nor trying many accounts from one machine works. A success clears
that account's count. Normal lab use (a mistyped password or two) never hits it.

In memory: the backend runs as one process (uvicorn, no workers), and a
restart resetting the counts is acceptable for this purpose.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional


class FailureThrottle:
    def __init__(self, max_failures: int, window_s: float):
        self.max_failures, self.window_s = max_failures, window_s
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque:
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] > self.window_s:
            q.popleft()
        return q

    def blocked_for(self, key: str, now: Optional[float] = None) -> float:
        """Seconds until this key may try again (0 = allowed)."""
        now = now or time.time()
        with self._lock:
            q = self._recent(key, now)
            if len(q) < self.max_failures:
                return 0.0
            return max(0.0, self.window_s - (now - q[0]))

    def fail(self, key: str, now: Optional[float] = None) -> None:
        now = now or time.time()
        with self._lock:
            self._recent(key, now).append(now)
            if len(self._hits) > 10_000:            # bounded memory under a flood
                for k in [k for k, v in self._hits.items() if not v][:5_000]:
                    del self._hits[k]

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


class RateLimit:
    """At most `max_calls` per key in any `window_s` seconds (every call counts, not only failures)."""

    def __init__(self, max_calls: int, window_s: float):
        self._t = FailureThrottle(max_calls, window_s)

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        now = now or time.time()
        if self._t.blocked_for(key, now) > 0:
            return False
        self._t.fail(key, now)
        return True


# Phone "which box?" runs several CPU detectors per frame: 6 frames in any 2 s per signed-in user, so a scripted
# loop cannot take the backend's cores (2026-11-11 closure audit, SEC-05).
scan_appearance = RateLimit(6, 2.0)

# 8 wrong passwords for one account in 15 min; 30 failures from one address in 15 min.
login_by_account = FailureThrottle(8, 15 * 60)
login_by_address = FailureThrottle(30, 15 * 60)
