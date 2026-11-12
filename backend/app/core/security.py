"""
Password hashing, JWT issue/verify, and opaque token generation.

New passwords are hashed with Argon2id; older bcrypt hashes still verify and
are re-hashed to Argon2id at the next successful sign-in (verify_and_upgrade).
Plaintext never reaches the database or the logs.
QR tokens come from secrets.token_urlsafe - a CSPRNG - because a guessable
token would let someone mint their own access credential.
"""
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt  # PyJWT (2026-11-12: replaces python-jose, which pulled in the unfixed ecdsa package)
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# Used when there is no such user, so a wrong email costs the same time as a
# wrong password (no account enumeration by timing).
_DUMMY_HASH = pwd_context.hash("not-a-real-password-0")


# Sign-in bursts (2026-10-26): every Argon2 hash takes 64 MB and 4 threads (~100 ms). 20 sign-ins at once ran 80
# hashing threads side by side and starved every other request. Hashes now queue for a few slots (cores / 6 = 2 on
# the 12-thread lab laptop): same strength, same total work. Measured (copy backend, 20 sign-ins at once, 3 rounds):
# unlimited -> 2 slots: sign-in p50 1.58 -> 0.94 s, max 1.74 -> 1.44 s; /monitor during it p50 317 -> 156 ms,
# max 1167 -> 331 ms. PASSWORD_HASH_SLOTS overrides.
_HASH_SLOTS = threading.BoundedSemaphore(int(os.environ.get("PASSWORD_HASH_SLOTS", "0") or 0)
                                         or max(1, (os.cpu_count() or 6) // 6))


def hash_password(plain: str) -> str:
    with _HASH_SLOTS:
        return pwd_context.hash(plain)


def verify_password(plain: str, hashed: Optional[str]) -> bool:
    with _HASH_SLOTS:
        if not hashed:
            pwd_context.verify(plain, _DUMMY_HASH)
            return False
        return pwd_context.verify(plain, hashed)


def verify_and_upgrade(plain: str, hashed: Optional[str]) -> tuple[bool, Optional[str]]:
    """(ok, new_hash): new_hash is set when an old-scheme hash should be replaced."""
    with _HASH_SLOTS:
        if not hashed:
            pwd_context.verify(plain, _DUMMY_HASH)
            return False, None
        return pwd_context.verify_and_update(plain, hashed)


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
