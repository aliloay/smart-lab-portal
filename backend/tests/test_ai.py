"""
AI assistant, maintenance priorities, trends and CSV export.

The Claude API is never called here: a fake client stands in for it, so the
tests check what the portal controls - the tool loop, that tools only read,
access control, limits, and that everything works with AI switched off.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

from app.core.config import settings
from app.models import (AuditLog, Booking, BookingStatus, Issue, IssueCategory,
                        IssueSeverity, IssueStatus)
from app.services import ai
from tests.conftest import auth_headers


class FakeClient:
    """Replays scripted responses and records every request."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append({**kw, "messages": list(kw["messages"])})
        return self.script.pop(0)


def tool_use(name, args, id_="t1"):
    return NS(stop_reason="tool_use", model="claude-opus-5",
              content=[NS(type="tool_use", id=id_, name=name, input=args)])


def final(text):
    return NS(stop_reason="end_turn", model="claude-opus-5",
              content=[NS(type="text", text=text)])


def _issue(db, user, lab, sev, hours_old=1, category=IssueCategory.MALFUNCTION,
           title="x"):
    i = Issue(reporter_id=user.id, lab_id=lab.id, title=title, description="d",
              category=category, severity=sev, status=IssueStatus.OPEN,
              ticket_number=f"ISS-{title}",
              created_at=datetime.now(timezone.utc) - timedelta(hours=hours_old))
    db.add(i)
    db.commit()
    return i


# ------------------------------------------------------------- priorities --
def test_priorities_rank_is_explainable(client, db, staff, alice, lab, now):
    _issue(db, alice, lab, IssueSeverity.LOW, title="low")
    _issue(db, alice, lab, IssueSeverity.HIGH, hours_old=100, title="high-overdue")
    _issue(db, alice, lab, IssueSeverity.MEDIUM, category=IssueCategory.SAFETY,
           title="safety")
    db.add(Booking(user_id=alice.id, lab_id=lab.id, status=BookingStatus.CONFIRMED,
                   start_time=now + timedelta(hours=3),
                   end_time=now + timedelta(hours=4)))
    db.commit()
    r = client.get("/api/ai/maintenance-priorities",
                   headers=auth_headers(client, staff.email)).json()
    order = [p["ticket"] for p in r["priorities"]]
    assert order[0] == "ISS-high-overdue"          # 60 + overdue 40+ + 10 + 5
    assert order[-1] == "ISS-low"
    top = r["priorities"][0]
    assert top["overdue"] and any("overdue" in x for x in top["reasons"])
    assert any("booking" in x for x in top["reasons"])


def test_priorities_work_without_ai(client, staff, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    h = auth_headers(client, staff.email)
    assert client.get("/api/ai/status", headers=h).json()["configured"] is False
    assert client.get("/api/ai/maintenance-priorities", headers=h).status_code == 200
    r = client.post("/api/ai/ask", headers=h, json={"question": "how busy?"})
    assert r.status_code == 503


def test_students_cannot_use_ai(client, alice):
    h = auth_headers(client, alice.email)
    assert client.get("/api/ai/status", headers=h).status_code == 403
    assert client.post("/api/ai/ask", headers=h,
                       json={"question": "hi there"}).status_code == 403


# ------------------------------------------------------------------- loop --
def test_tool_loop_answers_from_tools(db, lab, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test")
    fake = FakeClient([tool_use("get_lab_readiness", {"lab_code": lab.code}),
                       final("LAB_TEST is ready.")])
    out = ai.ask(db, "Is LAB_TEST ready?", client=fake)
    assert out["answer"] == "LAB_TEST is ready."
    assert out["tools_used"] == ["get_lab_readiness"]
    # The tool result went back to the model, and it came from the database.
    second = fake.requests[1]["messages"][-1]["content"][0]
    assert second["type"] == "tool_result" and '"lab_code":"LAB_TEST"' in second["content"]
    # Request shape: current model, adaptive thinking, fallbacks on.
    req = fake.requests[0]
    assert req["model"] == settings.AI_MODEL
    assert req["thinking"] == {"type": "adaptive"}
    assert req["fallbacks"] == "default" and ai.FALLBACK_BETA in req["betas"]
    # Only read-only tools exist.
    assert all(not n.startswith(("set_", "update_", "delete_", "create_", "open_"))
               for n in ai.HANDLERS)


def test_unknown_tool_and_bad_args_are_errors_not_crashes(db, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test")
    fake = FakeClient([tool_use("open_door", {}),
                       tool_use("get_trends", {"weeks": "lots"}, id_="t2"),
                       final("done")])
    out = ai.ask(db, "open the door", client=fake)
    err = fake.requests[1]["messages"][-1]["content"][0]
    assert err["is_error"] is True
    ok = fake.requests[2]["messages"][-1]["content"][0]
    assert ok["is_error"] is False            # "lots" clamped to the default
    assert out["answer"] == "done"


def test_refusal_is_reported(db, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test")
    fake = FakeClient([NS(stop_reason="refusal", model="m", content=[])])
    assert "declined" in ai.ask(db, "q", client=fake)["answer"]


def test_ask_endpoint_limits_and_audits(client, db, staff, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(settings, "AI_QUESTIONS_PER_HOUR", 2)
    monkeypatch.setattr(ai, "_client", lambda: FakeClient([final("a"), final("b")]))
    h = auth_headers(client, staff.email)
    for _ in range(2):
        assert client.post("/api/ai/ask", headers=h,
                           json={"question": "how busy?"}).status_code == 200
    assert client.post("/api/ai/ask", headers=h,
                       json={"question": "again?"}).status_code == 429
    assert db.query(AuditLog).filter_by(action="AI_QUESTION").count() == 2


def test_automation_weekly_summary_optional(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTOMATION_API_KEY", "k")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    r = client.get("/api/automation/ai/weekly-summary",
                   headers={"X-Automation-Key": "k"}).json()
    assert r["available"] is False and r["summary"] is None


# --------------------------------------------------------- trends / export --
def test_trends_no_shows_and_late(client, db, staff, alice, lab, now):
    start = now - timedelta(hours=5)
    db.add_all([
        Booking(user_id=alice.id, lab_id=lab.id, status=BookingStatus.CONFIRMED,
                start_time=start, end_time=start + timedelta(hours=1)),          # no-show
        Booking(user_id=alice.id, lab_id=lab.id, status=BookingStatus.CONFIRMED,
                start_time=start, end_time=start + timedelta(hours=1),
                first_entry_at=start + timedelta(minutes=30)),                  # late
        Booking(user_id=alice.id, lab_id=lab.id, status=BookingStatus.CONFIRMED,
                start_time=start, end_time=start + timedelta(hours=1),
                first_entry_at=start + timedelta(minutes=2)),                   # on time
    ])
    db.commit()
    r = client.get("/api/analytics/trends?weeks=2",
                   headers=auth_headers(client, staff.email)).json()
    week = [w for w in r["series"] if w["finished"]][0]
    assert week["no_shows"] == 1 and week["late"] == 1
    assert week["no_show_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert week["late_rate"] == 0.5
    assert r["by_lab"][0]["lab_code"] == lab.code


def test_csv_export(client, db, staff, alice, lab, now):
    db.add(Booking(user_id=alice.id, lab_id=lab.id, status=BookingStatus.CONFIRMED,
                   start_time=now - timedelta(hours=3),
                   end_time=now - timedelta(hours=2)))
    db.commit()
    h = auth_headers(client, staff.email)
    r = client.get("/api/analytics/export.csv?kind=bookings&days=7", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("booking_id,lab,")
    assert lines[1].endswith(",yes,")               # finished, no entry: no-show
    assert client.get("/api/analytics/export.csv?kind=weekly",
                      headers=h).status_code == 200
    assert client.get("/api/analytics/export.csv?kind=users",
                      headers=h).status_code == 422
