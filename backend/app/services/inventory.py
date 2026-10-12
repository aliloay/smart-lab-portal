"""
Consumable inventory (Robotics Lab, System 3): weighing bins.

The bin node sends the STABLE mass of each bin. Here that becomes:
  * the current stock: mass, and - only once the bin is calibrated - the
    estimated quantity n = round((m - tare) / unit_mass) with an error band
    of +/- noise / unit_mass when the noise has been measured;
  * transactions: a confirmed (two readings agree) net change larger than
    the bin's threshold is a WITHDRAWAL or a REFILL; while the container is
    lifted off the scale nothing is booked. If exactly one person is inside the lab it is
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


def _notify_change(db: Session, b: InventoryBin, tx: InventoryTransaction,
                   user_id: Optional[int], label: str) -> None:
    """Staff are told every stock change - what, how much, by whom; the person
    inside (when it is one person) is told what they took or put back."""
    from app.models import User
    from app.services.notifications import notify, staff_ids
    took = tx.kind == "WITHDRAWAL"
    grams = abs(tx.delta_mass_g)
    n = abs(tx.delta_qty_est) if tx.delta_qty_est else None
    after = tx.qty_est_after
    pcs = f"{n} pcs" if n else f"{grams:.2f} g"
    left = (f" · {after} left (was {after + n if took else after - n})"
            if n is not None and after is not None else "")
    who = db.get(User, user_id) if user_id else None
    by = (who.full_name if who else
          "nobody signed in at the door" if label == "NOBODY_INSIDE" else "one of several people inside")
    title = f"{b.item_name}: {pcs} {'taken' if took else 'added'}{left}"
    body = (f"{b.item_name} ({b.code}): {'-' if took else '+'}{grams:.2f} g"
            + (f" = {pcs}" if n else "") + f" - {by}.")
    notify(db, staff_ids(db), "CONSUMABLE_" + tx.kind, title, body=body,
           link="/inventory", severity="info" if who else "warning", exclude=user_id)
    if who:
        notify(db, [who.id], "CONSUMABLE_" + tx.kind,
               f"You {'took' if took else 'put back'} {pcs} of {b.item_name}{left}",
               body=f"The consumables bin recorded {'-' if took else '+'}{grams:.2f} g.", link="/inventory")


def lifted(b: InventoryBin, mass: float) -> bool:
    """The container is off the scale (lighter than the empty container): someone
    is taking from it in their hand. Nothing is booked until it is back."""
    return calibrated(b) and b.tare_g > 0 and mass < b.tare_g - threshold_g(b)


# A reading counts as N pieces only when it sits this close to N (in pieces):
# a value half-way between two counts (load-cell drift, a container still
# settling) is never booked. Measured 2026-10-13 (10k resistors, 1 kg cell):
# zero drift up to ~0.4 pc, removed by ZERO_FROM_LIFT; the rest stays < 0.3 pc.
CLEAN_PC = 0.3
# While the container is lifted the platform is empty: that reading is a fresh
# zero. Used for the next readings when it is this close to 0 (else ignored).
ZERO_MAX_G = 0.5


def _zero_g(db: Session, b: InventoryBin) -> float:
    """The platform's zero seen at the last lift (load-cell drift), else 0."""
    z = db.scalar(select(InventoryMeasurement.mass_g)
                  .where(InventoryMeasurement.bin_id == b.id,
                         InventoryMeasurement.mass_g < b.tare_g - threshold_g(b))
                  .order_by(InventoryMeasurement.recorded_at.desc(),
                            InventoryMeasurement.id.desc()).limit(1))
    return z if z is not None and abs(z) <= ZERO_MAX_G else 0.0


def _pieces(b: InventoryBin, mass: float) -> float:
    return (mass - b.tare_g) / b.unit_mass_g


def _clean_count(b: InventoryBin, mass: float) -> Optional[int]:
    x = _pieces(b, mass)
    n = round(x)
    return max(0, n) if abs(x - n) <= CLEAN_PC else None


def record(db: Session, b: InventoryBin, mass: float,
           now: Optional[datetime] = None) -> Optional[InventoryTransaction]:
    """Store one stable reading; returns the transaction it caused, if any.

    b.last_mass_g is the last CONFIRMED stock. Calibrated bins are booked in
    whole pieces: a new count is booked when two readings in a row both sit
    cleanly on it (see CLEAN_PC), as the NET change from the confirmed count -
    lifting the container out and putting it back with 5 fewer is one
    withdrawal of 5. Nothing is booked while the container is lifted.
    Uncalibrated bins are booked in grams the same way.
    """
    now = now or datetime.now(timezone.utc)
    prev = db.scalar(select(InventoryMeasurement.mass_g)
                     .where(InventoryMeasurement.bin_id == b.id)
                     .order_by(InventoryMeasurement.recorded_at.desc(),
                               InventoryMeasurement.id.desc()).limit(1))
    if lifted(b, mass):
        db.add(InventoryMeasurement(bin_id=b.id, mass_g=mass, recorded_at=now))
        return None                      # keep the confirmed stock until it is back
    if calibrated(b) and b.tare_g > 0:
        # Raw readings are stored; the stock uses the reading minus the zero
        # seen at the last lift (so slow load-cell drift does not shift counts).
        z = _zero_g(db, b)
        if prev is not None and not lifted(b, prev):
            prev = prev - z
        db.add(InventoryMeasurement(bin_id=b.id, mass_g=mass, recorded_at=now))
        mass = round(mass - z, 3)
    else:
        db.add(InventoryMeasurement(bin_id=b.id, mass_g=mass, recorded_at=now))
    thr = threshold_g(b)
    if b.last_mass_g is None:
        b.last_mass_g, b.last_measured_at = mass, now
        _check_reorder(db, b, qty_estimate(b, mass))
        return None
    if calibrated(b):
        before = qty_estimate(b, b.last_mass_g)
        n = _clean_count(b, mass)
        if n is None:
            return None                  # between two counts: wait
        if n == before:
            b.last_mass_g, b.last_measured_at = mass, now   # same count: follow drift
            return None
        if prev is None or _clean_count(b, prev) != n:
            return None                  # not confirmed yet: wait for the next reading
        dq = n - before
    else:
        if abs(mass - b.last_mass_g) < thr:
            b.last_mass_g, b.last_measured_at = mass, now
            return None
        if prev is None or abs(mass - prev) >= thr:
            return None
        dq = None
    delta = mass - b.last_mass_g
    user_id, booking_id, label = attribution(db, b.lab_id)
    tx = InventoryTransaction(
        bin_id=b.id, kind="WITHDRAWAL" if delta < 0 else "REFILL",
        delta_mass_g=round(delta, 2), delta_qty_est=dq,
        qty_est_after=qty_estimate(b, mass), user_id=user_id,
        booking_id=booking_id, attribution=label, recorded_at=now)
    db.add(tx)
    _notify_change(db, b, tx, user_id, label)
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
