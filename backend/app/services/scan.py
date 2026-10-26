"""
"Scan the lab" (phone camera, 2026-10-26): exact asset identification + live state.

Three separate layers - never mixed:
  1. visual DETECTION (people boxes) - the camera service's detector, a generic class only;
  2. exact IDENTIFICATION - a printed QR marker whose text is the asset's own key:
        SLAB:D:<device_uid>   a networked device (robot, PC, ESP node, door controller, camera)
        SLAB:B:<bin code>     a consumables bin (load cell)
        SLAB:A:<asset tag>    an equipment item (e.g. a reusable-bin item)
     A look-alike object without a marker stays "unidentified" - appearance never names an asset;
  3. live INFORMATION - read from the authoritative record of THAT key (device heartbeat, sensor readings,
     bin measurements, robot telemetry, PC agent), with its timestamp and a data-quality state. Nothing here is
     estimated from the image.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alert, Asset, Device, DeviceType, InventoryBin, Issue, Lab, SensorReading
from app.services.devices import device_out, is_fresh
from app.services.inventory import bin_out
from app.services.issues import ACTIVE as ISSUE_ACTIVE

PREFIX = "SLAB"
KINDS = {"D": "device", "B": "bin", "A": "asset"}
READING_STALE = timedelta(minutes=5)
TYPE_LABEL = {DeviceType.ROBOT: "Robot", DeviceType.PC: "Lab PC", DeviceType.SENSOR_NODE: "Sensor node",
              DeviceType.MASTER_CONTROLLER: "Door controller (master ESP32)", DeviceType.SECURITY_CAMERA:
              "Security camera", DeviceType.CAMERA: "Entry camera", DeviceType.FACE_SERVER: "Face server",
              DeviceType.OTHER: "Device"}


def marker(kind: str, key: str) -> str:
    """The exact text printed in the QR marker."""
    return f"{PREFIX}:{kind}:{key}"


def parse(code: str) -> Optional[tuple[str, str]]:
    parts = (code or "").strip().split(":", 2)
    if len(parts) != 3 or parts[0] != PREFIX or parts[1] not in KINDS or not parts[2] or len(parts[2]) > 64:
        return None
    return parts[1], parts[2]


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def registry(db: Session) -> list[dict]:
    """Every asset that can carry a marker, from the existing records (no separate asset list to keep in sync)."""
    labs = {lab.id: lab.code for lab in db.scalars(select(Lab)).all()}
    out = []
    for d in db.scalars(select(Device).order_by(Device.lab_id, Device.device_type, Device.name)).all():
        if d.device_uid.upper().endswith("_SIM") or (d.component_state or {}).get("source") == "SIMULATION":
            continue                                        # simulators never get a physical marker
        out.append({"code": marker("D", d.device_uid), "kind": "device", "key": d.device_uid, "name": d.name,
                    "type": TYPE_LABEL.get(d.device_type, d.device_type.value), "lab_code": labs.get(d.lab_id)})
    for b in db.scalars(select(InventoryBin).where(InventoryBin.is_active.is_(True)).order_by(InventoryBin.code)).all():
        out.append({"code": marker("B", b.code), "kind": "bin", "key": b.code, "name": f"{b.item_name} bin",
                    "type": "Consumables bin", "lab_code": labs.get(b.lab_id)})
    networked = set(db.scalars(select(Device.asset_id).where(Device.asset_id.is_not(None))).all())
    for a in db.scalars(select(Asset).order_by(Asset.asset_tag)).all():
        if a.id in networked:
            continue                                         # its device marker carries the live state
        out.append({"code": marker("A", a.asset_tag), "kind": "asset", "key": a.asset_tag, "name": a.name,
                    "type": "Reusable-bin item" if a.bin_item else (a.category or "Equipment"),
                    "lab_code": labs.get(a.lab_id)})
    return out


def _readings(db: Session, device_id: int, now: datetime) -> list[dict]:
    """The newest value of every metric this node reported in the last 24 h, each with its own age."""
    since = now - timedelta(hours=24)
    sub = (select(SensorReading.metric, func.max(SensorReading.recorded_at).label("t"))
           .where(SensorReading.device_id == device_id, SensorReading.recorded_at >= since)
           .group_by(SensorReading.metric).subquery())
    rows = db.execute(select(SensorReading).join(sub, (SensorReading.metric == sub.c.metric)
                                                 & (SensorReading.recorded_at == sub.c.t))
                      .where(SensorReading.device_id == device_id)).scalars().all()
    out, seen = [], set()
    for r in sorted(rows, key=lambda r: r.metric):
        if r.metric in seen:
            continue
        seen.add(r.metric)
        age = (now - _utc(r.recorded_at)).total_seconds()
        out.append({"metric": r.metric, "value": r.value, "unit": r.unit, "at": _utc(r.recorded_at).isoformat(),
                    "age_s": round(age), "quality": "LIVE" if age <= READING_STALE.total_seconds() else "STALE"})
    return out


def _facts_for_device(db: Session, d: Device, now: datetime, staff: bool) -> list[dict]:
    cs = d.component_state or {}
    facts: list[dict] = []

    def f(label, value, quality="RECORD"):
        facts.append({"label": label, "value": value, "quality": quality})
    fresh = is_fresh(d, now)
    if d.device_type == DeviceType.ROBOT:
        f("Robot state", cs.get("state") or "not reported", "LIVE" if fresh else "STALE")
        if cs.get("home"):
            f("Home", cs["home"], "LIVE" if fresh else "STALE")
        if cs.get("source"):
            f("Driven from", cs["source"], "LIVE" if fresh else "STALE")
        if cs.get("q"):
            f("Joints (deg)", ", ".join(f"{v * 57.29578:.1f}" for v in cs["q"][:6]), "LIVE" if fresh else "STALE")
    elif d.device_type == DeviceType.PC:
        # what the PC agent reports (equipment.StateReport): state RUNNING / IDLE / FAULT + the Windows account
        f("Agent state", cs.get("state") or "not reported", "LIVE" if fresh else "STALE")
        if staff and cs.get("os_user"):
            f("Windows account", cs["os_user"], "LIVE" if fresh else "STALE")
        f("Mode", d.mode or "NORMAL")
    elif d.device_type == DeviceType.MASTER_CONTROLLER:
        f("Door", "not reported" if d.door_closed is None else ("closed" if d.door_closed else "OPEN"),
          "LIVE" if fresh else "STALE")
    elif d.device_type == DeviceType.SECURITY_CAMERA:
        if cs.get("people") is not None:
            f("People in view", cs["people"], "LIVE" if fresh else "STALE")
    if d.firmware_version:
        f("Firmware", d.firmware_version)
    return facts


def _open_counts(db: Session, device_id: Optional[int], lab_id: int) -> dict:
    alerts = db.scalar(select(func.count()).select_from(Alert).where(
        Alert.device_id == device_id, Alert.is_resolved.is_(False))) if device_id else 0
    issues = db.scalar(select(func.count()).select_from(Issue).where(
        Issue.lab_id == lab_id, Issue.status.in_(ISSUE_ACTIVE)))
    return {"open_alerts": int(alerts or 0), "open_issues_in_lab": int(issues or 0)}


def asset_card(db: Session, code: str, staff: bool, now: Optional[datetime] = None) -> Optional[dict]:
    """The live card for one scanned marker; None = not a known asset (shown as 'unidentified')."""
    p = parse(code)
    if p is None:
        return None
    kind, key = p
    now = now or datetime.now(timezone.utc)
    if kind == "D":
        d = db.scalar(select(Device).where(Device.device_uid == key))
        if d is None:
            return None
        lab = db.get(Lab, d.lab_id)
        o = device_out(d, lab.code if lab else None, now)
        card = {"code": code, "kind": "device", "key": key, "name": d.name,
                "type": TYPE_LABEL.get(d.device_type, d.device_type.value), "lab_code": lab.code if lab else None,
                "status": o.state, "last_seen_at": _utc(d.last_seen_at).isoformat() if d.last_seen_at else None,
                "seconds_since_seen": o.seconds_since_seen, "facts": _facts_for_device(db, d, now, staff),
                "readings": _readings(db, d.id, now) if d.device_type == DeviceType.SENSOR_NODE else [],
                **_open_counts(db, d.id, d.lab_id),
                "link": {DeviceType.ROBOT: "/admin/equipment?tab=noncons", DeviceType.PC: "/admin/equipment?tab=noncons",
                         DeviceType.SECURITY_CAMERA: "/admin/security"}.get(d.device_type, "/admin/devices"),
                "ask": f"What is the current state of {d.name} ({d.device_uid}), and has anything gone wrong with it recently?"}
        return card
    if kind == "B":
        b = db.scalar(select(InventoryBin).where(InventoryBin.code == key))
        if b is None:
            return None
        o = bin_out(db, b, now)
        q = o["quality"]
        facts = [{"label": "Estimated stock", "value": "not calibrated - no count" if o["qty_est"] is None else
                  f"{o['qty_est']}" + (f" +/- {o['qty_err']}" if o["qty_err"] else "") + " pieces (estimate from weight)",
                  "quality": "LIVE" if q == "VALID" else q},
                 {"label": "Mass on the scale", "value": "no reading" if o["mass_g"] is None else f"{o['mass_g']:.1f} g",
                  "quality": "LIVE" if q == "VALID" else q}]
        if o["reorder_qty"] is not None:
            facts.append({"label": "Reorder at", "value": f"{o['reorder_qty']} pieces" + (" - LOW" if o["low"] else ""),
                          "quality": "RECORD"})
        last = o["last_reading_at"]
        return {"code": code, "kind": "bin", "key": key, "name": f"{b.item_name} bin", "type": "Consumables bin",
                "lab_code": o["lab_code"], "status": q,
                "last_seen_at": _utc(last).isoformat() if last else None,
                "seconds_since_seen": int((now - _utc(last)).total_seconds()) if last else None,
                "facts": facts, "readings": [], **_open_counts(db, b.device_id, b.lab_id),
                "link": "/admin/equipment?tab=cons",
                "ask": f"How many {b.item_name} remain in bin {b.code}, is the reading trustworthy, and should we reorder?"}
    a = db.scalar(select(Asset).where(Asset.asset_tag == key))
    if a is None:
        return None
    dev = db.scalar(select(Device).where(Device.asset_id == a.id))
    if dev is not None:                                      # a networked item: its device holds the live state
        card = asset_card(db, marker("D", dev.device_uid), staff, now)
        return card and {**card, "code": code}
    lab = db.get(Lab, a.lab_id)
    facts = [{"label": "Status", "value": a.status.value.replace("_", " ").lower(), "quality": "RECORD"}]
    if a.checked_out_at:
        facts.append({"label": "Checked out", "value": _utc(a.checked_out_at).isoformat(), "quality": "RECORD"})
    if a.next_maintenance_at:
        facts.append({"label": "Next maintenance", "value": _utc(a.next_maintenance_at).date().isoformat(),
                      "quality": "RECORD"})
    if a.last_inspected_at:
        facts.append({"label": "Last inspected", "value": _utc(a.last_inspected_at).date().isoformat(),
                      "quality": "RECORD"})
    return {"code": code, "kind": "asset", "key": key, "name": a.name,
            "type": "Reusable-bin item" if a.bin_item else (a.category or "Equipment"),
            "lab_code": lab.code if lab else None, "status": a.status.value, "last_seen_at": None,
            "seconds_since_seen": None, "facts": facts, "readings": [], **_open_counts(db, None, a.lab_id),
            "link": "/admin/equipment?tab=noncons" if not a.bin_item else "/admin/equipment",
            "ask": f"Tell me about {a.name} ({a.asset_tag}): status, history and maintenance."}
