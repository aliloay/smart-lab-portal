"""The signed PC agent update on this portal (tools/pc_agent/make_bundle.py writes it, the agent checks the signature).
Only the sequence number travels with every poll, so a poll stays small; the file is re-read only when it changes."""
from __future__ import annotations

import json
import os
from typing import Optional

_cache: dict = {"mtime": None, "info": None}


def path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "data", "pc_agent_bundle", "bundle.json")


def current() -> Optional[dict]:
    """{"seq": n, "id": "..."} of the bundle here, or None when this portal has none."""
    try:
        mtime = os.path.getmtime(path())
    except OSError:
        return None
    if mtime != _cache["mtime"]:
        try:
            with open(path(), encoding="utf-8") as f:
                m = json.load(f)["manifest"]
            _cache.update(mtime=mtime, info={"seq": m["seq"], "id": m["id"]})
        except (OSError, ValueError, KeyError):
            _cache.update(mtime=mtime, info=None)
    return _cache["info"]