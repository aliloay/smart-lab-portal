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
from app.models import Alert, Asset, Device, DeviceType, Lab, User

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
