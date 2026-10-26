"""
Client for the UR5e Local-mode control agent (tools/ur5e_control/ur_local_control.py, 2026-10-26).

The agent runs natively on the lab laptop; the pendant program with the External Control node connects to it.
This client can only read its state and pass Home / Stop requests - the agent runs every check again and is the
only process that can talk to the robot. Endpoints are a fixed allowlist; the key never leaves the backend.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import httpx

URL = os.environ.get("UR_AGENT_URL", "http://host.docker.internal:5310")
KEY = os.environ.get("UR_AGENT_KEY", "")
ALLOWED = {("GET", "/state"), ("POST", "/command"), ("POST", "/recover")}
_cache: dict = {"t": 0.0, "v": None}


def call(method: str, path: str, body: Optional[dict] = None, timeout: float = 2.0) -> Optional[dict]:
    """None = not configured / not reachable (then nothing can be sent)."""
    if (method, path) not in ALLOWED:
        raise ValueError(f"not an agent endpoint: {method} {path}")
    if not KEY:
        return None
    try:
        r = httpx.request(method, URL.rstrip("/") + path, json=body, timeout=timeout, headers={"X-UR-Agent-Key": KEY})
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def state(max_age: float = 1.0) -> Optional[dict]:
    if time.time() - _cache["t"] > max_age:
        _cache.update(t=time.time(), v=call("GET", "/state", timeout=1.5))
    return _cache["v"]
