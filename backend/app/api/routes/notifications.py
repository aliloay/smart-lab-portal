"""The caller's own notifications. Nobody can read anyone else's."""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Notification, User
from app.schemas import NotificationOut
from app.services.notifications import ensure_booking_reminders

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(unread_only: bool = False,
                       limit: int = Query(50, le=200),
                       db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    ensure_booking_reminders(db, user)
    stmt = (select(Notification).where(Notification.user_id == user.id)
            .order_by(desc(Notification.created_at)).limit(limit))
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return db.scalars(stmt).all()


@router.get("/inbox")
def inbox(tab: Literal["all", "unread", "n8n", "portal", "critical"] = "all",
          kind: Optional[str] = Query(None, max_length=48),
          q: Optional[str] = Query(None, max_length=80),
          offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The Notifications page: one page of the caller's notifications with
    the tab counts and the kinds present, newest first."""
    ensure_booking_reminders(db, user)
    mine = Notification.user_id == user.id
    tabs = {"all": None, "unread": Notification.is_read.is_(False),
            "n8n": Notification.source == "n8n", "portal": Notification.source == "portal",
            "critical": Notification.severity == "critical"}
    counts = {k: db.scalar(select(func.count()).select_from(Notification).where(
        mine, *([] if c is None else [c]))) or 0 for k, c in tabs.items()}
    stmt = select(Notification).where(mine)
    if tabs[tab] is not None:
        stmt = stmt.where(tabs[tab])
    if kind:
        stmt = stmt.where(Notification.kind == kind)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Notification.title.ilike(like) | Notification.body.ilike(like))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(desc(Notification.created_at), desc(Notification.id))
                       .offset(offset).limit(limit)).all()
    kinds = sorted(db.scalars(select(Notification.kind).where(mine).distinct()).all())
    return {"items": [NotificationOut.model_validate(n).model_dump() for n in items],
            "total": total, "counts": counts, "kinds": kinds}


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    ensure_booking_reminders(db, user)
    n = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.is_read.is_(False))) or 0
    return {"unread": n}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(n)
    return n


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    res = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(timezone.utc)))
    db.commit()
    return {"updated": res.rowcount or 0}
