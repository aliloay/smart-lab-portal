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
from app.models import Alert, Booking, BookingStatus, Device, Lab, Role, User

BOOK = re.compile(r"\b(book|reserve)\b(?!ings?\b)", re.I)
CANCEL = re.compile(r"\b(cancel|delete|remove)\b.*\b(booking|reservation|slot)\b|\bcancel (it|that)\b", re.I)
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


# 2026-11-11: maintenance reports. "the oscilloscope in LAB_01 is broken", "report a network problem on PC-04".
ISSUE = re.compile(r"\b(report|log|submit|raise|file|open)\b.*\b(issue|fault|problem|ticket|broken|damage\w*)\b|"
                   r"\b(is|are|seems?|looks?) (broken|not working|faulty|damaged|dead|missing)\b|"
                   r"\b(doesn'?t|does not|won'?t|will not|can'?t|cannot) (work|turn on|start|boot|connect)\b", re.I)
_CATEGORY = [("SAFETY", r"smoke|fire|burn|spark|shock|leak|smell"), ("DAMAGED", r"broken|crack|damag|snapped|bent"),
             ("MISSING", r"missing|lost|stolen|gone"), ("NETWORK", r"network|wi-?fi|internet|ethernet|router|switch"),
             ("SOFTWARE", r"software|app\b|install|licen[cs]e|login|update|windows"),
             ("ACCESS_CONTROL", r"door|card|fingerprint|qr|badge|lock")]


# 2026-11-11: "acknowledge the alerts", "ack alert 12", "acknowledge the camera alert in LAB_01" (staff and admins).
ACK = re.compile(r"\b(acknowledge|ack|accept|confirm)\b.*\b(alerts?|alarms?|incidents?)\b", re.I)
ACK_SEVERITY = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def _ack_proposal(db: Session, user: User, question: str) -> dict:
    """Open (not yet acknowledged) alerts for the person to confirm one by one. Confirm = the Incidents page's own
    POST /api/incidents/{id}/actions {action: acknowledge}: staff only, audited, refused if already acknowledged."""
    if user.role not in (Role.ADMIN, Role.LAB_STAFF):
        return {"answer": "Only lab staff and admins can acknowledge alerts.", "intent": "ack_alert"}
    q = question.lower()
    rows = [a for a in db.scalars(select(Alert).where(Alert.is_resolved.is_(False))).all()
            if (getattr(a, "state", None) or "OPEN") == "OPEN"]
    num = re.search(r"(?:#|\balert\s+|\bincident\s+)(\d+)\b", q)
    if num:
        rows = [a for a in rows if a.id == int(num.group(1))]
    lab, _ = _lab(db, q)
    if lab is not None:
        rows = [a for a in rows if a.lab_id == lab.id]
    words = [w for w in re.findall(r"[a-z0-9]{4,}", q) if w not in {"acknowledge", "alert", "alerts", "please", "incident",
                                                                    "incidents", "alarm", "alarms", "confirm", "accept", "every", "them"}]
    picked = [a for a in rows if any(w in (a.title or "").lower() for w in words)] or rows
    picked.sort(key=lambda a: (ACK_SEVERITY.get(getattr(a.severity, "value", str(a.severity)), 3), -a.created_at.timestamp()))
    picked = picked[:5]
    if not picked:
        return {"answer": "There is no open, unacknowledged alert matching that.", "intent": "ack_alert"}
    acts = [{"type": "ack_alert", "alert_id": a.id,
             "label": f"Acknowledge #{a.id} {a.title[:60]}"} for a in picked]
    more = f" (showing {len(picked)} of {len(rows)})" if len(rows) > len(picked) else ""
    return {"answer": "Acknowledge which alert?" + more + "\n" +
                      "\n".join(f"- #{a.id} [{getattr(a.severity, 'value', a.severity)}] {a.title}" for a in picked)
                      + "\n\nAcknowledging says someone is on it; it does not resolve the alert.",
            "intent": "ack_alert", "actions": acts}


def wants_issue(question: str) -> bool:
    q = question.lower().strip()
    if re.match(r"(which|what|when|where|who|how many|show|list)\b", q):
        return False                                        # "which issues are open?" asks - it does not report
    return bool(ISSUE.search(q))


def _issue_proposal(db: Session, user: User, question: str) -> dict:
    """A maintenance ticket for the page to confirm: lab, device, category and severity guessed from the words, the
    person's own sentence as the description. Nothing is filed until the person presses Confirm (POST /api/issues)."""
    q = question.lower()
    lab, _ = _lab(db, q)
    if lab is None:
        lab = db.scalar(select(Lab).where(Lab.code == settings.AI_DEFAULT_LAB))
    if lab is None:
        return {"answer": "Which lab is it in? Say the lab, e.g. \"report a broken monitor in LAB_01\".",
                "intent": "create_issue"}
    device = None
    for d in db.scalars(select(Device).where(Device.lab_id == lab.id)).all():
        names = {d.device_uid.lower(), (d.name or "").lower()}
        if any(n and len(n) >= 3 and re.search(r"\b" + re.escape(n).replace("\\ ", "[ -]?") + r"\b", q) for n in names):
            device = d
            break
    category = next((c for c, pat in _CATEGORY if re.search(pat, q)), "MALFUNCTION")
    severity = "HIGH" if category == "SAFETY" else "MEDIUM"
    text = " ".join(question.split())
    title = re.sub(r"^(please\s+)?(report|log|submit|raise|file|open)\s+(an?\s+)?(issue|fault|problem|ticket)?\s*(that|:|-)?\s*",
                   "", text, flags=re.I).strip() or text
    title = (title[0].upper() + title[1:])[:120] if len(title) >= 5 else f"{category.title()} reported in {lab.code}"
    desc = text if len(text) >= 10 else f"{text} (reported through the assistant)"
    act = {"type": "create_issue", "lab_id": lab.id, "device_id": device.id if device else None,
           "category": category, "severity": severity, "title": title, "description": desc[:4000],
           "label": f"Report \"{title[:60]}\" in {lab.code}"}
    where = f" on **{device.name}**" if device else ""
    return {"answer": f"Report this in **{lab.code}**{where} as {category.replace('_', ' ').lower()}, "
                      f"severity {severity.lower()}?\n> {title}\n\nYou can add photos on the issue page afterwards.",
            "intent": "create_issue", "actions": [act]}


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
    if ACK.search(question) and not re.match(r"\s*(which|what|how many|show|list)\b", question.lower()):
        return _ack_proposal(db, user, question)
    if wants_issue(question) and not BOOK.search(question):
        return _issue_proposal(db, user, question)
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
