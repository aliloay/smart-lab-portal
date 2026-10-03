"""
Reusable smart bin (Robotics Lab, System 4): NFC-tagged items.

PN532 answers "which item was scanned"; this module answers "is it allowed".
An NFC UID is an IDENTIFIER of an item, not authentication of a person.

RETURN (scan-driven)
  bin node: POST /reusable/scan {uid}
  -> item CHECKED_OUT: reply OPEN_FOR_RETURN; the node opens the lid,
     waits for it to close, then POST /reusable/complete; the item becomes
     AVAILABLE (transaction source BIN).

CHECKOUT (portal-driven, selected item + tag confirmation)
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
from app.models import (AccessSession, Alert, AlertSeverity, Asset, AssetStatus,
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
    session = _inside(db, user.id, a.lab_id)
    if session is None and not _staff(user):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "You can take items only while you are inside the lab.")
    node = bin_node(db, a.lab_id)
    if node is None or not is_fresh(node, datetime.now(timezone.utc)):
        raise HTTPException(status.HTTP_409_CONFLICT, "The smart bin is offline.")
    if _active_checkout(db, node.id):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The bin is busy with another request - try again in a minute.")
    now = datetime.now(timezone.utc)
    c = DeviceCommand(device_id=node.id, command=OPEN_LID, status="PENDING",
                      args={"intent": "CHECKOUT", "asset_id": a.id, "asset_tag": a.asset_tag,
                            "user_id": user.id,
                            "booking_id": session.booking_id if session else None},
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
    return {**cmds.out(c), "message": f"The bin opens - take {a.asset_tag} and scan its tag."}


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
            "inside": _inside(db, user.id, lab_id) is not None, "items": out}


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

    if a.status == AssetStatus.CHECKED_OUT:
        db.commit()
        return {"action": "OPEN_FOR_RETURN", "asset_tag": a.asset_tag,
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
    if a.status != AssetStatus.CHECKED_OUT:
        return {"recorded": False, "lcd1": a.asset_tag[:16], "lcd2": "ALREADY IN"}
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
              message=f"{a.name} returned to the smart bin"
                      + ("" if req.lid_closed else " - lid did not close")
                      + (" - weight does not match" if verdict == "MISMATCH" else ""))
    db.commit()
    return {"recorded": True, "lcd1": a.asset_tag[:16],
            "lcd2": "CLOSE THE LID" if not req.lid_closed
            else "CHECK WEIGHT" if verdict == "MISMATCH" else "RETURN RECORDED",
            "weight_check": verdict}
