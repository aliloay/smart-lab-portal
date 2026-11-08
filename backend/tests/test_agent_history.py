"""
The agent answers date ranges, door history and charts itself, exactly, from
the records - no language model (the model misread periods and invented
"Color: Red" lists).

Tested: dates in the forms people type ("15 sep till today", "last tuesday",
"yesterday", "last 10 days", "from 1 oct to 3 oct"); "who went to <lab> on
<day>" lists that day's entries and nothing from other days; a chart request
returns chart data (coloured series, one point per day); a report for a
custom range covers exactly that range.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import AccessEvent, EventType
from app.services import agent, agent_history as ah

TZ = ZoneInfo("Africa/Cairo")
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=TZ)             # a Tuesday


def local(y, m, d):
    return datetime(y, m, d, tzinfo=TZ)


@pytest.mark.parametrize("text,start,end", [
    ("15 sep till today", local(2026, 9, 15), local(2026, 10, 7)),
    ("report from 1 oct to 3 oct", local(2026, 10, 1), local(2026, 10, 4)),
    ("who went to lab1 last tuesday", local(2026, 9, 29), local(2026, 9, 30)),
    ("yesterday", local(2026, 10, 5), local(2026, 10, 6)),
    ("door entries in the last 10 days", local(2026, 9, 27), local(2026, 10, 7)),
    ("since september 20", local(2026, 9, 20), local(2026, 10, 7)),
    ("on 2 oct", local(2026, 10, 2), local(2026, 10, 3)),
])
def test_dates_people_type(text, start, end):
    r = ah.parse_range(text, NOW)
    assert r is not None, text
    assert (r[0], r[1]) == (start.astimezone(timezone.utc), end.astimezone(timezone.utc)), text


def test_no_date_means_none():
    assert ah.parse_range("who is inside now", NOW) is None


def _entry(db, lab, user, at, kind=EventType.ACCESS_GRANTED, reason=None):
    db.add(AccessEvent(event_type=kind, lab_id=lab.id, user_id=user.id, method="RFID",
                       result="GRANTED" if kind == EventType.ACCESS_GRANTED else "DENIED", reason=reason,
                       message="test", created_at=at.astimezone(timezone.utc)))
    db.commit()


def test_who_went_to_a_lab_on_a_day(db, lab, alice, staff, monkeypatch):
    monkeypatch.setattr(ah, "_now", lambda: NOW)
    _entry(db, lab, alice, datetime(2026, 9, 29, 10, 15, tzinfo=TZ))
    _entry(db, lab, alice, datetime(2026, 9, 29, 14, 0, tzinfo=TZ), EventType.ACCESS_DENIED, "WRONG FINGER")
    _entry(db, lab, staff, datetime(2026, 9, 30, 9, 0, tzinfo=TZ))            # the next day: not listed
    out = agent.quick_answer(db, staff, f"who went to {lab.code} last tuesday")
    assert out and out["instant"]
    text = out["answer"]
    assert "Alice" in text and "10:15" in text and "Lab Technician" not in text
    assert "1 refused" in text or "refused 1" in text


def test_chart_request_returns_coloured_daily_series(db, lab, alice, staff, monkeypatch):
    monkeypatch.setattr(ah, "_now", lambda: NOW)
    _entry(db, lab, alice, datetime(2026, 10, 1, 10, 0, tzinfo=TZ))
    _entry(db, lab, alice, datetime(2026, 10, 2, 10, 0, tzinfo=TZ))
    out = agent.quick_answer(db, staff, "send a chart of last weeks report with colors")
    assert out and out["instant"] and out.get("charts")
    door = next(c for c in out["charts"] if "Door" in c["title"])
    assert len(door["x"]) == 7 and all(s.get("color") for s in door["series"])
    granted = next(s for s in door["series"] if s["name"].startswith("Entries"))
    assert sum(granted["data"]) == 2


def test_report_for_a_custom_range(db, lab, alice, staff, monkeypatch):
    monkeypatch.setattr(ah, "_now", lambda: NOW)
    _entry(db, lab, alice, datetime(2026, 9, 16, 10, 0, tzinfo=TZ))
    _entry(db, lab, alice, datetime(2026, 9, 10, 10, 0, tzinfo=TZ))           # before the range
    out = agent.quick_answer(db, staff, "15 sep till today")
    assert out and out["instant"]
    assert "15 Sep" in out["answer"] and "1 entr" in out["answer"]
    assert out.get("charts")


def test_a_refused_attempt_counts_once(db, lab, alice, staff, monkeypatch):
    """The door reports one refused attempt as IDENTITY_MISMATCH + ACCESS_DENIED."""
    monkeypatch.setattr(ah, "_now", lambda: NOW)
    at = datetime(2026, 10, 2, 9, 0, tzinfo=TZ)
    _entry(db, lab, alice, at, EventType.IDENTITY_MISMATCH, "IDENTITY_MISMATCH")
    _entry(db, lab, alice, at, EventType.ACCESS_DENIED, "FACE MISMATCH")
    out = agent.quick_answer(db, staff, "door history last 7 days chart")
    door = next(c for c in out["charts"] if "Door" in c["title"])
    assert sum(next(s for s in door["series"] if s["name"] == "Refused")["data"]) == 1
    assert "1 refused" in out["answer"]


@pytest.mark.parametrize("q", ["Send charts of past week", "graphs for last month", "plot the door entries",
                               "show me a diagram of yesterday", "charts please"])
def test_every_chart_wording_gets_real_charts(db, lab, staff, monkeypatch, q):
    """Plurals too: 'charts' fell through to the model, which claimed it had drawn them."""
    monkeypatch.setattr(ah, "_now", lambda: NOW)
    out = agent.quick_answer(db, staff, q)
    assert out and out["instant"] and out.get("charts"), q


def test_printable_report_has_the_charts(db, lab, alice):
    """The PDF is the printable report page: it must carry the same charts."""
    r = agent.management_report(db, "weekly")
    titles = [c["title"] for c in r["charts"]]
    assert any("Door activity" in t for t in titles) and any("Bookings" in t for t in titles)
    assert len(r["charts"][0]["x"]) == 7
