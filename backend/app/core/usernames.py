"""
Usernames (owner, 2026-10-20): sign in with the e-mail OR a username; new accounts choose one in the
form firstname.lastname (ali.abozeid, nour.ramy, ramy.shenouda, ahmed.hemaly); administrators can
give or change anyone's username at any time. Stored lower case; unique; never contains "@" (that is
how sign-in tells the two apart).
"""
from __future__ import annotations

import re
import unicodedata

MAX_LEN = 64
# first.last, optionally more parts (first.middle.last); letters, digits and "-" inside a part
PATTERN = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")
HINT = "Use firstname.lastname - small letters, a dot between the names (for example ali.abozeid)"
TITLES = {"dr", "eng", "engr", "prof", "mr", "mrs", "ms", "miss", "sir"}


def normalize(name: str | None) -> str | None:
    """Lower-case and trim; None / blank -> None. Raises ValueError when the format is wrong."""
    if name is None:
        return None
    n = name.strip().lower()
    if not n:
        return None
    if len(n) > MAX_LEN or not PATTERN.fullmatch(n):
        raise ValueError(HINT)
    return n


def suggest(full_name: str) -> str:
    """firstname.lastname from a full name: titles dropped, accents removed ("Dr. Ramy Amir Shawkey
    Shenouda" -> ramy.shenouda). Only a suggestion - the person / admin types the final one."""
    plain = unicodedata.normalize("NFKD", full_name).encode("ascii", "ignore").decode().lower()
    parts = [p for p in re.split(r"[^a-z0-9]+", plain) if p and p not in TITLES]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}.{parts[-1]}"
