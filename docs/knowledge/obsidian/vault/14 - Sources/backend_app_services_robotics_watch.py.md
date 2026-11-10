---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/robotics_watch.py"
source_hash: "cf58ffe3d25625e4786defc7a0daa721f1ef38ec13ac19297415ad5368ef4316"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/robotics_watch.py` - edit the original in the repository, not this note.

Systems: [[Robots (read-only)]]

## Related
- [[backend_app_api_routes_automation.py]] - imports
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_inventory.py]] - imports
- [[backend_app_services_devices.py]] - imports
- [[docs_PLAN_2026-10-08_VISION_ROBOTS_SECURITY_UI.md]] - mentioned by docs

```py
"""
Robotics Lab watch rules for n8n workflows 13-22.

Each topic returns notification items {title, body, severity, link,
dedupe_key, lab_id} computed from stored data only. n8n polls a topic,
notifies staff, and the dedupe key keeps a repeat poll from repeating a
notification. Read-only: nothing here changes data or actuates anything.

  13 hazards          environment hazard still active after 5 min (escalation)
  14 env-offline      environment / bin node stopped reporting
  15 low-stock        consumable at or below its reorder quantity
  16 unattended-stock stock withdrawn while nobody was inside the lab
  17 assets-overdue   reusable item out for more than ASSET_LOAN_HOURS
  18 robots           robot offline or in FAULT
  19 robot-unbooked   robot RUNNING with no booking in force
  20 pcs-offline      lab PC stopped reporting
  21 exam-violations  unreviewed exam-mode reports
  22 daily            one Robotics Lab summary per day
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (Alert, Asset, AssetStatus, Device, DeviceType, EquipmentSession,
                        InventoryBin, InventoryTransaction, Lab, PolicyViolation)
from app.services import inventory as inv
from app.services.devices import is_fresh

ASSET_LOAN_HOURS = 24


def _utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _code(db: Session, lab_id) -> str:
    lab = db.get(Lab, lab_id) if lab_id else None
    return lab.code if lab else "?"


def _item(title, body, severity, link, key, lab_id=None) -> dict:
    return {"title": title[:160], "body": body[:500], "severity": severity,
            "link": link, "dedupe_key": key, "lab_id": lab_id}


def hazards(db: Session, now: datetime) -> list[dict]:
    out = []
    for a in db.scalars(select(Alert).where(Alert.dedupe_key.like("env:%"),
                                            Alert.is_resolved.is_(False))).all():
        minutes = (now - _utc(a.created_at)).total_seconds() / 60
        if minutes >= 5:
            out.append(_item(f"Still active: {a.title}",
                             f"Active for {int(minutes)} min. {a.detail}", "critical",
                             f"/labs/{a.lab_id}", f"{a.dedupe_key}:escalate:{a.id}", a.lab_id))
    return out


def _offline(db: Session, now: datetime, types, label, link) -> list[dict]:
    out = []
    for d in db.scalars(select(Device).where(Device.device_type.in_(types))).all():
        if is_fresh(d, now) is False:
            day = now.strftime("%Y-%m-%d")
            out.append(_item(f"{label} offline: {d.name} ({_code(db, d.lab_id)})",
                             f"Last report {_utc(d.last_seen_at):%H:%M} UTC.", "warning", link,
                             f"robotics:offline:{d.device_uid}:{day}", d.lab_id))
    return out


def env_offline(db: Session, now: datetime) -> list[dict]:
    return _offline(db, now, (DeviceType.SENSOR_NODE,), "Node", "/admin/devices")


def low_stock(db: Session, now: datetime) -> list[dict]:
    out = []
    for b in db.scalars(select(InventoryBin).where(InventoryBin.is_active.is_(True))).all():
        qty = inv.qty_estimate(b, b.last_mass_g)
        if qty is not None and b.reorder_qty is not None and qty <= b.reorder_qty:
            out.append(_item(f"Reorder {b.item_name} ({b.code})",
                             f"About {qty} left; reorder level {b.reorder_qty}.", "warning",
                             "/admin/equipment?tab=consumables",
                             f"robotics:low:{b.id}:{now:%Y-%m-%d}", b.lab_id))
    return out


def unattended_stock(db: Session, now: datetime) -> list[dict]:
    out = []
    for t in db.scalars(select(InventoryTransaction).where(
            InventoryTransaction.kind == "WITHDRAWAL",
            InventoryTransaction.attribution == "NOBODY_INSIDE",
            InventoryTransaction.recorded_at >= now - timedelta(hours=1))).all():
        b = db.get(InventoryBin, t.bin_id)
        out.append(_item(f"Stock change with nobody inside: {b.item_name}",
                         f"{t.delta_mass_g} g at {_utc(t.recorded_at):%H:%M} UTC with no access "
                         "session open. A record to check, not an accusation.", "info",
                         "/admin/equipment?tab=consumables", f"robotics:unattended:{t.id}", b.lab_id))
    return out


def assets_overdue(db: Session, now: datetime) -> list[dict]:
    out = []
    for a in db.scalars(select(Asset).where(Asset.status == AssetStatus.CHECKED_OUT,
                                            Asset.bin_item.is_(True))).all():
        if a.checked_out_at and now - _utc(a.checked_out_at) > timedelta(hours=ASSET_LOAN_HOURS):
            hours = int((now - _utc(a.checked_out_at)).total_seconds() // 3600)
            out.append(_item(f"Not returned: {a.asset_tag}", f"{a.name} out for {hours} h.",
                             "warning", "/admin/equipment?tab=reusables",
                             f"robotics:overdue:{a.id}:{now:%Y-%m-%d}", a.lab_id))
    return out


def robots(db: Session, now: datetime) -> list[dict]:
    out = _offline(db, now, (DeviceType.ROBOT,), "Robot", "/admin/equipment?tab=noncons")
    for s in db.scalars(select(EquipmentSession).where(EquipmentSession.state == "FAULT",
                                                       EquipmentSession.ended_at.is_(None))).all():
        d = db.get(Device, s.device_id)
        out.append(_item(f"Robot fault: {d.name}", f"Reported {_utc(s.started_at):%H:%M} UTC: "
                         f"{s.detail or ''}", "critical", "/admin/equipment?tab=noncons",
                         f"robotics:fault:{s.id}", s.lab_id))
    return out


def robot_unbooked(db: Session, now: datetime) -> list[dict]:
    out = []
    for s in db.scalars(select(EquipmentSession).where(
            EquipmentSession.state == "RUNNING", EquipmentSession.booking_id.is_(None),
            EquipmentSession.started_at >= now - timedelta(hours=2))).all():
        d = db.get(Device, s.device_id)
        if d is not None and d.device_type == DeviceType.ROBOT:
            out.append(_item(f"Robot running without a booking: {d.name}",
                             f"Running since {_utc(s.started_at):%H:%M} UTC with no booking in force.",
                             "warning", "/admin/equipment?tab=noncons",
                             f"robotics:unbooked:{s.id}", s.lab_id))
    return out


def pcs_offline(db: Session, now: datetime) -> list[dict]:
    return _offline(db, now, (DeviceType.PC,), "PC", "/admin/equipment?tab=noncons")


def exam_violations(db: Session, now: datetime) -> list[dict]:
    out = []
    for v in db.scalars(select(PolicyViolation).where(
            PolicyViolation.reviewed.is_(False),
            PolicyViolation.created_at >= now - timedelta(hours=1))).all():
        d = db.get(Device, v.device_id)
        out.append(_item(f"Exam report: {d.device_uid}",
                         f"{v.detail}" + (f" (account {v.os_user})" if v.os_user else "") +
                         ". Staff decide what it means.", "warning", "/admin/equipment?tab=noncons",
                         f"robotics:exam:{v.id}", v.lab_id))
    return out


def daily(db: Session, now: datetime) -> list[dict]:
    since = now - timedelta(days=1)
    run_s = 0.0
    for s in db.scalars(select(EquipmentSession).where(
            EquipmentSession.state == "RUNNING", EquipmentSession.started_at >= since)).all():
        run_s += ((_utc(s.ended_at) if s.ended_at else now) - _utc(s.started_at)).total_seconds()
    withdrawals = db.scalar(select(func.count()).select_from(InventoryTransaction).where(
        InventoryTransaction.kind == "WITHDRAWAL", InventoryTransaction.recorded_at >= since)) or 0
    out_now = db.scalar(select(func.count()).select_from(Asset).where(
        Asset.status == AssetStatus.CHECKED_OUT, Asset.bin_item.is_(True))) or 0
    hazards_24h = db.scalar(select(func.count()).select_from(Alert).where(
        Alert.dedupe_key.like("env:%"), Alert.created_at >= since)) or 0
    body = (f"Last 24 h: robots ran {run_s / 3600:.1f} h; {withdrawals} consumable "
            f"withdrawal(s); {out_now} reusable item(s) out now; {hazards_24h} environment "
            "hazard alert(s). From recorded data only.")
    return [_item(f"Robotics Lab daily summary {now:%Y-%m-%d}", body, "info",
                  "/admin/equipment", f"robotics:daily:{now:%Y-%m-%d}")]


TOPICS: dict[str, Callable[[Session, datetime], list[dict]]] = {
    "hazards": hazards, "env-offline": env_offline, "low-stock": low_stock,
    "unattended-stock": unattended_stock, "assets-overdue": assets_overdue,
    "robots": robots, "robot-unbooked": robot_unbooked, "pcs-offline": pcs_offline,
    "exam-violations": exam_violations, "daily": daily,
}

```
