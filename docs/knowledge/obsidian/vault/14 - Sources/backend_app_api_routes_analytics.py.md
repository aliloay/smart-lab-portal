---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/analytics.py"
source_hash: "09d5befd20bcbd3dab3f91546fc98acc13234a0572ac6d0ffa26ab98e018679b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/analytics.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_anomalies.py]] - imports
- [[backend_app_services_analytics.py]] - imports
- [[backend_app_services_system_analytics.py]] - imports

```py
"""Aggregates for the Operations Center, the lab digital twin and "my usage"."""
import csv
import io
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_staff
from app.db.session import get_db
from app.models import Lab, User
from app.services import analytics, system_analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/operations")
def operations(days: int = Query(30, ge=1, le=365),
               lab_id: Optional[int] = None,
               db: Session = Depends(get_db), _: User = Depends(require_staff)):
    from app.core.ttl import cached     # shared 20 s: identical for every staff viewer (2026-10-27 ramp)
    return cached(f"analytics.operations.{days}.{lab_id}", 20, lambda: analytics.operations(db, days, lab_id))


@router.get("/system")
def system(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Every subsystem (door, environment, robots, consumables, cameras, PCs, automation, alerts):
    daily series, totals and the freshness of each data source. Real tables only. Shared 20 s (app/core/ttl.py)."""
    from app.core.ttl import cached
    return cached(f"analytics.system.{days}", 20, lambda: system_analytics.system(db, days))


@router.get("/kpis")
def kpis(_: User = Depends(require_staff)):
    """The shared KPI catalogue: id, definition, unit, source table, kind."""
    return system_analytics.KPIS


@router.get("/labs/{lab_id}")
def lab_twin(lab_id: int, db: Session = Depends(get_db),
             _: User = Depends(get_current_user)):
    """Typical week, recent days and environment. No per-person data."""
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(404, "Lab not found")
    return analytics.lab_twin(db, lab)


@router.get("/me")
def me(days: int = Query(90, ge=7, le=365), db: Session = Depends(get_db),
       user: User = Depends(get_current_user)):
    """The caller's own bookings only - never anyone else's."""
    return analytics.my_stats(db, user.id, days)


@router.get("/trends")
def trends(weeks: int = Query(8, ge=2, le=52), lab_id: Optional[int] = None,
           db: Session = Depends(get_db), _: User = Depends(require_staff)):
    from app.core.ttl import cached
    return cached(f"analytics.trends.{weeks}.{lab_id}", 20, lambda: analytics.trends(db, weeks, lab_id))


@router.get("/export.csv")
def export_csv(kind: Literal["bookings", "sessions", "events", "weekly"] = "bookings",
               days: int = Query(90, ge=1, le=730),
               db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Recorded rows as CSV, for spreadsheets and the thesis appendix."""
    head, rows = analytics.export_rows(db, kind, days)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(head)
    w.writerows(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="smartlab-{kind}-{days}d-{stamp}.csv"'})


# ------------------------------------------------------------- anomalies ---
@router.get("/anomalies")
def anomalies(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Rules, sensor-fault checks and statistical baselines on the real measurements (no ML - see ml_status).
    Cached 60 s: the scan reads ~25k readings (~0.9 s) and sensors report at most once a minute."""
    import time as _t
    from app.services import anomalies as an
    if _anom_cache["body"] is None or _t.monotonic() - _anom_cache["at"] > 60:
        _anom_cache.update(at=_t.monotonic(), body=an.scan(db))
    return _anom_cache["body"]


_anom_cache: dict = {"at": 0.0, "body": None}


@router.post("/anomalies/raise")
def raise_anomaly(index: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """Raise finding #index of the current scan as an incident (once per day per device/metric/kind)."""
    from fastapi import HTTPException
    from app.models import AuditLog
    from app.services import anomalies as an
    found = (_anom_cache["body"] or an.scan(db))["findings"]      # the same list the page showed
    if not 0 <= index < len(found):
        raise HTTPException(404, "No such finding (the scan changed - reload)")
    created, alert_id = an.raise_alert(db, found[index])
    db.add(AuditLog(actor_user_id=user.id, action="ANOMALY_RAISED", entity_type="alert", entity_id=str(alert_id),
                    detail={"created": created, "kind": found[index]["kind"], "metric": found[index]["metric"]}))
    db.commit()
    return {"created": created, "incident_id": alert_id}

```
