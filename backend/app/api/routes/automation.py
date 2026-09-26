"""
Automation API - what n8n calls.

Authenticated with X-Automation-Key (AUTOMATION_API_KEY), never a user JWT,
and disabled (503) while the key is unset. Nothing here can open, lock or
unlock a door, and nothing here cancels a booking: reads return judgements
computed by app.services.automation; the few writes create notifications,
alerts and run records, each idempotent on a dedupe key.
"""
import hmac
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import (Alert, AlertSeverity, AuditLog, Booking,
                        BookingStatus, IntegrationEvent, Issue)
from app.services import automation as rules
from app.services.integration import ALL_TYPES, serialize
from app.services.notifications import admin_ids, booking_reminder, notify, staff_ids

router = APIRouter(prefix="/automation", tags=["automation (n8n)"])


def require_automation(x_automation_key: Optional[str] = Header(None)) -> None:
    if not settings.AUTOMATION_API_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Automation is not configured")
    if not x_automation_key or not hmac.compare_digest(
            x_automation_key.encode(), settings.AUTOMATION_API_KEY.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Invalid automation key")


guard = [Depends(require_automation)]


@router.get("/health", dependencies=guard)
def health():
    return {"ok": True, "event_types": ALL_TYPES,
            "push_types": sorted(settings.automation_push_types)}


# ------------------------------------------------------------------- events --
@router.get("/events", dependencies=guard)
def events(after: int = Query(0, ge=0, description="sequence of the last "
                              "event already processed"),
           limit: int = Query(100, ge=1, le=500),
           types: Optional[str] = None, db: Session = Depends(get_db)):
    """Pull feed over the outbox, in commit order. Resume from `next_after`."""
    q = select(IntegrationEvent).where(IntegrationEvent.id > after)
    if types:
        q = q.where(IntegrationEvent.event_type.in_(
            [t.strip() for t in types.split(",") if t.strip()]))
    rows = db.scalars(q.order_by(IntegrationEvent.id).limit(limit)).all()
    return {"events": [serialize(r) for r in rows],
            "next_after": rows[-1].id if rows else after}


# ----------------------------------------------------------------- bookings --
@router.get("/bookings/upcoming", dependencies=guard)
def upcoming(within_minutes: int = Query(60, ge=1, le=24 * 60),
             db: Session = Depends(get_db)):
    return {"bookings": rules.upcoming_bookings(db, within_minutes)}


@router.get("/bookings/ended", dependencies=guard)
def ended(minutes: int = Query(60, ge=5, le=24 * 60),
          db: Session = Depends(get_db)):
    return {"bookings": rules.ended_bookings(db, minutes)}


@router.get("/bookings/{booking_id}", dependencies=guard)
def booking(booking_id: int, db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "Booking not found")
    return rules.booking_context(db, b)


@router.post("/bookings/{booking_id}/remind", dependencies=guard)
def remind(booking_id: int, db: Session = Depends(get_db)):
    """The same reminder the portal raises itself - at most once per booking."""
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "Booking not found")
    if b.status != BookingStatus.CONFIRMED:
        return {"created": False, "reason": f"booking is {b.status.value}"}
    created = booking_reminder(db, b)
    db.commit()
    return {"created": created}


# ------------------------------------------------------------------- access --
@router.get("/access/denials", dependencies=guard)
def denials(lab_id: Optional[int] = None,
            window_minutes: Optional[int] = Query(None, ge=1, le=24 * 60),
            db: Session = Depends(get_db)):
    return rules.denial_burst(db, lab_id, window_minutes)


# -------------------------------------------------------------- devices etc --
@router.get("/devices/offline", dependencies=guard)
def devices_offline(db: Session = Depends(get_db)):
    return rules.device_escalation(db)


@router.get("/maintenance", dependencies=guard)
def maintenance(db: Session = Depends(get_db)):
    return rules.maintenance_digest(db)


@router.get("/issues/{issue_id}", dependencies=guard)
def issue(issue_id: int, db: Session = Depends(get_db)):
    i = db.get(Issue, issue_id)
    if i is None:
        raise HTTPException(404, "Issue not found")
    return rules.issue_context(db, i)


@router.get("/reports/daily", dependencies=guard)
def report_daily(day: Optional[date] = None, db: Session = Depends(get_db)):
    return rules.daily_report(db, day)


@router.get("/reports/weekly", dependencies=guard)
def report_weekly(end: Optional[date] = None, db: Session = Depends(get_db)):
    return rules.weekly_report(db, end)


@router.get("/sensors/evaluate", dependencies=guard)
def sensors(max_age_minutes: int = Query(30, ge=1, le=24 * 60),
            db: Session = Depends(get_db)):
    return rules.sensor_evaluation(db, max_age_minutes)


@router.get("/data-quality", dependencies=guard)
def quality(db: Session = Depends(get_db)):
    return rules.data_quality(db)


@router.get("/maintenance/priorities", dependencies=guard)
def maintenance_ranked(limit: int = Query(10, ge=1, le=50),
                       db: Session = Depends(get_db)):
    return rules.maintenance_priorities(db, limit)


@router.get("/ai/weekly-summary", dependencies=guard)
def ai_weekly(db: Session = Depends(get_db)):
    """AI-written weekly summary for the n8n weekly report. Optional."""
    from app.services import ai
    if not ai.configured():
        return {"available": False, "summary": None,
                "reason": "AI assistant not configured"}
    try:
        out = ai.ask(db, ai.WEEKLY_PROMPT)
    except ai.AIUnavailable as exc:
        return {"available": False, "summary": None, "reason": str(exc)}
    return {"available": True, "summary": out["answer"][:1500],
            "dedupe_key": f"ai-weekly:{date.today().isoformat()}"}


@router.get("/anomalies", dependencies=guard)
def anomaly_scan(hours: int = Query(24, ge=1, le=24 * 14),
                 db: Session = Depends(get_db)):
    return rules.anomalies(db, hours)


# ------------------------------------------------------------------- writes --
# Kinds automation may raise. A closed list: n8n cannot impersonate portal
# events such as BOOKING_CONFIRMED or ISSUE_ASSIGNED.
AUTOMATION_KINDS = {
    "BOOKING_BRIEFING", "PRE_BOOKING_CHECK", "SECURITY_EVENT", "DEVICE_OFFLINE",
    "MAINTENANCE_DIGEST", "DAILY_REPORT", "WEEKLY_REPORT", "SENSOR_THRESHOLD",
    "POST_SESSION", "DATA_QUALITY", "ANOMALY",
}


class NotifyRequest(BaseModel):
    audience: Literal["user", "staff", "admins"]
    user_id: Optional[int] = None
    kind: str
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=500)
    link: Optional[str] = Field(default=None, max_length=160, pattern=r"^/")
    severity: Literal["info", "warning", "critical"] = "info"
    booking_id: Optional[int] = None
    issue_id: Optional[int] = None
    dedupe_key: str = Field(min_length=3, max_length=160)


@router.post("/notify", dependencies=guard)
def post_notify(req: NotifyRequest, db: Session = Depends(get_db)):
    if req.kind not in AUTOMATION_KINDS:
        raise HTTPException(422, f"kind must be one of {sorted(AUTOMATION_KINDS)}")
    if req.audience == "user":
        if req.user_id is None:
            raise HTTPException(422, "user_id is required for audience=user")
        recipients = [req.user_id]
    else:
        recipients = staff_ids(db) if req.audience == "staff" else admin_ids(db)
    rows = notify(db, recipients, req.kind, req.title, body=req.body,
                  link=req.link, severity=req.severity,
                  booking_id=req.booking_id, issue_id=req.issue_id,
                  dedupe_key=req.dedupe_key)
    db.commit()
    return {"created": len(rows), "duplicate": not rows and bool(recipients)}


class AlertRequest(BaseModel):
    severity: Literal["INFO", "WARNING", "CRITICAL"] = "WARNING"
    title: str = Field(min_length=1, max_length=128)
    detail: str = Field(default="", max_length=2000)
    lab_id: Optional[int] = None
    device_id: Optional[int] = None
    dedupe_key: str = Field(min_length=3, max_length=160)


@router.post("/alerts", dependencies=guard)
def post_alert(req: AlertRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(Alert).where(Alert.dedupe_key == req.dedupe_key))
    if existing:
        return {"created": False, "alert_id": existing.id}
    a = Alert(severity=AlertSeverity(req.severity), title=req.title,
              detail=req.detail + "\n\nRaised by automation.",
              lab_id=req.lab_id, device_id=req.device_id,
              dedupe_key=req.dedupe_key)
    db.add(a)
    db.commit()
    return {"created": True, "alert_id": a.id}


class RunRequest(BaseModel):
    workflow: str = Field(min_length=1, max_length=48)
    status: Literal["success", "error", "skipped"] = "success"
    summary: str = Field(default="", max_length=500)
    execution_id: Optional[str] = Field(default=None, max_length=64)


@router.post("/runs", dependencies=guard)
def post_run(req: RunRequest, db: Session = Depends(get_db)):
    """A workflow reports that it ran - the Operations Center shows it."""
    db.add(AuditLog(action="AUTOMATION_RUN", entity_type="workflow",
                    entity_id=req.workflow,
                    detail={"status": req.status, "summary": req.summary,
                            "execution_id": req.execution_id}))
    db.commit()
    return {"recorded": True}
