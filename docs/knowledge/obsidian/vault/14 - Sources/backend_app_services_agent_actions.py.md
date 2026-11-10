---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/agent_actions.py"
source_hash: "16d16b256597ad559678ddfd4528d977da2dea2fe819ef2354989498bbfbfb76"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/agent_actions.py` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_api_routes_ai.py]] - imports
- [[backend_app_services_agent.py]] - imports
- [[backend_app_core_config.py]] - imports
- [[backend_app_models___init__.py]] - imports

```py
"""
Assistant ACTIONS (2026-10-27, owner: "the agent should be able to make a new booking or cancel - not only read - super
smooth and fast"). Bookings only - doors, relays and robots stay out of reach.

The assistant never changes anything itself. It reads the request (no language model - regular expressions over the
portal's own lab list, so it answers in milliseconds), checks it against the same rules the booking page uses, and
returns a PROPOSAL. The page shows it with Confirm / Not now; Confirm calls the normal booking endpoints as the signed-in
user (/api/bookings, /api/bookings/{id}/cancel) - same validation, permissions and audit as clicking through the pages.

  "book LAB_01 tomorrow 10-12", "reserve the robotics lab on friday from 2pm to 4pm", "book PLC lab today at 15 for 2 hours"
  "cancel my booking", "cancel my booking tomorrow", "cancel my LAB_02 booking"
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Booking, BookingStatus, Lab, User

BOOK = re.compile(r"\b(book|reserve)\b(?!ings?\b)", re.I)
CANCEL = re.compile(r"\b(cancel|delete|remove)\b.*\b(booking|reservation|slot)\b|\bcancel (it|that)\b", re.I)
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def wants_action(question: str) -> bool:
    q = question.lower().strip()
    if re.match(r"(which|what|when|where|who|is|are|how|do|does|did|why)\b", q):
        return False                                        # "which labs can I book?" asks - it does not order
    if re.search(r"\b(my|the|show|list|how many|which)\b.*\bbookings\b", q) and not CANCEL.search(q):
        return False                                        # "show my bookings" is a question, not an action
    return bool(BOOK.search(q) or CANCEL.search(q))


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.LOCAL_TIMEZONE)


def _day(q: str, today: date) -> Optional[date]:
    if re.search(r"\btoday\b", q):
        return today
    if re.search(r"\btomorrow\b", q):
        return today + timedelta(days=1)
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", q)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")\w*\b", q) or \
        re.search(r"\b(" + "|".join(MONTHS) + r")\w*\s+(\d{1,2})(?:st|nd|rd|th)?\b", q)
    if m:
        a, b = m.group(1), m.group(2)
        d, mon = (int(a), b) if a.isdigit() else (int(b), a)
        y = today.year
        cand = date(y, MONTHS.index(mon[:3]) + 1, d)
        return cand if cand >= today else date(y + 1, cand.month, cand.day)
    for i, name in enumerate(DAYS):
        if re.search(rf"\b(on |next |this )?{name}\b", q):
            ahead = (i - today.weekday()) % 7 or 7
            return today + timedelta(days=ahead)
    return None


def _hour(h: str, ampm: Optional[str]) -> Optional[int]:
    v = int(h)
    if ampm:
        ampm = ampm.lower()
        if ampm.startswith("p") and v < 12:
            v += 12
        if ampm.startswith("a") and v == 12:
            v = 0
    elif 1 <= v <= 7:                                       # "from 2 to 4" in a lab means the afternoon
        v += 12
    return v if 0 <= v <= 23 else None


def _times(q: str) -> Optional[tuple[time, time]]:
    T = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?"
    m = re.search(rf"\b(?:from\s+)?{T}\s*(?:-|to|until|till|–)\s*{T}\b", q)
    if m:
        h1, m1, a1, h2, m2, a2 = m.groups()
        if a2 and not a1 and int(h1) < 12 and int(h1) <= int(h2):
            a1 = a2                                         # "2-4pm"
        s, e = _hour(h1, a1), _hour(h2, a2)
        if s is None or e is None:
            return None
        return time(s, int(m1 or 0)), time(e, int(m2 or 0))
    m = re.search(rf"\bat\s+{T}(?:.*?\bfor\s+(\d+(?:\.\d)?)\s*(h|hours?|hrs?))?", q)
    if m:
        h1, m1, a1, dur, _ = m.groups()
        s = _hour(h1, a1)
        if s is None:
            return None
        start = datetime(2000, 1, 1, s, int(m1 or 0))
        end = start + timedelta(hours=float(dur or 2))
        return start.time(), end.time()
    return None


def _lab(db: Session, q: str) -> tuple[Optional[Lab], list[Lab]]:
    labs = db.scalars(select(Lab).where(Lab.is_active.is_(True)).order_by(Lab.code)).all()
    exact = [l for l in labs if re.search(rf"\b{re.escape(l.code.lower())}\b", q)]
    if exact:
        return exact[0], []
    m = re.search(r"\blab[_ ]?(\d{1,2})\b", q)
    if m:
        code = f"LAB_{int(m.group(1)):02d}"
        hit = [l for l in labs if l.code == code]
        if hit:
            return hit[0], []
    words = [w for w in re.findall(r"[a-z]{3,}", q) if w not in ("lab", "labs", "laboratory", "the", "book", "reserve",
                                                                 "tomorrow", "today", "from", "for", "and", "please")]
    scored = []
    for l in labs:
        name = l.name.lower()
        n = sum(1 for w in words if w in name)
        if n:
            scored.append((n, l))
    if not scored:
        return None, []
    scored.sort(key=lambda x: -x[0])
    best = [l for n, l in scored if n == scored[0][0]]
    return (best[0], []) if len(best) == 1 else (None, best)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(_tz()).strftime("%a %d %b %H:%M")


def propose(db: Session, user: User, question: str, now: Optional[datetime] = None) -> Optional[dict]:
    """A booking proposal (or a clarifying question) for the page to confirm, or None when it is not an action."""
    if not wants_action(question):
        return None
    now = now or datetime.now(timezone.utc)
    q = question.lower()
    local_today = now.astimezone(_tz()).date()

    if CANCEL.search(q):
        live = (BookingStatus.CONFIRMED, BookingStatus.PENDING)
        rows = db.scalars(select(Booking).where(Booking.user_id == user.id, Booking.status.in_(live),
                                                Booking.end_time > now).order_by(Booking.start_time)).all()
        labs = {l.id: l for l in db.scalars(select(Lab)).all()}
        d = _day(q, local_today)
        if d:
            rows = [b for b in rows if b.start_time.astimezone(_tz()).date() == d]
        lab, _ = _lab(db, q)
        if lab:
            rows = [b for b in rows if b.lab_id == lab.id]
        if not rows:
            return {"answer": "You have no upcoming booking" + (" that matches" if d or lab else "") + " to cancel.",
                    "intent": "cancel_booking"}
        opts = [{"type": "cancel_booking", "booking_id": b.id,
                 "label": f"Cancel {labs[b.lab_id].code if b.lab_id in labs else b.lab_id} {_fmt(b.start_time)}-"
                          f"{b.end_time.astimezone(_tz()):%H:%M}"} for b in rows[:4]]
        text = ("Cancel this booking?" if len(opts) == 1 else
                f"You have {len(rows)} upcoming bookings - which one should I cancel?")
        return {"answer": text + "\n" + "\n".join(f"- {o['label'][7:]}" for o in opts), "intent": "cancel_booking",
                "actions": opts}

    lab, several = _lab(db, q)
    d = _day(q, local_today)
    t = _times(q)
    missing = []
    if lab is None:
        missing.append("which lab" + (f" ({', '.join(l.code + ' ' + l.name for l in several[:4])})" if several else
                                      " (e.g. LAB_01 or 'robotics lab')"))
    if d is None:
        missing.append("which day (today, tomorrow, a weekday or a date)")
    if t is None:
        missing.append("the time (e.g. 10-12 or 'at 2pm for 2 hours')")
    if missing:
        return {"answer": "To book, I still need " + ", ".join(missing) + ".\nExample: *book LAB_01 tomorrow 10-12*.",
                "intent": "create_booking"}
    start = datetime.combine(d, t[0], tzinfo=_tz()).astimezone(timezone.utc)
    end = datetime.combine(d, t[1], tzinfo=_tz()).astimezone(timezone.utc)
    if end <= start:
        return {"answer": "The end time must be after the start time.", "intent": "create_booking"}
    if start < now:
        return {"answer": "That time has already passed - pick a later time.", "intent": "create_booking"}
    clash = db.scalar(select(Booking).where(Booking.lab_id == lab.id,
                                            Booking.status.in_((BookingStatus.CONFIRMED, BookingStatus.PENDING)),
                                            Booking.start_time < end, Booking.end_time > start))
    note = (f"\nHeads-up: {lab.code} already has a booking {_fmt(clash.start_time)}-"
            f"{clash.end_time.astimezone(_tz()):%H:%M} - the portal will refuse an overlap.") if clash else ""
    act = {"type": "create_booking", "lab_id": lab.id, "start_time": start.isoformat(), "end_time": end.isoformat(),
           "reason": "Booked from the assistant", "label": f"Book {lab.code} {_fmt(start)}-{end.astimezone(_tz()):%H:%M}"}
    return {"answer": f"Book **{lab.code} - {lab.name}** on {_fmt(start)} until {end.astimezone(_tz()):%H:%M}?" + note,
            "intent": "create_booking", "actions": [act]}

```
