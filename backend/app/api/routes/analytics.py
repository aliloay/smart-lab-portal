"""Aggregates for the Operations Center, the lab digital twin and "my usage"."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_staff
from app.db.session import get_db
from app.models import Lab, User
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/operations")
def operations(days: int = Query(30, ge=1, le=365),
               lab_id: Optional[int] = None,
               db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return analytics.operations(db, days, lab_id)


@router.get("/labs/{lab_id}")
def lab_twin(lab_id: int, db: Session = Depends(get_db),
             _: User = Depends(get_current_user)):
    """Typical week, recent days and environment. No per-person data."""
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(404, "Lab not found")
    return analytics.lab_twin(db, lab)


@router.get("/me")
def me(days: int = Query(90, ge=7, le=365), db: Session = Depends(get_db),
       user: User = Depends(get_current_user)):
    """The caller's own bookings only - never anyone else's."""
    return analytics.my_stats(db, user.id, days)
