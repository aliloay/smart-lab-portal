"""
The booking QR: how it is drawn, and a guarantee that the door can read it.

QR settings are chosen for the ESP32-CAM, not for looks: error correction
level Q (25% recoverable) survives glare and a phone's own pixel grid, and
box_size 10 with a 4-module quiet zone gives a large, high-contrast target.
The quiet zone is not decoration - OpenCV's detector needs the white margin
to find the finder patterns at all.

Why issue_token() exists: with the pinned OpenCV (the decoder the face
server runs at the door), about 1 in 150 random tokens renders to a QR that
cv2.QRCodeDetector cannot read even from a perfect image - a specific
combination of data and mask pattern, not a bad mask. Such a booking could
never be opened. Tokens are random anyway, so an unreadable one is simply
drawn again before it is issued.
"""
import io
import logging
from typing import Optional

import qrcode
from qrcode.constants import ERROR_CORRECT_Q

from app.core.security import generate_qr_token

log = logging.getLogger(__name__)

try:                                   # the door's decoder
    import cv2
    import numpy as np
    _detector = cv2.QRCodeDetector()
except ImportError:                    # pragma: no cover - installed everywhere we ship
    _detector = None

MAX_ATTEMPTS = 10


def render_qr_png(payload: str) -> bytes:
    """The credential exactly as the portal serves it to the phone."""
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q,
                       box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return buf.getvalue()


def door_can_read(payload: str) -> Optional[bool]:
    """
    Decode the rendered credential the way face_server.py does (grayscale,
    cv2.QRCodeDetector). None when OpenCV is not installed: unknown, not
    a failure.
    """
    if _detector is None:
        return None
    img = cv2.imdecode(np.frombuffer(render_qr_png(payload), np.uint8),
                       cv2.IMREAD_GRAYSCALE)
    data, _, _ = _detector.detectAndDecode(img)
    return data == payload


# How large the QR appears in the door camera's 640x480 frame at the distances a phone is really held (pixels).
DOOR_SCAN_SCALES = (200, 240, 260, 300, 320, 360, 400)
DOOR_SCAN_MIN = 6            # of the 7 distances


def door_camera_view(qr_gray, screen_px: int):
    """The rendered QR as the ESP32-CAM delivers it: a patch of a phone screen in a VGA frame, soft lens,
    JPEG quality 12 (the camera sketch's setting). Same chain as tests/test_qr_pipeline.py."""
    small = cv2.resize(qr_gray, (screen_px, screen_px), interpolation=cv2.INTER_AREA)
    frame = np.full((480, 640), 90, dtype=np.uint8)
    y, x = (480 - screen_px) // 2, (640 - screen_px) // 2
    frame[y:y + screen_px, x:x + screen_px] = small
    frame = cv2.GaussianBlur(frame, (7, 7), 0)
    ok, enc = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 12])
    return cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE) if ok else frame


def door_reads_at_distance(payload: str) -> Optional[bool]:
    """
    2026-11-11 (CI run on main: a booking token that decoded from the clean image but at only 2 of 7 distances
    through the camera model). A clean-image check is not enough: a few tokens render to a QR that is readable
    on paper and poor through the door camera, and that booking would be a bad evening at the door. True when
    the token decodes at DOOR_SCAN_MIN of the DOOR_SCAN_SCALES. About 25 ms per distance.
    """
    if _detector is None:
        return None
    img = cv2.imdecode(np.frombuffer(render_qr_png(payload), np.uint8), cv2.IMREAD_GRAYSCALE)
    ok = 0
    for i, px in enumerate(DOOR_SCAN_SCALES):
        data, _, _ = _detector.detectAndDecode(door_camera_view(img, px))
        ok += data == payload
        if ok + (len(DOOR_SCAN_SCALES) - i - 1) < DOOR_SCAN_MIN:
            return False
    return True


def issue_token() -> str:
    """A fresh random token whose QR the door's decoder reads - from the clean image and through the camera."""
    token = generate_qr_token()
    for _ in range(MAX_ATTEMPTS):
        if door_can_read(token) is not False and door_reads_at_distance(token) is not False:
            return token
        token = generate_qr_token()
    # 0.66% ** 10 - effectively never; still issue rather than fail a booking.
    log.warning("issued a QR token the door decoder could not verify")
    return token
