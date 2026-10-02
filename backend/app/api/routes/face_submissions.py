"""
Face photos sent by the person themselves, approved by staff.

A person whose Face ID is not registered can send 5-10 photos of their face
from the portal (Profile). Nothing is enrolled yet: staff look at the
photos and approve them only if they show the account holder - otherwise
anyone could register someone else's face under their own door identity,
and the face check at the door would mean nothing.

Approve: each photo goes to the face server as a sample (it finds the face
itself and updates the person's template). Reject: with a reason the person
sees. Either way the portal then deletes its copies of the images; only
the record of the decision stays. Every step is audited.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import AuditLog, FaceSubmission, Role, User
from app.services import enrolment
from app.services.notifications import notify, staff_ids
from app.services.storage import ImageRejected, get_storage, new_key, process_image

router = APIRouter(tags=["face submissions"])

MIN_PHOTOS, MAX_PHOTOS = 5, 10
# Fewer usable faces than this and Face ID is not marked as registered.
MIN_SAMPLES_TO_ENROLL = 3


def _staff(u: User) -> bool:
    return u.role in (Role.ADMIN, Role.LAB_STAFF)


def _out(db: Session, s: FaceSubmission) -> dict:
    owner = db.get(User, s.user_id)
    return {"id": s.id, "user_id": s.user_id,
            "user_name": owner.full_name if owner else None,
            "auth_subject": owner.auth_subject if owner else None,
            "status": s.status, "photo_count": s.photo_count,
            "has_photos": bool(s.photo_keys),
            "created_at": s.created_at, "reviewed_at": s.reviewed_at,
            "reason": s.reason, "samples_saved": s.samples_saved,
            "min_samples": MIN_SAMPLES_TO_ENROLL}


def _delete_files(s: FaceSubmission) -> None:
    storage = get_storage()
    for key in (s.photo_keys or []) + (s.thumb_keys or []):
        try:
            if storage.exists(key):
                storage.delete(key)
        except OSError:
            pass
    s.photo_keys, s.thumb_keys = [], []


def _pending(db: Session, user_id: int) -> Optional[FaceSubmission]:
    return db.scalar(select(FaceSubmission).where(
        FaceSubmission.user_id == user_id, FaceSubmission.status == "PENDING"))


# ----------------------------------------------------------- the person ---
@router.post("/auth/me/face-submission", status_code=status.HTTP_201_CREATED)
async def submit_photos(files: list[UploadFile] = File(...),
                        db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    if not user.auth_subject:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "You have no door identity yet - ask lab staff.")
    if user.face_enrolled_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "Your Face ID is already registered.")
    if _pending(db, user.id):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Your photos are already waiting for review.")
    if not MIN_PHOTOS <= len(files) <= MAX_PHOTOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Send between {MIN_PHOTOS} and {MAX_PHOTOS} photos.")
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    raws = [await f.read(limit + 1) for f in files]

    def store() -> tuple[list[str], list[str]]:
        storage, keys, thumbs = get_storage(), [], []
        try:
            for i, raw in enumerate(raws, 1):
                try:
                    img = process_image(raw)     # re-encoded: EXIF/GPS removed
                except ImageRejected as e:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Photo {i}: {e}")
                key, tkey = new_key(f"face-submissions/{user.id}", img.ext)
                storage.put(key, img.data, img.content_type)
                storage.put(tkey, img.thumb, img.content_type)
                keys.append(key)
                thumbs.append(tkey)
        except HTTPException:
            for k in keys + thumbs:
                storage.delete(k)
            raise
        return keys, thumbs

    keys, thumbs = await run_in_threadpool(store)
    s = FaceSubmission(user_id=user.id, status="PENDING", photo_keys=keys,
                       thumb_keys=thumbs, photo_count=len(keys))
    db.add(s)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="FACE_PHOTOS_SUBMITTED",
                    entity_type="face_submission", entity_id=str(s.id),
                    detail={"photos": len(keys)}))
    notify(db, staff_ids(db), "FACE_REVIEW",
           f"Face photos to review - {user.full_name} ({user.auth_subject})",
           body="Check that the photos show this person, then approve or reject "
                "them in Users & roles -> Edit -> Face ID.",
           link="/admin/users", severity="info")
    db.commit()
    return _out(db, s)


@router.get("/auth/me/face-submission")
def my_submission(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.scalar(select(FaceSubmission).where(FaceSubmission.user_id == user.id)
                  .order_by(desc(FaceSubmission.created_at)))
    return _out(db, s) if s else None


@router.post("/auth/me/face-submission/withdraw")
def withdraw(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _pending(db, user.id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nothing waiting for review.")
    _delete_files(s)
    s.status = "WITHDRAWN"
    db.commit()
    return _out(db, s)


# ---------------------------------------------------------------- staff ---
@router.get("/users/{user_id}/face/submission")
def pending_for_user(user_id: int, db: Session = Depends(get_db),
                     _: User = Depends(require_staff)):
    s = _pending(db, user_id)
    return _out(db, s) if s else None


@router.get("/face-submissions/{sid}/photos/{n}")
def submission_photo(sid: int, n: int,
                     variant: str = Query("thumb", pattern="^(full|thumb)$"),
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """The person or staff only; never public - these are photos of a face."""
    s = db.get(FaceSubmission, sid)
    if s is None or not (_staff(user) or s.user_id == user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    keys = s.thumb_keys if variant == "thumb" else s.photo_keys
    if not keys or not 0 <= n < len(keys) or not get_storage().exists(keys[n]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    ext = keys[n].rsplit(".", 1)[-1]
    media = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    return StreamingResponse(get_storage().open(keys[n]), media_type=media,
                             headers={"Cache-Control": "private, no-store",
                                      "X-Content-Type-Options": "nosniff"})


@router.post("/face-submissions/{sid}/approve")
def approve(sid: int, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    s = db.get(FaceSubmission, sid)
    if s is None or s.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, "This submission is not waiting for review.")
    person = db.get(User, s.user_id)
    if person is None or not person.auth_subject:
        raise HTTPException(status.HTTP_409_CONFLICT, "This person has no door identity.")
    storage, saved = get_storage(), 0
    try:
        for key in s.photo_keys or []:
            data = b"".join(storage.open(key))
            r = httpx.post(f"{settings.FACE_SERVER_URL}/enroll",
                           params={"name": person.auth_subject}, content=data,
                           headers={"Content-Type": "image/jpeg"},
                           timeout=httpx.Timeout(20.0, connect=3.0))
            r.raise_for_status()
            saved += r.json().get("status") == "saved"
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"The face server is not reachable at {settings.FACE_SERVER_URL}. "
                            "Nothing was approved; try again when it is running.")
    now = datetime.now(timezone.utc)
    s.status, s.reviewed_by_id, s.reviewed_at, s.samples_saved = "APPROVED", staff.id, now, saved
    _delete_files(s)
    enrolled = saved >= MIN_SAMPLES_TO_ENROLL
    if enrolled:
        enrolment.mark(db, person, "face", True)
    else:
        s.reason = (f"Only {saved} of {s.photo_count} photos had a usable face - "
                    "add samples at the door camera.")
        notify(db, [person.id], "ACCESS_SETUP", "Face photos approved, but too few were usable",
               body=f"Only {saved} of your photos showed a clear face. Visit lab staff "
                    "to add a few more at the door camera.", link="/profile",
               severity="warning")
    db.add(AuditLog(actor_user_id=staff.id, action="FACE_PHOTOS_APPROVED",
                    entity_type="face_submission", entity_id=str(s.id),
                    detail={"user_id": person.id, "photos": s.photo_count,
                            "samples_saved": saved, "face_enrolled": enrolled}))
    db.commit()
    return _out(db, s)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


@router.post("/face-submissions/{sid}/reject")
def reject(sid: int, req: RejectRequest, db: Session = Depends(get_db),
           staff: User = Depends(require_staff)):
    s = db.get(FaceSubmission, sid)
    if s is None or s.status != "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, "This submission is not waiting for review.")
    s.status, s.reviewed_by_id = "REJECTED", staff.id
    s.reviewed_at, s.reason = datetime.now(timezone.utc), req.reason.strip()
    _delete_files(s)
    notify(db, [s.user_id], "ACCESS_SETUP", "Face photos not accepted",
           body=f"{s.reason} You can send new photos from your profile.",
           link="/profile", severity="warning")
    db.add(AuditLog(actor_user_id=staff.id, action="FACE_PHOTOS_REJECTED",
                    entity_type="face_submission", entity_id=str(s.id),
                    detail={"user_id": s.user_id, "reason": s.reason}))
    db.commit()
    return _out(db, s)
