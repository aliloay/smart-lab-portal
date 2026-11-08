"""
Password rules for every NEW password (sign-up, admin-created account,
password set by staff). Existing passwords keep working; the rule applies
the next time one is set.

Length matters most, so the minimum is 10 characters, plus at least three of
the four kinds (lower, upper, digit, symbol). Common or lab-guessable
passwords and passwords containing the person's own name / email are refused.
"""
from __future__ import annotations

import re
from typing import Optional

MIN_LENGTH = 10
MAX_LENGTH = 128

# Small built-in list: the most used passwords plus obvious lab words. The
# point is to refuse the ones an attacker tries first.
COMMON = {
    "password", "password1", "password123", "passw0rd", "p@ssw0rd", "p@ssword1", "qwerty123",
    "qwertyuiop", "123456789", "1234567890", "12345678910", "iloveyou1", "welcome1", "welcome123",
    "admin123", "administrator", "letmein123", "football1", "baseball1", "abc123456", "trustno1",
    "changeme", "changeme123", "smartlab", "smartlab123", "smartlab2026", "giu12345", "giu2026",
    "robotics", "robotics123", "laboratory", "student123", "university1",
}


def problems(password: str, email: Optional[str] = None, name: Optional[str] = None) -> list[str]:
    """Why this password is not acceptable ([] = fine)."""
    out = []
    if len(password) < MIN_LENGTH:
        out.append(f"at least {MIN_LENGTH} characters")
    if len(password) > MAX_LENGTH:
        out.append(f"at most {MAX_LENGTH} characters")
    kinds = sum(bool(re.search(p, password)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if kinds < 3:
        out.append("at least three of: lowercase, uppercase, a digit, a symbol")
    low = password.lower()
    if low in COMMON or re.sub(r"[^a-z0-9]", "", low) in COMMON:
        out.append("not a common password")
    personal = []
    if email:
        personal.append(email.split("@", 1)[0].lower())
    if name:
        personal += [p.lower() for p in re.split(r"\s+", name) if len(p) >= 4]
    if any(len(p) >= 4 and p in low for p in personal):
        out.append("not your name or email")
    return out


def check(password: str, email: Optional[str] = None, name: Optional[str] = None) -> str:
    """For pydantic validators: raises ValueError with a readable message."""
    bad = problems(password, email, name)
    if bad:
        raise ValueError("Password needs " + "; ".join(bad) + ".")
    return password
