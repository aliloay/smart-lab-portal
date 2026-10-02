"""
Consumable inventory (Robotics Lab, System 2): weighing bins.

The bin node sends the STABLE mass of each bin. Here that becomes:
  * the current stock: mass, and - only once the bin is calibrated - the
    estimated quantity n = round((m - tare) / unit_mass) with an error band
    of +/- noise / unit_mass when the noise has been measured;
  * transactions: a stable change larger than the bin's threshold is a
    WITHDRAWAL or a REFILL. If exactly one person is inside the lab it is
    linked to them and their booking - a correlation, never an accusation;
  * a low-stock alert below the bin's reorder quantity, cleared on refill.

Nothing is estimated from defaults: an uncalibrated bin reports mass only.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (AccessSession, Alert, AlertSeverity, Device, InventoryBin,
                        InventoryMeasurement, InventoryTransaction, Lab)
from app.services.devices import is_fresh

# The node reports at least once a minute; five minutes without = stale.
STALE_AFTER = timedelta(minutes=5)
DEFAULT_MIN_CHANGE_G = 1.0


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


def threshold_g(b: InventoryBin) -> float:
    if b.min_change_g:
        return b.min_change_g
    return 3 * b.noise_g if b.noise_g else DEFAULT_MIN_CHANGE_G


def calibrated(b: InventoryBin) -> bool:
    return b.tare_g is not None and bool(b.unit_mass_g)


def qty_estimate(b: InventoryBin, mass: Optional[float]) -> Optional[int]:
    if mass is None or not calibrated(b):
        return None
    return max(0, round((mass - b.tare_g) / b.unit_mass_g))


def qty_error(b: InventoryBin) -> Optional[int]:
    """+/- pieces from the measured noise; None until noise is measured."""
    if not b.noise_g or not b.unit_mass_g:
        return None
    return max(1, math.ceil(b.noise_g / b.unit_mass_g))


def attribution(db: Session, lab_id: int):
    """(user_id, booking_id, label) for a stock change happening now."""
    inside = db.scalars(select(AccessSession).where(
        AccessSession.lab_id == lab_id, AccessSession.ended_at.is_(None))).all()
    if len(inside) == 1:
        return inside[0].user_id, inside[0].booking_id, "SINGLE_OCCUPANT"
    return None, None, "MULTIPLE_OCCUPANTS" if inside else "NOBODY_INSIDE"


def _low_key(b: InventoryBin) -> str:
    return f"inv:{b.id}:low"


def _check_reorder(db: Session, b: InventoryBin, qty: Optional[int]) -> None:
    open_alert = db.scalar(select(Alert).where(
        Alert.dedupe_key == _low_key(b), Alert.is_resolved.is_(False)))
    low = qty is not None and b.reorder_qty is not None and qty <= b.reorder_qty
    if low and open_alert is None:
        db.add(Alert(lab_id=b.lab_id, device_id=b.device_id, severity=AlertSeverity.WARNING,
                     title=f"Low stock: {b.item_name} ({b.code})",
                     detail=f"About {qty} left (reorder at {b.reorder_qty}).",
                     dedupe_key=_low_key(b)))
    elif not low and open_alert is not None:
        open_alert.is_resolved = True
        open_alert.resolved_at = datetime.now(timezone.utc)


def record(db: Session, b: InventoryBin, mass: float,
           now: Optional[datetime] = None) -> Optional[InventoryTransaction]:
    """Store one stable reading; returns the transaction it caused, if any."""
    now = now or datetime.now(timezone.utc)
    db.add(InventoryMeasurement(bin_id=b.id, mass_g=mass, recorded_at=now))
    tx = None
    if b.last_mass_g is not None and abs(mass - b.last_mass_g) >= threshold_g(b):
        delta = mass - b.last_mass_g
        user_id, booking_id, label = attribution(db, b.lab_id)
        tx = InventoryTransaction(
            bin_id=b.id, kind="WITHDRAWAL" if delta < 0 else "REFILL",
            delta_mass_g=round(delta, 2),
            delta_qty_est=round(delta / b.unit_mass_g) if b.unit_mass_g else None,
            qty_est_after=qty_estimate(b, mass), user_id=user_id,
            booking_id=booking_id, attribution=label, recorded_at=now)
        db.add(tx)
    b.last_mass_g, b.last_measured_at = mass, now
    _check_reorder(db, b, qty_estimate(b, mass))
    return tx


def bin_out(db: Session, b: InventoryBin, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    lab = db.get(Lab, b.lab_id)
    dev = db.get(Device, b.device_id) if b.device_id else None
    if b.last_measured_at is None:
        quality = "MISSING"
    elif dev is not None and is_fresh(dev, now) is False:
        quality = "DEVICE_OFFLINE"
    elif now - _utc(b.last_measured_at) > STALE_AFTER:
        quality = "STALE"
    else:
        quality = "VALID"
    qty = qty_estimate(b, b.last_mass_g)
    return {"id": b.id, "code": b.code, "item_name": b.item_name, "category": b.category,
            "lab_id": b.lab_id, "lab_code": lab.code if lab else None,
            "device_uid": dev.device_uid if dev else None,
            "mass_g": b.last_mass_g, "measured_at": b.last_measured_at, "quality": quality,
            "calibrated": calibrated(b), "tare_g": b.tare_g, "unit_mass_g": b.unit_mass_g,
            "noise_g": b.noise_g, "calibrated_at": b.calibrated_at,
            "min_change_g": threshold_g(b), "qty_est": qty, "qty_err": qty_error(b),
            "reorder_qty": b.reorder_qty,
            "low": qty is not None and b.reorder_qty is not None and qty <= b.reorder_qty,
            "notes": b.notes, "is_active": b.is_active}
