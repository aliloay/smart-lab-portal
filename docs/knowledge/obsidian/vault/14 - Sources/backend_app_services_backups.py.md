---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/backups.py"
source_hash: "36045164301aa16abba4996fa44b4a91cf3ca4285d9f4b00a7122b80fa4a9ee9"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/backups.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_reliability.py]] - imports
- [[backend_app_api_routes_system.py]] - imports
- [[backend_app_core_config.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services_notifications.py]] - imports
- [[backend_app_services_devices.py]] - imports
- [[backend_app_services_drift.py]] - imports

```py
"""
Watching the database backups (docker-compose service `backup`).

The backup service dumps the database every BACKUP_EVERY_HOURS, checks the
dump can be read back, and writes backup_status.json next to the dumps. The
portal reads that file whenever it refreshes device liveness:

  OK              last run succeeded, recently
  FAILED          the last run failed                  -> one CRITICAL alert
  STALE           no success for 2 intervals + 1 hour  -> one CRITICAL alert
  NOT_CONFIGURED  no status path set (tests, a bare install) - silent

A later success resolves the alert. Admins are notified once per outage.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Alert, AlertSeverity
from app.services.notifications import admin_ids, notify

TITLE = "Database backup failing"
DEDUPE = "backup:failing"


_status_cache: dict = {"key": None, "data": None}


def read_status() -> dict:
    path = settings.BACKUP_STATUS_PATH
    if not path:
        return {"state": "NOT_CONFIGURED"}
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return {"state": "MISSING", "detail": "The backup service has not reported yet (is it running?)."}
    # The file sits on a Windows bind mount (slow to read) and changes only every few hours:
    # re-read it only when its modification time or size changes.
    key = (str(p), st.st_mtime_ns, st.st_size)
    if _status_cache["key"] == key:
        s = _status_cache["data"]
    else:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"state": "FAILED", "detail": "The backup status file cannot be read."}
        _status_cache.update(key=key, data=s)
    every = float(s.get("every_hours") or 6)
    last_ok = s.get("last_success")
    out = {"last_attempt": s.get("last_attempt"), "last_success": last_ok, "file": s.get("file"),
           "size_kb": s.get("size_kb"), "every_hours": every}
    if not s.get("ok"):
        return {**out, "state": "FAILED", "detail": f"The last backup attempt ({s.get('last_attempt')}) failed."}
    age = datetime.now(timezone.utc) - datetime.fromisoformat(last_ok)
    if age > timedelta(hours=2 * every + 1):
        return {**out, "state": "STALE",
                "detail": f"No successful backup for {age.total_seconds() / 3600:.0f} h (expected every {every:g} h)."}
    return {**out, "state": "OK"}


def check(db: Session) -> dict:
    """Read the status; open or resolve the backup alert. The caller commits."""
    s = read_status()
    open_alert = db.scalar(select(Alert).where(Alert.dedupe_key == DEDUPE, Alert.is_resolved.is_(False)))
    if s["state"] in ("FAILED", "STALE", "MISSING"):
        if open_alert is None:
            db.add(Alert(severity=AlertSeverity.CRITICAL, title=TITLE, detail=s["detail"], dedupe_key=DEDUPE))
            notify(db, admin_ids(db), "SYSTEM", TITLE, body=s["detail"] + " Check the backup service.",
                   link="/admin/settings", severity="critical")
            db.flush()
    elif open_alert is not None:
        now = datetime.now(timezone.utc)
        open_alert.is_resolved, open_alert.resolved_at = True, now
        open_alert.dedupe_key = f"{DEDUPE}:{open_alert.id}"      # free the key for a later outage
        db.flush()
    return s

```
