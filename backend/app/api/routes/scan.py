"""
"Scan the lab" - the phone camera in the AI assistant (2026-10-26). Staff only.

  GET  /scan/registry          every asset that can carry a marker (devices, consumables bins, equipment)
  GET  /scan/asset?code=...    the live card of one scanned marker (404 = unidentified)
  GET  /scan/marker.png?code=  the printable QR marker for an asset (exact text = the asset's own key)
  POST /scan/people            one phone frame (JPEG) -> person boxes from the lab's camera service detector

Identification is ONLY by marker (app/services/scan.py); the people boxes are a generic class and never carry a
name. No phone frame is stored: it is forwarded once and dropped.
"""
import io
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.core.config import settings
from app.db.session import get_db
from app.models import Device, DeviceType, User
from app.services import scan
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
    return card


@router.get("/marker.png")
def marker_png(code: str = Query(min_length=6, max_length=80), db: Session = Depends(get_db),
               _: User = Depends(require_staff)):
    card = scan.asset_card(db, code, staff=True)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown asset")
    import qrcode
    from qrcode.constants import ERROR_CORRECT_Q
    from PIL import Image, ImageDraw
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_Q, box_size=10, border=4)
    qr.add_data(code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    w, h = img.size
    sheet = Image.new("RGB", (w, h + 70), "white")
    sheet.paste(img, (0, 0))
    d = ImageDraw.Draw(sheet)
    d.text((w // 2, h + 10), card["name"][:40], fill="black", anchor="mt")
    d.text((w // 2, h + 38), code[:48], fill="black", anchor="mt")
    buf = io.BytesIO()
    sheet.save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


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
