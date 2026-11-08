"""
Dependencies: database session, current user, role gates, device auth.

Devices authenticate with a shared API key rather than a user JWT. An ESP32
is not a person: it has no login, cannot refresh a token, and must keep
working across reboots without human interaction.
"""
import hashlib
import hmac
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Not authenticated")
    payload = decode_access_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not active")
    return user


def require_roles(*roles: Role):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Insufficient permissions")
        return user
    return _dep


require_admin = require_roles(Role.ADMIN)
require_staff = require_roles(Role.ADMIN, Role.LAB_STAFF)


SHARED = "*"


def hash_device_key(key: str) -> str:
    """Device keys are long random tokens, so a plain SHA-256 is enough to
    store them without keeping the key itself."""
    return hashlib.sha256(key.encode()).hexdigest()


def pc_enroll_code() -> str:
    """What the flash-drive kit carries instead of DEVICE_API_KEY (2026-11-04, Gemini + Claude audit P0-A). It can do
    one thing: register a lab PC and get that PC's own key. Derived one-way, so the door boards' key cannot be
    recovered from it. It changes if DEVICE_API_KEY is ever rotated, so a rotation also needs a new kit."""
    return hmac.new(settings.DEVICE_API_KEY.encode(), b"smartlab-pc-enroll-v1", hashlib.sha256).hexdigest()


def require_device(request: Request, x_device_key: Optional[str] = Header(None),
                   db: Session = Depends(get_db)) -> str:
    """
    Guards every endpoint the hardware calls. Without it, anything on the LAN
    could post ACCESS_GRANTED events or fake sensor readings - it still could
    not open the door, because the backend never drives the relay, but a
    trustworthy log is the whole point of the portal.

    Two kinds of key:
      * the shared DEVICE_API_KEY (what the door boards use) -> returns "*";
      * a device's own key (issued on Devices) -> returns that device_uid,
        and device_scope() then lets it report only as itself.
    DEVICE_SHARED_KEY=false refuses the shared key once every device has its own.
    A lab PC's own key opens the PC endpoints (/api/equipment/...) and nothing else: anyone signed in to a lab
    PC can read that file, and it must not reach door, sensor, robot or inventory reports.
    """
    if not x_device_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device key")
    # Constant-time comparison: the key is not leaked through response timing.
    if settings.DEVICE_SHARED_KEY and hmac.compare_digest(
            x_device_key.encode(), settings.DEVICE_API_KEY.encode()):
        return SHARED
    from app.models import Device, DeviceType
    from app.models import PcAccountKey
    hashed = hash_device_key(x_device_key)
    row = db.execute(select(Device.device_uid, Device.device_type).where(Device.key_hash == hashed)).first()
    if row is None:
        row = db.execute(select(Device.device_uid, Device.device_type).join(
            PcAccountKey, PcAccountKey.device_id == Device.id).where(PcAccountKey.key_hash == hashed)).first()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device key")
    if row.device_type == DeviceType.PC and not request.url.path.startswith("/api/equipment/"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A lab PC's key only works for the PC endpoints")
    return row.device_uid


def device_scope(identity: str, device_uid: Optional[str]) -> None:
    """A device with its own key may only report as itself."""
    if identity != SHARED and identity != device_uid:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This device key belongs to another device")
