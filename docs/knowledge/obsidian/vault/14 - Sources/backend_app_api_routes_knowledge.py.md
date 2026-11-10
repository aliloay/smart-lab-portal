---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/knowledge.py"
source_hash: "66624a5f41b659f600044b5f038af8bfdd7df76726eef364bf47bfde2ea126e7"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/knowledge.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_core_config.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[docs_knowledge-platform_AGENT.md]] - mentioned by docs

```py
"""
Project knowledge (admins and lab staff only): the portal's window onto the local
knowledge agent on this laptop (tools/knowledge/serve.py, 127.0.0.1:5199, reached from the
container as host.docker.internal). The agent answers from the project's documents, code,
history and approved conversations, with citations. It is read-only: it never touches the
database, devices or n8n. If the service is not running the portal says so; nothing else
in the portal depends on it.
"""
from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import require_staff
from app.core.config import settings
from app.models import User

router = APIRouter(prefix="/knowledge", tags=["project knowledge (staff)"])


def _headers() -> dict:
    if not settings.KB_SERVICE_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Project knowledge is not set up (KB_SERVICE_KEY missing in .env).")
    return {"X-KB-Key": settings.KB_SERVICE_KEY}


@router.get("/status")
def knowledge_status(_: User = Depends(require_staff)):
    try:
        r = httpx.get(settings.KB_SERVICE_URL.rstrip("/") + "/status", headers=_headers(), timeout=5)
    except httpx.HTTPError:
        return {"ok": False, "error": "The knowledge service is not running on this laptop (launch.bat starts it)."}
    if r.status_code != 200:
        return {"ok": False, "error": f"Knowledge service answered {r.status_code}."}
    return r.json()


class Ask(BaseModel):
    question: str = Field(min_length=2, max_length=600)
    route: str | None = Field(default=None, pattern="^(lookup|answer|investigate)$")


@router.post("/ask")
def knowledge_ask(req: Ask, user: User = Depends(require_staff)):
    """Streams the agent's events (NDJSON): meta, step, sources, token, done."""
    headers = _headers()
    url = settings.KB_SERVICE_URL.rstrip("/") + "/ask"

    def stream():
        try:
            with httpx.stream("POST", url, headers=headers, json=req.model_dump(),
                              timeout=httpx.Timeout(240, connect=3)) as r:
                if r.status_code != 200:
                    yield json.dumps({"type": "done", "status": "failed",
                                      "error": f"knowledge service answered {r.status_code}"}) + "\n"
                    return
                for line in r.iter_lines():
                    if line:
                        yield line + "\n"
        except httpx.HTTPError:
            yield json.dumps({"type": "done", "status": "failed",
                              "error": "The knowledge service is not running on this laptop (launch.bat starts it)."}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

```
