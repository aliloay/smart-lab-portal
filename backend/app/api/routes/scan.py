"""
"Scan the lab" - the phone camera in the AI assistant (2026-10-26). Staff only.

  GET  /scan/registry          every asset that can carry a marker (devices, consumables bins, equipment)
  GET  /scan/asset?code=...    the live card of one scanned marker (404 = unidentified)
  GET  /scan/marker.png?code=  the printable QR marker for an asset (exact text = the asset's own key)
  GET  /scan/markers.pdf       all markers (or one kind) on A4 sheets - prints from a phone too
  POST /scan/identify          one phone frame -> the enrolled person on a clear face match (else unnamed)
  POST /scan/people            one phone frame (JPEG) -> person boxes from the lab's camera service detector

Identification is ONLY by marker (app/services/scan.py); the people boxes are a generic class and never carry a
name. No phone frame is stored: it is forwarded once and dropped.
"""
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import Device, DeviceType, User
from app.services import live_target, scan
from app.services.devices import is_fresh

router = APIRouter(prefix="/scan", tags=["scan"])
MAX_FRAME = 400_000                         # a phone frame scaled to <= 640 px wide is ~30-80 KB
_detect = httpx.Client(timeout=httpx.Timeout(2.5, connect=0.5))


@router.get("/registry")
def registry(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return {"prefix": scan.PREFIX, "assets": scan.registry(db)}


@router.get("/asset")
def asset(code: str = Query(min_length=6, max_length=80), db: Session = Depends(get_db),
          user: User = Depends(require_staff)):
    card = scan.asset_card(db, code, staff=True)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a Smart Lab asset marker - shown as unidentified")
    card["live"] = live_target.live_block(db, card, staff=True)
    return card


@router.get("/marker.png")
def marker_png(code: str = Query(min_length=6, max_length=80), qr_only: bool = False,
               style: str = Query("pack", pattern="^(pack|shape)$"), db: Session = Depends(get_db),
               _: User = Depends(require_staff)):
    """The printable marker of a registered asset (exact text = its record key). style=pack (default): the owner's
    marker pack - category motif in recoloured real modules (services/marker_pack.py); style=shape: the object-
    shaped variant (marker_shapes.py). qr_only=1: the code alone. Every marker is decoded back before serving."""
    item = next((i for i in scan.registry(db) if i["code"] == code), None)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown asset")
    if style == "shape":
        from app.services import marker_shapes
        body = marker_shapes.png(item)
    else:
        from app.services import marker_pack
        body = marker_pack.qr_png(code, marker_pack.category(item))[0] if qr_only else marker_pack.card_png(item)
    return Response(body, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/marker.svg")
def marker_svg(code: str = Query(min_length=6, max_length=80), db: Session = Depends(get_db),
               _: User = Depends(require_staff)):
    """Vector QR of a registered asset (responsive previews; the PNG card is for printing)."""
    item = next((i for i in scan.registry(db) if i["code"] == code), None)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown asset")
    from app.services import marker_pack
    cat = marker_pack.category(item)
    return Response(marker_pack.qr_svg(code, cat), media_type="image/svg+xml",
                    headers={"Cache-Control": "private, max-age=3600", "X-Marker-Source": marker_pack.qr_png(code, cat)[1],
                             "X-Marker-Category": cat})


@router.get("/markers.json")
def markers_page(kind: str = Query("all", pattern="^(all|device|bin|asset)$"),
                 style: str = Query("pack", pattern="^(pack|shape)$"), db: Session = Depends(get_db),
                 _: User = Depends(require_staff)):
    """All markers of one kind for the markers page in one response (registry read once, artwork cached)."""
    from app.services import marker_pack
    items = [i for i in scan.registry(db) if kind == "all" or i["kind"] == kind]
    return {"style": style, "markers": marker_pack.page_items(items, style)}


@router.get("/markers.pdf")
def markers_pdf(kind: str = Query("all", pattern="^(all|device|bin|asset)$"),
                style: str = Query("art", pattern="^(art|pack)$"), db: Session = Depends(get_db),
                _: User = Depends(require_staff)):
    """Every marker of one kind on A4 sheets (the pack's 2 x 4 card layout, 300 dpi)."""
    items = [i for i in scan.registry(db) if kind == "all" or i["kind"] == kind]
    if not items:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No assets of this kind")
    from app.services import marker_pack
    return Response(marker_pack.sheet_pdf(items, style=style), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="smartlab_markers_{kind}.pdf"',
                             "Cache-Control": "no-store"})


@router.get("/link.png")
def link_png(url: str = Query(min_length=10, max_length=200, pattern=r"^https://[A-Za-z0-9.:\-]+/[A-Za-z0-9/_\-?=&.]*$"),
             _: User = Depends(require_staff)):
    """QR of a portal address (desktop -> phone handoff). https:// portal paths only - not a general QR maker."""
    from app.services.qr import render_qr_png
    return Response(render_qr_png(url), media_type="image/png", headers={"Cache-Control": "no-store"})


def _vision_url(db: Session) -> str:
    now = datetime.now(timezone.utc)
    cams = db.scalars(select(Device).where(Device.device_type == DeviceType.SECURITY_CAMERA)
                      .order_by(Device.id)).all()
    live = [d for d in cams if is_fresh(d, now)] or cams
    if not live:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No camera service is registered - people boxes are "
                                                                 "unavailable (markers still work)")
    port = int((live[0].component_state or {}).get("port", 5100))
    return f"http://{settings.SECURITY_VISION_HOST}:{port}/detect"


@router.post("/people")
async def people(request: Request, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Person boxes for one phone frame. The camera service answers 429 while it is busy with another phone frame
    (one at a time - the fixed cameras keep priority); the phone then simply sends its NEXT frame."""
    body = await request.body()
    # 2026-10-27 (owner: "it takes a lot of time to detect and to hear the answer"): the blocking calls (camera /
    # face / voice service, database) run on a worker thread - they used to hold the event loop, so every other
    # request, the spoken answer included, queued behind the phone's back-to-back frames.

    def _work():
        if not body.startswith(b"\xff\xd8") or len(body) > MAX_FRAME:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Expected one JPEG frame under 400 KB")
        url = _vision_url(db)
        t0 = time.perf_counter()
        try:
            r = _detect.post(url, content=body, headers={"X-Device-Key": settings.DEVICE_API_KEY,
                                                         "Content-Type": "image/jpeg"})
        except httpx.HTTPError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The camera service is not reachable - people "
                                                                     "boxes are unavailable (markers still work)")
        if r.status_code == 429:
            return Response(status_code=status.HTTP_429_TOO_MANY_REQUESTS, headers={"Retry-After": "0"})
        if r.status_code != 200:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The camera service could not detect on this frame")
        out = r.json()
        out["proxy_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    return await run_in_threadpool(_work)


# ------------------------------------------------------------------ who is this (face) - 2026-10-27 ---
# Owner: "why does it say person and not USER1 Ali Loay - my face is enrolled". The phone frame goes to the lab's
# own face server (/identify: the door's SFace templates, nothing logged there) and is named only on a CLEAR match:
# the same rule as the fixed security cameras - score >= FACE_MIN and ahead of the next person by FACE_MARGIN.
# Anything less stays "person". Staff only; every identification is written to the audit log; no frame is stored.
FACE_MIN, FACE_MARGIN = 0.50, 0.08
_face = httpx.Client(timeout=httpx.Timeout(3.0, connect=0.5))


@router.post("/identify")
async def identify(request: Request, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    body = await request.body()
    # 2026-10-27 (owner: "it takes a lot of time to detect and to hear the answer"): the blocking calls (camera /
    # face / voice service, database) run on a worker thread - they used to hold the event loop, so every other
    # request, the spoken answer included, queued behind the phone's back-to-back frames.

    def _work():
        if not body.startswith(b"\xff\xd8") or len(body) > MAX_FRAME:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Expected one JPEG frame under 400 KB")
        t0 = time.perf_counter()
        try:
            r = _face.post(settings.FACE_SERVER_URL.rstrip("/") + "/identify", content=body,
                           headers={"X-Device-Key": settings.DEVICE_API_KEY, "Content-Type": "image/jpeg"})
        except httpx.HTTPError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The face server is not reachable - people stay "
                                                                     "unnamed")
        if r.status_code in (409, 429, 503):
            return Response(status_code=status.HTTP_429_TOO_MANY_REQUESTS, headers={"Retry-After": "1"})
        if r.status_code != 200:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The face server could not check this frame")
        res = r.json()
        name, score, second = res.get("name"), res.get("score"), res.get("second")
        out = {"face": bool(res.get("face")), "score": score, "second": second, "known": False,
               "ms": round((time.perf_counter() - t0) * 1000, 1)}
        clear = bool(name) and score is not None and score >= FACE_MIN and (second is None or score - second >= FACE_MARGIN)
        if not clear:
            out["reason"] = ("no face in the picture" if not res.get("face") else
                             "no clear match - stays unnamed" if name or score else "not an enrolled person")
            return out
        from app.models import AuditLog
        person = db.scalar(select(User).where(User.auth_subject == name))
        if person is None or not person.is_active:
            out["reason"] = f"face label {name} has no active portal account"
            return out
        db.add(AuditLog(actor_user_id=user.id, action="PHONE_FACE_IDENTIFIED", entity_type="user",
                        entity_id=str(person.id), detail={"score": score, "second": second}))
        db.commit()
        now_s = int(time.time())
        # approved overlay fields only (masked student id); the ticket lets a voice question about "this person"
        # be answered for the next TICKET_S seconds without the phone ever naming a user id itself
        out.update(known=True, person=live_target.person_card(db, person.id, score, now_s),
                   ticket=live_target.person_ticket(person.id, score, now_s))
        return out

    return await run_in_threadpool(_work)


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    code: Optional[str] = Field(default=None, max_length=80)      # the selected/visible marker target
    ticket: Optional[str] = Field(default=None, max_length=300)   # a face-match ticket from /scan/identify
    history: list[dict] = Field(default_factory=list, max_length=8)


@router.post("/ask")
def ask(req: AskIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """One target-aware question from the live camera (typed or spoken). The target is resolved on the server
    from the marker code / face ticket; intents with live data are answered exactly and instantly; anything
    else goes to the local model with that live data as explicit context."""
    from app.models import AuditLog
    t0 = time.perf_counter()
    card = None
    if req.code:
        card = scan.asset_card(db, req.code, staff=True)
        if card is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown marker - the target is unidentified")
        card["live"] = live_target.live_block(db, card, staff=True)
    person = None
    if req.ticket:
        t = live_target.person_from_ticket(req.ticket)
        if t is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "The face match expired - point the camera at the face again")
        person = live_target.person_card(db, t["u"], t["s"], t["t"])
    out = live_target.answer(db, user, req.question, card, person)
    if out is None:
        from app.api.routes.ai import _knowledge_lookup, _run
        hist = [{"role": "user", "content": live_target.context_text(card, person)},
                {"role": "assistant", "content": "Understood - I will answer from that live data only."}]
        hist += [h for h in req.history if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str)][-4:]
        out = _knowledge_lookup(db, user, req.question) or _run(db, user, req.question, hist)
        out = {**out, "deterministic": False, "intent": "model",
               "target": {"code": card["code"], "name": card["name"]} if card else None}
    else:
        db.add(AuditLog(actor_user_id=user.id, action="SCAN_ASK", entity_type="scan",
                        entity_id=(card or {}).get("code") or ("person" if person else "none"),
                        detail={"question": req.question[:300], "intent": out["intent"]}))
        db.commit()
    out["live"] = card.get("live") if card else None
    out["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out
    inside = db.scalar(select(AccessSession).where(AccessSession.user_id == person.id,
                                                   AccessSession.ended_at.is_(None))) is not None
    db.add(AuditLog(actor_user_id=user.id, action="PHONE_FACE_IDENTIFIED", entity_type="user",
                    entity_id=str(person.id), detail={"score": score, "second": second}))
    db.commit()
    out.update(known=True, person={"name": person.full_name, "auth_subject": person.auth_subject,
                                   "role": person.role.value, "department": person.department,
                                   "student_id": person.student_id, "inside_by_door": inside})
    return out


# ------------------------------------------------------------------ enclosure appearance (hint only) - 2026-10-27 ---
@router.get("/appearance/refs")
def appearance_refs(_: User = Depends(require_staff)):
    """Which registered enclosures have reference photos yet (data/asset_refs/manifest.json)."""
    from app.services import appearance
    m = appearance.matcher()
    return {"assets": m.status(), "min_inliers": appearance.MIN_INLIERS, "margin": appearance.MARGIN}


@router.post("/appearance")
async def appearance_match(request: Request, _: User = Depends(require_staff)):
    """One phone frame -> which enclosure it LOOKS like (PROBABLE / AMBIGUOUS / UNKNOWN). A hint only: identity and
    live data still come from the asset's QR marker. Run on request, not per frame; nothing is stored."""
    body = await request.body()
    # 2026-10-27 (owner: "it takes a lot of time to detect and to hear the answer"): the blocking calls (camera /
    # face / voice service, database) run on a worker thread - they used to hold the event loop, so every other
    # request, the spoken answer included, queued behind the phone's back-to-back frames.

    def _work():
        if not body.startswith(b"\xff\xd8") or len(body) > MAX_FRAME:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Expected one JPEG frame under 400 KB")
        import cv2
        import numpy as np
        img = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Not a decodable JPEG")
        from app.services import appearance
        m = appearance.matcher()
        if not any(r.views for r in m.refs):
            return {"decision": "UNKNOWN", "best": None, "candidates": [], "note": "no reference photos yet - scan the marker"}
        return m.match(img)

    return await run_in_threadpool(_work)
