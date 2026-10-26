"""
Reliability centre API (2026-10-18): dependency graph / digital twin with impact and a sandboxed
what-if, incident investigation, configuration drift, request performance + objectives, the action
policy, capacity, backups + restore drill, the operator briefing. Staff read; administrators accept
drift deviations and capture baselines. Everything is read-only towards devices: nothing here sends a
command to a door, robot, camera, PC or controller. Audited where a person decides something.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_staff
from app.core.config import settings
from app.db.session import engine, get_db
from app.models import Alert, AuditLog, SystemSetting, User
from app.services import alert_grouping, briefing, dependency_graph, drift, investigate, perfmon, policy

router = APIRouter(prefix="/reliability", tags=["reliability"])


def _services(db: Session, user: User) -> list[dict]:
    from app.api.routes.system import services
    return services(db, user)["services"]


def _restore_status() -> Optional[dict]:
    p = os.path.join(os.path.dirname(settings.BACKUP_STATUS_PATH or "/backups/x"), "restore_drill_status.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ graph ---
@router.get("/graph")
def graph(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    g = dependency_graph.build(_services(db, user))
    return {**g, "likely_roots": dependency_graph.likely_roots(g)}


class WhatIf(BaseModel):
    node: str = Field(max_length=120)


@router.post("/graph/whatif")
def whatif(req: WhatIf, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """SIMULATION only: the consequences of `node` failing now. Nothing is changed."""
    g = dependency_graph.build(_services(db, user))
    out = dependency_graph.whatif(g, req.node)
    if out.get("error"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown component")
    return out


# --------------------------------------------------------------- incidents ---
@router.get("/incidents/{incident_id}/investigate")
def investigate_incident(incident_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    a = db.get(Alert, incident_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return investigate.investigate(db, a, _services(db, user))


@router.get("/alert-quality")
def alert_quality(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), _: User = Depends(require_staff)):
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    return alert_grouping.quality(db, now - timedelta(days=days), now)


# ------------------------------------------------------------------- drift ---
@router.get("/drift")
def drift_check(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return {**drift.check(db), "history": drift.history(db)[-10:]}


class AcceptIn(BaseModel):
    id: str = Field(max_length=120)
    reason: str = Field(min_length=5, max_length=300)
    days: Optional[int] = Field(default=None, ge=1, le=365)


@router.post("/drift/accept")
def drift_accept(req: AcceptIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Accept a deviation with a reason and an optional expiry. It stays visible; the baseline is not changed."""
    rec = drift.accept(db, req.id, req.reason, admin.full_name, req.days)
    db.add(AuditLog(actor_user_id=admin.id, action="DRIFT_DEVIATION_ACCEPTED", entity_type="config",
                    entity_id=req.id[:48], detail=rec))
    db.commit()
    return rec


# ------------------------------------------------------------- performance ---
@router.get("/performance")
def performance(_: User = Depends(require_staff), db: Session = Depends(get_db)):
    pool = engine.pool
    row = db.get(SystemSetting, "perf.baseline")
    saved = json.loads(row.value) if row and row.value else None
    cur = perfmon.summary()
    compare = []
    if saved:
        base = {r["route"]: r for r in saved.get("routes", [])}
        for r in cur["routes"]:
            b = base.get(r["route"])
            if b and b.get("p95") and r["p95"] and b["n"] >= perfmon.MIN_SAMPLES and r["n"] >= perfmon.MIN_SAMPLES:
                compare.append({"route": r["route"], "baseline_p95": b["p95"], "current_p95": r["p95"],
                                "change_pct": round(100 * (r["p95"] - b["p95"]) / b["p95"])})
    return {"summary": cur, "regressions": perfmon.regressions(), "objectives": perfmon.objectives(),
            "baseline": {"captured_at": saved.get("captured_at") if saved else None,
                         "note": "compare only under comparable load", "compare": compare},
            "db_pool": {"size": pool.size(), "checked_out": pool.checkedout(), "overflow": pool.overflow()}}


@router.post("/performance/baseline")
def capture_baseline(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    snap = {**perfmon.summary(top=200), "captured_at": datetime.now(timezone.utc).isoformat()}
    row = db.get(SystemSetting, "perf.baseline")
    if row is None:
        db.add(SystemSetting(key="perf.baseline", value=json.dumps(snap), updated_at=datetime.now(timezone.utc)))
    else:
        row.value, row.updated_at = json.dumps(snap), datetime.now(timezone.utc)
    db.add(AuditLog(actor_user_id=admin.id, action="PERF_BASELINE_CAPTURED", entity_type="system",
                    entity_id="perf", detail={"requests": snap["requests"], "routes": len(snap["routes"])}))
    db.commit()
    return {"captured_at": snap["captured_at"], "requests": snap["requests"], "routes": len(snap["routes"])}


# ------------------------------------------------------------------ policy ---
@router.get("/policy")
def policy_table(_: User = Depends(require_staff)):
    return {"rules": policy.table(), "results": [policy.ALLOWED, policy.APPROVAL, policy.DRY, policy.PROHIBITED,
                                                  policy.UNKNOWN]}


class EvalIn(BaseModel):
    action: str = Field(max_length=64)
    automatic: bool = False


@router.post("/policy/evaluate")
def policy_evaluate(req: EvalIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    from app.services import robot_control
    d = policy.evaluate(req.action, {"automatic": req.automatic, "robot_control": robot_control.MODE})
    db.add(AuditLog(actor_user_id=user.id, action="POLICY_EVALUATED", entity_type="policy",
                    entity_id=req.action[:48], detail=d))
    db.commit()
    return d


# --------------------------------------------------------------- diagnose ---
class DiagnoseIn(BaseModel):
    check: str = Field(default="services", pattern="^(services)$")


@router.post("/diagnose")
def diagnose(req: DiagnoseIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """Re-run the read-only health checks now (policy: health.recheck = allowed). Bounded by their timeouts."""
    from app.services import health_monitor
    t0 = time.perf_counter()
    try:
        health_monitor.check_once()
    except Exception:
        pass
    took = round((time.perf_counter() - t0) * 1000)
    db.add(AuditLog(actor_user_id=user.id, action="DIAGNOSTIC_RUN", entity_type="system", entity_id=req.check,
                    detail={"ms": took, "policy": policy.evaluate("health.recheck")["result"]}))
    db.commit()
    return {"ran_ms": took, "services": _services(db, user)}


# --------------------------------------------------------- capacity / backups ---
@router.get("/capacity")
def capacity(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    out = {"warnings": []}
    try:
        du = shutil.disk_usage(os.path.dirname(settings.BACKUP_STATUS_PATH or "/backups/x"))
        out["disk"] = {"total_gb": round(du.total / 1e9, 1), "free_gb": round(du.free / 1e9, 1),
                       "used_pct": round(100 * du.used / du.total, 1), "where": "the laptop drive holding backups"}
        if du.free / du.total < 0.10:
            out["warnings"].append("less than 10 % disk space left")
    except OSError:
        out["disk"] = None
    out["database_mb"] = round(db.execute(text("select pg_database_size(current_database())")).scalar() / 1e6, 1)
    out["largest_tables"] = [{"table": r[0], "mb": round(r[1] / 1e6, 2)} for r in db.execute(text(
        "select relname, pg_total_relation_size(relid) from pg_catalog.pg_statio_user_tables "
        "order by 2 desc limit 6")).all()]
    out["retention"] = "records are kept indefinitely (no automatic deletion)"
    return out


@router.get("/backups")
def backups(_: User = Depends(require_staff)):
    from app.services.backups import read_status
    return {"backup": read_status(), "restore_drill": _restore_status(),
            "how": "tools/evidence/restore_drill.py restores the newest dump into a NEW isolated database and "
                   "compares every table; production is only read."}


# -------------------------------------------------------------- evaluation ---
@router.get("/evaluation")
def get_evaluation(_: User = Depends(require_staff)):
    """The thesis evaluation (priority B): measured before/after results with their conditions and the script or
    document that produced them; unmeasured items are listed as such (app/data/evaluation.json)."""
    import json
    import os
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "evaluation.json"),
              encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- briefing ---
@router.get("/briefing")
def get_briefing(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    from app.services.backups import read_status
    try:
        dr = drift.check(db)
    except Exception:
        dr = None
    return briefing.build(db, _services(db, user), dr, [r for r in perfmon.regressions() if r.get("new", True)],
                          read_status(), _restore_status())
