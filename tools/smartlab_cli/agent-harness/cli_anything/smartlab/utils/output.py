"""One JSON envelope for every command, and a plain-text view for people."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .redaction import redact


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def envelope(command: str, data: Any, source: str, success: bool = True, warnings: Optional[list] = None,
             errors: Optional[list] = None, freshness: Optional[str] = None) -> dict:
    e = {"success": success, "command": command, "timestamp": now_iso(), "source": source,
         "freshness": freshness or "live", "data": data, "warnings": warnings or [], "errors": errors or []}
    return redact(e)


def dumps(e: dict) -> str:
    return json.dumps(e, indent=2, ensure_ascii=False, default=str)


def table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "(none)"
    w = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    w = {c: min(v, 48) for c, v in w.items()}
    head = "  ".join(c.upper().ljust(w[c]) for c in cols)
    line = "  ".join("-" * w[c] for c in cols)
    body = ["  ".join(str(r.get(c, "") if r.get(c) is not None else "-")[:w[c]].ljust(w[c]) for c in cols) for r in rows]
    return "\n".join([head, line, *body])


def human(e: dict) -> str:
    """Readable rendering of an envelope: tables for lists of dicts, key: value for dicts."""
    out = []
    d = e.get("data")
    if isinstance(d, dict) and isinstance(d.get("rows"), list):
        out.append(table(d["rows"], d.get("columns") or list(d["rows"][0].keys()) if d["rows"] else []))
        extra = {k: v for k, v in d.items() if k not in ("rows", "columns")}
        if extra:
            out.append("")
            out.extend(f"{k}: {json.dumps(v, default=str) if isinstance(v, (dict, list)) else v}" for k, v in extra.items())
    elif isinstance(d, dict):
        for k, v in d.items():
            out.append(f"{k}: {json.dumps(v, default=str, ensure_ascii=False) if isinstance(v, (dict, list)) else v}")
    elif isinstance(d, list):
        out.append(table(d, list(d[0].keys())) if d and isinstance(d[0], dict) else "\n".join(map(str, d)))
    elif d is not None:
        out.append(str(d))
    for w in e.get("warnings") or []:
        out.append(f"WARNING: {w}")
    for er in e.get("errors") or []:
        out.append(f"ERROR: {er.get('message', er) if isinstance(er, dict) else er}"
                   + (f"\n  hint: {er['hint']}" if isinstance(er, dict) and er.get("hint") else ""))
    out.append(f"[source: {e['source']} | {e['freshness']} | {e['timestamp']}]")
    return "\n".join(out)
