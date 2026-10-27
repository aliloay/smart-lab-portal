"""Reasoning-model families answer without a hidden thinking pass (2026-10-27 model sweep): qwen3 sends think=false,
qwen2.5 sends nothing; OLLAMA_THINK=True allows thinking."""
import httpx

from app.core.config import settings
from app.services import ai


def _capture(monkeypatch):
    sent = []

    def post(url, json=None, timeout=None):
        sent.append(json)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}, "done": True},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(ai.httpx, "post", post)
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama.test:11434")
    return sent


def test_think_off_only_for_reasoning_families(monkeypatch):
    sent = _capture(monkeypatch)
    for m in ("qwen3:1.7b", "qwen3.5:0.8b", "qwen2.5:1.5b", "llama3.2:1b"):
        ai._ollama_chat_unbounded(m, [{"role": "user", "content": "hi"}])
    assert [b.get("think") for b in sent] == [False, False, None, None]
    assert ai.thinks("LiquidAI/lfm2.5-thinking:1.2b") and not ai.thinks("LiquidAI/lfm2.5-1.2b-instruct")


def test_owner_can_allow_thinking(monkeypatch):
    sent = _capture(monkeypatch)
    monkeypatch.setattr(settings, "OLLAMA_THINK", True)
    ai._ollama_chat_unbounded("qwen3:1.7b", [{"role": "user", "content": "hi"}])
    assert "think" not in sent[0]
