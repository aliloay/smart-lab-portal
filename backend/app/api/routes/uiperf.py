"""
Browser freezes as the staff's own browsers see them (2026-10-22, owner: "Robots & PCs still freezes" - while
every test browser measured it smooth). The portal page reports each long frame (> 150 ms) with Chrome's
Long Animation Frames attribution (which script / function, how much style + layout) and what was on screen.
Kept in memory only (last MAX_KEEP reports), never written to the database. Read by admins.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_admin, require_staff
from app.models import User

router = APIRouter(prefix="/uiperf", tags=["system"])
MAX_KEEP = 1000
_lock = threading.Lock()
_reports: deque = deque(maxlen=MAX_KEEP)


class Script(BaseModel):
    invoker: str = Field(default="", max_length=200)
    type: str = Field(default="", max_length=40)
    fn: str = Field(default="", max_length=120)
    url: str = Field(default="", max_length=200)
    char: int = 0
    ms: int = 0
    forced_layout_ms: int = 0


class Frame(BaseModel):
    at: float
    ms: int = Field(ge=0, le=600000)
    blocking_ms: int = 0
    render_ms: int = 0                  # style + layout + paint after the scripts
    style_layout_ms: int = 0
    scripts: list[Script] = Field(default_factory=list, max_length=20)


class Report(BaseModel):
    page: str = Field(max_length=200)
    build: str = Field(default="", max_length=40)
    ua: str = Field(default="", max_length=200)
    dom_nodes: int = 0
    heap_mb: Optional[float] = None
    canvases: int = 0
    feeds: int = 0
    hidden: bool = False
    window_s: float = 0
    frames: list[Frame] = Field(default_factory=list, max_length=60)
    fps: Optional[float] = None


@router.post("/report")
def report(r: Report, user: User = Depends(require_staff)):
    with _lock:
        _reports.append({"received": time.time(), "user": user.email, **r.model_dump()})
    return {"ok": True}


@router.get("/reports")
def reports(limit: int = 200, _: User = Depends(require_admin)) -> dict[str, Any]:
    with _lock:
        rows = list(_reports)[-max(1, min(limit, MAX_KEEP)):]
    return {"count": len(rows), "reports": rows}
