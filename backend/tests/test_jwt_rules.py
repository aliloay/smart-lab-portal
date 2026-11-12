"""JWT rules after the python-jose -> PyJWT swap (2026-11-12): HS256 only, signature, expiry, no 'none' algorithm."""
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token


def test_a_fresh_token_round_trips():
    t = create_access_token("42", role="ADMIN")
    p = decode_access_token(t)
    assert p["sub"] == "42" and p["role"] == "ADMIN" and jwt.get_unverified_header(t)["alg"] == "HS256"


def test_wrong_key_expired_none_and_other_algorithms_are_rejected():
    now = datetime.now(timezone.utc)
    base = {"sub": "1", "role": "ADMIN", "iat": now, "exp": now + timedelta(minutes=5)}
    assert decode_access_token(jwt.encode(base, "not-the-key", algorithm="HS256")) is None
    assert decode_access_token(jwt.encode({**base, "exp": now - timedelta(seconds=5)},
                                          settings.SECRET_KEY, algorithm="HS256")) is None
    assert decode_access_token(jwt.encode(base, settings.SECRET_KEY, algorithm="HS512")) is None
    unsigned = jwt.encode(base, key=None, algorithm="none") if hasattr(jwt, "encode") else None
    assert decode_access_token(unsigned) is None
    assert decode_access_token("garbage.token.value") is None
