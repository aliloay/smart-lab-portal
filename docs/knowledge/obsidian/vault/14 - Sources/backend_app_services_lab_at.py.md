---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/lab_at.py"
source_hash: "cecd4c0a592d5ff660ff40ba15c200a9b64de1b709c918bb32fc310d942964b7"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/lab_at.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_labs.py]] - imports
- [[backend_app_models___init__.py]] - imports

```py
"""
Whole-lab time slider (2026-10-27, backlog 15.3): "what did the lab look like at time T?" rebuilt ONLY from what was
recorded - nothing interpolated, every value with its own timestamp and its age at T.

  people inside      door sessions open at T (started <= T, not ended by T) - the door record, not the camera
  environment        each metric's last reading at or before T (within 24 h), with its age at T
  alerts             alerts open at T (created <= T, not resolved by T)
  robots             each robot's last recorded EVENT at or before T (home left/returned, faults, ...) - continuous
                     joint telemetry is not stored, so no pose is shown for the past
  PCs                equipment sessions running at T
  consumables        each bin's last weighing at or before T
  reusables          each tagged item's last checkout/return at or before T
  camera             the camera's security events in the 5 minutes before T (people seen / inside per event)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (AccessSession, Alert, Asset, AssetTransaction, Device, DeviceType, EquipmentSession, InventoryBin,
                        InventoryMeasurement, Lab, RobotEvent, SecurityEvent, SensorReading, User)


def _utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _age(dt, t) -> Optional[int]:
    dt = _utc(dt)
    return None if dt is None else int((t - dt).total_seconds())


def lab_at(db: Session, lab: Lab, t: datetime, staff: bool = True) -> dict:
    t = _utc(t)
    sessions = db.scalars(select(AccessSession).where(
        AccessSession.lab_id == lab.id, AccessSession.started_at <= t,
        (AccessSession.ended_at.is_(None)) | (AccessSession.ended_at > t)).order_by(AccessSession.started_at)).all()
    people = []
    for s in sessions:
        u = db.get(User, s.user_id)
        people.append({"name": (u.full_name if u else "?") if staff else "someone", "since": _utc(s.started_at).isoformat(),
                       "for_s": _age(s.started_at, t), "entry": s.entry_method.value if s.entry_method else None})

    sub = (select(SensorReading.metric, func.max(SensorReading.recorded_at).label("at"))
           .where(SensorReading.lab_id == lab.id, SensorReading.recorded_at <= t,
                  SensorReading.recorded_at >= t - timedelta(hours=24))
           .group_by(SensorReading.metric).subquery())
    env = []
    for r in db.execute(select(SensorReading).join(sub, (SensorReading.metric == sub.c.metric)
                                                   & (SensorReading.recorded_at == sub.c.at))
                        .where(SensorReading.lab_id == lab.id)).scalars().all():
        if any(e["metric"] == r.metric for e in env):
            continue
        env.append({"metric": r.metric, "value": r.value, "unit": r.unit, "at": _utc(r.recorded_at).isoformat(),
                    "age_s": _age(r.recorded_at, t)})
    env.sort(key=lambda e: e["metric"])

    alerts = [{"title": a.title, "severity": a.severity.value, "since": _utc(a.created_at).isoformat()}
              for a in db.scalars(select(Alert).where(
                  Alert.lab_id == lab.id, Alert.created_at <= t,
                  (Alert.resolved_at.is_(None)) | (Alert.resolved_at > t)).order_by(Alert.created_at.desc()).limit(50)).all()]

    robots = []
    for d in db.scalars(select(Device).where(Device.lab_id == lab.id, Device.device_type == DeviceType.ROBOT)).all():
        ev = db.scalar(select(RobotEvent).where(RobotEvent.device_id == d.id, RobotEvent.occurred_at <= t)
                       .order_by(RobotEvent.occurred_at.desc()).limit(1))
        robots.append({"name": d.name, "last_event": ev.kind if ev else None,
                       "at": _utc(ev.occurred_at).isoformat() if ev else None, "age_s": _age(ev.occurred_at, t) if ev else None,
                       "note": "last recorded event - joint positions are not stored for the past"})

    pcs = []
    for e in db.scalars(select(EquipmentSession).where(
            EquipmentSession.lab_id == lab.id, EquipmentSession.started_at <= t,
            (EquipmentSession.ended_at.is_(None)) | (EquipmentSession.ended_at > t))).all():
        dev = db.get(Device, e.device_id)
        u = db.get(User, e.user_id) if e.user_id else None
        pcs.append({"pc": dev.name if dev else e.device_id, "state": e.state, "since": _utc(e.started_at).isoformat(),
                    "user": (u.full_name if u else None) if staff else None})

    bins = []
    for b in db.scalars(select(InventoryBin).where(InventoryBin.lab_id == lab.id)).all():
        m = db.scalar(select(InventoryMeasurement).where(InventoryMeasurement.bin_id == b.id, InventoryMeasurement.recorded_at <= t)
                      .order_by(InventoryMeasurement.recorded_at.desc()).limit(1))
        qty = None
        if m and b.unit_mass_g and b.tare_g is not None:
            qty = max(0, round((m.mass_g - b.tare_g) / b.unit_mass_g))
        bins.append({"code": b.code, "item": b.item_name, "mass_g": m.mass_g if m else None,
                     "qty_est": qty, "count_is": "estimate from weight (calibrated)" if qty is not None else "no count",
                     "at": _utc(m.recorded_at).isoformat() if m else None, "age_s": _age(m.recorded_at, t) if m else None})

    reusables = []
    for a in db.scalars(select(Asset).where(Asset.lab_id == lab.id, (Asset.bin_item.is_(True)) | (Asset.nfc_uid.is_not(None)))).all():
        tx = db.scalar(select(AssetTransaction).where(AssetTransaction.asset_id == a.id, AssetTransaction.created_at <= t)
                       .order_by(AssetTransaction.created_at.desc()).limit(1))
        reusables.append({"item": a.name, "last_action": tx.action if tx else None,
                          "at": _utc(tx.created_at).isoformat() if tx else None})

    cam = [{"kind": e.kind, "people_seen": e.people_seen, "people_inside": e.people_inside, "at": _utc(e.created_at).isoformat()}
           for e in db.scalars(select(SecurityEvent).where(SecurityEvent.lab_id == lab.id, SecurityEvent.created_at <= t,
                                                           SecurityEvent.created_at > t - timedelta(minutes=5))
                               .order_by(SecurityEvent.created_at.desc()).limit(20)).all()]

    return {"lab": lab.code, "at": t.isoformat(), "people_inside": people, "environment": env, "alerts_open": alerts,
            "robots": robots, "pcs_in_use": pcs, "bins": bins, "reusables": reusables, "camera_events_5min": cam,
            "note": "Rebuilt from recorded history only; each value carries its own time. Nothing is interpolated."}

```
