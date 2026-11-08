"""
Asset Administration Shell export (2026-10-26, priority J - Industry 4.0 digital-twin interchange).

One AAS (metamodel V3.0, JSON serialisation) per registered asset, with two submodels built only from the portal's
records:
  * Nameplate      - name, asset tag, category, serial number, lab (static identity)
  * OperationalData - status, last inspection / next maintenance, and for a networked item its device: online, last
                      seen, and the newest reported state values (as reported, never filled in)
Read-only, nothing is written back; an AAS-capable tool (e.g. Eclipse BaSyx / AASX Package Explorer) can import it.
Identifiers are stable URNs from the asset tag. OPC UA is NOT provided (it needs a server package and a security
model - proposal only).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Device, Lab
from app.services.devices import is_fresh

BASE = "urn:giu:smartlab"


def _prop(id_short: str, value: Any, vtype: str = "xs:string") -> Optional[dict]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        value, vtype = value.astimezone(timezone.utc).isoformat(), "xs:dateTime"
    elif isinstance(value, bool):
        value, vtype = str(value).lower(), "xs:boolean"
    elif isinstance(value, int):
        vtype = "xs:int"
    elif isinstance(value, float):
        vtype = "xs:double"
    return {"modelType": "Property", "idShort": id_short, "valueType": vtype, "value": str(value)}


def _safe(s: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in s)
    return out if out[:1].isalpha() else "a" + out


def _submodel(sid: str, id_short: str, sem: str, props: list) -> dict:
    return {"modelType": "Submodel", "id": sid, "idShort": id_short, "kind": "Instance",
            "semanticId": {"type": "ExternalReference", "keys": [{"type": "GlobalReference", "value": sem}]},
            "submodelElements": [p for p in props if p]}


def environment(db: Session, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    labs = {l.id: l for l in db.scalars(select(Lab)).all()}
    devs = {d.asset_id: d for d in db.scalars(select(Device).where(Device.asset_id.is_not(None))).all()}
    shells, submodels = [], []
    for a in db.scalars(select(Asset).order_by(Asset.asset_tag)).all():
        tag = _safe(a.asset_tag)
        aid, lab, d = f"{BASE}:asset:{tag}", labs.get(a.lab_id), devs.get(a.id)
        name_id, op_id = f"{BASE}:sm:{tag}:nameplate", f"{BASE}:sm:{tag}:operational"
        submodels.append(_submodel(name_id, "Nameplate", "https://admin-shell.io/zvei/nameplate/2/0/Nameplate", [
            _prop("ManufacturerProductDesignation", a.name), _prop("AssetTag", a.asset_tag),
            _prop("Category", a.category), _prop("SerialNumber", a.serial_number),
            _prop("Location", f"{lab.code} {lab.name}" if lab else None)]))
        cs = (d.component_state or {}) if d else {}
        reported = [_prop(_safe(k), v) for k, v in sorted(cs.items())
                    if isinstance(v, (str, int, float, bool)) and len(str(v)) < 200][:30]
        submodels.append(_submodel(op_id, "OperationalData", f"{BASE}:semantic:OperationalData", [
            _prop("Status", a.status.value if a.status else None), _prop("LastInspected", a.last_inspected_at),
            _prop("NextMaintenance", a.next_maintenance_at),
            _prop("DeviceUid", d.device_uid if d else None),
            _prop("Online", is_fresh(d, now) if d else None), _prop("LastSeen", d.last_seen_at if d else None),
            {"modelType": "SubmodelElementCollection", "idShort": "ReportedState", "value": [r for r in reported if r]}
            if reported else None]))
        shells.append({"modelType": "AssetAdministrationShell", "id": f"{aid}:aas", "idShort": f"AAS_{tag}",
                       "assetInformation": {"assetKind": "Instance", "globalAssetId": aid},
                       "submodels": [{"type": "ModelReference", "keys": [{"type": "Submodel", "value": i}]}
                                     for i in (name_id, op_id)]})
    return {"assetAdministrationShells": shells, "submodels": submodels, "conceptDescriptions": []}
