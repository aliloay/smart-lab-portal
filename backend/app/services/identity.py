"""
Door identities (auth subjects).

An auth subject such as USER7 is the label that ties a portal account to its
biometrics: fingerprint slot 7 on the AS608 sensor and the face-server label
"USER7". The master firmware derives the fingerprint slot from the number,
so a new person needs no firmware change - only enrolment at the sensor and
the camera.

Numbers are handed out in order and never reused (accounts are disabled,
not deleted): reusing one could inherit a previous person's fingerprint
template if the slot was not cleared.

Having a subject does not open anything. Entry still needs the person's own
fingerprint or face enrolled under that number, and a valid booking.
"""
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, User

PATTERN = re.compile(r"^USER(\d{1,3})$")
# AS608 slots are 1..127 on the common modules; stay inside that.
MAX_SLOT = 127


def slot_of(subject: Optional[str]) -> Optional[int]:
    m = PATTERN.match(subject or "")
    return int(m.group(1)) if m else None


def next_auth_subject(db: Session) -> Optional[str]:
    """The next free USERn, or None when every sensor slot is used."""
    current = db.scalars(
        select(User.auth_subject).where(User.auth_subject.is_not(None))).all()
    # Numbers that were assigned once and later cleared still count: the
    # audit log keeps every assignment.
    past = db.scalars(select(AuditLog.detail["auth_subject"].as_string()).where(
        AuditLog.action.in_(["USER_CREATED", "USER_SIGNUP", "USER_UPDATED"]))).all()
    used = [slot_of(s) for s in [*current, *past]]
    n = max([u for u in used if u] or [0]) + 1
    return f"USER{n}" if n <= MAX_SLOT else None
