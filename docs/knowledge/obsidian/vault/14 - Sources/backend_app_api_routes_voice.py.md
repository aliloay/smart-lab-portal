---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/voice.py"
source_hash: "e7494c39b415e3f71a8d7c8eed8ba23f65621f431f2d78cb71dc54c9369563e1"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/voice.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_core_config.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_api_routes_ai.py]] - imports
- [[docs_FINAL_IMPLEMENTATION_AUDIT_2026-10-26.md]] - mentioned by docs
- [[tools_voice_README.md]] - mentioned by docs

```py
"""
Voice for the AI assistant (2026-10-26): push-to-talk -> text, short answer -> speech.

Both run in the local voice service on the lab laptop (tools/voice/voice_service.py: faster-whisper + Piper on the
CPU, cameras keep the GPU). This route only passes audio through: nothing is stored, nothing is logged except a
counter row for the hourly limit. The transcribed text goes back to the browser, which sends it through the normal
/ai/ask (or /ai/student/ask) path - same tools, same permissions, same question limit as typing. The assistant
cannot open doors or move robots, spoken or typed.
"""
from __future__ import annotations

import os
import time

import httpx
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import AuditLog, User

router = APIRouter(prefix="/voice", tags=["ai"])

URL = os.environ.get("VOICE_URL", "http://host.docker.internal:5320").rstrip("/")
KEY = os.environ.get("VOICE_KEY", "")
MAX_AUDIO = 2_000_000
_client = httpx.Client(timeout=httpx.Timeout(30.0, connect=0.5))
_health: dict = {"t": 0.0, "v": None}


def _hourly(db: Session, user: User, action: str, per_hour: int) -> None:
    from app.api.routes.ai import _limit
    _limit(db, user, action, per_hour)
    db.add(AuditLog(actor_user_id=user.id, action=action, entity_type="ai", entity_id="voice"))
    db.commit()


@router.get("/status")
def voice_status(_: User = Depends(get_current_user)):
    """What the browser can use: local STT / TTS, or none (then the mic is hidden, answers use the browser voice)."""
    if not KEY:
        return {"stt": False, "tts": False, "reason": "voice service not configured (VOICE_KEY)"}
    if time.time() - _health["t"] > 10:
        try:
            h = _client.get(URL + "/health", timeout=1.0).json()
        except (httpx.HTTPError, ValueError):
            h = None
        _health.update(t=time.time(), v=h)
    h = _health["v"]
    if not h:
        return {"stt": False, "tts": False, "reason": "voice service not running (tools/voice/voice_service.py)"}
    return {"stt": bool(h.get("stt")), "tts": bool(h.get("tts")), "model": h.get("stt"), "voice": h.get("tts")}


@router.post("/transcribe")
async def transcribe(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    body = await request.body()
    # 2026-10-27 (owner: "it takes a lot of time to detect and to hear the answer"): the blocking calls (camera /
    # face / voice service, database) run on a worker thread - they used to hold the event loop, so every other
    # request, the spoken answer included, queued behind the phone's back-to-back frames.

    def _work():
        if not body:
            raise HTTPException(422, "No recording")
        if len(body) > MAX_AUDIO:
            raise HTTPException(413, "Recording too long - keep a question under 30 s")
        if not KEY:
            raise HTTPException(503, "Voice is not set up on this portal")
        _hourly(db, user, "AI_VOICE", settings.AI_QUESTIONS_PER_HOUR * 2)
        try:
            r = _client.post(URL + "/transcribe", content=body, headers={"X-Voice-Key": KEY,
                             "Content-Type": request.headers.get("content-type", "application/octet-stream")})
        except httpx.HTTPError:
            raise HTTPException(503, "The voice service is not running - type the question instead")
        if r.status_code == 429:
            raise HTTPException(429, "Someone else is speaking to the assistant - try again in a moment")
        if r.status_code != 200:
            raise HTTPException(422 if r.status_code < 500 else 503, (r.json() if r.content else {}).get("error", "voice error"))
        return r.json()

    return await run_in_threadpool(_work)


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=600)


@router.post("/speak")
def speak(req: SpeakIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not KEY:
        raise HTTPException(503, "Voice is not set up on this portal")
    _hourly(db, user, "AI_VOICE_SPEAK", settings.AI_QUESTIONS_PER_HOUR * 4)
    try:
        r = _client.post(URL + "/speak", json={"text": req.text}, headers={"X-Voice-Key": KEY}, timeout=15.0)
    except httpx.HTTPError:
        raise HTTPException(503, "The voice service is not running")
    if r.status_code != 200:
        raise HTTPException(429 if r.status_code == 429 else 503, "voice busy" if r.status_code == 429 else "no voice")
    return Response(r.content, media_type="audio/wav", headers={"Cache-Control": "no-store"})

```
