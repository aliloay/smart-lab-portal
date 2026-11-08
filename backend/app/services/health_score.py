"""
Lab Health Score (2026-10-26, priority H): one number per lab, 0-100, that staff can take apart.

Every part comes from records the portal already keeps; a part with no data is UNKNOWN and left out of the average
(never counted as healthy or as zero), and the answer says how much of the score is covered by data.

  devices      30  share of the lab's devices (not simulators) reporting in time
  alerts       25  open alerts: each CRITICAL -0.5, each WARNING -0.15, INFO -0.05 (floor 0)
  environment  20  share of the environment metrics whose newest reading is VALID (not STALE / OFFLINE / OUT_OF_RANGE)
  issues       15  active issue reports: HIGH/CRITICAL -0.3 each, others -0.1 (floor 0)
  hazards      10  smoke / flame hazard open -> 0, and the whole score is capped at 20
GOOD >= 85, FAIR >= 60, else POOR. Advisory: it ranks attention, it does not certify that a lab is safe.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, AlertSeverity, Device, DeviceType, Issue, Lab
from app.services.devices import is_fresh

WEIGHTS = {"devices": 30, "alerts": 25, "environment": 20, "issues": 15, "hazards": 10}
ALERT_COST = {AlertSeverity.CRITICAL: 0.5, AlertSeverity.WARNING: 0.15, AlertSeverity.INFO: 0.05}


def _band(score: Optional[float]) -> str:
    if score is None:
        return "UNKNOWN"
    return "GOOD" if score >= 85 else "FAIR" if score >= 60 else "POOR"


def score_labs(db: Session, now: Optional[datetime] = None) -> list[dict]:
    from app.services import environment
    from app.services.issues import ACTIVE
    from app.models import IssueSeverity
    now = now or datetime.now(timezone.utc)
    labs = db.scalars(select(Lab).where(Lab.is_active.is_(True)).order_by(Lab.code)).all()
    if not labs:
        return []
    devices = db.scalars(select(Device).where(Device.lab_id.in_([l.id for l in labs]))).all()
    alerts = db.scalars(select(Alert).where(Alert.is_resolved.is_(False))).all()
    issues = db.scalars(select(Issue).where(Issue.status.in_(ACTIVE))).all()
    env = environment.latest_many(db, list(labs), now)
    high = (IssueSeverity.HIGH, IssueSeverity.CRITICAL)
    out = []
    for lab in labs:
        parts: dict[str, dict] = {}
        devs = [d for d in devices if d.lab_id == lab.id and (d.component_state or {}).get("source") != "SIMULATION"
                and d.device_type != DeviceType.OTHER]
        fresh = [is_fresh(d, now) for d in devs]
        known = [f for f in fresh if f is not None]
        parts["devices"] = {"value": (sum(1 for f in known if f) / len(known)) if known else None,
                            "evidence": f"{sum(1 for f in known if f)} of {len(known)} devices reporting"
                            if known else "no devices with a reporting interval"}
        la = [a for a in alerts if a.lab_id == lab.id]
        c = Counter(a.severity for a in la)
        parts["alerts"] = {"value": max(0.0, 1 - sum(ALERT_COST.get(s, 0.1) * n for s, n in c.items())),
                           "evidence": f"{len(la)} open alerts" + (f" ({c[AlertSeverity.CRITICAL]} critical)"
                                                                     if c[AlertSeverity.CRITICAL] else "")}
        e = env.get(lab.id) or {}
        q = [m["quality"] for m in (e.get("metrics") or {}).values() if m["quality"] != "MISSING"]
        if e.get("node") is None or not q:
            parts["environment"] = {"value": None, "evidence": "no environment node / no readings"}
        else:
            ok = sum(1 for x in q if x == "VALID")
            parts["environment"] = {"value": ok / len(q), "evidence": f"{ok} of {len(q)} readings valid"
                                    + ("" if ok == len(q) else f" ({', '.join(sorted(set(x for x in q if x != 'VALID'))).lower()})")}
        li = [i for i in issues if i.lab_id == lab.id]
        nh = sum(1 for i in li if i.severity in high)
        parts["issues"] = {"value": max(0.0, 1 - 0.3 * nh - 0.1 * (len(li) - nh)),
                           "evidence": f"{len(li)} active issue reports ({nh} high/critical)"}
        hz = e.get("hazards") or []
        parts["hazards"] = {"value": 0.0 if hz else 1.0,
                            "evidence": ("hazard: " + ", ".join(hz)) if hz else "no smoke / flame hazard"}
        num = sum(WEIGHTS[k] * p["value"] for k, p in parts.items() if p["value"] is not None)
        den = sum(WEIGHTS[k] for k, p in parts.items() if p["value"] is not None)
        score = round(100 * num / den, 1) if den else None
        if hz and score is not None:
            score = min(score, 20.0)
        for k, p in parts.items():
            p["weight"] = WEIGHTS[k]
            p["value"] = None if p["value"] is None else round(p["value"], 3)
        out.append({"lab_id": lab.id, "lab_code": lab.code, "lab_name": lab.name, "score": score, "band": _band(score),
                    "coverage": round(den / sum(WEIGHTS.values()), 2), "parts": parts,
                    "weakest": min((k for k, p in parts.items() if p["value"] is not None),
                                   key=lambda k: parts[k]["value"], default=None)})
    return out
