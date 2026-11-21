"""Status labels. A historical value is never reported as current and UNKNOWN is never ONLINE."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

ONLINE, OFFLINE, STALE, UNKNOWN = "ONLINE", "OFFLINE", "STALE", "UNKNOWN"
NOT_CONFIGURED, NOT_ACCESSIBLE = "NOT_CONFIGURED", "NOT_ACCESSIBLE"
LABELS = (ONLINE, OFFLINE, STALE, UNKNOWN, NOT_CONFIGURED, NOT_ACCESSIBLE)


def parse_time(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def age_seconds(last_seen, now: Optional[datetime] = None) -> Optional[float]:
    dt = parse_time(last_seen)
    if dt is None:
        return None
    return max(0.0, ((now or datetime.now(timezone.utc)) - dt).total_seconds())


def device_status(is_online, last_seen, stale_after_s: int, now: Optional[datetime] = None) -> str:
    """ONLINE only when the portal says online AND the last report is recent."""
    age = age_seconds(last_seen, now)
    if age is None:
        return UNKNOWN if is_online is None or is_online else OFFLINE
    if is_online is False:
        return OFFLINE
    if is_online is None:
        return UNKNOWN
    return STALE if age > stale_after_s else ONLINE


def human_age(sec: Optional[float]) -> str:
    if sec is None:
        return "never"
    sec = int(sec)
    if sec < 90:
        return f"{sec}s ago"
    if sec < 5400:
        return f"{sec // 60}m ago"
    if sec < 172800:
        return f"{sec // 3600}h ago"
    return f"{sec // 86400}d ago"
