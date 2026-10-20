"""
Global search (2026-10-18): one box that finds devices, incidents, equipment and labs, each with a
direct link. Staff only (students search pages in the browser). Bounded: at most PER_TYPE results per
kind, simple ILIKE on small tables, minimum 2 characters - never a scan of history tables. It only
NAVIGATES: nothing here starts an action.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.db.session import get_db
from app.models import Alert, Asset, Device, DeviceType, Lab, Role, User

router = APIRouter(prefix="/search", tags=["search"])
PER_TYPE = 6


def _device_link(d: Device) -> str:
    if d.device_type == DeviceType.ROBOT:
        return f"/robots/{d.id}"
    if d.device_type == DeviceType.SECURITY_CAMERA:
        return "/admin/security"
    if d.device_type == DeviceType.PC:
        return "/admin/equipment?tab=noncons"     # the Robots & PCs tab (was tab=robots: no such tab)
    return "/admin/devices"


@router.get("")
def search(q: str = Query(min_length=2, max_length=60), db: Session = Depends(get_db), _: User = Depends(require_staff)):
    term = f"%{q.strip()}%"
    out: list[dict] = []
    m = re.fullmatch(r"(?:inc-?)?0*(\d{1,7})", q.strip().lower())
    if m:
        a = db.get(Alert, int(m.group(1)))
        if a is not None:
            out.append({"type": "incident", "title": f"INC-{a.id:06d} {a.title}", "subtitle": "incident",
                        "to": f"/admin/incidents?open={a.id}"})
    for d in db.scalars(select(Device).where(or_(Device.device_uid.ilike(term), Device.name.ilike(term)))
                        .order_by(Device.device_uid).limit(PER_TYPE)).all():
        out.append({"type": "device", "title": f"{d.name} ({d.device_uid})",
                    "subtitle": d.device_type.value.lower().replace("_", " "), "to": _device_link(d)})
    for a in db.scalars(select(Asset).where(or_(Asset.asset_tag.ilike(term), Asset.name.ilike(term)))
                        .order_by(Asset.name).limit(PER_TYPE)).all():
        out.append({"type": "equipment", "title": f"{a.name} ({a.asset_tag})", "subtitle": "equipment",
                    "to": f"/equipment/{a.id}"})
    for lab in db.scalars(select(Lab).where(or_(Lab.code.ilike(term), Lab.name.ilike(term))).limit(PER_TYPE)).all():
        out.append({"type": "lab", "title": f"{lab.name} ({lab.code})", "subtitle": "laboratory", "to": f"/labs/{lab.id}"})
    # Incidents after the things themselves (owner 2026-10-18: "UR5" listed an old resolved incident
    # before the robot): open ones first, resolved ones last.
    incidents = db.scalars(select(Alert).where(Alert.title.ilike(term))
                           .order_by(Alert.is_resolved, Alert.created_at.desc()).limit(PER_TYPE)).all()
    for a in incidents:
        out.append({"type": "incident", "title": f"INC-{a.id:06d} {a.title}",
                    "subtitle": "resolved" if a.is_resolved else (a.state or "open").lower(), "to": f"/admin/incidents?open={a.id}"})
    seen, uniq = set(), []
    for r in out:
        if r["to"] + r["title"] not in seen:
            seen.add(r["to"] + r["title"])
            uniq.append(r)
    return {"q": q, "results": uniq[:24]}


# ------------------------------------------------------------------ index ---
# 2026-10-20 (owner: "search shouldn't be the literal word - lab1 or robot should show the Robotics
# Lab"): the palette loads this small index once and ranks it in the browser on every keystroke
# (frontend/src/lib/searchRank.ts) - instant, and matched by meaning: every item carries words for
# what it IS, its lab's name and code, and the subject words of that lab. Same staff-only scope as
# /search; bounded (all labs / devices / equipment are small tables, incidents capped).
LAB_WORDS = [            # (words in the lab's name, subject words people type for it)
    (("robot",), "robot robots robotics robotic arm arms cobot ur5e ur5 fanuc gripper automation workcell"),
    (("plc",), "plc automation siemens hmi control controls industrial ladder"),
    (("production",), "production manufacturing machining machine drilling workshop cnc metal"),
    (("material",), "materials testing tensile hardness microscope 3d printer printing"),
    (("automotive",), "automotive car cars vehicle ev engine powertrain"),
    (("pcb",), "pcb electronics soldering oscilloscope circuit boards"),
    (("microcontroller",), "microcontroller microcontrollers mcu embedded arduino esp32 stm32"),
    (("power",), "power electrical energy motor motors drives"),
    (("fabrication",), "fabrication laser cutter maker woodwork cnc router"),
    (("cad",), "cad digital design solidworks modelling 3d"),
    (("fashion", "textile"), "fashion textile textiles sewing garments"),
]
TYPE_WORDS = {
    DeviceType.ROBOT: "robot robots arm cobot twin",
    DeviceType.SECURITY_CAMERA: "camera cameras cctv security surveillance video tracking people person identity",
    DeviceType.CAMERA: "camera face door entry esp32cam",
    DeviceType.MASTER_CONTROLLER: "door lock access entry master controller esp32 nfc fingerprint",
    DeviceType.FACE_SERVER: "face recognition server identity",
    DeviceType.SENSOR_NODE: "sensor node iot",
    DeviceType.PC: "pc computer computers laptop workstation",
}
UID_WORDS = [("ENV", "environment temperature humidity gas air smoke"),
             ("BIN", "bin bins consumables inventory weight scale"),
             ("REUSE", "reusable reusables tools return")]
INDEX_INCIDENTS = 150


def _lab_words(lab: Lab) -> str:
    name = lab.name.lower()
    return " ".join(w for keys, w in LAB_WORDS if any(k in name for k in keys))


def _lab_ref(lab: Lab | None) -> str:
    return f"{lab.name} {lab.code}" if lab else ""


@router.get("/index")
def search_index(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """Everything the palette can find, with the words that make it relevant. `keys` = what the item
    is called (code, tag, uid); `words` = what it is (type and subject words); `lab` = where it is."""
    labs = {lab.id: lab for lab in db.scalars(select(Lab).order_by(Lab.id)).all()}
    items: list[dict] = []
    for lab in labs.values():
        items.append({"type": "lab", "title": lab.name, "subtitle": lab.code, "to": f"/labs/{lab.id}",
                      "keys": lab.code, "words": f"lab laboratory {_lab_words(lab)}", "lab": ""})
    for d in db.scalars(select(Device).order_by(Device.device_uid)).all():
        lab = labs.get(d.lab_id)
        extra = " ".join(w for k, w in UID_WORDS if k in d.device_uid.upper())
        items.append({"type": "device", "title": d.name, "subtitle": f"{d.device_type.value.lower().replace('_', ' ')} · {d.device_uid}",
                      "to": _device_link(d), "keys": d.device_uid,
                      "words": f"device {TYPE_WORDS.get(d.device_type, '')} {extra}", "lab": _lab_ref(lab)})
    for a in db.scalars(select(Asset).order_by(Asset.name)).all():
        lab = labs.get(a.lab_id)
        items.append({"type": "equipment", "title": a.name, "subtitle": f"equipment · {a.asset_tag}",
                      "to": f"/equipment/{a.id}", "keys": a.asset_tag,
                      "words": f"equipment {_lab_words(lab) if lab else ''}", "lab": _lab_ref(lab)})
    incidents = db.scalars(select(Alert).order_by(Alert.is_resolved, Alert.created_at.desc()).limit(INDEX_INCIDENTS)).all()
    for a in incidents:
        lab = labs.get(a.lab_id) if a.lab_id else None
        items.append({"type": "incident", "title": a.title, "subtitle": "resolved" if a.is_resolved else (a.state or "open").lower(),
                      "to": f"/admin/incidents?open={a.id}", "keys": f"INC-{a.id:06d} {a.id}",
                      "words": "incident alert alarm problem", "lab": _lab_ref(lab), "resolved": bool(a.is_resolved)})
    for u in db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name)).all():
        role = u.role.value if hasattr(u.role, "value") else str(u.role)
        items.append({"type": "person", "title": u.full_name, "subtitle": role.lower().replace("_", " "),
                      "to": f"/admin/users?find={u.email}", "keys": u.email.split("@")[0],
                      "words": "user person people student staff" if u.role != Role.ADMIN else "user person admin", "lab": ""})
    return {"items": items}
