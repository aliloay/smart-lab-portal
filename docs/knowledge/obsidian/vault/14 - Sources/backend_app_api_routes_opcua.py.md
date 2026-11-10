---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/opcua.py"
source_hash: "3e3cba21c7dbc28f8d4e9efda698a2f86d3cfa2e814f6343525c7b602d18cf2b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/opcua.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services_devices.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_environment.py]] - imports

```py
"""
Read-only data feed for the OPC UA server (tools/opcua/opcua_server.py, 2026-10-26, priority J).

OPC UA is the industrial standard for machines and software to share live values (SCADA / MES / UaExpert / Siemens /
Node-RED read it). The server on the lab laptop polls this endpoint and publishes the values as OPC UA variables;
nothing can be written back. Only equipment state - no names of people, no PC accounts, no camera images.
Key: X-OPCUA-Key = OPCUA_KEY (unset -> 503, the feed is off).
"""
from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Device, DeviceType, Lab
from app.services.devices import is_fresh

router = APIRouter(prefix="/opcua", tags=["integration"])
KEY = os.environ.get("OPCUA_KEY", "")
ROBOT_KEYS = ("robot_mode", "safety", "program_state", "program", "speed_scaling", "source", "model", "state")
PC_KEYS = ("state", "mode", "agent")
CAM_KEYS = ("people", "fps", "source_ok", "door_open")


def _iso(dt):
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _scalar(v):
    return v if isinstance(v, (int, float, bool, str)) or v is None else None


@router.get("/snapshot")
def snapshot(x_opcua_key: str = Header(""), db: Session = Depends(get_db)):
    if not KEY:
        raise HTTPException(503, "OPC UA feed off (OPCUA_KEY not set)")
    if not hmac.compare_digest(x_opcua_key, KEY):
        raise HTTPException(401, "bad key")
    from app.services import environment
    now = datetime.now(timezone.utc)
    labs = db.scalars(select(Lab).where(Lab.is_active.is_(True)).order_by(Lab.code)).all()
    devs = db.scalars(select(Device).order_by(Device.device_uid)).all()
    env = environment.latest_many(db, list(labs), now)
    out = []
    for lab in labs:
        items = []
        for d in (x for x in devs if x.lab_id == lab.id):
            cs = d.component_state or {}
            keys = (ROBOT_KEYS if d.device_type == DeviceType.ROBOT else PC_KEYS if d.device_type == DeviceType.PC
                    else CAM_KEYS if d.device_type == DeviceType.SECURITY_CAMERA else ())
            vals = {k: _scalar(cs.get(k)) for k in keys if _scalar(cs.get(k)) is not None}
            q = cs.get("q")
            if d.device_type == DeviceType.ROBOT and isinstance(q, list) and len(q) == 6:
                vals.update({f"J{i + 1}_deg": round(float(v) * 57.29578, 3) for i, v in enumerate(q)})
            if d.device_type == DeviceType.MASTER_CONTROLLER and d.door_closed is not None:
                vals["door_closed"] = bool(d.door_closed)
            items.append({"uid": d.device_uid, "name": d.name, "type": d.device_type.value,
                          "online": is_fresh(d, now), "last_seen": _iso(d.last_seen_at), "values": vals})
        e = env.get(lab.id) or {}
        metrics = {m: {"value": v.get("value"), "unit": v.get("unit"), "quality": v.get("quality"), "at": _iso(v.get("at"))}
                   for m, v in (e.get("metrics") or {}).items()}
        out.append({"code": lab.code, "name": lab.name, "devices": items, "environment": metrics})
    return {"server_time": now.isoformat(), "labs": out}

```
