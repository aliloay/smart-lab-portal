---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/incidents.py"
source_hash: "21e52c75a4178845fefee63a21f3215cdc8f13a7eadce6f40f177b2ec5cdd182"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/incidents.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_core_config.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_alert_grouping.py]] - imports
- [[backend_app_services_reports_center.py]] - imports

```py
"""
Incidents (2026-10-17): the portal's alerts handled as incidents - acknowledge, assign an owner,
notes and recovery actions, resolve with a reason, reopen. Staff only; every change is audited
and kept as an incident note.

Evidence: each incident lists the source records the alert names (device, lab) and the records
from other subsystems in the same lab within +/- 10 minutes, marked as RELATED BY TIME ONLY.
Nothing here identifies a person from timing. An AI hypothesis can be added only as a note of kind
AI_HYPOTHESIS and is shown as such. Nothing here controls a door, robot, PLC or alarm.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import Alert, AuditLog, Device, IncidentNote, Lab, Role, User
from app.services import alert_grouping
from app.services import reports_center as rc

router = APIRouter(prefix="/incidents", tags=["incidents"])

# Lifecycle: OPEN (= new) -> ACKNOWLEDGED -> INVESTIGATING -> MITIGATED -> RESOLVED, reopen allowed.
# The lifecycle is about the INCIDENT; it never changes a device's own state (acknowledging an
# offline camera does not make it online).
STATES = ("OPEN", "ACKNOWLEDGED", "INVESTIGATING", "MITIGATED", "RESOLVED")


def escalate_after() -> dict:
    return {"CRITICAL": timedelta(minutes=settings.INCIDENT_ESCALATE_CRITICAL_MIN),
            "WARNING": timedelta(minutes=settings.INCIDENT_ESCALATE_WARNING_MIN)}


ESCALATE_AFTER = escalate_after()
EVIDENCE_WINDOW = timedelta(minutes=10)


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    return None if dt is None else dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def code(a: Alert) -> str:
    return f"INC-{a.id:06d}"


def state(a: Alert) -> str:
    return "RESOLVED" if a.is_resolved else (a.state if a.state != "RESOLVED" else "OPEN")


def escalation(a: Alert, st: str, sev: str, now: datetime) -> Optional[str]:
    """Why this incident needs attention now, or None. Configurable (settings.INCIDENT_ESCALATE_*)."""
    if st == "RESOLVED":
        return None
    limit = escalate_after().get(sev)
    if st == "OPEN" and limit is not None and now - _utc(a.created_at) > limit:
        return f"not acknowledged for more than {int(limit.total_seconds() // 60)} min"
    if st != "MITIGATED" and (a.occurrences or 1) >= settings.INCIDENT_ESCALATE_OCCURRENCES:
        return f"repeated {a.occurrences} times"
    if (a.reopened_count or 0) >= settings.INCIDENT_ESCALATE_REOPENS:
        return f"came back {a.reopened_count} times after being resolved"
    return None


def _out(a: Alert, labs: dict, users: dict, devices: dict, now: datetime) -> dict:
    st = state(a)
    sev = a.severity.value if hasattr(a.severity, "value") else str(a.severity)
    why = escalation(a, st, sev, now)
    escalate = why is not None
    d = devices.get(a.device_id)
    return {"id": a.id, "code": code(a), "title": a.title, "detail": a.detail, "severity": sev, "state": st,
            "lab": labs.get(a.lab_id), "device": d.device_uid if d else None,
            "source": (d.device_type.value if hasattr(d.device_type, "value") else str(d.device_type)) if d else "portal",
            "created_at": a.created_at, "acknowledged_at": a.acknowledged_at,
            "acknowledged_by": users.get(a.acknowledged_by_id), "owner": users.get(a.owner_id), "owner_id": a.owner_id,
            "resolved_at": a.resolved_at, "resolved_by": users.get(a.resolved_by_id),
            "resolution": a.resolution or ("Resolved automatically by the system (the condition cleared)."
                                           if a.is_resolved and not a.resolved_by_id else None),
            "escalate": escalate, "escalation_reason": why, "provenance": getattr(a, "provenance", None),
            "occurrences": a.occurrences or 1, "last_seen_at": a.last_seen_at or a.created_at,
            "reopened_count": a.reopened_count or 0, "fingerprint": a.fingerprint}


def _maps(db: Session):
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    users = {u.id: u.full_name for u in db.scalars(select(User).where(User.role.in_((Role.ADMIN, Role.LAB_STAFF)))).all()}
    devices = {d.id: d for d in db.scalars(select(Device)).all()}
    return labs, users, devices


@router.get("")
def list_incidents(state_: Optional[str] = Query(None, alias="state", pattern="^(OPEN|ACKNOWLEDGED|INVESTIGATING|MITIGATED|RESOLVED|ACTIVE)$"),
                   severity: Optional[str] = Query(None, max_length=16), lab: Optional[str] = Query(None, max_length=16),
                   q: Optional[str] = Query(None, max_length=80), days: int = Query(30, ge=1, le=365),
                   db: Session = Depends(get_db), _: User = Depends(require_staff)):
    now = datetime.now(timezone.utc)
    stmt = select(Alert).where(Alert.created_at >= now - timedelta(days=days)).order_by(desc(Alert.created_at)).limit(500)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if q:
        stmt = stmt.where(or_(Alert.title.ilike(f"%{q}%"), Alert.detail.ilike(f"%{q}%")))
    labs, users, devices = _maps(db)
    rows = [_out(a, labs, users, devices, now) for a in db.scalars(stmt).all()]
    if lab:
        rows = [r for r in rows if r["lab"] == lab]
    if state_ == "ACTIVE":
        rows = [r for r in rows if r["state"] != "RESOLVED"]
    elif state_:
        rows = [r for r in rows if r["state"] == state_]
    counts = {s: sum(1 for r in rows if r["state"] == s) for s in STATES}
    return {"incidents": rows, "counts": counts, "escalations": sum(1 for r in rows if r["escalate"]),
            "reports": sum(r["occurrences"] for r in rows)}


@router.get("/quality")
def incident_quality(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
                     _: User = Depends(require_staff)):
    """Alert quality: grouped share, repeat rows, noisy devices and conditions, time to acknowledge /
    resolve, reopen (recurrence), storms. Read-only."""
    now = datetime.now(timezone.utc)
    out = alert_grouping.quality(db, now - timedelta(days=days), now)
    devices = {d.id: d.device_uid for d in db.scalars(select(Device)).all()}
    for n in out["noisy_devices"]:
        n["device"] = devices.get(n["device_id"], "portal")
    return out


def _get(db: Session, incident_id: int) -> Alert:
    a = db.get(Alert, incident_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return a


@router.get("/{incident_id}")
def get_incident(incident_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    a = _get(db, incident_id)
    now = datetime.now(timezone.utc)
    labs, users, devices = _maps(db)
    notes = db.scalars(select(IncidentNote).where(IncidentNote.alert_id == a.id).order_by(IncidentNote.created_at)).all()
    t0 = _utc(a.created_at)
    related = rc.timeline(db, t0 - EVIDENCE_WINDOW, t0 + EVIDENCE_WINDOW, a.lab_id, None, 60)["items"] if a.lab_id else []
    related = [r for r in related if r["ref"] != f"alerts#{a.id}"]
    return {**_out(a, labs, users, devices, now),
            "facts": [f"Raised {t0.isoformat()} with severity {a.severity.value if hasattr(a.severity, 'value') else a.severity}.",
                      f"Source record: alerts#{a.id}" + (f", device {devices[a.device_id].device_uid}" if a.device_id in devices else "") + ".",
                      *([a.detail] if a.detail else [])],
            "related": related,
            "related_note": "Records from other subsystems in the same lab within 10 minutes - related BY TIME ONLY, "
                            "not evidence of cause or of who was involved.",
            "notes": [{"id": n.id, "kind": n.kind, "text": n.text, "by": users.get(n.user_id), "at": n.created_at,
                       **({"label": "AI hypothesis - not a confirmed fact"} if n.kind == "AI_HYPOTHESIS" else {})} for n in notes]}


class ActionIn(BaseModel):
    action: Literal["acknowledge", "investigate", "mitigate", "assign", "note", "recovery", "ai_hypothesis", "resolve", "reopen"]
    text: str = Field(default="", max_length=2000)
    owner_id: Optional[int] = None


@router.post("/{incident_id}/actions")
def act(incident_id: int, req: ActionIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    a = _get(db, incident_id)
    now = datetime.now(timezone.utc)
    st = state(a)
    text = req.text.strip()
    note_kind, note = "STATE", None
    if req.action == "acknowledge":
        if st != "OPEN":
            raise HTTPException(status.HTTP_409_CONFLICT, f"Already {st.lower()}")
        a.state, a.acknowledged_at, a.acknowledged_by_id = "ACKNOWLEDGED", now, user.id
        note = f"Acknowledged by {user.full_name}"
    elif req.action == "investigate":
        if st == "RESOLVED":
            raise HTTPException(status.HTTP_409_CONFLICT, "Reopen it first")
        a.state = "INVESTIGATING"
        if not a.acknowledged_at:
            a.acknowledged_at, a.acknowledged_by_id = now, user.id
        a.owner_id = a.owner_id or user.id
        note = f"Investigation started by {user.full_name}"
    elif req.action == "mitigate":
        if st in ("RESOLVED", "MITIGATED"):
            raise HTTPException(status.HTTP_409_CONFLICT, f"Already {st.lower()}")
        if len(text) < 5:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Say what was done to limit the impact")
        a.state = "MITIGATED"
        if not a.acknowledged_at:
            a.acknowledged_at, a.acknowledged_by_id = now, user.id
        note = f"Mitigated by {user.full_name}: {text} (still open until the cause is resolved)"
    elif req.action == "assign":
        owner = db.get(User, req.owner_id) if req.owner_id else None
        if owner is None or owner.role not in (Role.ADMIN, Role.LAB_STAFF) or not owner.is_active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The owner must be an active staff member")
        a.owner_id = owner.id
        note = f"Owner set to {owner.full_name} by {user.full_name}"
    elif req.action in ("note", "recovery", "ai_hypothesis"):
        if not text:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Write the note first")
        note_kind, note = {"note": "NOTE", "recovery": "RECOVERY", "ai_hypothesis": "AI_HYPOTHESIS"}[req.action], text
    elif req.action == "resolve":
        if st == "RESOLVED":
            raise HTTPException(status.HTTP_409_CONFLICT, "Already resolved")
        if len(text) < 5:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give the closure reason (what was found / done)")
        a.state, a.is_resolved, a.resolved_at, a.resolved_by_id, a.resolution = "RESOLVED", True, now, user.id, text[:500]
        note = f"Resolved by {user.full_name}: {text}"
    elif req.action == "reopen":
        if st != "RESOLVED":
            raise HTTPException(status.HTTP_409_CONFLICT, "It is not resolved")
        a.state, a.is_resolved, a.resolved_at, a.resolved_by_id, a.resolution = "OPEN", False, None, None, None
        note = f"Reopened by {user.full_name}" + (f": {text}" if text else "")
    db.add(IncidentNote(alert_id=a.id, user_id=user.id, kind=note_kind, text=note[:2000], created_at=now))
    db.add(AuditLog(actor_user_id=user.id, action=f"INCIDENT_{req.action.upper()}", entity_type="alert",
                    entity_id=str(a.id), detail={"code": code(a), "text": text[:300] or None, "owner_id": req.owner_id}))
    db.commit()
    return get_incident(a.id, db, user)

```
