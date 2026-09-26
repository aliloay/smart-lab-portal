"""
Outbound integration events (the n8n outbox).

    change + outbox row  --same transaction-->  commit
    dispatcher thread    --HTTP POST-->         n8n webhook  (selected types)
    n8n                  --GET-->               /api/automation/events (all)

Why an outbox and not "call n8n from the endpoint": a webhook call inside a
request would make booking, or worse the door path, wait on - and fail with
- an optional external service. Here the request only inserts a row. The
dispatcher delivers it later, retries with backoff, and gives up after
AUTOMATION_MAX_ATTEMPTS without ever touching the change it describes.

Every event carries:
    event_id        UUID; the idempotency key for consumers
    type            dotted name, e.g. "access.denied"
    occurred_at     ISO-8601 UTC
    lab_id / user_id / device_id
    object          {"type": "booking", "id": "42"}
    correlation_id  ties related events together (e.g. "booking:42")
    payload         type-specific detail, never secrets or biometrics
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import EventType, IntegrationEvent

log = logging.getLogger("smartlab.integration")

# Access-event types that become integration events, and their public names.
# Scan/attempt noise (QR_SCAN, *_ATTEMPT, RFID_SCAN) is left out on purpose:
# consumers want outcomes, and the audit log already has every step.
EVENT_NAMES: dict[EventType, str] = {
    EventType.BOOKING_CREATED: "booking.created",
    EventType.BOOKING_CONFIRMED: "booking.confirmed",
    EventType.BOOKING_CANCELLED: "booking.cancelled",
    EventType.ACCESS_GRANTED: "access.granted",
    EventType.ACCESS_DENIED: "access.denied",
    EventType.IDENTITY_MISMATCH: "access.identity_mismatch",
    EventType.DOOR_OPENED: "door.opened",
    EventType.DOOR_CLOSED: "door.closed",
    EventType.ALARM: "door.alarm",
    EventType.EXIT_RECORDED: "session.exit_recorded",
    EventType.DEVICE_ONLINE: "device.online",
    EventType.DEVICE_OFFLINE: "device.offline",
    EventType.ASSET_CHECKOUT: "asset.checked_out",
    EventType.ASSET_RETURN: "asset.returned",
}

# Every name the portal can emit - documented in docs/AUTOMATION.md.
ALL_TYPES = sorted(set(EVENT_NAMES.values()) | {
    "issue.created", "issue.status_changed", "session.ended",
})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def emit(db: Session, event_type: str, *,
         lab_id: Optional[int] = None, user_id: Optional[int] = None,
         device_id: Optional[int] = None,
         object_type: Optional[str] = None, object_id: Any = None,
         correlation_id: Optional[str] = None,
         payload: Optional[dict[str, Any]] = None) -> IntegrationEvent:
    """Stage one outbox row. The caller's commit publishes it."""
    pushed = bool(settings.AUTOMATION_WEBHOOK_BASE) and \
        event_type in settings.automation_push_types
    row = IntegrationEvent(
        event_id=str(uuid.uuid4()), event_type=event_type, occurred_at=_now(),
        lab_id=lab_id, user_id=user_id, device_id=device_id,
        object_type=object_type,
        object_id=str(object_id) if object_id is not None else None,
        correlation_id=correlation_id, payload=payload or {},
        delivery_status="PENDING" if pushed else "SKIPPED",
        next_attempt_at=_now() if pushed else None)
    db.add(row)
    return row


def emit_for_access_event(db: Session, ev) -> None:
    """Called by log_event for every audit row; maps the ones that matter."""
    name = EVENT_NAMES.get(ev.event_type)
    if name is None:
        return
    if ev.booking_id:
        obj, oid, corr = "booking", ev.booking_id, f"booking:{ev.booking_id}"
    elif ev.device_id:
        obj, oid, corr = "device", ev.device_id, f"device:{ev.device_id}"
    else:
        obj, oid, corr = "access_event", ev.id, None
    emit(db, name, lab_id=ev.lab_id, user_id=ev.user_id, device_id=ev.device_id,
         object_type=obj, object_id=oid, correlation_id=corr,
         payload={"access_event_id": ev.id,
                  "method": ev.method.value if ev.method else None,
                  "result": ev.result.value if ev.result else None,
                  "reason": ev.reason, "message": ev.message})


def serialize(row: IntegrationEvent) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "sequence": row.id,
        "type": row.event_type,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        "lab_id": row.lab_id,
        "user_id": row.user_id,
        "device_id": row.device_id,
        "object": {"type": row.object_type, "id": row.object_id},
        "correlation_id": row.correlation_id,
        "payload": row.payload or {},
    }


def webhook_url(event_type: str) -> str:
    base = settings.AUTOMATION_WEBHOOK_BASE.rstrip("/")
    return f"{base}/smartlab-{event_type.replace('.', '-').replace('_', '-')}"


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(30 * (2 ** max(attempts - 1, 0)), 3600))


def _post(row: IntegrationEvent) -> None:
    body = json.dumps(serialize(row)).encode()
    req = urllib.request.Request(
        webhook_url(row.event_type), data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "X-Smartlab-Token": settings.AUTOMATION_WEBHOOK_TOKEN,
                 "X-Smartlab-Event": row.event_type,
                 "X-Smartlab-Event-Id": row.event_id,
                 "User-Agent": "smart-lab-portal/automation"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status >= 300:
            raise urllib.error.HTTPError(req.full_url, resp.status,
                                         "non-2xx", resp.headers, None)


def deliver_due(db: Session, limit: int = 20, sender=_post) -> int:
    """
    Push the outbox rows that are due. Returns how many were delivered.
    FOR UPDATE SKIP LOCKED keeps two workers from sending the same row.
    """
    now = _now()
    q = (select(IntegrationEvent)
         .where(IntegrationEvent.delivery_status == "PENDING",
                IntegrationEvent.next_attempt_at <= now)
         .order_by(IntegrationEvent.id).limit(limit))
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        q = q.with_for_update(skip_locked=True)
    rows = db.scalars(q).all()
    delivered = 0
    for row in rows:
        row.attempts += 1
        try:
            sender(row)
        except Exception as exc:              # noqa: BLE001 - any failure
            row.last_error = f"{type(exc).__name__}: {exc}"[:255]
            if row.attempts >= settings.AUTOMATION_MAX_ATTEMPTS:
                row.delivery_status = "FAILED"
                row.next_attempt_at = None
            else:
                row.next_attempt_at = now + _backoff(row.attempts)
        else:
            row.delivery_status = "DELIVERED"
            row.delivered_at = _now()
            row.next_attempt_at = None
            row.last_error = None
            delivered += 1
    db.commit()
    return delivered


def prune(db: Session) -> int:
    cutoff = _now() - timedelta(days=settings.AUTOMATION_RETENTION_DAYS)
    n = db.execute(delete(IntegrationEvent).where(
        IntegrationEvent.delivery_status.in_(["DELIVERED", "SKIPPED"]),
        IntegrationEvent.occurred_at < cutoff)).rowcount or 0
    db.commit()
    return n


def requeue_failed(db: Session) -> int:
    n = db.execute(update(IntegrationEvent)
                   .where(IntegrationEvent.delivery_status == "FAILED")
                   .values(delivery_status="PENDING", attempts=0,
                           next_attempt_at=_now())).rowcount or 0
    db.commit()
    return n


class Dispatcher:
    """A daemon thread; its failures are logged and never propagate."""

    def __init__(self, session_factory, interval: float = 5.0):
        self._factory = session_factory
        self._interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_run_at: Optional[datetime] = None
        self.last_error: Optional[str] = None

    def start(self) -> None:
        if not settings.AUTOMATION_WEBHOOK_BASE or self._thread:
            return
        self._thread = threading.Thread(target=self._run, name="outbox",
                                        daemon=True)
        self._thread.start()
        log.info("Automation dispatcher pushing to %s",
                 settings.AUTOMATION_WEBHOOK_BASE)

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        last_prune = datetime.min.replace(tzinfo=timezone.utc)
        while not self._stop.wait(self._interval):
            try:
                with self._factory() as db:
                    deliver_due(db)
                    if _now() - last_prune > timedelta(hours=1):
                        prune(db)
                        last_prune = _now()
                self.last_run_at = _now()
                self.last_error = None
            except Exception as exc:          # noqa: BLE001
                self.last_error = f"{type(exc).__name__}: {exc}"[:255]
                log.warning("Automation dispatcher: %s", self.last_error)


dispatcher: Optional[Dispatcher] = None
