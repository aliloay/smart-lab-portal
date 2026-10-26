"""Deterministic tool router for the local model (2026-10-26): qwen2.5:1.5b picked a tool for 0/8 tool questions."""
import json
import os

import pytest

from app.services import ai

EVAL = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "llm_bench", "eval_lab.json")


def _questions():
    if not os.path.isfile(EVAL):
        pytest.skip("eval set not mounted")
    return json.load(open(EVAL, encoding="utf-8"))["questions"]


def test_every_tool_question_routes_to_its_tool():
    for q in _questions():
        if q["kind"] == "tools" and not any(t.startswith("instant:") for t in q["tool"]):   # answered before the LLM
            r = ai.route(q["q"])
            assert r is not None and r[0] in q["tool"], (q["q"], r)


def test_snapshot_and_unknown_questions_are_not_hijacked():
    wrong = [(q["q"], ai.route(q["q"])) for q in _questions()
             if q["kind"] not in ("tools", "instant") and ai.route(q["q"])]     # instant ones never reach the router
    # the forecast question mentions temperature -> environment tool is acceptable (its data shows no forecast)
    assert all(r[0] == "get_environment" for _, r in wrong), wrong


def test_arguments_from_the_question():
    assert ai.route("temperature in lab 2 over the last 48 hours") == ("get_environment", {"lab_code": "LAB_02", "hours": 48})
    assert ai.route("show trends for 12 weeks") == ("get_trends", {"weeks": 12})
    assert ai.route("daily report please") == ("get_report", {"period": "daily"})
    assert ai.route("is LAB_03 ready?") == ("get_lab_readiness", {"lab_code": "LAB_03"})


def test_routed_answer_uses_one_tool_and_a_bounded_answer(db, lab, monkeypatch):
    seen = {}

    def fake_chat(model, messages, tools=None, num_predict=None):
        seen.update(system=messages[0]["content"], tools=tools, num_predict=num_predict)
        return {"message": {"content": "- LAB_TEST: no readings"}}
    monkeypatch.setattr(ai, "_ollama_chat", fake_chat)
    out = ai._ask_ollama(db, "What was the humidity in LAB_TEST over the last 24 hours?", None)
    assert out["routed"] and out["tools_used"] == ["get_environment"] and out["answer"].startswith("- LAB_TEST")
    assert "TOOL RESULT (get_environment" in seen["system"] and seen["tools"] is None
    assert seen["num_predict"] == ai.settings.AI_MAX_ANSWER_TOKENS


def test_router_off_restores_the_model_loop(db, monkeypatch):
    monkeypatch.setattr(ai.settings, "AI_ROUTER", False)
    monkeypatch.setattr(ai, "_ollama_chat", lambda *a, **k: {"message": {"content": "from snapshot"}})
    assert ai._ask_ollama(db, "What is the temperature trend?", None)["tools_used"] == ["snapshot"]
