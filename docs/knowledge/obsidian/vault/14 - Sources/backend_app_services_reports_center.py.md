---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/reports_center.py"
source_hash: "b7208ceec843db193ec9a4f1f1136fe053a2ebb77d3c427f5e74ae075be97985"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/reports_center.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_incidents.py]] - imports
- [[backend_app_api_routes_reports_center.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_inventory.py]] - imports
- [[backend_app_services_system_analytics.py]] - imports

```py
"""
Reports Centre, cross-system incident timeline and inventory discrepancies (2026-10-17).

Every row comes from a named table (`source`); nothing is estimated. Each report carries warnings
when its source has no rows in the period, is stale, or the row limit cut it. The timeline lists
records from several subsystems in time order and marks records that happened close together in
the same lab as CO-OCCURRING - timing only, never evidence of who did what: identities are shown
only where the record itself names the person (e.g. a door access by card).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import inventory as inv
from app.services.system_analytics import SOURCES, freshness

ROW_LIMIT = 5000

# kind -> (title, freshness key, SQL with :start/:end, description)
REPORTS: dict[str, tuple[str, str, str, str]] = {
    "access": ("Door access events", "door", """
        select a.created_at as time, l.code as lab, a.event_type, a.method, a.result, a.reason,
               u.full_name as person, a.provenance
        from access_events a left join labs l on l.id = a.lab_id left join users u on u.id = a.user_id
        where a.created_at >= :start and a.created_at < :end order by a.created_at""",
        "Every door event; the person is the one the door controller identified (card / QR / finger / face)."),
    "environment": ("Environment - daily averages", "environment", """
        select date_trunc('day', s.recorded_at) as day, l.code as lab, s.metric, s.unit,
               round(avg(s.value)::numeric, 2) as avg, round(min(s.value)::numeric, 2) as min,
               round(max(s.value)::numeric, 2) as max, count(*) as readings
        from sensor_readings s left join labs l on l.id = s.lab_id
        where s.recorded_at >= :start and s.recorded_at < :end
        group by 1, 2, 3, 4 order by 1, 2, 3""",
        "Daily mean/min/max per lab and metric from the environment nodes."),
    "robots": ("Robot events", "robots", """
        select r.occurred_at as time, d.device_uid as robot, r.kind, r.joint, r.severity, r.source, r.provenance
        from robot_events r join devices d on d.id = r.device_id
        where r.occurred_at >= :start and r.occurred_at < :end order by r.occurred_at""",
        "Robot movements and state changes as reported by the read-only collectors."),
    "cameras": ("Security camera events", "cameras", """
        select e.created_at as time, d.device_uid as camera, l.code as lab, e.kind, e.detail,
               e.people_seen, e.people_inside, e.acknowledged_at, e.provenance
        from security_events e left join devices d on d.id = e.device_id left join labs l on l.id = e.lab_id
        where e.created_at >= :start and e.created_at < :end order by e.created_at""",
        "Camera events. A detection is not a confirmed identity."),
    "pcs": ("Lab PC and equipment sessions", "pcs", """
        select s.started_at, s.ended_at, d.device_uid as device, d.device_type as type, s.state,
               round((extract(epoch from (coalesce(s.ended_at, now()) - s.started_at)) / 3600)::numeric, 2) as hours,
               u.full_name as booked_by
        from equipment_sessions s join devices d on d.id = s.device_id left join users u on u.id = s.user_id
        where s.started_at >= :start and s.started_at < :end order by s.started_at""",
        "Sessions reported by the PC agents and robot collectors; 'booked_by' comes from the booking in force."),
    "inventory": ("Consumables transactions", "inventory", """
        select t.recorded_at as time, b.code as bin, b.item_name, t.kind, t.delta_mass_g, t.delta_qty_est,
               t.qty_est_after, t.actual_count, t.attribution, u.full_name as person, t.note
        from inventory_transactions t join inventory_bins b on b.id = t.bin_id left join users u on u.id = t.user_id
        where t.recorded_at >= :start and t.recorded_at < :end order by t.recorded_at""",
        "Scale changes and staff counts. 'attribution' says how (or whether) a person was linked."),
    "alerts": ("Alerts", "alerts", """
        select a.created_at as time, l.code as lab, a.severity, a.title, a.is_resolved, a.resolved_at, a.provenance
        from alerts a left join labs l on l.id = a.lab_id
        where a.created_at >= :start and a.created_at < :end order by a.created_at""",
        "Alerts raised by the portal and the devices."),
}


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def run(db: Session, kind: str, start: datetime, end: datetime, now: Optional[datetime] = None) -> dict:
    title, fkey, sql, desc = REPORTS[kind]
    rows = [{k: _iso(v) for k, v in r._mapping.items()}
            for r in db.execute(text(sql + f" limit {ROW_LIMIT + 1}"), {"start": start, "end": end})]
    warnings = []
    truncated = len(rows) > ROW_LIMIT
    rows = rows[:ROW_LIMIT]
    if truncated:
        warnings.append(f"More than {ROW_LIMIT} rows - only the first {ROW_LIMIT} are included; narrow the dates.")
    if not rows:
        warnings.append("No records in this period - this is missing data, not a zero.")
    fr = freshness(db, now or datetime.now(timezone.utc)).get(fkey, {})
    if fr.get("state") in ("stale", "offline", "never"):
        warnings.append(f"Source {fr.get('source')} is {fr.get('state')} (last record {fr.get('last') or 'never'}).")
    return {"kind": kind, "title": title, "description": desc, "source": SOURCES[fkey][0],
            "start": start.isoformat(), "end": end.isoformat(), "generated_at": datetime.now(timezone.utc).isoformat(),
            "columns": list(rows[0].keys()) if rows else [], "rows": rows, "count": len(rows),
            "truncated": truncated, "warnings": warnings, "freshness": fr}


# ------------------------------------------------------------------ timeline ---
TIMELINE_SQL = """
select * from (
  select a.created_at as time, 'door' as source, 'access_events' as tbl, a.id, a.lab_id,
         a.event_type || coalesce(' ' || a.result, '') as kind,
         coalesce(a.message, a.reason, '') as summary, u.full_name as person
    from access_events a left join users u on u.id = a.user_id
   where a.created_at >= :start and a.created_at < :end
  union all
  select e.created_at, 'camera', 'security_events', e.id, e.lab_id, e.kind,
         coalesce(e.detail, '') || coalesce(' (people seen ' || e.people_seen || ')', ''), null
    from security_events e where e.created_at >= :start and e.created_at < :end
  union all
  select r.occurred_at, 'robot', 'robot_events', r.id, r.lab_id, r.kind,
         d.device_uid || coalesce(' J' || r.joint, '') || coalesce(' [' || r.severity || ']', ''), null
    from robot_events r join devices d on d.id = r.device_id
   where r.occurred_at >= :start and r.occurred_at < :end and r.kind not in ('JOINT_MOVED')
  union all
  select a.created_at, 'alert', 'alerts', a.id, a.lab_id, a.severity, a.title, null
    from alerts a where a.created_at >= :start and a.created_at < :end
  union all
  select s.recorded_at, 'environment', 'sensor_readings', s.id, s.lab_id, s.metric || ' ALARM',
         s.metric || ' = ' || s.value, null
    from sensor_readings s
   where s.recorded_at >= :start and s.recorded_at < :end and s.metric in ('smoke', 'flame', 'gas') and s.value > 0
  union all
  select s.started_at, 'pc', 'equipment_sessions', s.id, s.lab_id, s.state, d.device_uid || ' session', null
    from equipment_sessions s join devices d on d.id = s.device_id
   where s.started_at >= :start and s.started_at < :end
  union all
  select c.created_at, 'pc-action', 'device_commands', c.id, d.lab_id, c.command || ' ' || c.status,
         coalesce(c.message, ''), u.full_name
    from device_commands c join devices d on d.id = c.device_id left join users u on u.id = c.requested_by_id
   where c.created_at >= :start and c.created_at < :end
) t order by time desc limit :limit"""

CLUSTER_S = 120


def timeline(db: Session, start: datetime, end: datetime, lab_id: Optional[int] = None,
             sources: Optional[set] = None, limit: int = 500) -> dict:
    rows = [dict(r._mapping) for r in db.execute(text(TIMELINE_SQL), {"start": start, "end": end, "limit": limit * 4})]
    if lab_id is not None:
        rows = [r for r in rows if r["lab_id"] == lab_id]
    if sources:
        rows = [r for r in rows if r["source"] in sources]
    rows = rows[:limit]
    labs = {r.id: r.code for r in db.execute(text("select id, code from labs"))}
    # Co-occurrence: consecutive records in the same lab within CLUSTER_S, from >= 2 subsystems.
    cluster, cid = [], 0
    out = []
    for r in sorted(rows, key=lambda x: x["time"]):
        if cluster and (r["lab_id"] != cluster[-1]["lab_id"] or (r["time"] - cluster[-1]["time"]).total_seconds() > CLUSTER_S):
            cid += 1
            cluster = []
        cluster.append(r)
        r["_c"] = cid
    groups: dict[int, set] = {}
    for r in rows:
        groups.setdefault(r["_c"], set()).add(r["source"])
    for r in sorted(rows, key=lambda x: x["time"], reverse=True):
        multi = len(groups[r["_c"]]) > 1 and r["lab_id"] is not None
        out.append({"time": r["time"].isoformat(), "source": r["source"], "kind": r["kind"], "summary": r["summary"],
                    "person": r["person"], "lab": labs.get(r["lab_id"]), "ref": f"{r['tbl']}#{r['id']}",
                    "group": r["_c"] if multi else None})
    return {"start": start.isoformat(), "end": end.isoformat(), "items": out, "count": len(out),
            "co_occurrence_window_s": CLUSTER_S,
            "note": "Records grouped as co-occurring happened in the same lab within 2 minutes. That is timing only - "
                    "it does not show that they are related or who was involved. A person is named only where the "
                    "record itself identifies them."}


# ------------------------------------------------------------ discrepancies ---
def discrepancies(db: Session) -> dict:
    out = []
    bins = db.execute(text("select * from inventory_bins where is_active order by code")).all()
    from app.models import InventoryBin
    for row in bins:
        b = db.get(InventoryBin, row.id)
        measured = inv.qty_estimate(b, b.last_mass_g)
        err = inv.qty_error(b)
        last_count = db.execute(text("""select actual_count, recorded_at, qty_est_after from inventory_transactions
                                        where bin_id = :b and kind = 'COUNT' and actual_count is not null
                                        order by recorded_at desc limit 1"""), {"b": b.id}).first()
        since = last_count.recorded_at if last_count else None
        q = """select coalesce(sum(delta_qty_est), 0) as net, count(*) as n,
                      count(*) filter (where kind = 'WITHDRAWAL' and user_id is null) as unattributed
               from inventory_transactions where bin_id = :b and kind in ('WITHDRAWAL', 'REFILL')"""
        led = db.execute(text(q + (" and recorded_at > :since" if since else "")),
                         {"b": b.id, **({"since": since} if since else {})}).one()
        expected = (last_count.actual_count + int(led.net)) if last_count else None
        diff = None if (expected is None or measured is None) else measured - expected
        tol = err or 1
        status = ("NOT_CALIBRATED" if measured is None else "NO_BASELINE_COUNT" if expected is None
                  else "OK" if abs(diff) <= tol else "DISCREPANCY")
        out.append({"bin_id": b.id, "bin": b.code, "item": b.item_name, "measured_qty": measured, "measured_error": err,
                    "last_measured_at": _iso(b.last_measured_at), "last_count": last_count.actual_count if last_count else None,
                    "last_count_at": _iso(since), "net_since_count": int(led.net), "transactions_since_count": led.n,
                    "unattributed_withdrawals": led.unattributed, "expected_qty": expected, "difference": diff,
                    "status": status})
    return {"bins": out, "note": "Expected = last staff count + scale-measured changes since. Measured = scale estimate "
                                 "(+/- error). A staff count is the auditable correction (Inventory -> Count)."}


# ---------------------------------------------------------------- lifecycle ---
CHECKOUT_LIMIT_H = 24          # a check-out with no booking end is overdue after this


def lifecycle(db: Session, now: Optional[datetime] = None) -> dict:
    """Every asset: status, custodian (from the check-out record), overdue check-outs, maintenance
    due, open faults, last movement. Only recorded fields; unknowns stay unknown."""
    now = now or datetime.now(timezone.utc)
    rows = db.execute(text("""
        select a.id, a.asset_tag, a.name, a.category, l.code as lab, a.status, a.serial_number,
               u.full_name as holder, a.checked_out_at, a.last_inspected_at, a.next_maintenance_at,
               (select b.end_time from bookings b join asset_transactions t on t.booking_id = b.id
                 where t.asset_id = a.id and t.action = 'CHECKOUT' order by t.created_at desc limit 1) as due_back,
               (select count(*) from issues i where i.asset_id = a.id and i.status not in ('RESOLVED', 'CLOSED')) as open_issues,
               (select max(created_at) from asset_transactions t where t.asset_id = a.id) as last_movement,
               (select count(*) from asset_transactions t where t.asset_id = a.id and t.action = 'CHECKOUT') as checkouts
        from assets a left join labs l on l.id = a.lab_id left join users u on u.id = a.holder_id
        order by l.code, a.asset_tag""")).all()
    out = []
    for r in rows:
        flags = []
        if r.checked_out_at:
            due = r.due_back or (r.checked_out_at + timedelta(hours=CHECKOUT_LIMIT_H))
            if now > due:
                flags.append(f"OVERDUE since {due.isoformat(timespec='minutes')}")
        if r.next_maintenance_at and r.next_maintenance_at < now:
            flags.append("MAINTENANCE_DUE")
        if r.open_issues:
            flags.append(f"{r.open_issues} open fault report(s)")
        out.append({"id": r.id, "asset_tag": r.asset_tag, "name": r.name, "category": r.category, "lab": r.lab,
                    "status": r.status, "serial": r.serial_number, "holder": r.holder, "checked_out_at": _iso(r.checked_out_at),
                    "due_back": _iso(r.due_back), "last_inspected_at": _iso(r.last_inspected_at),
                    "next_maintenance_at": _iso(r.next_maintenance_at), "open_issues": r.open_issues,
                    "last_movement": _iso(r.last_movement), "checkouts": r.checkouts, "flags": flags})
    return {"assets": out, "count": len(out), "flagged": sum(1 for a in out if a["flags"]),
            "note": f"Overdue = past the booking's end, or {CHECKOUT_LIMIT_H} h after check-out without a booking. "
                    "Maintenance dates appear only where staff set them; none set = not tracked yet (not 'fine')."}

```
