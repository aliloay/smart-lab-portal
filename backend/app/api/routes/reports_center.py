"""Reports Centre (CSV / JSON exports), cross-system timeline, inventory discrepancies - staff only."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.db.session import get_db
from app.models import AuditLog, User
from app.services import reports_center as rc

router = APIRouter(prefix="/reports-center", tags=["reports"])


def _range(start: Optional[date], end: Optional[date], days: int) -> tuple[datetime, datetime]:
    e = datetime.combine(end, time.max, tzinfo=timezone.utc) if end else datetime.now(timezone.utc)
    s = datetime.combine(start, time.min, tzinfo=timezone.utc) if start else e - timedelta(days=days)
    if s >= e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The start must be before the end.")
    if (e - s).days > 400:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At most 400 days per report.")
    return s, e


@router.get("")
def catalogue(_: User = Depends(require_staff)):
    return [{"kind": k, "title": v[0], "description": v[3], "source": rc.SOURCES[v[1]][0]} for k, v in rc.REPORTS.items()]


@router.get("/timeline")
def timeline(start: Optional[date] = None, end: Optional[date] = None, days: int = Query(2, ge=1, le=60),
             lab_id: Optional[int] = None, sources: Optional[str] = Query(None, max_length=120),
             limit: int = Query(300, ge=10, le=2000), db: Session = Depends(get_db), _: User = Depends(require_staff)):
    s, e = _range(start, end, days)
    return rc.timeline(db, s, e, lab_id, set(sources.split(",")) if sources else None, limit)


@router.get("/inventory-discrepancies")
def inventory_discrepancies(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return rc.discrepancies(db)


@router.get("/asset-lifecycle")
def asset_lifecycle(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return rc.lifecycle(db)


@router.get("/{kind}")
def report(kind: str, start: Optional[date] = None, end: Optional[date] = None, days: int = Query(7, ge=1, le=400),
           format: Literal["json", "csv"] = "json", db: Session = Depends(get_db), user: User = Depends(require_staff)):
    if kind not in rc.REPORTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown report")
    s, e = _range(start, end, days)
    r = rc.run(db, kind, s, e)
    db.add(AuditLog(actor_user_id=user.id, action="REPORT_EXPORTED" if format == "csv" else "REPORT_VIEWED",
                    entity_type="report", entity_id=kind, detail={"start": r["start"], "end": r["end"], "rows": r["count"]}))
    db.commit()
    if format == "json":
        return r
    buf = io.StringIO()
    buf.write(f"# {r['title']} | source: {r['source']} | {r['start']} to {r['end']} | generated {r['generated_at']}\n")
    for w in r["warnings"]:
        buf.write(f"# WARNING: {w}\n")
    if r["columns"]:
        wr = csv.DictWriter(buf, fieldnames=r["columns"])
        wr.writeheader()
        wr.writerows(r["rows"])
    name = f"smartlab_{kind}_{s.date()}_{e.date()}.csv"
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
