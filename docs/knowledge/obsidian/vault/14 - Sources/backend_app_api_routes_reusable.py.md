---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/reusable.py"
source_hash: "a2923f602a92b38d8ce28f59d9819c1eb4511ca0caf165c2fe30a2f603a29fc8"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/reusable.py` - edit the original in the repository, not this note.

Systems: [[Reusables bin]]

## Related
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_commands.py]] - imports
- [[backend_app_services_access.py]] - imports
- [[backend_app_services_devices.py]] - imports
- [[backend_app_services_events.py]] - imports
- [[backend_app_services_notifications.py]] - imports
- [[firmware_SmartLab_Reusable_Bin_Modular_src_config.h]] - mentioned by docs

```py
"""
Reusable smart bin (Robotics Lab, System 4): NFC-tagged items.

PN532 answers "which item was scanned"; this module answers "is it allowed".
An NFC UID is an IDENTIFIER of an item, not authentication of a person.

RETURN (scan-driven)
  bin node: POST /reusable/scan {uid}
  -> item CHECKED_OUT: reply OPEN_FOR_RETURN; the node opens the lid,
     waits for it to close, then POST /reusable/complete; the item becomes
     AVAILABLE (transaction source BIN).

CHECKOUT BY WEIGHT (portal-driven, the bin holds one kind of item)
  person picks the item in the portal -> OPEN_LID -> the node weighs before,
  opens, waits for the weight to settle, closes, weighs after, then
  POST /reusable/checkout-complete. A drop of about one item = CHECKED_OUT
  to that person; no drop = nothing was taken (the request fails). The
  person is notified either way, staff are told who took what.

UNEXPLAINED WEIGHT CHANGES
  The node reports a settled weight change while no request is running:
  POST /reusable/weight-change. Staff get an alert with the likely number
  of items (change / the items' learnt mass).

CHECKOUT (portal-driven, selected item + tag confirmation - older nodes)
  person, inside the lab: POST /reusable/checkout {asset_id}
  -> a device command OPEN_LID for the lab's bin node (fetched while idle)
  -> the person takes the item and scans its tag at the bin
  -> /reusable/scan: the tag matches the selected item -> CHECKED_OUT to
     that person; any other tag -> WRONG_ITEM, nothing changes.
This never guesses which item left the bin: only the selected item, and
only when its own tag is scanned.

WEIGHT (third proof, the load cell under the bin)
  The node weighs before the lid opens and after it closes. A return must
  add about the item's mass, a checkout remove about one item's mass; a
  mismatch (nothing went in, two items left) is an alert for staff, never
  a block - the tag and the portal decide, the scale double-checks. The
  item's mass is learnt from its first return or set by staff.

Unknown tags are remembered (last one per node) so staff can assign them
to an item on the Inventory page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import device_scope, get_current_user, require_device, require_staff
from app.db.session import get_db
from app.models import (AccessSession, Alert, AlertSeverity, Asset, AssetStatus, Booking, BookingStatus,
                        AssetTransaction, AuditLog, Device, DeviceCommand, DeviceType,
                        EventType, Role, User)
from app.services import commands as cmds
from app.services.access import get_device
from app.services.devices import is_fresh
from app.services.events import log_event
from app.services.notifications import notify, staff_ids

router = APIRouter(prefix="/reusable", tags=["reusable inventory"])

OPEN_LID = "OPEN_LID"
# Last unknown tag per bin node, for assigning it on the Inventory page.
_last_unknown: dict[str, dict] = {}


MIN_ITEM_G = 2.0                     # less than this = nothing went in / came out
TOLERANCE_G = 3.0                    # scale noise + tag/sticker variation...
TOLERANCE_FRACTION = 0.15            # ...or this share of the item's mass, if larger


def weight_check(expected_g: Optional[float], observed_g: Optional[float]) -> str:
    """observed_g: mass that went in (return) or came out (checkout), grams."""
    if observed_g is None:
        return "NO_SCALE"
    if expected_g is None:
        return "LEARNED" if observed_g >= MIN_ITEM_G else "MISMATCH"
    tolerance = max(TOLERANCE_G, TOLERANCE_FRACTION * expected_g)
    return "MATCH" if abs(observed_g - expected_g) <= tolerance else "MISMATCH"


def _weight(db: Session, a: Asset, device: Device, tx: AssetTransaction,
            observed_g: Optional[float], what: str) -> str:
    """Record the load cell's verdict on a transaction; alert staff on a mismatch."""
    verdict = weight_check(a.unit_mass_g, observed_g)
    tx.mass_delta_g = None if observed_g is None else \
        round(observed_g if what == "RETURN" else -observed_g, 1)
    tx.weight_check = verdict
    if verdict == "LEARNED":
        a.unit_mass_g = round(observed_g, 1)
    elif verdict == "MISMATCH":
        exp = f"{a.unit_mass_g:.0f} g" if a.unit_mass_g else "the item's mass"
        detail = (f"{a.asset_tag} ({a.name}): {'return' if what == 'RETURN' else 'checkout'} - the bin "
                  f"{'gained' if what == 'RETURN' else 'lost'} {observed_g:.1f} g, expected about {exp}. "
                  + ("The item may not be in the bin." if what == "RETURN"
                     else "More (or other) items may have been taken."))
        title = f"Smart bin weight does not match: {a.asset_tag}"
        db.add(Alert(lab_id=a.lab_id, device_id=device.id, severity=AlertSeverity.WARNING,
                     title=title[:128], detail=detail))
        notify(db, staff_ids(db), "SECURITY_EVENT", title[:160], body=detail,
               link="/admin/equipment?tab=reusables", severity="warning")
    return verdict


def norm_uid(uid: str) -> str:
    """'04:A2:..' / '04a2..' -> '04A2..' (hex, no separators)."""
    return "".join(c for c in uid.upper() if c in "0123456789ABCDEF")


def _staff(u: User) -> bool:
    return u.role in (Role.ADMIN, Role.LAB_STAFF)


def bin_node(db: Session, lab_id: int) -> Optional[Device]:
    """The lab's reusable-bin node: it says so in its heartbeat."""
    for d in db.scalars(select(Device).where(Device.lab_id == lab_id,
                                             Device.device_type == DeviceType.SENSOR_NODE)).all():
        if (d.component_state or {}).get("reusable_bin") is True:
            return d
    return None


def _inside(db: Session, user_id: int, lab_id: int) -> Optional[AccessSession]:
    return db.scalar(select(AccessSession).where(
        AccessSession.user_id == user_id, AccessSession.lab_id == lab_id,
        AccessSession.ended_at.is_(None)))


def may_take(db: Session, user: User, lab_id: int) -> tuple[bool, Optional[int]]:
    """(allowed, booking_id): staff always; a person inside the lab; or a person
    in their confirmed booking's window whom the door already let in."""
    session = _inside(db, user.id, lab_id)
    if session is not None:
        return True, session.booking_id
    now = datetime.now(timezone.utc)
    b = db.scalar(select(Booking).where(
        Booking.user_id == user.id, Booking.lab_id == lab_id,
        Booking.status == BookingStatus.CONFIRMED, Booking.start_time <= now,
        Booking.end_time > now, Booking.first_entry_at.is_not(None)))
    if b is not None:
        return True, b.id
    return _staff(user), None


def kind_name(name: str) -> str:
    """'Breadboard 2' -> 'Breadboard': identical items differ only by their number.
    A take-out is 'a breadboard'; which one is known when its tag is scanned back."""
    import re
    return re.sub(r"\s*#?\d+$", "", name).strip() or name


def _swapped_for(db: Session, a: Asset) -> Optional[Asset]:
    """The bin holds interchangeable items and a checkout is confirmed by weight,
    so the item picked in the portal may not be the one physically taken. A tag
    scanned for return that is recorded as IN the bin, while another bin item
    of this lab is recorded as OUT, stands for that checked-out item (oldest first)."""
    if a.status != AssetStatus.AVAILABLE or not a.bin_item:
        return None
    return db.scalar(select(Asset).where(
        Asset.lab_id == a.lab_id, Asset.bin_item.is_(True), Asset.id != a.id,
        Asset.status == AssetStatus.CHECKED_OUT).order_by(Asset.checked_out_at))


def _active_checkout(db: Session, device_id: int) -> Optional[DeviceCommand]:
    cmds.expire_stale(db)
    return db.scalar(select(DeviceCommand).where(
        DeviceCommand.device_id == device_id, DeviceCommand.command == OPEN_LID,
        DeviceCommand.status.in_(cmds.ACTIVE)).order_by(DeviceCommand.created_at))


# ------------------------------------------------------------ person ---
class CheckoutRequest(BaseModel):
    asset_id: int


@router.post("/checkout")
def request_checkout(req: CheckoutRequest, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    a = db.get(Asset, req.asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if a.status != AssetStatus.AVAILABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The item is {a.status.value.lower()}.")
    if not a.nfc_uid:
        raise HTTPException(status.HTTP_409_CONFLICT, "This item has no NFC tag - ask lab staff.")
    allowed, booking_id = may_take(db, user, a.lab_id)
    if not allowed:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "You can take items while you are inside the lab (or in your booking, after the door let you in).")
    node = bin_node(db, a.lab_id)
    if node is None or not is_fresh(node, datetime.now(timezone.utc)):
        raise HTTPException(status.HTTP_409_CONFLICT, "The smart bin is offline.")
    if _active_checkout(db, node.id):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The bin is busy with another request - try again in a minute.")
    now = datetime.now(timezone.utc)
    c = DeviceCommand(device_id=node.id, command=OPEN_LID, status="PENDING",
                      args={"intent": "CHECKOUT", "asset_id": a.id, "asset_tag": a.asset_tag,
                            "asset_name": kind_name(a.name),
                            "user_id": user.id,
                            "booking_id": booking_id},
                      target_user_id=user.id, requested_by_id=user.id,
                      created_at=now, expires_at=now + cmds.PICKUP_WINDOW)
    db.add(c)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="BIN_CHECKOUT_REQUESTED",
                    entity_type="asset", entity_id=str(a.id),
                    detail={"command_id": c.id, "device": node.device_uid}))
    cmds.publish_later(db, c)
    db.commit()
    cmds.flush_published(db)
    return {**cmds.out(c), "message": f"The bin opens - take one {kind_name(a.name).lower()}; the bin weighs to confirm."}


# ------------------------------------------------- staff, on someone's behalf ---
class StaffCheckout(BaseModel):
    asset_id: Optional[int] = None
    asset_ids: list[int] = Field(default_factory=list, max_length=20)
    user_id: int


@router.post("/staff-checkout")
def staff_checkout(req: StaffCheckout, db: Session = Depends(get_db),
                   staff: User = Depends(require_staff)):
    """Staff take an item out of the bin FOR a person (e.g. their booking has
    ended). Same bin path: the lid opens and the weight confirms the take."""
    ids = list(dict.fromkeys(req.asset_ids or ([req.asset_id] if req.asset_id else [])))
    person = db.get(User, req.user_id)
    items = [db.get(Asset, i) for i in ids]
    if not ids or person is None or any(x is None for x in items):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item or person not found")
    for x in items:
        if x.status != AssetStatus.AVAILABLE:
            raise HTTPException(status.HTTP_409_CONFLICT, f"{x.name} is {x.status.value.lower()}.")
    if len({x.lab_id for x in items}) > 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pick items from one bin at a time.")
    a = items[0]
    node = bin_node(db, a.lab_id)
    if node is None or not is_fresh(node, datetime.now(timezone.utc)):
        raise HTTPException(status.HTTP_409_CONFLICT, "The smart bin is offline.")
    if _active_checkout(db, node.id):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The bin is busy with another request - try again in a minute.")
    now = datetime.now(timezone.utc)
    c = DeviceCommand(device_id=node.id, command=OPEN_LID, status="PENDING",
                      args={"intent": "CHECKOUT", "asset_id": a.id, "asset_ids": ids,
                            "asset_tag": a.asset_tag,
                            "asset_name": (f"{len(ids)} x " if len(ids) > 1 else "") + kind_name(a.name),
                            "user_id": person.id, "booking_id": None, "by_staff": staff.id},
                      target_user_id=person.id, requested_by_id=staff.id,
                      created_at=now, expires_at=now + cmds.PICKUP_WINDOW)
    db.add(c)
    db.flush()
    db.add(AuditLog(actor_user_id=staff.id, action="BIN_CHECKOUT_BY_STAFF",
                    entity_type="asset", entity_id=str(a.id),
                    detail={"command_id": c.id, "for_user": person.id, "items": ids,
                            "device": node.device_uid}))
    cmds.publish_later(db, c)
    db.commit()
    cmds.flush_published(db)
    what = f"{len(ids)} {kind_name(a.name).lower()}s" if len(ids) > 1 else f"one {kind_name(a.name).lower()}"
    return {**cmds.out(c), "message": f"The bin opens - take {what} for {person.full_name}; "
                                      f"the bin weighs to confirm."}


class StaffReturn(BaseModel):
    asset_id: int
    note: str = Field(default="", max_length=255)


@router.post("/staff-return")
def staff_return(req: StaffReturn, db: Session = Depends(get_db),
                 staff: User = Depends(require_staff)):
    """Staff record that a checked-out item is back (it came back without the
    bin - bin fault, booking over). Logged as a STAFF return, never by the bin."""
    a = db.get(Asset, req.asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if a.status != AssetStatus.CHECKED_OUT:
        raise HTTPException(status.HTTP_409_CONFLICT, "This item is not checked out.")
    holder = a.holder_id
    a.status, a.holder_id, a.checked_out_at = AssetStatus.AVAILABLE, None, None
    if holder:
        db.add(AssetTransaction(asset_id=a.id, user_id=holder, lab_id=a.lab_id, action="RETURN",
                                source="STAFF", note=(req.note or f"Recorded by {staff.full_name}")[:255]))
    db.add(AuditLog(actor_user_id=staff.id, action="BIN_RETURN_BY_STAFF", entity_type="asset",
                    entity_id=str(a.id), detail={"holder": holder, "note": req.note}))
    log_event(db, EventType.ASSET_RETURN, lab_id=a.lab_id, user_id=holder,
              message=f"{a.name} returned (recorded by staff)")
    if holder:
        notify(db, [holder], "BIN_RETURN", f"Returned: {a.name}",
               body=f"{a.name} was recorded as returned by {staff.full_name}.", link=f"/labs/{a.lab_id}")
    db.commit()
    return {"asset_id": a.id, "status": a.status.value}


@router.get("/items")
def bin_items(lab_id: int, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    """Tagged items of a lab's smart bin. Who holds an item: staff see the
    name, the holder sees "you", everyone else only that it is out."""
    node = bin_node(db, lab_id)
    items = db.scalars(select(Asset).where(
        Asset.lab_id == lab_id, (Asset.bin_item.is_(True)) | (Asset.nfc_uid.is_not(None)))
        .order_by(Asset.asset_tag)).all()
    out = []
    for a in items:
        holder = None
        if a.holder_id:
            if _staff(user):
                h = db.get(User, a.holder_id)
                holder = h.full_name if h else None
            elif a.holder_id == user.id:
                holder = "you"
        out.append({"id": a.id, "asset_tag": a.asset_tag, "name": a.name,
                    "category": a.category, "status": a.status.value,
                    "holder": holder, "checked_out_at": a.checked_out_at,
                    "unit_mass_g": a.unit_mass_g,
                    **({"nfc_uid": a.nfc_uid} if _staff(user) else {})})
    return {"bin_online": bool(node and is_fresh(node, datetime.now(timezone.utc))),
            "bin_device": node.device_uid if node else None,
            "inside": may_take(db, user, lab_id)[0], "items": out}


# --------------------------------------------------------------- staff ---
@router.get("/last-unknown")
def last_unknown(_: User = Depends(require_staff)):
    """The most recent tag a bin node scanned that no item has."""
    if not _last_unknown:
        return None
    return max(_last_unknown.values(), key=lambda x: x["at"])


class SetMass(BaseModel):
    unit_mass_g: Optional[float] = Field(default=None, gt=0, le=5000)


@router.put("/assets/{asset_id}/mass")
def set_mass(asset_id: int, req: SetMass, db: Session = Depends(get_db),
             staff: User = Depends(require_staff)):
    """The item's mass for the bin's weight check (None = learn it again)."""
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    a.unit_mass_g = req.unit_mass_g
    db.add(AuditLog(actor_user_id=staff.id, action="ASSET_MASS_SET", entity_type="asset",
                    entity_id=str(a.id), detail={"unit_mass_g": req.unit_mass_g}))
    db.commit()
    return {"asset_id": a.id, "unit_mass_g": a.unit_mass_g}


class AssignTag(BaseModel):
    nfc_uid: Optional[str] = Field(default=None, max_length=32)


@router.put("/assets/{asset_id}/tag")
def assign_tag(asset_id: int, req: AssignTag, db: Session = Depends(get_db),
               staff: User = Depends(require_staff)):
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    uid = norm_uid(req.nfc_uid) if req.nfc_uid else None
    if uid and db.scalar(select(Asset).where(Asset.nfc_uid == uid, Asset.id != a.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This tag is already on another item.")
    a.nfc_uid = uid
    db.add(AuditLog(actor_user_id=staff.id, action="ASSET_TAG_ASSIGNED",
                    entity_type="asset", entity_id=str(a.id), detail={"nfc_uid": uid}))
    db.commit()
    for k, v in list(_last_unknown.items()):
        if v["nfc_uid"] == uid:
            _last_unknown.pop(k)
    return {"asset_id": a.id, "asset_tag": a.asset_tag, "nfc_uid": a.nfc_uid}


# ------------------------------------------------------------ bin node ---
class ScanReport(BaseModel):
    device_uid: str = Field(max_length=64)
    nfc_uid: str = Field(min_length=4, max_length=32)
    # Load cell: mass change over the last lid cycle (checkout), if weighed.
    mass_delta_g: Optional[float] = Field(default=None, ge=-10000, le=10000)


def _tx(db: Session, a: Asset, user_id: int, action: str, device: Device,
        booking_id: Optional[int]) -> AssetTransaction:
    tx = AssetTransaction(asset_id=a.id, user_id=user_id, lab_id=a.lab_id, action=action,
                          booking_id=booking_id, device_id=device.id, source="BIN")
    db.add(tx)
    return tx


@router.post("/scan", tags=["devices"])
def scan(req: ScanReport, db: Session = Depends(get_db),
         identity: str = Depends(require_device)):
    """A tag at the bin. Replies with what the node does and shows."""
    device_scope(identity, req.device_uid)
    device = get_device(db, req.device_uid)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown device - send a heartbeat first")
    uid = norm_uid(req.nfc_uid)
    now = datetime.now(timezone.utc)
    device.last_seen_at = now
    a = db.scalar(select(Asset).where(Asset.nfc_uid == uid))
    if a is None:
        _last_unknown[device.device_uid] = {"nfc_uid": uid, "device_uid": device.device_uid,
                                            "at": now}
        db.commit()
        return {"action": "UNKNOWN", "lcd1": "UNKNOWN TAG", "lcd2": uid[-8:]}

    # A checkout in progress at this bin: only the selected item's tag completes it.
    pending = _active_checkout(db, device.id)
    if pending is not None and (pending.args or {}).get("intent") == "CHECKOUT":
        args = pending.args or {}
        if args.get("asset_id") != a.id:
            db.commit()
            return {"action": "WRONG_ITEM", "lcd1": "WRONG ITEM",
                    "lcd2": f"SCAN {args.get('asset_tag', '')}"[:16]}
        if a.status != AssetStatus.AVAILABLE:
            pending.status, pending.completed_at = "FAILED", now
            pending.message = f"The item is {a.status.value.lower()}."
            cmds.publish_later(db, pending)
            db.commit()
            cmds.flush_published(db)
            return {"action": "NOT_ALLOWED", "lcd1": a.asset_tag[:16], "lcd2": "NOT AVAILABLE"}
        a.status, a.holder_id, a.checked_out_at = AssetStatus.CHECKED_OUT, args.get("user_id"), now
        tx = _tx(db, a, args["user_id"], "CHECKOUT", device, args.get("booking_id"))
        verdict = _weight(db, a, device, tx,
                          None if req.mass_delta_g is None else -req.mass_delta_g, "CHECKOUT")
        log_event(db, EventType.ASSET_CHECKOUT, lab_id=a.lab_id, user_id=args["user_id"],
                  message=f"{a.name} taken from the smart bin")
        pending.status, pending.step, pending.completed_at = "DONE", "TAG_CONFIRMED", now
        cmds.publish_later(db, pending)
        db.commit()
        cmds.flush_published(db)
        return {"action": "CHECKOUT_OK", "lcd1": a.asset_tag[:16],
                "lcd2": "CHECK WEIGHT" if verdict == "MISMATCH" else "CHECKED OUT",
                "weight_check": verdict}

    if a.status == AssetStatus.CHECKED_OUT or _swapped_for(db, a) is not None:
        db.commit()
        return {"action": "OPEN_FOR_RETURN", "asset_tag": a.asset_tag, "asset_name": a.name,
                "lcd1": a.asset_tag[:16], "lcd2": "RETURNING..."}
    db.commit()
    return {"action": "NOT_ALLOWED", "lcd1": a.asset_tag[:16],
            "lcd2": "TAKE VIA PORTAL" if a.status == AssetStatus.AVAILABLE
            else a.status.value[:16]}


class CompleteReport(BaseModel):
    device_uid: str = Field(max_length=64)
    nfc_uid: str = Field(min_length=4, max_length=32)
    lid_opened: bool
    lid_closed: bool
    # Load cell, before the lid opened and after it closed (None = not weighed).
    mass_before_g: Optional[float] = Field(default=None, ge=-10000, le=10000)
    mass_after_g: Optional[float] = Field(default=None, ge=-10000, le=10000)


@router.post("/complete", tags=["devices"])
def complete_return(req: CompleteReport, db: Session = Depends(get_db),
                    identity: str = Depends(require_device)):
    """After OPEN_FOR_RETURN: the lid cycle finished. The return is recorded
    only if the lid opened (the item could go in) - it is never assumed."""
    device_scope(identity, req.device_uid)
    device = get_device(db, req.device_uid)
    a = db.scalar(select(Asset).where(Asset.nfc_uid == norm_uid(req.nfc_uid)))
    if device is None or a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown device or item")
    scanned = returned = a
    if a.status != AssetStatus.CHECKED_OUT:
        a = _swapped_for(db, scanned)
        if a is None:
            return {"recorded": False, "lcd1": scanned.asset_tag[:16], "lcd2": "ALREADY IN"}
        # The person had the scanned one; the record said the other: the open
        # checkout is closed by this return, and staff are told about the swap.
        note = (f"{scanned.name} was returned while {a.name} was recorded as taken - "
                f"the item taken was {scanned.name}. {a.name}'s checkout is closed by this return.")
        db.add(AuditLog(actor_user_id=None, action="BIN_ITEM_SWAPPED", entity_type="asset",
                        entity_id=str(a.id), detail={"recorded": a.id, "returned": scanned.id}))
        notify(db, staff_ids(db), "BIN_RETURN", f"Smart bin: {scanned.name} returned for {a.name}",
               body=note, link="/admin/equipment?tab=reusables")
    returned = scanned
    if not req.lid_opened:
        return {"recorded": False, "lcd1": "LID DID NOT OPEN", "lcd2": "CALL STAFF"}
    holder = a.holder_id
    session = _inside(db, holder, a.lab_id) if holder else None
    a.status, a.holder_id, a.checked_out_at = AssetStatus.AVAILABLE, None, None
    verdict = None
    if holder:
        tx = _tx(db, a, holder, "RETURN", device, session.booking_id if session else None)
        put_in = (req.mass_after_g - req.mass_before_g
                  if req.mass_before_g is not None and req.mass_after_g is not None else None)
        verdict = _weight(db, a, device, tx, put_in, "RETURN")
    log_event(db, EventType.ASSET_RETURN, lab_id=a.lab_id, user_id=holder,
              message=f"{returned.name} returned to the smart bin"
                      + ("" if req.lid_closed else " - lid did not close")
                      + (" - weight does not match" if verdict == "MISMATCH" else ""))
    if holder:
        notify(db, [holder], "BIN_RETURN", f"Returned: {returned.name}",
               body=f"{returned.name} is back in the smart bin. Thank you."
                    + ("" if verdict != "MISMATCH" else " The weight did not match - staff will check."),
               link=f"/labs/{a.lab_id}")
    who = db.get(User, holder) if holder else None
    notify(db, staff_ids(db), "BIN_RETURN", f"{returned.name} returned",
           body=f"{who.full_name if who else 'Someone'} returned {returned.name} ({returned.asset_tag})"
                + (f", +{put_in:.1f} g" if holder and put_in is not None else ""),
           link="/admin/equipment?tab=reusables", exclude=holder)
    db.commit()
    return {"recorded": True, "lcd1": a.asset_tag[:16],
            "lcd2": "CLOSE THE LID" if not req.lid_closed
            else "CHECK WEIGHT" if verdict == "MISMATCH" else "RETURN RECORDED",
            "weight_check": verdict}


# ----------------------------------------------- checkout by weight ---
class CheckoutCompleteReport(BaseModel):
    device_uid: str = Field(max_length=64)
    command_id: int
    lid_opened: bool
    lid_closed: bool
    mass_before_g: Optional[float] = Field(default=None, ge=-10000, le=10000)
    mass_after_g: Optional[float] = Field(default=None, ge=-10000, le=10000)


@router.post("/checkout-complete", tags=["devices"])
def checkout_complete(req: CheckoutCompleteReport, db: Session = Depends(get_db),
                      identity: str = Depends(require_device)):
    """After OPEN_LID for a checkout: the bin weighed before and after.
    About one item less = the selected item is CHECKED_OUT to the person."""
    device_scope(identity, req.device_uid)
    device = get_device(db, req.device_uid)
    c = db.get(DeviceCommand, req.command_id)
    if device is None or c is None or c.device_id != device.id or c.command != OPEN_LID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown device or request")
    args = c.args or {}
    a = db.get(Asset, args.get("asset_id"))
    user_id = args.get("user_id")
    if a is None or user_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown item")
    now = datetime.now(timezone.utc)
    taken = (req.mass_before_g - req.mass_after_g
             if req.mass_before_g is not None and req.mass_after_g is not None else None)

    def fail(msg: str, lcd2: str):
        c.status, c.completed_at, c.message = "FAILED", now, msg
        cmds.publish_later(db, c)
        notify(db, [user_id], "BIN_CHECKOUT", f"Not taken: {a.name}", body=msg,
               link=f"/labs/{a.lab_id}", severity="warning")
        db.commit()
        cmds.flush_published(db)
        return {"recorded": False, "lcd1": a.name[:16], "lcd2": lcd2}

    if c.status not in cmds.ACTIVE:
        return {"recorded": False, "lcd1": a.name[:16], "lcd2": "REQUEST EXPIRED"}
    if not req.lid_opened:
        return fail("The bin lid did not open.", "LID DID NOT OPEN")
    if a.status != AssetStatus.AVAILABLE:
        return fail(f"{a.name} is {a.status.value.lower()}.", "NOT AVAILABLE")
    if taken is not None and taken < MIN_ITEM_G:
        return fail("The bin's weight did not drop - nothing was taken.", "NOTHING TAKEN")

    # Several items picked (staff, one lid opening): how many came out is read
    # from the weight; only that many are recorded (identical items).
    chosen = [x for x in (db.get(Asset, i) for i in (args.get("asset_ids") or [a.id]))
              if x is not None and x.status == AssetStatus.AVAILABLE]
    k = len(chosen)
    if k > 1 and taken is not None and a.unit_mass_g:
        k = max(1, min(k, round(taken / a.unit_mass_g)))
    picked = len(args.get("asset_ids") or [a.id])
    verdict = "NO_SCALE"
    for x in chosen[:k]:
        x.status, x.holder_id, x.checked_out_at = AssetStatus.CHECKED_OUT, user_id, now
        tx = _tx(db, x, user_id, "CHECKOUT", device, args.get("booking_id"))
        v = _weight(db, x, device, tx, None if taken is None else taken / k, "CHECKOUT")
        verdict = "MISMATCH" if v == "MISMATCH" else v
    who = db.get(User, user_id)
    log_event(db, EventType.ASSET_CHECKOUT, lab_id=a.lab_id, user_id=user_id,
              message=f"{a.name} taken from the smart bin"
                      + (" - weight does not match" if verdict == "MISMATCH" else ""))
    c.status, c.step, c.completed_at = "DONE", "WEIGHT_CONFIRMED", now
    kind = kind_name(a.name)
    c.message = (f"{k} of {picked} {kind.lower()}s taken" if picked > 1 else f"{kind} taken")         + (f" (-{taken:.1f} g)" if taken is not None else "")
    cmds.publish_later(db, c)
    many = f"{k} {kind.lower()}s" if k > 1 else f"a {kind.lower()}"
    notify(db, [user_id], "BIN_CHECKOUT", f"Taken: {k} x {kind}" if k > 1 else f"Taken: {kind}",
           body=f"You took {many} from the smart bin. Scan each tag at the bin to return it.",
           link=f"/labs/{a.lab_id}")
    notify(db, staff_ids(db), "BIN_CHECKOUT", f"{kind} taken",
           body=f"{who.full_name if who else 'Someone'} took {many} from the smart bin"
                + (f", -{taken:.1f} g" if taken is not None else ""),
           link="/admin/equipment?tab=reusables", exclude=user_id)
    db.commit()
    cmds.flush_published(db)
    return {"recorded": True, "lcd1": kind[:16],
            "lcd2": "CHECK WEIGHT" if verdict == "MISMATCH" else "ENJOY!",
            "weight_check": verdict}


class WeightChangeReport(BaseModel):
    device_uid: str = Field(max_length=64)
    delta_g: float = Field(ge=-10000, le=10000)
    mass_g: Optional[float] = Field(default=None, ge=-10000, le=10000)


@router.post("/weight-change", tags=["devices"])
def weight_change(req: WeightChangeReport, db: Session = Depends(get_db),
                  identity: str = Depends(require_device)):
    """A settled weight change with no request running: nobody explained it."""
    device_scope(identity, req.device_uid)
    device = get_device(db, req.device_uid)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown device")
    if abs(req.delta_g) < MIN_ITEM_G:
        return {"alerted": False}
    masses = [m for m in db.scalars(select(Asset.unit_mass_g).where(
        Asset.lab_id == device.lab_id, Asset.bin_item.is_(True), Asset.unit_mass_g.is_not(None))).all()]
    guess = ""
    if masses:
        unit = sum(masses) / len(masses)
        n = round(abs(req.delta_g) / unit)
        if n >= 1:
            guess = f" - about {n} item{'s' if n > 1 else ''} ({unit:.0f} g each)"
    what = "removed" if req.delta_g < 0 else "added"
    title = f"Smart bin: {abs(req.delta_g):.1f} g {what} without a request"
    detail = f"The bin's weight changed by {req.delta_g:+.1f} g with no checkout or return{guess}."
    db.add(Alert(lab_id=device.lab_id, device_id=device.id, severity=AlertSeverity.WARNING,
                 title=title[:128], detail=detail))
    notify(db, staff_ids(db), "SECURITY_EVENT", title[:160], body=detail,
           link="/admin/equipment?tab=reusables", severity="warning")
    db.commit()
    return {"alerted": True, "guess": guess.strip(" -")}

```
