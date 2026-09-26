"""
Event logging plus the live broadcast that drives the activity streams.

log_event() stages a row; the caller commits. That is deliberate - an event
and the state change it describes must land in the same transaction, or the
timeline can claim something happened that was rolled back.

The broadcast follows the same rule. Messages are queued on the database
session and only published by an after_commit hook, so a live dashboard can
never show an event that the database then rolled back.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import AccessEvent, AccessResult, AuthMethod, EventType, Lab, User

_PENDING = "ws_pending"


def log_event(db: Session, event_type: EventType, *,
              lab_id: Optional[int] = None,
              user_id: Optional[int] = None,
              booking_id: Optional[int] = None,
              device_id: Optional[int] = None,
              method: Optional[AuthMethod] = None,
              result: Optional[AccessResult] = None,
              reason: Optional[str] = None,
              message: str = "",
              metadata: Optional[dict[str, Any]] = None) -> AccessEvent:
    ev = AccessEvent(
        event_type=event_type, lab_id=lab_id, user_id=user_id,
        booking_id=booking_id, device_id=device_id, method=method,
        result=result, reason=reason, message=message,
        event_metadata=metadata,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.flush()          # populate ev.id without committing
    queue_message(db, {"type": "access_event", "event": _payload(db, ev)})
    # Same transaction: the outbox row exists only if this event commits.
    from app.services.integration import emit_for_access_event
    emit_for_access_event(db, ev)
    return ev


def queue_message(db: Session, message: dict[str, Any]) -> None:
    """Stage a live message; it is published only if the session commits."""
    db.info.setdefault(_PENDING, []).append(message)


def _payload(db: Session, ev: AccessEvent) -> dict[str, Any]:
    lab = db.get(Lab, ev.lab_id) if ev.lab_id else None
    user = db.get(User, ev.user_id) if ev.user_id else None
    return {
        "id": ev.id,
        "event_type": ev.event_type.value if ev.event_type else None,
        "lab_id": ev.lab_id,
        "lab_code": lab.code if lab else None,
        "user_id": ev.user_id,
        "user_name": user.full_name if user else None,
        "booking_id": ev.booking_id,
        "device_id": ev.device_id,
        "method": ev.method.value if ev.method else None,
        "result": ev.result.value if ev.result else None,
        "reason": ev.reason,
        "message": ev.message,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


# ---------------------------------------------------------------------------
# Transaction hooks
# ---------------------------------------------------------------------------
@event.listens_for(Session, "after_commit")
def _publish_after_commit(session: Session) -> None:
    pending = session.info.pop(_PENDING, None)
    if not pending:
        return
    # Imported lazily and fully guarded: a failure to notify a dashboard must
    # never propagate into the access-control path. A door decision does not
    # depend on a browser being connected.
    try:
        from app.ws.manager import manager
        for message in pending:
            manager.publish(message)
    except Exception:
        pass


@event.listens_for(Session, "after_rollback")
def _discard_after_rollback(session: Session) -> None:
    session.info.pop(_PENDING, None)
