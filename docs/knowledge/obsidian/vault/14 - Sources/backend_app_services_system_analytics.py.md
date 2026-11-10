---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/system_analytics.py"
source_hash: "2d20304c4df454f62389511943b8b235a9fe874dff72b622d8986e61113aeb57"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/system_analytics.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_analytics.py]] - imports
- [[backend_app_api_routes_system.py]] - imports
- [[backend_app_services_agent.py]] - imports
- [[backend_app_services_reports_center.py]] - imports
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs

```py
"""
System-wide analytics for the whole Smart Lab (not only the door): one server-side aggregation per
subsystem, daily series over a window, and the freshness of every data source.

Every number comes from a real table (named in `source`); nothing is estimated here. A source with
no rows in the window is reported as `available: False`, never as a zero chart. Freshness:
  live   - last record younger than its expected cadence x 3
  stale  - older than that but within 7 days
  offline / never - older, or no record at all
KPI definitions live in KPIS (also served at /analytics/kpis) so pages, reports and the AI agent
share one definition.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

# source -> (table, time column, expected cadence in seconds)
SOURCES = {
    "environment": ("sensor_readings", "recorded_at", 60),
    "door": ("access_events", "created_at", 3600),
    "robots": ("robot_events", "occurred_at", 600),
    "consumables": ("inventory_measurements", "recorded_at", 300),
    "inventory": ("inventory_transactions", "recorded_at", 86400),
    "cameras": ("security_events", "created_at", 3600),
    "pcs": ("equipment_sessions", "started_at", 86400),
    "automation": ("integration_events", "occurred_at", 3600),
    "alerts": ("alerts", "created_at", 86400),
}

KPIS = [
    {"id": "door_granted", "name": "Door access granted", "unit": "events/day", "source": "access_events",
     "rule": "count of result=GRANTED per day", "kind": "measured"},
    {"id": "door_denied", "name": "Door access denied", "unit": "events/day", "source": "access_events",
     "rule": "count of result=DENIED per day", "kind": "measured"},
    {"id": "env_temp_avg", "name": "Average temperature", "unit": "°C", "source": "sensor_readings",
     "rule": "daily mean of metric=temperature", "kind": "measured"},
    {"id": "env_humidity_avg", "name": "Average humidity", "unit": "%", "source": "sensor_readings",
     "rule": "daily mean of metric=humidity", "kind": "measured"},
    {"id": "env_hazard_readings", "name": "Smoke / flame readings above zero", "unit": "readings/day",
     "source": "sensor_readings", "rule": "count of metric in (smoke, flame) with value > 0 per day", "kind": "measured"},
    {"id": "robot_events", "name": "Robot events", "unit": "events/day", "source": "robot_events",
     "rule": "count per robot per day (movements, telemetry changes)", "kind": "measured"},
    {"id": "robot_movements", "name": "Robot movements completed", "unit": "movements/day", "source": "robot_events",
     "rule": "count of kind=MOVEMENT_STOPPED per robot per day", "kind": "measured"},
    {"id": "bin_weight", "name": "Consumables bin weight", "unit": "g", "source": "inventory_measurements",
     "rule": "daily min / max of mass_g per bin", "kind": "measured"},
    {"id": "inventory_tx", "name": "Inventory transactions", "unit": "transactions/day", "source": "inventory_transactions",
     "rule": "count per day", "kind": "measured"},
    {"id": "camera_events", "name": "Camera security events", "unit": "events/day", "source": "security_events",
     "rule": "count per kind per day", "kind": "measured (detections are not confirmed identities)"},
    {"id": "pc_hours", "name": "Lab PC usage", "unit": "hours/day", "source": "equipment_sessions",
     "rule": "sum of (ended_at or now) - started_at per day of start", "kind": "calculated"},
    {"id": "automation_delivery", "name": "Automation deliveries", "unit": "events/day", "source": "integration_events",
     "rule": "count per delivery_status per day", "kind": "measured"},
    {"id": "alerts", "name": "Alerts raised", "unit": "alerts/day", "source": "alerts",
     "rule": "count per severity per day", "kind": "measured"},
]


def _rows(db: Session, sql: str, **kw):
    return [dict(r._mapping) for r in db.execute(text(sql), kw)]


def freshness(db: Session, now: datetime) -> dict:
    out = {}
    for key, (table, col, cadence) in SOURCES.items():
        r = db.execute(text(f"select max({col}) as last, count(*) as n from {table}")).one()
        last = r.last
        if last is None:
            state = "never"
            age = None
        else:
            age = (now - last).total_seconds()
            state = "live" if age <= cadence * 3 else "stale" if age <= 7 * 86400 else "offline"
        out[key] = {"source": table, "last": last.isoformat() if last else None, "age_s": round(age) if age is not None else None,
                    "records": r.n, "state": state, "expected_every_s": cadence}
    return out


def _days(start: datetime, days: int) -> list[str]:
    return [(start + timedelta(days=i)).date().isoformat() for i in range(days + 1)]


def system(db: Session, days: int = 30, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    axis = _days(since, days)
    p = {"since": since}

    def pivot(rows, key, val):
        """[{day, key, val}] -> [{day, k1: v, k2: v}] for every day of the window."""
        keys = sorted({str(r[key]) for r in rows})
        by = {d: {"day": d, **{k: 0 for k in keys}} for d in axis}
        for r in rows:
            d = r["day"].isoformat() if hasattr(r["day"], "isoformat") else str(r["day"])
            if d in by:
                by[d][str(r[key])] = round(float(r[val]), 2)
        return {"keys": keys, "series": list(by.values()), "available": bool(rows)}

    door = pivot(_rows(db, """select date(created_at) as day, coalesce(result,'OTHER') as k, count(*) as v
                              from access_events where created_at >= :since group by 1,2""", **p), "k", "v")
    env = _rows(db, """select date(recorded_at) as day, metric, avg(value) as avg, min(value) as min, max(value) as max,
                              count(*) filter (where value > 0) as positive, count(*) as n
                       from sensor_readings where recorded_at >= :since group by 1,2""", **p)
    env_series = {d: {"day": d} for d in axis}
    for r in env:
        d = r["day"].isoformat()
        if d not in env_series:
            continue
        m = r["metric"]
        if m in ("temperature", "humidity"):
            env_series[d][f"{m}_avg"] = round(r["avg"], 1)
            env_series[d][f"{m}_min"] = round(r["min"], 1)
            env_series[d][f"{m}_max"] = round(r["max"], 1)
        elif m in ("smoke", "flame", "motion"):
            env_series[d][f"{m}_pos"] = r["positive"]
    robots = pivot(_rows(db, """select date(e.occurred_at) as day, d.device_uid as k, count(*) as v
                               from robot_events e join devices d on d.id = e.device_id
                               where e.occurred_at >= :since group by 1,2""", **p), "k", "v")
    moves = pivot(_rows(db, """select date(e.occurred_at) as day, d.device_uid as k, count(*) as v
                              from robot_events e join devices d on d.id = e.device_id
                              where e.occurred_at >= :since and e.kind = 'MOVEMENT_STOPPED' group by 1,2""", **p), "k", "v")
    bins = _rows(db, """select date(recorded_at) as day, bin_id, min(mass_g) as min, max(mass_g) as max, avg(mass_g) as avg
                        from inventory_measurements where recorded_at >= :since group by 1,2 order by 1""", **p)
    tx = pivot(_rows(db, """select date(recorded_at) as day, coalesce(kind::text, 'TX') as k, count(*) as v
                           from inventory_transactions where recorded_at >= :since group by 1,2""", **p), "k", "v")
    cams = pivot(_rows(db, """select date(created_at) as day, kind as k, count(*) as v
                             from security_events where created_at >= :since group by 1,2""", **p), "k", "v")
    pcs = pivot(_rows(db, """select date(started_at) as day, 'hours' as k,
                                    sum(extract(epoch from (coalesce(ended_at, now()) - started_at))) / 3600.0 as v
                             from equipment_sessions where started_at >= :since group by 1,2""", **p), "k", "v")
    auto = pivot(_rows(db, """select date(occurred_at) as day, coalesce(delivery_status,'UNKNOWN') as k, count(*) as v
                             from integration_events where occurred_at >= :since group by 1,2""", **p), "k", "v")
    al = pivot(_rows(db, """select date(created_at) as day, severity as k, count(*) as v
                           from alerts where created_at >= :since group by 1,2""", **p), "k", "v")
    totals = {
        "door_events": sum(sum(v for k, v in s.items() if k != "day") for s in door["series"]),
        "robot_events": sum(sum(v for k, v in s.items() if k != "day") for s in robots["series"]),
        "alerts": sum(sum(v for k, v in s.items() if k != "day") for s in al["series"]),
        "camera_events": sum(sum(v for k, v in s.items() if k != "day") for s in cams["series"]),
        "pc_hours": round(sum(s.get("hours", 0) for s in pcs["series"]), 1),
        "env_readings": sum(r["n"] for r in env),
    }
    return {
        "generated_at": now.isoformat(), "days": days, "since": since.isoformat(), "timezone": "UTC (days)",
        "freshness": freshness(db, now), "totals": totals,
        "door": door, "environment": {"series": list(env_series.values()), "available": bool(env)},
        "robots": robots, "robot_movements": moves,
        "bins": {"rows": [{**r, "day": r["day"].isoformat()} for r in bins], "available": bool(bins)},
        "inventory_tx": tx, "cameras": cams, "pcs": pcs, "automation": auto, "alerts": al,
        "kpis": KPIS,
    }


def _has_col(db: Session, table: str, col: str) -> bool:
    return bool(db.execute(text("select 1 from information_schema.columns where table_name=:t and column_name=:c"),
                           {"t": table, "c": col}).first())

```
