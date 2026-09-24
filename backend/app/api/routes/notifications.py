"""The caller's own notifications. Nobody can read anyone else's."""
from datetime import datetime, timezone

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
