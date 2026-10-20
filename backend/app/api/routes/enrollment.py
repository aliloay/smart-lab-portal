"""
Face enrollment from the portal: Users & roles -> Edit user -> Face ID.

Staff stand the person in front of the door camera and capture samples
here instead of on the camera's own page. The portal only relays: the
camera takes the frame, the face server keeps the samples and the photo,
and the portal stores no biometric - only the fact and the time that a face
was enrolled, as before. The door logic is untouched.

Finishing retrains the face server (so the new person is recognised at once)
and marks Face ID as registered, which clears the person's "visit lab staff"
reminder and notifies them.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import AuditLog, User
from app.services import enrolment
from app.services.storage import ImageRejected, process_image

router = APIRouter(tags=["enrollment"])

# One kept-alive connection pool to the face server (same pattern as the camera frames in
# security.py). Measured 2026-10-18 from the backend container: a new connection per call cost
# 38 ms (preview) / 51 ms (/users) against 8 / 10 ms reused - and the Face ID panel calls it every
# 0.4-0.5 s. Per-request timeouts below are unchanged. The ESP32-CAM itself keeps one-off calls.
_face = httpx.Client(limits=httpx.Limits(max_connections=10, max_keepalive_connections=4))

# Enough variety (angle, expression, distance) for a reliable match; fewer
# is refused at "finish", more is welcome.
TARGET_SAMPLES = 20
MIN_SAMPLES = 8


def _person(db: Session, user_id: int) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not u.auth_subject:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Give this person a door identity (USERn) first, then save.")
    return u


def _unreachable(what: str, url: str) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                         f"The {what} is not reachable at {url}. "
                         "Is it on, and on the lab Wi-Fi?")


def _face_server_users() -> tuple[dict, list]:
    """(samples per USERn, names that have a grant-screen photo); raises 503."""
    try:
        r = _face.get(f"{settings.FACE_SERVER_URL}/users", timeout=4.0)
        r.raise_for_status()
        body = r.json()
    except (httpx.HTTPError, ValueError):
        raise _unreachable("face server", settings.FACE_SERVER_URL)
    return body.get("users", {}), body.get("portraits", [])


@router.get("/enrollment/camera/snapshot")
def camera_snapshot(_: User = Depends(require_staff)):
    """One frame from the door camera, for the live preview while enrolling. First the frame the
    camera already sent to the face server (no extra work for the camera, which is also busy with
    the door); the camera's own /snapshot only when the face server has no fresh frame."""
    try:
        r = _face.get(f"{settings.FACE_SERVER_URL}/preview.jpg", timeout=httpx.Timeout(2.0, connect=1.0))
        if r.status_code == 200 and r.content:
            return Response(r.content, media_type="image/jpeg",
                            headers={"Cache-Control": "no-store", "X-Frame-Source": "face-server"})
    except httpx.HTTPError:
        pass
    try:
        r = httpx.get(f"{settings.CAMERA_URL}/snapshot",
                      timeout=httpx.Timeout(5.0, connect=2.5))
    except httpx.HTTPError:
        raise _unreachable("door camera", settings.CAMERA_URL)
    if r.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The camera returned no frame")
    return Response(r.content, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@router.get("/users/{user_id}/face")
def face_status(user_id: int, db: Session = Depends(get_db),
                _: User = Depends(require_staff)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    out = {"auth_subject": u.auth_subject, "face_enrolled_at": u.face_enrolled_at,
           "samples": 0, "has_photo": False, "face_server_online": False,
           "camera_page_url": settings.CAMERA_URL,
           "target_samples": TARGET_SAMPLES, "min_samples": MIN_SAMPLES}
    if u.auth_subject:
        try:
            users, portraits = _face_server_users()
        except HTTPException:
            return out
        out.update(samples=int(users.get(u.auth_subject, 0)),
                   has_photo=u.auth_subject in portraits, face_server_online=True)
    return out


@router.post("/users/{user_id}/face/capture")
def face_capture(user_id: int, db: Session = Depends(get_db),
                 _: User = Depends(require_staff)):
    """The camera takes one frame and hands it to the face server as a sample."""
    u = _person(db, user_id)
    try:
        r = httpx.get(f"{settings.CAMERA_URL}/enroll", params={"name": u.auth_subject},
                      timeout=httpx.Timeout(12.0, connect=2.5))
        body = r.json()
    except (httpx.HTTPError, ValueError):
        raise _unreachable("door camera", settings.CAMERA_URL)
    if "error" in body:
        # The camera answered but could not capture or reach the face server.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            f"Capture failed ({body['error']}). Is the face server running?")
    saved = body.get("status") == "saved"
    return {"saved": saved, "samples": body.get("samples"),
            "message": "Sample saved" if saved else
                       f"Not saved: {body['reason']}" if body.get("reason") else
                       "No face found - look straight at the camera and try again"}


def _auto(method: str, params: dict | None = None) -> dict:
    """Relay to the face server's automatic enrolment (device key: it stores pictures of people)."""
    try:
        r = _face.request(method, f"{settings.FACE_SERVER_URL}/enroll/auto", params=params,
                          headers={"X-Device-Key": settings.DEVICE_API_KEY},
                          timeout=httpx.Timeout(5.0, connect=2.0))
        body = r.json()
    except (httpx.HTTPError, ValueError):
        raise _unreachable("face server", settings.FACE_SERVER_URL)
    if r.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, body.get("error") or "Face server refused")
    return body


@router.post("/users/{user_id}/face/auto")
def face_auto_start(user_id: int, target: int = TARGET_SAMPLES, db: Session = Depends(get_db),
                    _: User = Depends(require_staff)):
    """Start automatic capture: the face server keeps every steady, sharp, new-looking frame of
    this person from the door camera's normal stream until `target` samples are saved."""
    u = _person(db, user_id)
    return _auto("POST", {"name": u.auth_subject, "target": max(1, min(40, target))})


@router.get("/users/{user_id}/face/auto")
def face_auto_status(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    u = _person(db, user_id)
    st = _auto("GET")
    if st.get("name") != u.auth_subject:          # a session for someone else: not this person's
        return {"active": False}
    return st


@router.delete("/users/{user_id}/face/auto")
def face_auto_stop(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    u = _person(db, user_id)
    st = _auto("GET")
    if st.get("name") == u.auth_subject and st.get("active"):
        st = _auto("DELETE")
    return st


@router.post("/users/{user_id}/face/reset")
def face_reset(user_id: int, db: Session = Depends(get_db),
               staff: User = Depends(require_staff)):
    """Stop using this person's saved face samples (bad / few photos): the
    face server moves them to its archive (kept, not deleted). Capture new
    ones, then Finish."""
    u = _person(db, user_id)
    try:
        r = _face.post(f"{settings.FACE_SERVER_URL}/reset", params={"name": u.auth_subject},
                       headers={"X-Device-Key": settings.DEVICE_API_KEY},
                       timeout=httpx.Timeout(30.0, connect=3.0))
        r.raise_for_status()
        body = r.json()
    except (httpx.HTTPError, ValueError):
        raise _unreachable("face server", settings.FACE_SERVER_URL)
    enrolment.mark(db, u, "face", False)
    db.add(AuditLog(actor_user_id=staff.id, action="FACE_SAMPLES_RESET",
                    entity_type="user", entity_id=str(u.id),
                    detail={"auth_subject": u.auth_subject, "archived_to": body.get("archived_to")}))
    db.commit()
    return {"reset": True, "archived_to": body.get("archived_to")}


@router.post("/users/{user_id}/face/finish")
def face_finish(user_id: int, db: Session = Depends(get_db),
                staff: User = Depends(require_staff)):
    """Retrain the face server with the new samples and mark Face ID done."""
    u = _person(db, user_id)
    users, portraits = _face_server_users()
    samples = int(users.get(u.auth_subject, 0))
    if samples < MIN_SAMPLES:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Only {samples} samples so far - capture at least {MIN_SAMPLES}.")
    try:
        r = _face.post(f"{settings.FACE_SERVER_URL}/train",
                       timeout=httpx.Timeout(120.0, connect=3.0))
        r.raise_for_status()
    except httpx.HTTPError:
        raise _unreachable("face server", settings.FACE_SERVER_URL)
    enrolment.mark(db, u, "face", True)
    db.add(AuditLog(actor_user_id=staff.id, action="FACE_ENROLLED",
                    entity_type="user", entity_id=str(u.id),
                    detail={"auth_subject": u.auth_subject, "samples": samples,
                            "photo": u.auth_subject in portraits}))
    db.commit()
    return {"trained": True, "samples": samples,
            "has_photo": u.auth_subject in portraits,
            "face_enrolled_at": u.face_enrolled_at}


# Photos staff upload for a person (e.g. taken with a phone). They go straight
# to the face server as samples - it finds the face in each - and the portal
# keeps none of them. Staff are the ones vouching that the photos show this
# person, as when they approve photos the person sent themselves.
MAX_UPLOAD_PHOTOS = 20
MIN_UPLOAD_SAMPLES = 3


@router.post("/users/{user_id}/face/upload")
async def face_upload(user_id: int, files: list[UploadFile] = File(...),
                      db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    u = _person(db, user_id)
    if not 1 <= len(files) <= MAX_UPLOAD_PHOTOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Choose between 1 and {MAX_UPLOAD_PHOTOS} photos.")
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    raws = [await f.read(limit + 1) for f in files]

    def send() -> int:
        saved = 0
        for i, raw in enumerate(raws, 1):
            try:
                img = process_image(raw)        # upright from EXIF, metadata removed
            except ImageRejected as e:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Photo {i}: {e}")
            try:
                r = _face.post(f"{settings.FACE_SERVER_URL}/enroll",
                               params={"name": u.auth_subject}, content=img.data,
                               headers={"Content-Type": img.content_type},
                               timeout=httpx.Timeout(20.0, connect=3.0))
                r.raise_for_status()
                saved += r.json().get("status") == "saved"
            except (httpx.HTTPError, ValueError):
                raise _unreachable("face server", settings.FACE_SERVER_URL)
        if saved:
            try:                                # LBPH needs it; SFace refreshes templates
                _face.post(f"{settings.FACE_SERVER_URL}/train",
                           timeout=httpx.Timeout(120.0, connect=3.0)).raise_for_status()
            except httpx.HTTPError:
                raise _unreachable("face server", settings.FACE_SERVER_URL)
        return saved

    saved = await run_in_threadpool(send)
    users, portraits = await run_in_threadpool(_face_server_users)
    samples = int(users.get(u.auth_subject, 0))
    enrolled = saved >= MIN_UPLOAD_SAMPLES or (saved > 0 and samples >= MIN_SAMPLES)
    if enrolled:
        enrolment.mark(db, u, "face", True)
    db.add(AuditLog(actor_user_id=staff.id, action="FACE_PHOTOS_UPLOADED",
                    entity_type="user", entity_id=str(u.id),
                    detail={"auth_subject": u.auth_subject, "photos": len(raws),
                            "samples_saved": saved, "face_enrolled": enrolled}))
    db.commit()
    skipped = len(raws) - saved
    message = (f"{saved} of {len(raws)} photos added as face samples ({samples} in total)."
               + (f" {skipped} had no clear face." if skipped else "")
               + (" Face ID is registered." if enrolled else
                  f" Add at least {MIN_UPLOAD_SAMPLES} clear photos to register Face ID."))
    return {"sent": len(raws), "saved": saved, "samples": samples,
            "face_enrolled": enrolled, "has_photo": u.auth_subject in portraits,
            "message": message}
