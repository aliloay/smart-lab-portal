"""
Inventory API (Robotics Lab).

Consumables (System 3): bin nodes post stable masses; staff manage bins,
enter the MEASURED calibration and record physical counts (the data for
measuring estimation error). See app/services/inventory.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, require_device, require_staff
from app.db.session import get_db
from app.models import (AuditLog, InventoryBin, InventoryMeasurement,
                        InventoryTransaction, Lab, User)
from app.services import inventory as inv
from app.services.access import get_device

router = APIRouter(prefix="/inventory", tags=["inventory"])


# ----------------------------------------------------------- bin node ---
class BinReading(BaseModel):
    bin_code: str = Field(max_length=32)
    mass_g: float = Field(allow_inf_nan=False, ge=-5000, le=50000)


class MeasurementReport(BaseModel):
    device_uid: str = Field(max_length=64)
    readings: list[BinReading] = Field(min_length=1, max_length=8)


@router.post("/measurements", tags=["devices"])
def post_measurements(req: MeasurementReport, db: Session = Depends(get_db),
                      identity: str = Depends(require_device)):
    """Stable masses from a bin node. Replies with what the LCD shows."""
    device_scope(identity, req.device_uid)
    device = get_device(db, req.device_uid)
    now = datetime.now(timezone.utc)
    out = []
    for r in req.readings:
        b = db.scalar(select(InventoryBin).where(InventoryBin.code == r.bin_code))
        if b is None or not b.is_active:
            out.append({"bin_code": r.bin_code, "known": False})
            continue
        if device is not None:
            if b.device_id is None:
                b.device_id = device.id          # first report binds the bin to its node
            elif b.device_id != device.id:
                raise HTTPException(status.HTTP_403_FORBIDDEN,
                                    f"{r.bin_code} is weighed by another device")
            device.last_seen_at = now
        tx = inv.record(db, b, round(r.mass_g, 2), now)
        out.append({"bin_code": b.code, "known": True, "item_name": b.item_name,
                    "qty_est": inv.qty_estimate(b, b.last_mass_g), "qty_err": inv.qty_error(b),
                    "calibrated": inv.calibrated(b),
                    "transaction": tx.kind if tx is not None else None})
    db.commit()
    # Open Consumables pages refetch at once instead of waiting for their poll.
    from app.services.environment import publish
    publish([{"type": "inventory_update", "bins": [o["bin_code"] for o in out if o.get("known")]}])
    return {"bins": out}


# --------------------------------------------------------------- staff ---
class BinCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{1,31}$")
    lab_id: int
    item_name: str = Field(min_length=1, max_length=64)
    category: str = Field(default="component", max_length=32)
    reorder_qty: Optional[int] = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=2000)


class BinUpdate(BaseModel):
    item_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    category: Optional[str] = Field(default=None, max_length=32)
    # Calibration - enter only measured values.
    tare_g: Optional[float] = Field(default=None, allow_inf_nan=False)
    unit_mass_g: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    noise_g: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    min_change_g: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    reorder_qty: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None


@router.get("/bins")
def list_bins(lab_id: Optional[int] = None, db: Session = Depends(get_db),
              _: User = Depends(require_staff)):
    q = select(InventoryBin).order_by(InventoryBin.code)
    if lab_id is not None:
        q = q.where(InventoryBin.lab_id == lab_id)
    now = datetime.now(timezone.utc)
    return [inv.bin_out(db, b, now) for b in db.scalars(q).all()]


@router.post("/bins", status_code=status.HTTP_201_CREATED)
def create_bin(req: BinCreate, db: Session = Depends(get_db),
               staff: User = Depends(require_staff)):
    if db.get(Lab, req.lab_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lab not found")
    if db.scalar(select(InventoryBin).where(InventoryBin.code == req.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A bin with this code exists")
    b = InventoryBin(**req.model_dump())
    db.add(b)
    db.flush()
    db.add(AuditLog(actor_user_id=staff.id, action="INVENTORY_BIN_CREATED",
                    entity_type="inventory_bin", entity_id=str(b.id),
                    detail={"code": b.code, "item": b.item_name}))
    db.commit()
    return inv.bin_out(db, b)


@router.patch("/bins/{bin_id}")
def update_bin(bin_id: int, req: BinUpdate, db: Session = Depends(get_db),
               staff: User = Depends(require_staff)):
    b = db.get(InventoryBin, bin_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bin not found")
    changes = req.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(b, k, v)
    if {"tare_g", "unit_mass_g", "noise_g"} & changes.keys():
        b.calibrated_at = datetime.now(timezone.utc)
    if {"tare_g", "unit_mass_g"} & changes.keys():
        b.last_mass_g = None          # recalibrated: the next reading is the new starting point
    db.add(AuditLog(actor_user_id=staff.id, action="INVENTORY_BIN_UPDATED",
                    entity_type="inventory_bin", entity_id=str(b.id), detail=changes))
    db.commit()
    return inv.bin_out(db, b)


@router.get("/bins/{bin_id}/history")
def bin_history(bin_id: int, hours: int = Query(168, ge=1, le=24 * 365),
                db: Session = Depends(get_db), _: User = Depends(require_staff)):
    b = db.get(InventoryBin, bin_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bin not found")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    ms = db.scalars(select(InventoryMeasurement).where(
        InventoryMeasurement.bin_id == b.id, InventoryMeasurement.recorded_at >= since)
        .order_by(InventoryMeasurement.recorded_at)).all()
    txs = db.scalars(select(InventoryTransaction).where(
        InventoryTransaction.bin_id == b.id, InventoryTransaction.recorded_at >= since)
        .order_by(desc(InventoryTransaction.recorded_at))).all()

    def tx_out(t: InventoryTransaction) -> dict:
        u = db.get(User, t.user_id) if t.user_id else None
        return {"id": t.id, "kind": t.kind, "delta_mass_g": t.delta_mass_g,
                "delta_qty_est": t.delta_qty_est, "qty_est_after": t.qty_est_after,
                "actual_count": t.actual_count, "attribution": t.attribution,
                "user_name": u.full_name if u else None, "booking_id": t.booking_id,
                "note": t.note, "recorded_at": t.recorded_at}

    return {"bin": inv.bin_out(db, b), "hours": hours,
            "measurements": [{"mass_g": m.mass_g, "at": m.recorded_at} for m in ms],
            "transactions": [tx_out(t) for t in txs]}


class CountRequest(BaseModel):
    actual_count: int = Field(ge=0)
    note: str = Field(default="", max_length=255)


@router.post("/bins/{bin_id}/count", status_code=status.HTTP_201_CREATED)
def record_count(bin_id: int, req: CountRequest, db: Session = Depends(get_db),
                 staff: User = Depends(require_staff)):
    """A physical count next to the current estimate: estimation error data."""
    b = db.get(InventoryBin, bin_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bin not found")
    est = inv.qty_estimate(b, b.last_mass_g)
    t = InventoryTransaction(bin_id=b.id, kind="COUNT", qty_est_after=est,
                             actual_count=req.actual_count, recorded_by_id=staff.id,
                             note=req.note, attribution="STAFF_COUNT")
    db.add(t)
    db.commit()
    return {"bin_code": b.code, "estimate": est, "actual_count": req.actual_count,
            "error": None if est is None else est - req.actual_count,
            "mass_g": b.last_mass_g}
