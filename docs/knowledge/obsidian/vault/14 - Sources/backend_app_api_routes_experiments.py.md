---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/api/routes/experiments.py"
source_hash: "e67ed133ec0fc19914f97d2b87247f8cfb76401dc3cbcf876172ee4a1c73bc9f"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/api/routes/experiments.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_models___init__.py]] - imports
- [[backend_app_services___init__.py]] - imports
- [[backend_app_services_provenance.py]] - imports

```py
"""
Thesis experiments (staff): plan one, START it - every new event, reading,
alert, booking, session, ticket and camera event is then stamped with its
data mode and id - record each repeat as a trial, STOP it with the result.

    GET  /experiments                 list, newest first
    POST /experiments                 plan one (code EXP-0001 ...)
    GET  /experiments/{id}            details, trials, and how many records it stamped
    POST /experiments/{id}/start      only one runs at a time (409 otherwise)
    POST /experiments/{id}/trials     one repeat: input, expected, actual, measurement
    POST /experiments/{id}/stop       actual result + PASS / FAIL / PARTIAL / INCONCLUSIVE

Nothing here edits or deletes recorded data; every step is in the audit log.
"""
from __future__ import annotations

from typing import Literal, Optional

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.db.session import get_db
from app.models import (PROVENANCES, AccessEvent, AccessSession, Alert, AuditLog, Booking, Experiment,
                        ExperimentTrial, Issue, SecurityEvent, SensorReading, User, utcnow)
from app.services import provenance

router = APIRouter(prefix="/experiments", tags=["experiments"])
STAMPED = {"access_events": AccessEvent, "sensor_readings": SensorReading, "alerts": Alert,
           "bookings": Booking, "access_sessions": AccessSession, "issues": Issue,
           "security_events": SecurityEvent}
Result = Literal["PASS", "FAIL", "PARTIAL", "INCONCLUSIVE"]


class ExperimentIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    subsystem: str = Field(min_length=1, max_length=32)
    device_id: Optional[int] = None
    firmware_version: Optional[str] = Field(default=None, max_length=64)
    hardware_configuration: str = ""
    configuration: Optional[dict] = None
    environment: str = ""
    network_state: str = ""
    data_mode: Literal["PHYSICAL_TEST", "BENCH_TEST", "SOFTWARE_TEST", "DEMO_DATA"] = "PHYSICAL_TEST"
    test_condition: str = ""
    expected_result: str = ""
    notes: str = ""


class TrialIn(BaseModel):
    repeat_number: int = Field(ge=1)
    input: str = ""
    expected: str = ""
    actual: str = ""
    measurement: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=24)
    result: Optional[Literal["PASS", "FAIL", "NA"]] = None
    notes: str = ""


class StopIn(BaseModel):
    actual_result: str = ""
    result: Optional[Result] = None
    notes: Optional[str] = None


def _out(db: Session, e: Experiment, full: bool = False) -> dict:
    out = {c.name: getattr(e, c.name) for c in Experiment.__table__.columns}
    if full:
        out["trials"] = [{c.name: getattr(t, c.name) for c in ExperimentTrial.__table__.columns}
                         for t in db.scalars(select(ExperimentTrial).where(ExperimentTrial.experiment_id == e.id)
                                             .order_by(ExperimentTrial.repeat_number, ExperimentTrial.id)).all()]
        out["records"] = {name: db.scalar(select(func.count()).select_from(m).where(m.experiment_id == e.id))
                          for name, m in STAMPED.items()}
    return out


def _get(db: Session, exp_id: int) -> Experiment:
    e = db.get(Experiment, exp_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    return e


def _audit(db: Session, user: User, action: str, e: Experiment, **detail):
    db.add(AuditLog(actor_user_id=user.id, action=action, entity_type="experiment",
                    entity_id=str(e.id), detail={"code": e.code, **detail}))


@router.get("")
def list_experiments(lab_id: Optional[int] = None, db: Session = Depends(get_db),
                     _: User = Depends(require_staff)):
    """All experiments, or one lab's: those run on a device of that lab
    (experiments have no lab column; the device says where it ran)."""
    q = select(Experiment).order_by(desc(Experiment.id))
    if lab_id is not None:
        from app.models import Device
        q = q.join(Device, Device.id == Experiment.device_id).where(Device.lab_id == lab_id)
    return [_out(db, e) for e in db.scalars(q).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create(req: ExperimentIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    import uuid
    # The code follows the id, which exists only after the insert: a unique
    # placeholder first, the real code in the same transaction.
    e = Experiment(**req.model_dump(), operator_id=user.id, status="PLANNED", code=f"NEW-{uuid.uuid4().hex[:24]}")
    db.add(e)
    db.flush()
    e.code = f"EXP-{e.id:04d}"
    _audit(db, user, "EXPERIMENT_PLANNED", e, name=e.name, subsystem=e.subsystem)
    db.commit()
    return _out(db, e)


@router.get("/{exp_id}")
def detail(exp_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return _out(db, _get(db, exp_id), full=True)


@router.post("/{exp_id}/start")
def start(exp_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    e = _get(db, exp_id)
    running = db.scalar(select(Experiment).where(Experiment.status == "RUNNING", Experiment.id != e.id))
    if running is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{running.code} is running - stop it first")
    if e.status == "FINISHED":
        raise HTTPException(status.HTTP_409_CONFLICT, "A finished experiment is not restarted - plan a new one")
    e.status, e.started_at = "RUNNING", e.started_at or utcnow()
    provenance.set_setting(db, provenance.ACTIVE_KEY, str(e.id))
    _audit(db, user, "EXPERIMENT_STARTED", e, data_mode=e.data_mode)
    db.commit()
    provenance.invalidate()
    return _out(db, e)


@router.post("/{exp_id}/trials", status_code=status.HTTP_201_CREATED)
def add_trial(exp_id: int, req: TrialIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    e = _get(db, exp_id)
    t = ExperimentTrial(experiment_id=e.id, recorded_by_id=user.id, **req.model_dump())
    db.add(t)
    _audit(db, user, "EXPERIMENT_TRIAL", e, repeat=req.repeat_number, result=req.result)
    db.commit()
    return {c.name: getattr(t, c.name) for c in ExperimentTrial.__table__.columns}


@router.post("/{exp_id}/stop")
def stop(exp_id: int, req: StopIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    e = _get(db, exp_id)
    if e.status != "RUNNING":
        raise HTTPException(status.HTTP_409_CONFLICT, "This experiment is not running")
    e.status, e.ended_at = "FINISHED", utcnow()
    e.actual_result, e.result = req.actual_result, req.result
    if req.notes is not None:
        e.notes = req.notes
    provenance.set_setting(db, provenance.ACTIVE_KEY, "")
    _audit(db, user, "EXPERIMENT_FINISHED", e, result=req.result)
    db.commit()
    provenance.invalidate()
    return _out(db, e)



```
