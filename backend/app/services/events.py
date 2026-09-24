"""
Event logging plus the live broadcast that drives the admin activity stream.

log_event() stages a row; the caller commits. That is deliberate - an event
and the state change it describes must land in the same transaction, or the
timeline can claim something happened that was rolled back.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AccessEvent, AccessResult, AuthMethod, EventType


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
    _queue_broadcast(ev)
    return ev


# ---------------------------------------------------------------------------
# Live broadcast
# ---------------------------------------------------------------------------
def _queue_broadcast(ev: AccessEvent) -> None:
    """
    Push to connected WebSocket clients without making the caller async.

    Imported lazily and wrapped in a broad except: a failure to notify a
    dashboard must never propagate into the access-control path. A door
    decision does not depend on a browser being connected.
    """
    try:
        from app.ws.manager import manager

        payload = {
            "id": ev.id,
            "event_type": ev.event_type.value if ev.event_type else None,
            "lab_id": ev.lab_id,
            "user_id": ev.user_id,
            "booking_id": ev.booking_id,
            "device_id": ev.device_id,
            "method": ev.method.value if ev.method else None,
            "result": ev.result.value if ev.result else None,
            "reason": ev.reason,
            "message": ev.message,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        }
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return          # no event loop (tests, scripts) - nothing to notify
        loop.create_task(manager.broadcast(payload))
    except Exception:
        pass
