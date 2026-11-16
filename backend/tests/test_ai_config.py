"""Hosted-model defaults must be real model ids, and local-only mode must never reach a hosted model (2026-11-16)."""
import typing

import pytest

from app.core.config import Settings, settings


def _known_model_ids():
    anthropic_model = pytest.importorskip("anthropic.types.model")
    ids = set()
    for arg in typing.get_args(anthropic_model.Model):
        ids.update(typing.get_args(arg))          # the Literal[...] part; the bare `str` fallback has no args
    return ids


def test_default_hosted_model_ids_exist_in_the_installed_sdk():
    known = _known_model_ids()
    assert known, "could not read the SDK's model list"
    s = Settings(_env_file=None)
    assert s.AI_MODEL in known, f"AI_MODEL default {s.AI_MODEL!r} is not a model id of the installed anthropic SDK"
    assert s.AI_STUDENT_MODEL in known, f"AI_STUDENT_MODEL default {s.AI_STUDENT_MODEL!r} is not known to the SDK"


def test_local_only_is_the_default_so_the_hosted_model_is_dormant():
    assert Settings(_env_file=None).AI_LOCAL_ONLY is True


def test_a_configured_cloud_key_is_ignored_in_local_only_mode(monkeypatch):
    from app.services import ai
    monkeypatch.setattr(settings, "AI_PROVIDER", "auto")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "not-a-real-key-for-tests")
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://127.0.0.1:1")          # a local assistant is configured
    monkeypatch.setattr(settings, "AI_LOCAL_ONLY", True)
    assert ai.provider() == "ollama"                                           # the key never selects the cloud
    monkeypatch.setattr(settings, "OLLAMA_URL", "")
    assert ai.provider() is None                                               # and without Ollama there is no silent cloud fallback


def test_the_hosted_model_is_reachable_only_by_explicit_opt_in(monkeypatch):
    from app.services import ai
    monkeypatch.setattr(settings, "AI_PROVIDER", "auto")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "not-a-real-key-for-tests")
    monkeypatch.setattr(settings, "AI_LOCAL_ONLY", False)
    assert ai.provider() == "anthropic"


def test_local_model_default_matches_what_the_lab_runs():
    assert Settings(_env_file=None).OLLAMA_MODEL == "qwen2.5:1.5b"
