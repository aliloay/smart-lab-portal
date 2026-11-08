"""
Equipment chosen while booking: smart-bin items, consumables, workstation.

A smart-bin item or a robot workstation is held by one booking at a time: a
PENDING or CONFIRMED booking whose window overlaps holds it. Consumables are
not held (they are counted by weight, not reserved); the booking records how
many the person expects to use. A lab PC is not held (labs have several).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, AssetStatus, Booking, BookingItem, BookingStatus, InventoryBin

WORKSTATION_CATEGORIES = ("Manipulator",)       # assets offered as "what are you working on"
HOLDING = (BookingStatus.PENDING, BookingStatus.CONFIRMED)


class EquipmentError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def held_asset_ids(db: Session, lab_id: int, start: datetime, end: datetime,
                   exclude_booking_id: Optional[int] = None) -> set[int]:
    """Assets held by another booking whose window overlaps [start, end)."""
    q = (select(BookingItem.asset_id)
         .join(Booking, Booking.id == BookingItem.booking_id)
         .where(Booking.lab_id == lab_id, Booking.status.in_(HOLDING),
                Booking.start_time < end, Booking.end_time > start,
                BookingItem.asset_id.is_not(None),
                BookingItem.kind.in_(("BIN_ITEM", "WORKSTATION"))))
    if exclude_booking_id is not None:
        q = q.where(Booking.id != exclude_booking_id)
    return set(db.scalars(q).all())


def options(db: Session, lab_id: int, start: datetime, end: datetime) -> dict:
    held = held_asset_ids(db, lab_id, start, end)
    assets = db.scalars(select(Asset).where(Asset.lab_id == lab_id).order_by(Asset.name)).all()

    def state(a: Asset) -> str:
        if a.id in held:
            return "RESERVED"
        if a.status not in (AssetStatus.AVAILABLE, AssetStatus.CHECKED_OUT):
            return a.status.value                  # MAINTENANCE / RETIRED
        return "AVAILABLE"

    bins = db.scalars(select(InventoryBin).where(InventoryBin.lab_id == lab_id,
                                                 InventoryBin.is_active.is_(True))
                      .order_by(InventoryBin.item_name)).all()
    return {
        "bin_items": [{"id": a.id, "name": a.name, "asset_tag": a.asset_tag, "state": state(a)}
                      for a in assets if a.bin_item or a.nfc_uid],
        "consumables": [{"id": b.id, "name": b.item_name, "category": b.category} for b in bins],
        "workstations": [{"key": f"ASSET:{a.id}", "name": a.name, "state": state(a)}
                         for a in assets if a.category in WORKSTATION_CATEGORIES]
                        + [{"key": "PC", "name": "Lab PC", "state": "AVAILABLE"}],
    }


def resolve(db: Session, lab_id: int, start: datetime, end: datetime, equipment) -> list[BookingItem]:
    """Checks the choices and returns the rows to add (booking_id set by the caller)."""
    if equipment is None:
        return []
    held = held_asset_ids(db, lab_id, start, end)
    rows: list[BookingItem] = []

    def usable(a: Optional[Asset], what: str) -> Asset:
        if a is None or a.lab_id != lab_id:
            raise EquipmentError("EQUIPMENT_UNKNOWN", f"That {what} is not in this laboratory.")
        if a.id in held:
            raise EquipmentError("EQUIPMENT_RESERVED", f"{a.name} is already reserved for that time.")
        if a.status not in (AssetStatus.AVAILABLE, AssetStatus.CHECKED_OUT):
            raise EquipmentError("EQUIPMENT_UNAVAILABLE", f"{a.name} is {a.status.value.lower()}.")
        return a

    for aid in dict.fromkeys(equipment.bin_asset_ids):          # duplicates ignored
        a = usable(db.get(Asset, aid), "item")
        if not (a.bin_item or a.nfc_uid):
            raise EquipmentError("EQUIPMENT_UNKNOWN", f"{a.name} is not a smart-bin item.")
        rows.append(BookingItem(kind="BIN_ITEM", asset_id=a.id, label=a.name))

    for c in equipment.consumables:
        b = db.get(InventoryBin, c.inventory_bin_id)
        if b is None or b.lab_id != lab_id or not b.is_active:
            raise EquipmentError("EQUIPMENT_UNKNOWN", "That consumable is not in this laboratory.")
        rows.append(BookingItem(kind="CONSUMABLE", inventory_bin_id=b.id, quantity=c.quantity,
                                label=b.item_name))

    chosen = [w.upper() for w in equipment.workstations] or [(equipment.workstation or "NONE").upper()]
    for ws in dict.fromkeys(chosen):
        if ws == "NONE":
            continue
        if ws == "PC":
            rows.append(BookingItem(kind="WORKSTATION", label="Lab PC"))
        elif ws.startswith("ASSET:"):
            try:
                aid = int(ws.split(":", 1)[1])
            except ValueError:
                raise EquipmentError("EQUIPMENT_UNKNOWN", "Unknown workstation.")
            a = usable(db.get(Asset, aid), "workstation")
            if a.category not in WORKSTATION_CATEGORIES:
                raise EquipmentError("EQUIPMENT_UNKNOWN", f"{a.name} is not a workstation.")
            rows.append(BookingItem(kind="WORKSTATION", asset_id=a.id, label=a.name))
        else:
            raise EquipmentError("EQUIPMENT_UNKNOWN", "Unknown workstation.")
    return rows


def items_of(db: Session, booking_id: int) -> list[BookingItem]:
    return list(db.scalars(select(BookingItem).where(BookingItem.booking_id == booking_id)
                           .order_by(BookingItem.id)).all())
