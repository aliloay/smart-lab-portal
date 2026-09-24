"""
Password hashing, JWT issue/verify, and opaque token generation.

Passwords are bcrypt-hashed; plaintext never reaches the database.
QR tokens come from secrets.token_urlsafe - a CSPRNG - because a guessable
token would let someone mint their own access credential.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str | int, role: str,
                        expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY,
                          algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def generate_qr_token() -> str:
    """
    Opaque booking token. The 'SLB:' prefix lets the ESP32 master distinguish
    a portal-issued booking token from a legacy local QR payload without
    needing to ask the backend first.
    """
    return "SLB:" + secrets.token_urlsafe(settings.QR_TOKEN_BYTES)
