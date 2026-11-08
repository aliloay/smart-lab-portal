"""
Safe errors outward, full detail inward.

* Every request gets an X-Request-ID (taken from the client if well-formed,
  else made here) - returned in the response and put in error logs.
* An unhandled exception becomes {"detail": "An unexpected error occurred.",
  "error_id": "..."} with status 500: no stack trace, SQL, path or secret
  reaches the browser. The error_id lets an administrator find the log line.
* The full traceback is logged - but the same error (same place, same type)
  repeating is logged in full only once a minute; the repeats are counted and
  the count is logged with the next full entry (no log flood).
"""
from __future__ import annotations

import logging
import re
import secrets
import threading
import time
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("smartlab.errors")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
REPEAT_WINDOW_S = 60.0


class _Dedupe:
    def __init__(self):
        self.seen: dict[str, tuple[float, int]] = {}      # signature -> (last full log, suppressed count)
        self.lock = threading.Lock()

    def should_log(self, sig: str, now: float) -> tuple[bool, int]:
        with self.lock:
            last, n = self.seen.get(sig, (0.0, 0))
            if now - last >= REPEAT_WINDOW_S:
                self.seen[sig] = (now, 0)
                if len(self.seen) > 2000:
                    self.seen = dict(list(self.seen.items())[-1000:])
                return True, n
            self.seen[sig] = (last, n + 1)
            return False, n + 1


_dedupe = _Dedupe()


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("x-request-id", "")
        rid = rid if _SAFE_ID.match(rid) else secrets.token_hex(8)
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        error_id = secrets.token_hex(6)
        tb = traceback.extract_tb(exc.__traceback__)
        where = f"{tb[-1].filename}:{tb[-1].lineno}" if tb else "?"
        sig = f"{type(exc).__name__}@{where}"
        full, suppressed = _dedupe.should_log(sig, time.time())
        rid = getattr(request.state, "request_id", "-")
        if full:
            log.error("error_id=%s request_id=%s %s %s %s%s", error_id, rid, request.method,
                      request.url.path, sig,
                      f" (repeated {suppressed}x since the last full entry)" if suppressed else "",
                      exc_info=exc)
        else:
            log.error("error_id=%s request_id=%s %s %s %s (repeat %d, traceback suppressed)",
                      error_id, rid, request.method, request.url.path, sig, suppressed)
        return JSONResponse(status_code=500, headers={"X-Request-ID": rid, "Cache-Control": "no-store"},
                            content={"detail": "An unexpected error occurred.", "error_id": error_id})
