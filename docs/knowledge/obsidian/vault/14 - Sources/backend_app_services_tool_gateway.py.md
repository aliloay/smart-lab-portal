---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/tool_gateway.py"
source_hash: "279e57e9cd3d224566effe8331f67c37e1f027b8ad807f8b6eb3c667cb2b3c1b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/tool_gateway.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_ai.py]] - imports
- [[backend_app_services_ai.py]] - imports
- [[backend_app_models___init__.py]] - imports

```py
"""
One gateway for the lab's READ-ONLY tools (2026-10-27): used by the portal agent and exposed to MCP clients through
/api/tools (tools/mcp_server/server.py is a thin MCP front for it, so the portal never depends on MCP running).

  - typed schemas: the same JSON schemas the local model sees (ai.TOOLS), plus numeric ranges
  - validation: unknown tools / unknown arguments / wrong types / out-of-range values are refused (strict) or, for the
    portal's own model, clamped to the documented range (lenient)
  - role-aware: staff and admins only (every tool reads lab-wide data); students get nothing here
  - timeout: each call runs in its own database session on a worker thread, max TIMEOUT_S, and is abandoned after
  - audit: every call (who, tool, arguments, ok/refused/error/timeout, ms) goes to the audit log
  - read-only by construction: only names in ai.HANDLERS, and none of them writes; physical actions (door, relay,
    robot motion) are not tools and are refused by name as well.
"""
from __future__ import annotations

import concurrent.futures as cf
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AuditLog, Role, User

TIMEOUT_S = 8.0
RANGES = {"days": (1, 365), "weeks": (2, 52), "limit": (1, 50), "hours": (1, 2160)}
RANGES_PER_TOOL = {("get_anomalies", "hours"): (1, 336)}
FORBIDDEN = ("unlock", "open_door", "relay", "move", "jog", "home", "stop_robot", "start", "control", "write", "delete")
_pool = cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix="labtool")


class ToolRefused(ValueError):
    pass


def schemas() -> list[dict]:
    from app.services.ai import TOOLS
    out = []
    for t in TOOLS:
        s = {**t["input_schema"], "additionalProperties": False}
        props = {}
        for k, p in (s.get("properties") or {}).items():
            p = dict(p)
            r = RANGES_PER_TOOL.get((t["name"], k)) or RANGES.get(k)
            if p.get("type") == "integer" and r:
                p["minimum"], p["maximum"] = r
            props[k] = p
        s["properties"] = props
        out.append({"name": t["name"], "description": t["description"], "input_schema": s, "read_only": True})
    return out


def validate(name: str, args: Any, strict: bool = True) -> dict:
    from app.services.ai import HANDLERS
    if any(f in name.lower() for f in FORBIDDEN) or name not in HANDLERS:
        raise ToolRefused(f"unknown or not allowed tool: {name}")
    schema = next(s["input_schema"] for s in schemas() if s["name"] == name)
    args = {} if args is None else args
    if not isinstance(args, dict):
        raise ToolRefused("arguments must be an object")
    props, out = schema.get("properties") or {}, {}
    for k, v in args.items():
        if k not in props:
            if strict:
                raise ToolRefused(f"unknown argument: {k}")
            continue
        p = props[k]
        if p.get("type") == "integer":
            try:
                if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                    raise ValueError
                n = int(v)
            except ValueError:
                if strict:
                    raise ToolRefused(f"{k} must be an integer")
                continue                                # lenient: the tool's own default applies
            lo, hi = p.get("minimum", n), p.get("maximum", n)
            if not lo <= n <= hi:
                if strict:
                    raise ToolRefused(f"{k} must be between {lo} and {hi}")
                n = max(lo, min(hi, n))
            out[k] = n
        elif p.get("type") == "string":
            if not isinstance(v, str) or len(v) > 64:
                raise ToolRefused(f"{k} must be a short string")
            if "enum" in p and v not in p["enum"]:
                raise ToolRefused(f"{k} must be one of {', '.join(p['enum'])}")
            out[k] = v.strip()
    for k in schema.get("required", []):
        if k not in out:
            raise ToolRefused(f"missing required argument: {k}")
    return out


def _run_isolated(name: str, args: dict) -> tuple[str, bool]:
    from app.db.session import SessionLocal
    from app.services.ai import run_tool
    db = SessionLocal()
    try:
        return run_tool(db, name, args)
    finally:
        db.close()


def call(db: Session, user: Optional[User], name: str, args: Any, via: str = "api", strict: bool = True,
         timeout_s: float = TIMEOUT_S) -> dict:
    t0 = time.perf_counter()
    status, result = "ok", None
    try:
        if user is None or user.role not in (Role.ADMIN, Role.LAB_STAFF):
            raise ToolRefused("lab tools are for staff and administrators")
        clean = validate(name, args, strict)
        fut = _pool.submit(_run_isolated, name, clean)
        try:
            result, err = fut.result(timeout=timeout_s)
            status = "error" if err else "ok"
        except cf.TimeoutError:
            fut.cancel()
            status, result = "timeout", f"the tool took longer than {timeout_s:.0f} s and was abandoned"
    except ToolRefused as e:
        status, result, clean = "refused", str(e), None
    ms = round((time.perf_counter() - t0) * 1000, 1)
    db.add(AuditLog(actor_user_id=user.id if user else None, action="LAB_TOOL_CALL", entity_type="tool", entity_id=name,
                    detail={"via": via, "args": clean if status != "refused" else str(args)[:200], "status": status, "ms": ms}))
    db.commit()
    return {"tool": name, "status": status, "result": result, "ms": ms}

```
