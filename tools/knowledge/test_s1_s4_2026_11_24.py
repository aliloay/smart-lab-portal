"""S-1 (FAQ question words) and S-4 (partial embeddings), 24 Nov 2026."""
import json
import os

import numpy as np
import pytest

import agent
import kb

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.parametrize("q", ["Where is the door camera?", "Why is the door camera?", "Where is the restore drill?",
                               "Who is the restore drill?", "Why are the robotics lab opening hours?"])
def test_wrong_question_word_gets_no_faq_answer(q):
    assert agent.faq_direct({"repo": REPO}, q) is None


@pytest.mark.parametrize("q", ["What is the door camera?", "door camera", "What are the robotics lab opening hours?",
                               "When is the Robotics Lab open?", "Has a backup restore been tested?"])
def test_right_question_word_still_answers(q):
    assert agent.faq_direct({"repo": REPO}, q) is not None


def _setup(tmp_path, monkeypatch, n=20, have=20):
    docs = [{"source": f"s{i}.md", "heading": f"h{i}", "text": f"pump word{i}", "kind": "doc",
             "tf": {"pump": 1, f"word{i}": 1}, "dl": 2} for i in range(n)]
    idx = {"docs": docs, "n": n, "avgdl": 2, "df": {"pump": n, **{f"word{i}": 1 for i in range(n)}}, "built": str(tmp_path)}
    mat = np.eye(n, dtype=np.float32)[:have]
    np.save(tmp_path / "embeddings.npy", mat)
    (tmp_path / "embeddings_keys.json").write_text(json.dumps([kb.chunk_key(d) for d in docs[:have]]))
    kb._EMB_CACHE.clear()
    monkeypatch.setattr(kb, "embed", lambda *a, **k: np.eye(n, dtype=np.float32)[:1])
    return {"data": str(tmp_path)}, idx


def test_full_coverage(tmp_path, monkeypatch):
    cfg, idx = _setup(tmp_path, monkeypatch)
    assert not np.isnan(kb.load_embeddings(cfg, idx)).any()


def test_one_missing_chunk_is_unknown_not_fatal(tmp_path, monkeypatch):
    cfg, idx = _setup(tmp_path, monkeypatch, have=19)
    mat = kb.load_embeddings(cfg, idx)
    assert np.isnan(mat[19]).all() and not np.isnan(mat[:19]).any()
    assert kb._EMB_CACHE["coverage"] == pytest.approx(0.95)
    hits = kb.search(cfg, "word19", k=3, idx=idx)                  # (s0 is the query's perfect meaning match)
    assert "s19.md" in [h["source"] for h in hits] and not any(np.isnan(h["score"]) for h in hits)


def test_unembedded_chunk_does_not_outrank_a_meaning_match(tmp_path, monkeypatch):
    cfg, idx = _setup(tmp_path, monkeypatch, have=19)
    assert kb.search(cfg, "pump", k=1, idx=idx)[0]["source"] == "s0.md"


def test_low_coverage_corrupt_and_mismatched_fall_back(tmp_path, monkeypatch):
    cfg, idx = _setup(tmp_path, monkeypatch, have=10)
    assert kb.load_embeddings(cfg, idx) is None
    cfg, idx = _setup(tmp_path, monkeypatch)
    (tmp_path / "embeddings.npy").write_bytes(b"broken")
    kb._EMB_CACHE.clear()
    assert kb.load_embeddings(cfg, idx) is None
    cfg, idx = _setup(tmp_path, monkeypatch)
    (tmp_path / "embeddings_keys.json").write_text(json.dumps(["x"]))
    kb._EMB_CACHE.clear()
    assert kb.load_embeddings(cfg, idx) is None


def test_wrong_dimension_is_keyword_only(tmp_path, monkeypatch):
    cfg, idx = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(kb, "embed", lambda *a, **k: np.ones((1, 7), np.float32))
    assert kb.search(cfg, "word3", k=1, idx=idx)[0]["source"] == "s3.md"
