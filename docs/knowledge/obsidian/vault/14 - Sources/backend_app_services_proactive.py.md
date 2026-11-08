---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/proactive.py"
source_hash: "58f3d6e3f9e2e0fd39a0ee585ec16b0ee03ac9f53c9b7fc9bc7a11c2c4836ff8"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/proactive.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_emergency.py]] - imports
- [[backend_app_services_agent.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services_devices.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_inventory.py]] - imports

```py
"""
Proactive suggestions (2026-10-27, owner: "actionable findings, deduplicated, with evidence and timestamps; confirmed
incidents kept apart from possible anomalies; computed on a schedule or when data changes - not on every refresh").

Rules only, all local, all from stored records:
  CONFIRMED  offline devices (no report within their own interval), low consumables (calibrated count at or below the
             reorder level), recurring problems (agent.insights: the same alert / refusal / fault again and again)
  POSSIBLE   unusual sensor readings (the latest value far outside its own last-7-days spread, robust z >= 4),
             occupancy change (door entries in the last 24 h vs the daily mean of the 7 days before: x3 or more,
             or none at all where there normally are some)
Each finding: key (for de-duplication), kind, level, title, evidence [{what, value, at}], suggestion. No root causes are
invented - a suggestion says what to check, never why it happened.

Recomputed only when the data fingerprint (newest row id of the source tables) changes, and at most every 60 s.
"""
from __future__ import annotations

import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccessEvent, Alert, Device, EventType, InventoryBin, SensorReading

MIN_INTERVAL_S = 60
Z_MIN = 4.0
_cache: dict = {"fp": None, "at": 0.0, "items": []}


def _utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _iso(dt) -> Optional[str]:
    dt = _utc(dt)
    return dt.isoformat() if dt else None


def fingerprint(db: Session) -> tuple:
    return (db.scalar(select(func.max(SensorReading.id))), db.scalar(select(func.max(Alert.id))),
            db.scalar(select(func.max(AccessEvent.id))), db.scalar(select(func.max(Device.last_seen_at))),
            db.scalar(select(func.max(InventoryBin.last_measured_at))))


def compute(db: Session, now: Optional[datetime] = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    out: dict[str, dict] = {}

    def add(item: dict):
        out.setdefault(item["key"], item)                     # de-duplicated by key: the first (strongest) wins

    # --- CONFIRMED: offline devices -------------------------------------------------------------------------
    from app.services.devices import is_fresh, refresh_liveness
    for d in refresh_liveness(db):
        if is_fresh(d, now) is False:
            add({"key": f"offline:{d.device_uid}", "kind": "offline", "level": "CONFIRMED",
                 "title": f"{d.name} is offline",
                 "evidence": [{"what": "last report", "value": d.device_uid, "at": _iso(d.last_seen_at)}],
                 "suggestion": "Check its power and network link, then that its service is running."})

    # --- CONFIRMED: low consumables -------------------------------------------------------------------------
    from app.services import inventory as inv
    for b in db.scalars(select(InventoryBin).where(InventoryBin.is_active.is_(True))).all():
        o = inv.bin_out(db, b, now)
        if o["low"]:
            add({"key": f"low:{b.code}", "kind": "low_stock", "level": "CONFIRMED",
                 "title": f"{o['item_name']} is low ({o['qty_est']} left)",
                 "evidence": [{"what": "estimated count", "value": o["qty_est"], "at": _iso(o.get("last_reading_at"))},
                              {"what": "reorder level", "value": b.reorder_qty, "at": None}],
                 "suggestion": "Reorder or refill this bin."})

    # --- CONFIRMED: recurring problems (the same alert / refusal / fault repeating) --------------------------
    from app.services import agent
    for i in agent.insights(db, now - timedelta(days=14), now)[:8]:
        add({"key": f"recurring:{i.get('kind', '')}:{i['title']}", "kind": "recurring", "level": "CONFIRMED",
             "title": i["title"],
             "evidence": [{"what": "times in 14 days", "value": i.get("count"), "at": _iso(i.get("last"))}],
             "suggestion": i.get("recommendation") or "Look at the repeated records together."})

    # --- POSSIBLE: unusual sensor readings (robust z-score against the metric's own last 7 days) -------------
    since = now - timedelta(days=7)
    rows = db.execute(select(SensorReading.lab_id, SensorReading.metric, SensorReading.value, SensorReading.recorded_at)
                      .where(SensorReading.recorded_at >= since).order_by(SensorReading.recorded_at)).all()
    series: dict[tuple, list] = {}
    for lab_id, metric, value, at in rows:
        series.setdefault((lab_id, metric), []).append((value, at))
    for (lab_id, metric), vals in series.items():
        if metric in ("motion", "flame", "smoke", "water_leak", "emergency") or len(vals) < 30:
            continue                                            # on/off signals are alarms, not trends
        hist = [v for v, _ in vals[:-1]]
        last, at = vals[-1]
        med = statistics.median(hist)
        mad = statistics.median([abs(v - med) for v in hist]) or 0.0
        if mad == 0:
            continue
        z = 0.6745 * (last - med) / mad
        if abs(z) >= Z_MIN and now - _utc(at) < timedelta(hours=2):
            add({"key": f"sensor:{lab_id}:{metric}", "kind": "sensor", "level": "POSSIBLE",
                 "title": f"Unusual {metric}: {last:g} (normally about {med:g})",
                 "evidence": [{"what": "latest", "value": round(last, 2), "at": _iso(at)},
                              {"what": "7-day median", "value": round(med, 2), "at": None},
                              {"what": "robust z", "value": round(z, 1), "at": None}],
                 "suggestion": "Check the reading at the node (sensor position, airflow) before acting on it."})

    # --- POSSIBLE: occupancy change -------------------------------------------------------------------------
    def entries(a, b):
        return db.scalar(select(func.count(AccessEvent.id)).where(AccessEvent.event_type == EventType.ACCESS_GRANTED,
                                                                  AccessEvent.created_at >= a, AccessEvent.created_at < b)) or 0
    last24 = entries(now - timedelta(hours=24), now)
    before = entries(now - timedelta(days=8), now - timedelta(hours=24)) / 7
    if before >= 2 and (last24 >= 3 * before or last24 == 0):
        add({"key": "occupancy", "kind": "occupancy", "level": "POSSIBLE",
             "title": f"Door entries changed: {last24} in the last 24 h (daily mean before: {before:.1f})",
             "evidence": [{"what": "entries last 24 h", "value": last24, "at": _iso(now)},
                          {"what": "daily mean, 7 days before", "value": round(before, 1), "at": None}],
             "suggestion": "Compare with the booking calendar (an exam or a holiday explains most changes)."})

    order = {"CONFIRMED": 0, "POSSIBLE": 1}
    return sorted(out.values(), key=lambda i: (order[i["level"]], i["kind"], i["title"]))


def current(db: Session) -> dict:
    """The cached list; recomputed only when the data changed and the last run is >= 60 s old."""
    fp = fingerprint(db)
    fresh = time.monotonic() - _cache["at"] < MIN_INTERVAL_S
    if _cache["fp"] != fp and not fresh or _cache["fp"] is None:
        _cache.update(fp=fp, at=time.monotonic(), items=compute(db), computed_at=datetime.now(timezone.utc).isoformat())
    return {"items": _cache["items"], "computed_at": _cache.get("computed_at"),
            "note": "Rules on stored records. CONFIRMED = the record shows it; POSSIBLE = unusual, check before acting."}

```
