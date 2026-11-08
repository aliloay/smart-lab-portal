---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/workcell.py"
source_hash: "3d5481180bf2c22cff738fbfc129dd1c101c7655a94273bd7515a6776f892b80"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/workcell.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_models___init__.py]] - imports

```py
"""
Virtual workcells for the robot digital twins: table + obstacles, drawn and collision-checked in
the browser. Every object is MANUAL or CAMERA_ESTIMATE - never "verified". Planning aid only:
nothing here reads from or writes to a robot. A save adds a new version; nothing is overwritten.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_staff
from app.db.session import get_db
from app.models import AuditLog, User, WorkcellSetup

router = APIRouter(prefix="/workcell", tags=["workcell"])
RobotKey = Literal["UR5E", "FANUC"]
M = Field(ge=-5.0, le=5.0)                 # metres, inside any lab cell
S = Field(gt=0.0, le=3.0)


class Obstacle(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    label: str = Field(default="Box", max_length=48)
    x: float = M; y: float = M; z: float = M            # centre, world frame (+x front, z up, floor = 0)
    w: float = S; d: float = S; h: float = S            # size along x, y, z
    source: Literal["MANUAL", "CAMERA_ESTIMATE"] = "MANUAL"
    uncertainty_m: Optional[float] = Field(default=None, ge=0, le=2)


class Table(BaseModel):
    present: bool = True
    x0: float = M; x1: float = M; y0: float = M; y1: float = M
    height: float = Field(ge=0.0, le=2.5)


class Setup(BaseModel):
    table: Optional[Table] = None
    obstacles: list[Obstacle] = Field(default_factory=list, max_length=50)


@router.get("/{robot_key}")
def setups(robot_key: RobotKey, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Newest version of each named setup."""
    rows = db.scalars(select(WorkcellSetup).where(WorkcellSetup.robot_key == robot_key)
                      .order_by(desc(WorkcellSetup.created_at), desc(WorkcellSetup.id))).all()
    seen, out = set(), []
    for r in rows:
        if r.name not in seen:
            seen.add(r.name)
            out.append({"name": r.name, "data": r.data, "saved_at": r.created_at, "version_id": r.id})
    return out


@router.put("/{robot_key}/{name}")
def save(robot_key: RobotKey, name: str, body: Setup, db: Session = Depends(get_db),
         admin: User = Depends(require_admin)):
    name = name.strip()[:64] or "default"
    row = WorkcellSetup(robot_key=robot_key, name=name, data=body.model_dump(), created_by_id=admin.id)
    db.add(row)
    db.add(AuditLog(actor_user_id=admin.id, action="WORKCELL_SAVED", entity_type="workcell",
                    entity_id=f"{robot_key}/{name}", detail={"obstacles": len(body.obstacles)}))
    db.commit()
    return {"name": name, "version_id": row.id}

```
