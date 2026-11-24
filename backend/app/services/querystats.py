"""
Database time per statement (2026-11-23): which queries cost the most, measured in the backend itself - no database
restart, no extension, nothing written to the database. Complements perfmon.py (time per API route).

SQLAlchemy engine events time every statement; statements are grouped by their text with quoted strings and numbers
replaced by "?" and placeholder lists folded, so no parameter value is ever kept. Bounded: MAX_STATEMENTS groups
(the least used is dropped), LAST times per group. Since this process started.
"""
from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Optional

MAX_STATEMENTS = 400
LAST = 200
SLOW_MS = 200.0
STARTED = time.time()

_lock = threading.Lock()
_stats: dict[str, dict] = {}

_STR = re.compile(r"'(?:[^']|'')*'")
_NUM = re.compile(r"(?<![\w$])\d+(?:\.\d+)?\b")
# S-6 (24 Nov): sized / array casts were left behind ("?(64)", "?[]"), and the greedy "[\w ]+" swallowed the SQL after
# an unsized cast ("a = %(x)s::VARCHAR AND b = ..." became "a = ?= ..."), merging different statements.
_PARAM = re.compile(
    r"%\([^)]*\)s(?:::[A-Za-z_][\w.]*(?:\s+(?:VARYING|PRECISION)\b)?(?:\(\d+(?:\s*,\s*\d+)?\))?"
    r"(?:\s+(?:WITH|WITHOUT)\s+(?:LOCAL\s+)?TIME\s+ZONE\b)?(?:\[\d*\])*)*", re.I)
_LIST = re.compile(r"\(\s*\?(?:\s*,\s*\?)+\s*\)")
_WS = re.compile(r"\s+")


def normalise(sql: str) -> str:
    s = _PARAM.sub("?", _STR.sub("?", sql))
    s = _LIST.sub("(?, ...)", _NUM.sub("?", s))
    return _WS.sub(" ", s).strip()[:600]


def record(sql: str, ms: float) -> None:
    key = normalise(sql)
    with _lock:
        d = _stats.get(key)
        if d is None:
            if len(_stats) >= MAX_STATEMENTS:
                _stats.pop(min(_stats, key=lambda k: _stats[k]["n"]))
            d = _stats[key] = {"n": 0, "total": 0.0, "max": 0.0, "slow": 0, "last": deque(maxlen=LAST)}
        d["n"] += 1
        d["total"] += ms
        d["max"] = max(d["max"], ms)
        d["slow"] += ms >= SLOW_MS
        d["last"].append(ms)


def install(engine) -> None:
    """Time every statement of this engine (idempotent). A failing hook must never break a query."""
    from sqlalchemy import event
    if getattr(engine, "_querystats", False):
        return
    engine._querystats = True

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        conn.info["qs_t0"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        t0 = conn.info.pop("qs_t0", None)
        if t0 is not None:
            try:
                record(statement, (time.perf_counter() - t0) * 1000)
            except Exception:
                pass


def _p95(v: list[float]) -> Optional[float]:
    v = sorted(v)
    return round(v[min(len(v) - 1, int(len(v) * 0.95))], 1) if len(v) >= 20 else None   # no p95 from a few samples


def summary(top: int = 20) -> dict:
    with _lock:
        rows = [{"statement": k, "n": d["n"], "total_ms": round(d["total"], 1), "mean_ms": round(d["total"] / d["n"], 2),
                 "p95_ms": _p95(list(d["last"])), "max_ms": round(d["max"], 1), "slow": d["slow"]}
                for k, d in _stats.items()]
    rows.sort(key=lambda r: -r["total_ms"])
    return {"since_s": round(time.time() - STARTED), "slow_threshold_ms": SLOW_MS, "statements": len(rows),
            "queries": sum(r["n"] for r in rows), "slow": sum(r["slow"] for r in rows), "top": rows[:top]}


def reset() -> None:
    """Tests only."""
    with _lock:
        _stats.clear()
