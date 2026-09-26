"""
AI assistant endpoints.

/ai/*          staff assistant - staff and administrators only.
/ai/student/*  student helper  - any signed-in user, answers only from the
               caller's own bookings and reports plus the public lab list.

Every endpoint answers even when AI is not configured: /status says so, the
priority list is deterministic and needs no AI, and the AI calls return 503
with a readable reason. Each question is recorded in the audit log.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import AuditLog, User
from app.services import ai
from app.services.automation import maintenance_priorities

router = APIRouter(prefix="/ai", tags=["ai assistant"])


@router.get("/status")
def status(_: User = Depends(require_staff)):
    return {**ai.health(), "questions_per_hour": settings.AI_QUESTIONS_PER_HOUR}


@router.get("/student/status")
def student_status(_: User = Depends(get_current_user)):
    h = ai.health()
    on = settings.AI_STUDENT_ENABLED and h["configured"]
    return {"configured": on, "provider": h["provider"] if on else None,
            "model": h["student_model"] if on else None,
            "reachable": on and h["reachable"],
            "missing_models": [m for m in h["missing_models"]
                               if m == h["student_model"]],
            "questions_per_hour": settings.AI_STUDENT_QUESTIONS_PER_HOUR}


@router.get("/maintenance-priorities")
def priorities(limit: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """The official ranking. Deterministic - works without AI."""
    return maintenance_priorities(db, limit)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=20)


def _limit(db: Session, user: User, action: str = "AI_QUESTION",
           per_hour: Optional[int] = None) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    n = db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.actor_user_id == user.id, AuditLog.action == action,
        AuditLog.created_at >= since)) or 0
    if n >= (per_hour if per_hour is not None else settings.AI_QUESTIONS_PER_HOUR):
        raise HTTPException(429, "Question limit reached for this hour.")


def _run(db: Session, user: User, question: str, history=None, kind="ask") -> dict:
    if not ai.configured():
        raise HTTPException(503, "The AI assistant is not configured.")
    _limit(db, user)
    db.add(AuditLog(actor_user_id=user.id, action="AI_QUESTION",
                    entity_type="ai", entity_id=kind,
                    detail={"question": question[:500]}))
    db.commit()
    try:
        return ai.ask(db, question, history)
    except ai.AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db),
        user: User = Depends(require_staff)):
    return _run(db, user, req.question,
                [t.model_dump() for t in req.history])


@router.post("/summaries/{kind}")
def summary(kind: Literal["issues", "weekly"], db: Session = Depends(get_db),
            user: User = Depends(require_staff)):
    prompt = ai.ISSUES_PROMPT if kind == "issues" else ai.WEEKLY_PROMPT
    return _run(db, user, prompt, kind=f"summary:{kind}")


@router.post("/student/ask")
def student_ask(req: AskRequest, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    if not (settings.AI_STUDENT_ENABLED and ai.configured()):
        raise HTTPException(503, "The AI helper is not configured.")
    _limit(db, user, "AI_STUDENT_QUESTION", settings.AI_STUDENT_QUESTIONS_PER_HOUR)
    db.add(AuditLog(actor_user_id=user.id, action="AI_STUDENT_QUESTION",
                    entity_type="ai", entity_id="student",
                    detail={"question": req.question[:500]}))
    db.commit()
    try:
        return ai.ask_student(db, user, req.question,
                              [t.model_dump() for t in req.history])
    except ai.AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
