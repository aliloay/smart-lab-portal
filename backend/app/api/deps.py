"""
Dependencies: database session, current user, role gates, device auth.

Devices authenticate with a shared API key rather than a user JWT. An ESP32
is not a person: it has no login, cannot refresh a token, and must keep
working across reboots without human interaction.
"""
import hashlib
import hmac
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
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


def require_device(x_device_key: Optional[str] = Header(None),
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
    """
    if not x_device_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device key")
    # Constant-time comparison: the key is not leaked through response timing.
    if settings.DEVICE_SHARED_KEY and hmac.compare_digest(
            x_device_key.encode(), settings.DEVICE_API_KEY.encode()):
        return SHARED
    from app.models import Device
    uid = db.scalar(select(Device.device_uid).where(
        Device.key_hash == hash_device_key(x_device_key)))
    if uid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device key")
    return uid


def device_scope(identity: str, device_uid: Optional[str]) -> None:
    """A device with its own key may only report as itself."""
    if identity != SHARED and identity != device_uid:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This device key belongs to another device")
