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


def issue_token() -> str:
    """A fresh random token whose QR the door's decoder is known to read."""
    token = generate_qr_token()
    for _ in range(MAX_ATTEMPTS):
        if door_can_read(token) is not False:
            return token
        token = generate_qr_token()
    # 0.66% ** 10 - effectively never; still issue rather than fail a booking.
    log.warning("issued a QR token the door decoder could not verify")
    return token
