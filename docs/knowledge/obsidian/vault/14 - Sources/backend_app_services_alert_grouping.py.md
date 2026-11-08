---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/alert_grouping.py"
source_hash: "163bb636224897069909d2557910dc4c916db408259c5e91b41b2f01c15290a1"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/alert_grouping.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_incidents.py]] - imports
- [[backend_app_api_routes_reliability.py]] - imports
- [[backend_app_api_routes_security.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services_anomalies.py]] - imports
- [[backend_app_services_devices.py]] - imports
- [[backend_app_services_environment.py]] - imports

```py
"""
Alert grouping (2026-10-18): one incident per continuing condition.

A condition is identified by a stable FINGERPRINT - by default device | lab | lower-cased title, or a
key the caller chooses (e.g. door:<lab>:FORCED_ENTRY). Never a timestamp: that would defeat grouping.

  * open alert with that fingerprint  -> GROUPED: occurrences + 1, last_seen_at = now (a higher
    severity raises the incident's severity, with a note);
  * resolved less than REOPEN_WINDOW ago -> REOPENED: the condition came back (reopened_count + 1,
    the previous resolution kept in a note);
  * otherwise -> CREATED: a new incident.

The original records stay where they are (access events, camera events, readings, ...): grouping only
decides how many incident rows the inbox shows. Notifications are the CALLER's business and are not
changed here - a safety alarm still notifies on every occurrence. Concurrent raises of the same
fingerprint are serialised with a transaction-scoped advisory lock (PostgreSQL).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Alert, AlertSeverity, IncidentNote

REOPEN_WINDOW = timedelta(minutes=30)
_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}


def fingerprint(device_id: Optional[int], lab_id: Optional[int], title: str) -> str:
    return f"{device_id or 0}|{lab_id or 0}|{(title or '').strip().lower()[:120]}"


def _sev(s: Any) -> str:
    return s.value if hasattr(s, "value") else str(s)


def _lock(db: Session, fp: str) -> None:
    # One lock for all alert writes (2026-10-29): a lock per fingerprint deadlocked when two requests each raised two
    # alerts in opposite order ("security camera: no picture" x2 cameras) - the backend then stalled and n8n's retries
    # piled up. Alert writes are rare and short, so one queue costs nothing and can never deadlock with itself.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("select pg_advisory_xact_lock(:ns, 0)"), {"ns": 51_002})


def raise_or_group(db: Session, *, lab_id: Optional[int], device_id: Optional[int],
                   severity: AlertSeverity, title: str, detail: str = "", fp: Optional[str] = None,
                   now: Optional[datetime] = None, fields: Optional[dict] = None,
                   dedupe_s: float = 0.0) -> tuple[Alert, str]:
    """Returns (alert, "created" | "grouped" | "reopened"). `fields` (e.g. dedupe_key) are set on the
    incident in every case. dedupe_s: a repeat within this many seconds of the last one is the SAME
    report delivered twice (e.g. two requests refreshing at once) and is not counted again.
    The caller commits."""
    now = now or datetime.now(timezone.utc)
    fp = fp or fingerprint(device_id, lab_id, title)
    fields = fields or {}
    _lock(db, fp)
    a = db.scalar(select(Alert).where(Alert.fingerprint == fp, Alert.is_resolved.is_(False))
                  .order_by(Alert.created_at.desc()).limit(1))
    if a is not None:
        last = a.last_seen_at if a.last_seen_at is None or a.last_seen_at.tzinfo else a.last_seen_at.replace(tzinfo=timezone.utc)
        if dedupe_s and last is not None and (now - last).total_seconds() < dedupe_s:
            return a, "duplicate"
        a.occurrences = (a.occurrences or 1) + 1
        a.last_seen_at = now
        if _RANK.get(_sev(severity), 0) > _RANK.get(_sev(a.severity), 0):
            db.add(IncidentNote(alert_id=a.id, kind="STATE", created_at=now,
                                text=f"Severity raised from {_sev(a.severity)} to {_sev(severity)} by a new occurrence: {detail}"[:2000]))
            a.severity = severity
        for k, v in fields.items():
            setattr(a, k, v)
        return a, "grouped"
    r = db.scalar(select(Alert).where(Alert.fingerprint == fp, Alert.is_resolved.is_(True),
                                      Alert.resolved_at.is_not(None), Alert.resolved_at >= now - REOPEN_WINDOW)
                  .order_by(Alert.resolved_at.desc()).limit(1))
    if r is not None:
        resolved_at = r.resolved_at if r.resolved_at.tzinfo else r.resolved_at.replace(tzinfo=timezone.utc)
        gap = int((now - resolved_at).total_seconds())
        db.add(IncidentNote(alert_id=r.id, kind="STATE", created_at=now, text=(
            f"Reopened automatically: the condition returned {gap} s after it was resolved"
            + (f" (previous resolution: {r.resolution})" if r.resolution else "") + f". {detail}")[:2000]))
        r.is_resolved, r.state, r.resolved_at, r.resolved_by_id, r.resolution = False, "OPEN", None, None, None
        r.reopened_count = (r.reopened_count or 0) + 1
        r.occurrences = (r.occurrences or 1) + 1
        r.last_seen_at = now
        if _RANK.get(_sev(severity), 0) > _RANK.get(_sev(r.severity), 0):
            r.severity = severity
        for k, v in fields.items():
            setattr(r, k, v)
        return r, "reopened"
    a = Alert(lab_id=lab_id, device_id=device_id, severity=severity, title=title[:128], detail=detail,
              fingerprint=fp, occurrences=1, last_seen_at=now, created_at=now, **fields)
    db.add(a)
    db.flush()
    return a, "created"


# ----------------------------------------------------------------- quality ---
def quality(db: Session, since: datetime, until: datetime) -> dict:
    """Alert-quality analytics for the period: how much grouping absorbs, noisy sources, recurrence,
    time to acknowledge / resolve, alert storms. Read-only."""
    rows = db.scalars(select(Alert).where(Alert.created_at >= since, Alert.created_at < until)).all()

    def utc(d):
        return None if d is None else d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    reports = sum(a.occurrences or 1 for a in rows)
    fps: dict[str, list[Alert]] = {}
    for a in rows:
        fps.setdefault(a.fingerprint or fingerprint(a.device_id, a.lab_id, a.title), []).append(a)
    by_dev: dict[Any, int] = {}
    for a in rows:
        by_dev[a.device_id] = by_dev.get(a.device_id, 0) + (a.occurrences or 1)
    ack = [(utc(a.acknowledged_at) - utc(a.created_at)).total_seconds() for a in rows if a.acknowledged_at]
    manual = [(utc(a.resolved_at) - utc(a.created_at)).total_seconds() for a in rows
              if a.resolved_at and a.resolved_by_id]
    auto = [(utc(a.resolved_at) - utc(a.created_at)).total_seconds() for a in rows
            if a.resolved_at and not a.resolved_by_id]
    per_min: dict[str, int] = {}
    for a in rows:
        k = utc(a.created_at).strftime("%Y-%m-%d %H:%M")
        per_min[k] = per_min.get(k, 0) + 1
    storms = sorted(((k, n) for k, n in per_min.items() if n >= 5), key=lambda x: -x[1])[:5]
    sev: dict[str, int] = {}
    for a in rows:
        sev[_sev(a.severity)] = sev.get(_sev(a.severity), 0) + 1
    top = sorted(fps.items(), key=lambda kv: -sum(a.occurrences or 1 for a in kv[1]))[:8]
    return {
        "period": {"since": since.isoformat(), "until": until.isoformat()},
        "incidents": len(rows), "reports": reports,
        # share of reports that did not become a new row (grouped or reopened)
        "grouped_share": round(1 - len(rows) / reports, 3) if reports else 0.0,
        # rows with a fingerprint that already had a row in the period (before grouping existed, or
        # a new episode after the reopen window)
        "repeat_rows": sum(len(v) - 1 for v in fps.values()),
        "distinct_conditions": len(fps),
        "by_severity": sev,
        "noisy_devices": sorted(({"device_id": k, "reports": v} for k, v in by_dev.items()),
                                key=lambda x: -x["reports"])[:8],
        "top_conditions": [{"fingerprint": k, "title": v[0].title, "rows": len(v),
                            "reports": sum(a.occurrences or 1 for a in v),
                            "reopened": sum(a.reopened_count or 0 for a in v)} for k, v in top],
        "reopened_incidents": sum(1 for a in rows if (a.reopened_count or 0) > 0),
        "time_to_acknowledge_s_median": round(median(ack)) if ack else None,
        "time_to_resolve_s_median": {"by_staff": round(median(manual)) if manual else None,
                                     "condition_cleared": round(median(auto)) if auto else None},
        "open": sum(1 for a in rows if not a.is_resolved),
        "storms": [{"minute": k, "new_incidents": n} for k, n in storms],
    }

```
