"""
Emergency controls: the password, the short emergency session, lab states.

The Emergency tab is for administrators only and opens only with the
emergency password (EMERGENCY_PASSWORD in .env, or the bcrypt hash stored
once it is changed from the portal). A correct password gives a short
emergency session (EMERGENCY_SESSION_MINUTES); every action needs both the
admin login and that session, and is audited. Wrong passwords are counted:
after MAX_FAILURES in FAILURE_WINDOW the tab stays closed for a while.

The emergency session token deliberately has no "sub" claim, so it can never
be used as a login token.
"""
from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models import AuditLog, LabEmergency, SystemSetting

PASSWORD_KEY = "emergency_password_hash"
MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=15)
DOOR_MODES = ("NORMAL", "UNLOCKED", "LOCKDOWN")


def _utc(dt):
    return None if dt is None else dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None \
        else dt.astimezone(timezone.utc)


# ------------------------------------------------------------- password ---
def password_configured(db: Session) -> bool:
    return db.get(SystemSetting, PASSWORD_KEY) is not None or bool(settings.EMERGENCY_PASSWORD)


def check_password(db: Session, password: str) -> bool:
    row = db.get(SystemSetting, PASSWORD_KEY)
    if row is not None:
        return verify_password(password, row.value)
    if settings.EMERGENCY_PASSWORD:
        return hmac.compare_digest(password.encode(), settings.EMERGENCY_PASSWORD.encode())
    return False


def set_password(db: Session, password: str) -> None:
    row = db.get(SystemSetting, PASSWORD_KEY)
    now = datetime.now(timezone.utc)
    if row is None:
        db.add(SystemSetting(key=PASSWORD_KEY, value=hash_password(password), updated_at=now))
    else:
        row.value, row.updated_at = hash_password(password), now


def recent_failures(db: Session, user_id: int, now: datetime) -> int:
    return db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.actor_user_id == user_id, AuditLog.action == "EMERGENCY_PASSWORD_WRONG",
        AuditLog.created_at >= now - FAILURE_WINDOW)) or 0


# -------------------------------------------------------------- session ---
def issue_session(user_id: int, now: datetime) -> tuple[str, datetime]:
    exp = now + timedelta(minutes=settings.EMERGENCY_SESSION_MINUTES)
    token = jwt.encode({"emg": str(user_id), "typ": "emergency", "exp": exp, "iat": now},
                       settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, exp


def session_user(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    try:
        p = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if p.get("typ") != "emergency" or "emg" not in p:
        return None
    return int(p["emg"])


# --------------------------------------------------------------- states ---
def state(db: Session, lab_id: int, now: Optional[datetime] = None) -> LabEmergency:
    """The lab's state, with anything whose time is over put back to normal."""
    now = now or datetime.now(timezone.utc)
    e = db.get(LabEmergency, lab_id)
    if e is None:
        e = LabEmergency(lab_id=lab_id, door_mode="NORMAL", message="", alarm=False, speak=True, version=0)
        db.add(e)
        db.flush()
    changed = False
    if e.door_mode == "UNLOCKED" and e.door_until is not None and _utc(e.door_until) <= now:
        e.door_mode, e.door_until, changed = "NORMAL", None, True
    if e.message and e.message_until is not None and _utc(e.message_until) <= now:
        e.message, e.message_until, changed = "", None, True
    if changed:
        e.version += 1
    return e


def active(e: LabEmergency) -> bool:
    return e.door_mode != "NORMAL" or bool(e.message) or e.alarm


def out(e: LabEmergency, now: datetime) -> dict:
    return {"door_mode": e.door_mode,
            "door_until": e.door_until, "message": e.message, "message_until": e.message_until,
            "alarm": e.alarm, "speak": bool(e.speak), "version": e.version, "active": active(e),
            "door_remaining_s": max(0, int((_utc(e.door_until) - now).total_seconds()))
            if e.door_until else None,
            "updated_at": e.updated_at}


def notice(e: LabEmergency, lab_code: str) -> tuple[str, str, str]:
    """(title, body, severity) telling the people INSIDE the lab what to do."""
    if not active(e):
        return (f"{lab_code} is back to normal", "The emergency is over.", "info")
    if e.alarm:
        title, body = f"EVACUATE {lab_code} now", "The evacuation alarm is on: leave by the nearest exit."
    elif e.door_mode == "UNLOCKED":
        title, body = f"Emergency in {lab_code}: please leave calmly", "The door is held open."
    elif e.door_mode == "LOCKDOWN":
        title, body = f"{lab_code} is in lockdown", "Nobody can enter. Follow the staff's instructions."
    else:
        title, body = f"Message for {lab_code}", ""
    if e.message:
        body = (body + " " if body else "") + f'"{e.message}"'
    return title, body, "critical" if e.alarm or e.door_mode != "NORMAL" else "warning"


def device_view(e: LabEmergency, now: datetime) -> dict:
    """Flat, for the door controller's small JSON reader."""
    rem = -1
    if e.door_mode == "UNLOCKED" and e.door_until is not None:
        rem = max(0, int((_utc(e.door_until) - now).total_seconds()))
    mrem = 0
    if e.message:
        mrem = -1 if e.message_until is None else max(1, int((_utc(e.message_until) - now).total_seconds()))
    return {"version": e.version, "door": e.door_mode, "remaining_s": rem if e.door_mode == "UNLOCKED" else 0,
            "message": e.message, "message_remaining_s": mrem, "alarm": e.alarm,
            "speak": bool(e.message) and bool(e.speak)}


def broadcast(lab_code: str, e: LabEmergency) -> dict:
    """What every signed-in screen needs: the message to show and read aloud,
    and whether the alarm sounds. version changes with every change, so a
    screen that stopped the voice hears a NEW message again."""
    return {"lab_id": e.lab_id, "lab_code": lab_code, "message": e.message,
            "speak": bool(e.message) and bool(e.speak), "alarm": bool(e.alarm),
            "version": e.version, "active": active(e),
            "at": e.updated_at.isoformat() if e.updated_at else None}
