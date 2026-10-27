"""
AI assistant endpoints.

/ai/*          staff assistant - staff and administrators only.
/ai/student/*  student helper  - any signed-in user, answers only from the
               caller's own bookings and reports plus the public lab list.

Every endpoint answers even when AI is not configured: /status says so, the
priority list is deterministic and needs no AI, and the AI calls return 503
with a readable reason. Each question is recorded in the audit log.
"""
import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import AuditLog, User
from app.services import agent, ai
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


def _instant(db: Session, user: User, question: str) -> Optional[dict]:
    """The agent's exact answer from the database, if the question is one it
    knows - milliseconds, no model, and it works with no AI configured."""
    # booking actions first (2026-10-27): a PROPOSAL the page confirms - the assistant itself changes nothing
    from app.services import agent_actions
    p = agent_actions.propose(db, user, question)
    out = ({"answer": p["answer"], "tools_used": [f"instant:{p['intent']}"], "model": "smartlab-instant",
            "instant": True, **({"actions": p["actions"]} if p.get("actions") else {})}
           if p else agent.quick_answer(db, user, question))
    if out is not None:
        db.add(AuditLog(actor_user_id=user.id, action="AI_INSTANT", entity_type="ai",
                        entity_id=out["tools_used"][0], detail={"question": question[:500]}))
        db.commit()
    return out


# Project / technical questions (how the system is built) are answered from the project's own
# documents and code: the knowledge service's "lookup" route returns cited passages in ~0.1-1.5 s
# with no model. The general model has no project documents - it took ~100 s on the CPU and could
# not answer them (measured 2026-10-17).
_PROJECT_Q = re.compile(
    r"\b(how (does|do|is|are)|why|where (is|are|do)|which (file|pin|gpio|port|ip)|what is the (ip|pin|port|home)|"
    r"firmware|esp32|arduino|gpio|pin|ur5e|fanuc|rtde|urscript|teach pendant|digital twin|n8n|workflow|obsidian|"
    r"docker|nginx|endpoint|api route|database schema|migration|yolo|homography|face server|door controller|"
    r"maglock|relay|architecture|thesis|commissioning|calibrat\w*|home (position|pose))\b", re.I)


# Questions about the lab's CURRENT state never go to the documents lookup, even with "why" / "how" in
# them: "compare the robotics and PLC labs, which needs attention first and why" got an unrelated
# chat-log quote (2026-10-19). They go to the model with the live lab data.
_LIVE_Q = re.compile(
    r"\b(now|today|tonight|currently|right now|at the moment|this (week|morning|afternoon)|need(s|ed)? attention|"
    r"compare|which (lab|room|robot|pc|camera)s?\b|state of|status of|open (alerts?|incidents?|issues?)|"
    r"who is|who was|how many)\b", re.I)


def _knowledge_lookup(db: Session, user: User, question: str) -> Optional[dict]:
    if not settings.KB_SERVICE_KEY or not _PROJECT_Q.search(question) or _LIVE_Q.search(question):
        return None
    import json as _json
    import httpx
    try:
        r = httpx.post(settings.KB_SERVICE_URL.rstrip("/") + "/ask", headers={"X-KB-Key": settings.KB_SERVICE_KEY},
                       json={"question": question[:600], "route": "lookup"}, timeout=httpx.Timeout(6.0, connect=1.0))
        events = [_json.loads(x) for x in r.text.splitlines() if x.strip()]
    except (httpx.HTTPError, ValueError):
        return None                                          # service down: fall back to the model
    sources = next((e.get("citations") for e in events if e.get("type") == "meta"), None) or []
    if not sources:
        return None
    lines = []
    for x in sources[:4]:
        snip = " ".join(str(x.get("snippet", "")).split())[:260]
        lines.append(f"- **{x.get('source')}** - {x.get('heading', '')} ({x.get('label', '')}):\n  {snip}...")
    db.add(AuditLog(actor_user_id=user.id, action="AI_INSTANT", entity_type="ai", entity_id="knowledge_lookup",
                    detail={"question": question[:500]}))
    db.commit()
    return {"answer": "**From the project's documents and code** (evidence only - the passages are quoted, "
                      "not interpreted):\n" + "\n".join(lines) +
                      "\n\nFor a written answer built from these sources, open the Project knowledge tab.",
            "tools_used": ["instant:knowledge_lookup"], "model": "smartlab-knowledge-lookup", "instant": True}


@router.post("/ask")
def ask(req: AskRequest, db: Session = Depends(get_db),
        user: User = Depends(require_staff)):
    return (_instant(db, user, req.question) or _knowledge_lookup(db, user, req.question)
            or _run(db, user, req.question, [t.model_dump() for t in req.history]))


@router.get("/report")
def management_report(period: Literal["weekly", "monthly"] = "weekly",
                      end_day: Optional[date] = None, db: Session = Depends(get_db),
                      _: User = Depends(require_staff)):
    """Weekly or monthly management report (no AI needed): figures, the
    previous period, equipment use, repeated problems with recommendations."""
    return agent.management_report(db, period, end_day)


@router.get("/insights")
def insights(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
             _: User = Depends(require_staff)):
    now = datetime.now(timezone.utc)
    return {"days": days, "insights": agent.insights(db, now - timedelta(days=days), now)}


@router.post("/summaries/{kind}")
def summary(kind: Literal["issues", "weekly"], db: Session = Depends(get_db),
            user: User = Depends(require_staff)):
    prompt = ai.ISSUES_PROMPT if kind == "issues" else ai.WEEKLY_PROMPT
    return _run(db, user, prompt, kind=f"summary:{kind}")


@router.post("/student/ask")
def student_ask(req: AskRequest, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    quick = _instant(db, user, req.question)
    if quick is not None:
        return quick
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


# ------------------------------------------------------------------ read-only lab tools (MCP front) - 2026-10-27 ---
@router.get("/tools")
def list_tools(user: User = Depends(require_staff)):
    """The read-only lab tools with typed input schemas (what tools/mcp_server/server.py exposes over MCP)."""
    from app.services import tool_gateway
    return {"tools": tool_gateway.schemas(), "read_only": True,
            "note": "Monitoring only. Door, relay and robot-motion actions are not tools and cannot be called here."}


class ToolCallIn(BaseModel):
    arguments: dict = Field(default_factory=dict)
    via: Literal["api", "mcp", "portal"] = "api"


@router.post("/tools/{name}")
def call_tool(name: str, body: ToolCallIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """One validated, audited, time-limited read-only tool call. Refusals and timeouts come back as status, not 500."""
    from app.services import tool_gateway
    r = tool_gateway.call(db, user, name, body.arguments, via=body.via, strict=True)
    if r["status"] == "refused":
        raise HTTPException(422, r["result"])
    return r


# ------------------------------------------------------------------ answer feedback - 2026-10-27 ---
# Optional thumbs up / down on an answer. Stored locally in the audit log (no new table). The review shows the down-rated
# answers per route (instant / model / document lookup) with personal details stripped, to find routing and retrieval
# failures - the evaluation set grows from reviewed examples, nothing trains on them automatically.
_ANON = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"), (re.compile(r"\b\d{5,}\b"), "<id>"),
         (re.compile(r"\bUSER\d+\b", re.I), "<user>")]


def anonymize(text: str) -> str:
    for rx, rep in _ANON:
        text = rx.sub(rep, text)
    return text[:600]


class FeedbackIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=8000)
    rating: Literal["up", "down"]
    route: Literal["instant", "model", "routed", "knowledge", "live"] = "model"
    intent: Optional[str] = Field(default=None, max_length=80)
    comment: Optional[str] = Field(default=None, max_length=300)


@router.post("/feedback")
def feedback(body: FeedbackIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.add(AuditLog(actor_user_id=user.id, action="AI_FEEDBACK", entity_type="ai_answer", entity_id=body.route,
                    detail={"rating": body.rating, "route": body.route, "intent": body.intent,
                            "question": anonymize(body.question), "answer": anonymize(body.answer)[:400],
                            "comment": anonymize(body.comment) if body.comment else None}))
    db.commit()
    return {"ok": True}


@router.get("/feedback/review")
def feedback_review(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
                    _: User = Depends(require_staff)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.scalars(select(AuditLog).where(AuditLog.action == "AI_FEEDBACK", AuditLog.created_at >= since)
                      .order_by(AuditLog.created_at.desc())).all()
    by: dict[str, dict] = {}
    for a in rows:
        d = a.detail or {}
        r = by.setdefault(d.get("route", "?"), {"up": 0, "down": 0, "examples": []})
        r[d.get("rating", "down")] += 1
        if d.get("rating") == "down" and len(r["examples"]) < 10:
            r["examples"].append({"question": d.get("question"), "intent": d.get("intent"), "comment": d.get("comment"),
                                  "at": a.created_at.isoformat() if a.created_at else None})
    return {"days": days, "routes": by, "note": "Anonymised (emails, ids and user labels removed). Review before adding "
                                                "an example to the evaluation set; nothing is trained automatically."}
