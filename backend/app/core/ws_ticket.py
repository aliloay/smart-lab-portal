"""
One-time tickets for the live-updates WebSocket (2026-11-11 closure audit, SEC-04).

A browser cannot set headers on a WebSocket, so the page used to put its 8-hour sign-in token in the URL
(/ws/activity?token=...) - and URLs are written to the web server's and the API's access logs. The page now
asks for a ticket over the normal authenticated API and connects with that: random, good for one connection,
and only for TICKET_S seconds, so a logged ticket is worth nothing.

In memory: the backend is one process (see core/throttle.py); a restart only makes pages ask again.
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Optional

TICKET_S = 30.0
_tickets: dict[str, tuple[int, float]] = {}
_lock = threading.Lock()


def issue(user_id: int, now: Optional[float] = None) -> str:
    now = now or time.monotonic()
    t = secrets.token_urlsafe(24)
    with _lock:
        for k in [k for k, (_, exp) in _tickets.items() if exp < now]:
            del _tickets[k]
        _tickets[t] = (user_id, now + TICKET_S)
    return t


def redeem(ticket: str, now: Optional[float] = None) -> Optional[int]:
    """The user id the ticket was issued to - once, and only while it is fresh."""
    now = now or time.monotonic()
    with _lock:
        got = _tickets.pop(ticket, None)
    return got[0] if got and got[1] >= now else None
