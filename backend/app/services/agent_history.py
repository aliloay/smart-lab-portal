"""
The agent's answers about any period: dates the way people type them, door
history ("who went to lab 1 last Tuesday"), a report for any range, and the
charts behind them - all counted from stored records, no language model.

Charts are data, not pictures: {"kind": "bar"|"pie", "title", "sub", "x",
"series": [{"name", "color", "data"}], "stacked"}; the chat draws them with
the portal's own chart components (and can save them as an image).
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AccessEvent, Booking, EventType, Lab, User
from app.services.automation import period_report
from app.ui_text import denial_sentence

GREEN, RED, BLUE, VIOLET, AMBER = "#10b981", "#ef4444", "#38bdf8", "#a78bfa", "#f59e0b"
PIE = ["#38bdf8", "#f59e0b", "#ef4444", "#a78bfa", "#2dd4bf", "#f0abfc", "#818cf8", "#94a3b8"]

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MON = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
        r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?")
_DATE = rf"(?:(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?{_MON}|{_MON}\s*(\d{{1,2}})(?:st|nd|rd|th)?)(?:\s*,?\s*(\d{{4}}))?"
_END = r"(?:till|until|untill|to|through|-|–|and)"
GRANT = (EventType.ACCESS_GRANTED,)
# One refused attempt is one ACCESS_DENIED (the door also sends IDENTITY_MISMATCH
# for the same attempt): counting both would show every refusal twice.
REFUSE = (EventType.ACCESS_DENIED,)


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.LOCAL_TIMEZONE)


def _now() -> datetime:
    return datetime.now(_tz())


def _utc(d: datetime) -> datetime:
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def _day_start(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=_tz())


def _date(m: re.Match, today: date) -> date:
    """A date match of _DATE: day + month (+ year); without a year, the most recent one."""
    g = m.groups()
    day, mon = (int(g[0]), MONTHS[g[1][:3]]) if g[0] else (int(g[3]), MONTHS[g[2][:3]])
    year = int(g[4]) if g[4] else today.year
    d = date(year, mon, day)
    if not g[4] and d > today:
        d = date(year - 1, mon, day)
    return d


def parse_range(text: str, now: Optional[datetime] = None) -> Optional[tuple[datetime, datetime, str]]:
    """(start, end, label) in UTC, end exclusive, for the period a question names; None if it names none."""
    now = (now or _now()).astimezone(_tz())
    today = now.date()
    q = text.lower()
    span = lambda a, b: (_utc(_day_start(a)), _utc(_day_start(b + timedelta(days=1))))  # noqa: E731
    lab = lambda a, b: (f"{a:%a %d %b}" if a == b else f"{a:%d %b} - {b:%d %b %Y}")   # noqa: E731

    dates = list(re.finditer(_DATE, q))
    if len(dates) >= 2 and re.search(_END, q[dates[0].end():dates[1].start()]):
        a, b = sorted((_date(dates[0], today), _date(dates[1], today)))
        return (*span(a, b), lab(a, b))
    if dates and (re.search(rf"{_END}\s*(today|now)\b", q[dates[0].end():]) or
                  re.search(r"\b(since|from)\s*$", q[:dates[0].start()])):
        a = _date(dates[0], today)
        return (*span(a, today), lab(a, today))
    if dates:
        a = _date(dates[0], today)
        return (*span(a, a), lab(a, a))
    if re.search(r"\btoday\b", q):
        return (*span(today, today), "today")
    if re.search(r"\byesterday\b", q):
        y = today - timedelta(days=1)
        return (*span(y, y), f"yesterday ({y:%a %d %b})")
    if (m := re.search(r"\b(last|on|this|past)\s+(" + "|".join(DAYS) + r")\b", q)) or \
            (m := re.search(r"\b()(" + "|".join(DAYS) + r")\b", q)):
        back = (today.weekday() - DAYS.index(m[2])) % 7
        if back == 0 and m[1] in ("last", "past"):
            back = 7
        d = today - timedelta(days=back)
        return (*span(d, d), f"{d:%A %d %b}")
    if m := re.search(r"\b(?:last|past|previous)\s+(\d{1,3})\s*(day|week|month)s?\b", q):
        n = int(m[1]) * {"day": 1, "week": 7, "month": 30}[m[2]]
        a = today - timedelta(days=n - 1)
        return (*span(a, today), f"last {m[1]} {m[2]}{'s' if m[1] != '1' else ''}")
    if re.search(r"\b(last|past|previous|this)\s+week|\bweek(ly)?\b", q):
        a = today - timedelta(days=6)
        return (*span(a, today), "last 7 days")
    if re.search(r"\b(last|past|previous|this)\s+month|\bmonth(ly)?\b", q):
        a = today - timedelta(days=29)
        return (*span(a, today), "last 30 days")
    return None


def find_lab(db: Session, text: str) -> Optional[Lab]:
    q = text.lower()
    labs = db.scalars(select(Lab)).all()
    for l in labs:                                   # the exact code, e.g. LAB_01
        if re.search(rf"\b{re.escape(l.code.lower())}\b", q):
            return l
    if m := re.search(r"\blab[\s_-]*0*(\d{1,3})\b", q):   # "lab1", "lab 1", "lab_01"
        n = int(m[1])
        return next((l for l in labs if re.fullmatch(rf"lab_?0*{n}", l.code.lower())), None)
    return None


def last_days(n: int) -> tuple[datetime, datetime]:
    """The last n local days, today included: what a chart of 'the last 7 days' shows."""
    today = _now().date()
    return _utc(_day_start(today - timedelta(days=n - 1))), _utc(_day_start(today + timedelta(days=1)))


# ----------------------------------------------------------------- charts ---
def _buckets(start: datetime, end: datetime) -> tuple[list[datetime], list[str]]:
    """Day buckets (weeks when the range is long), as local starts + labels."""
    a, b = start.astimezone(_tz()).date(), (end.astimezone(_tz()) - timedelta(seconds=1)).date()
    days = (b - a).days + 1
    step = 1 if days <= 62 else 7
    starts, labels = [], []
    d = a
    while d <= b:
        starts.append(_day_start(d))
        labels.append(f"{d:%d %b}" if step == 1 else f"wk {d:%d %b}")
        d += timedelta(days=step)
    return starts, labels


def _per_bucket(times: list[datetime], starts: list[datetime]) -> list[int]:
    out = [0] * len(starts)
    for t in times:
        t = t.astimezone(_tz())
        i = max((k for k, s in enumerate(starts) if s <= t), default=None)
        if i is not None:
            out[i] += 1
    return out


def charts(db: Session, start: datetime, end: datetime, lab: Optional[Lab] = None) -> list[dict]:
    starts, labels = _buckets(start, end)
    unit = "day" if len(labels) < 2 or labels[0][:2] != "wk" else "week"
    ev = select(AccessEvent.event_type, AccessEvent.reason, AccessEvent.created_at).where(
        AccessEvent.created_at >= start, AccessEvent.created_at < end,
        AccessEvent.event_type.in_(GRANT + REFUSE))
    bk = select(Booking.start_time).where(Booking.start_time >= start, Booking.start_time < end)
    if lab is not None:
        ev, bk = ev.where(AccessEvent.lab_id == lab.id), bk.where(Booking.lab_id == lab.id)
    rows = db.execute(ev).all()
    where = f" · {lab.code}" if lab else ""
    out = [{
        "kind": "bar", "stacked": True, "title": f"Door activity per {unit}{where}", "x": labels,
        "series": [{"name": "Entries granted", "color": GREEN,
                    "data": _per_bucket([r.created_at for r in rows if r.event_type in GRANT], starts)},
                   {"name": "Refused", "color": RED,
                    "data": _per_bucket([r.created_at for r in rows if r.event_type in REFUSE], starts)}]},
        {"kind": "bar", "title": f"Bookings per {unit}{where}", "x": labels,
         "series": [{"name": "Bookings", "color": BLUE,
                     "data": _per_bucket([t for (t,) in db.execute(bk).all()], starts)}]}]
    reasons = Counter(r.reason or "Other" for r in rows if r.event_type in REFUSE)
    if reasons:
        top = reasons.most_common(7)
        out.append({"kind": "pie", "title": f"Why the door refused{where}",
                    "x": [denial_sentence(k) if k != "Other" else k for k, _ in top],
                    "series": [{"name": "Refusals", "color": RED, "data": [n for _, n in top],
                                "colors": PIE[:len(top)]}]})
    return out


# ---------------------------------------------------------------- answers ---
def door_history(db: Session, start: datetime, end: datetime, label: str, lab: Optional[Lab]) -> dict:
    q = select(AccessEvent).where(AccessEvent.created_at >= start, AccessEvent.created_at < end,
                                  AccessEvent.event_type.in_(GRANT + REFUSE)).order_by(AccessEvent.created_at)
    if lab is not None:
        q = q.where(AccessEvent.lab_id == lab.id)
    rows = db.scalars(q).all()
    users = {u.id: u for u in db.scalars(select(User)).all()}
    labs = {l.id: l.code for l in db.scalars(select(Lab)).all()}
    granted = [e for e in rows if e.event_type in GRANT]
    refused = [e for e in rows if e.event_type in REFUSE]
    where = lab.code if lab else "all labs"
    one_day = (end - start) <= timedelta(days=1)
    when = (lambda e: f"{_utc(e.created_at).astimezone(_tz()):%H:%M}") if one_day else \
        (lambda e: f"{_utc(e.created_at).astimezone(_tz()):%a %d %b %H:%M}")
    who = lambda e: users[e.user_id].full_name if e.user_id in users else "unknown person"  # noqa: E731
    head = (f"**Door activity · {where} · {label}**: {len(granted)} "
            f"entr{'y' if len(granted) == 1 else 'ies'} by {len({e.user_id for e in granted})} "
            f"{'person' if len({e.user_id for e in granted}) == 1 else 'people'}, {len(refused)} refused.")
    if not rows:
        return {"text": f"**Door activity · {where} · {label}**: nobody entered and nothing was refused "
                        f"(checked {label}, door records).", "charts": [] if one_day else charts(db, start, end, lab)}
    lines = [head, "**Entries:**" if granted else ""]
    lines += [f"- {when(e)} {who(e)}" + ("" if lab else f" ({labs.get(e.lab_id, '?')})")
              + (f" · {e.method.lower()}" if e.method else "") for e in granted[:20]]
    if len(granted) > 20:
        lines.append(f"- … and {len(granted) - 20} more")
    if refused:
        lines.append("**Refused:**")
        lines += [f"- {when(e)} {who(e)}: {denial_sentence(e.reason) if e.reason else 'refused'}"
                  for e in refused[:10]]
    return {"text": "\n".join(l for l in lines if l), "charts": [] if one_day else charts(db, start, end, lab)}


def range_report(db: Session, start: datetime, end: datetime, label: str, lab: Optional[Lab] = None) -> dict:
    r = period_report(db, start, end)
    b, a, m = r["bookings"], r["access"], r["maintenance"]
    g = a["granted"]
    lines = [f"**Lab report** · {label}",
             f"- Bookings: {b['confirmed']} confirmed, {b['booked_hours']} h booked",
             f"- Attendance: {round(b['attendance_rate'] * 100)}%, {b['no_show']} no-show"
             if b["attendance_rate"] is not None else "- Attendance: no finished bookings",
             f"- Door: {g} entr{'y' if g == 1 else 'ies'}, {a['denied']} refused",
             f"- Maintenance: {m['opened']} opened, {m['resolved']} resolved, {m['open_now']} open now"]
    reasons = a.get("top_denial_reasons") or []
    if reasons:
        lines.append("- Top refusal reasons: " + ", ".join(
            f"{denial_sentence(d['reason'])} ×{d['count']}" for d in reasons[:3]))
    return {"text": "\n".join(lines), "charts": charts(db, start, end, lab)}


HISTORY = re.compile(r"\b(who|whom)\b.*\b(went|entered|enter|visited|came|was|were|used|accessed)\b|"
                     r"\b(door|access) (history|log|activity|records?)\b|\bentries\b|\bentered\b")
CHART = re.compile(r"\b(charts?|graphs?|plot\w*|diagrams?|visuali[sz]\w*|colou?r\w*)\b")
REPORT = re.compile(r"\b(report|summary|overview|analysis|statistics|stats|usage)\b")


def answer(db: Session, question: str) -> Optional[dict]:
    """Staff: door history / chart / report for a named period. None when not that kind of question."""
    q = question.lower()
    rng = parse_range(q)
    lab = find_lab(db, q)
    if HISTORY.search(q):
        if rng is None:
            now = _now().date()
            rng = (_utc(_day_start(now - timedelta(days=6))), _utc(_day_start(now + timedelta(days=1))),
                   "last 7 days")
        return {"intent": "door_history", **door_history(db, *rng, lab)}
    # A plain "weekly / monthly report" keeps its own answer (agent.py); here: an
    # explicit period (a date, "last 10 days", "yesterday"...) or a chart request.
    explicit = rng is not None and rng[2] not in ("last 7 days", "last 30 days")
    if CHART.search(q) or explicit:
        if rng is None:
            now = _now().date()
            rng = (_utc(_day_start(now - timedelta(days=6))), _utc(_day_start(now + timedelta(days=1))),
                   "last 7 days")
        return {"intent": "range_report", **range_report(db, *rng, lab)}
    return None
