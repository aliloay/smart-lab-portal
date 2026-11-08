"""
History importer tests - fixtures only (no real transcripts, git repo in a temp dir).
    py -m pytest -q tools/knowledge
"""
import json
import os
import subprocess

import pytest

import history
import kb

SECRET = "Camera#Secret99"


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo, home = tmp_path / "repo", tmp_path / "know"
    (repo / "backend/app/models").mkdir(parents=True)
    (repo / "backend/app/models/tables.py").write_text(
        'class Lab(Base):\n    """A laboratory."""\n    __tablename__ = "labs"\n'
        '    id: Mapped[int] = mapped_column(primary_key=True)\n\n'
        'class Booking(Base):\n    __tablename__ = "bookings"\n'
        '    id: Mapped[int] = mapped_column(primary_key=True)\n'
        '    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"))\n', encoding="utf-8")
    (repo / ".env").write_text(f"CAMERA_SOURCE=rtsp://user:{SECRET}@10.0.0.5/s\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@t", "add", "."], cwd=repo)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@t", "commit", "-qm", "first commit"], cwd=repo)
    claude = tmp_path / "claude" / "x-smart-lab-portal"
    claude.mkdir(parents=True)
    lines = [
        {"type": "user", "uuid": "u1", "timestamp": "2026-09-24T17:00:00Z",
         "message": {"content": "<ide_opened_file>noise</ide_opened_file> The Smart Lab is my thesis project."}},
        {"type": "assistant", "uuid": "a1", "timestamp": "2026-09-24T17:01:00Z",
         "message": {"content": [{"type": "text", "text": "I propose a FastAPI backend."},
                                 {"type": "tool_use", "name": "Bash", "input": {}}]}},
        {"type": "user", "uuid": "u2", "timestamp": "2026-09-24T17:02:00Z",
         "message": {"content": f"camera is rtsp://user:{SECRET}@10.0.0.5/s"}},
        "not json at all",
    ]
    (claude / "s1.jsonl").write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines), encoding="utf-8")
    inbox = home / "inbox_raw"
    inbox.mkdir(parents=True)
    (inbox / "export.json").write_text(json.dumps([{"title": "Bsc. Smart Lab (1)", "mapping": {
        "a": {"message": {"author": {"role": "user"}, "create_time": 1727000000, "content": {"parts": ["Three ESP32 systems."]}}},
        "b": {"message": {"author": {"role": "assistant"}, "create_time": 1727000100, "content": {"parts": ["Use HX711."]}}},
        "c": {"message": {"author": {"role": "user"}, "create_time": None, "content": {"parts": ["No time on this one."]}}}}}]),
        encoding="utf-8")
    cfgp = tmp_path / "cfg.json"
    cfgp.write_text(json.dumps({"repo": str(repo), "vault": str(home / "vault"), "data": str(home / "data")}), encoding="utf-8")
    cfg = kb.load_config(str(cfgp))
    cfg["repo"] = str(repo)
    monkeypatch.setattr(history, "claude_files", lambda: [str(claude / "s1.jsonl")])
    return cfg


def test_import_all_connectors_with_provenance(env):
    r = history.run_import(env)
    recs = history.load_records(env)
    kinds = {x["kind"] for x in recs}
    assert {"commit", "message", "table"} <= kinds and r["records"] == len(recs)
    owner = [x for x in recs if x["source"].startswith("claude") and x["role"] == "owner"]
    assert owner[0]["text"] == "The Smart Lab is my thesis project."        # IDE noise stripped
    assert owner[0]["time"] == "2026-09-24T17:00:00Z" and owner[0]["conversation"].startswith("Claude Code session")
    a = [x for x in recs if x["role"] == "assistant" and x["source"].startswith("claude")]
    assert a and a[0]["text"] == "I propose a FastAPI backend."               # tool calls skipped


def test_secret_from_env_file_is_redacted_everywhere(env):
    history.run_import(env)
    history.pages(env)
    blob = open(os.path.join(env["data"], "history", "records.jsonl"), encoding="utf-8").read()
    for dp, _, fn in os.walk(env["vault"]):
        for n in fn:
            blob += open(os.path.join(dp, n), encoding="utf-8").read()
    assert SECRET not in blob and "REDACTED" in blob


def test_repeat_import_creates_no_duplicates(env):
    a = history.run_import(env)["records"]
    b = history.run_import(env)["records"]
    assert a == b and len(history.load_records(env)) == a


def test_chatgpt_export_order_roles_and_missing_timestamp(env):
    history.run_import(env)
    g = [x for x in history.load_records(env) if x["source"].startswith("chatgpt")]
    assert [x["role"] for x in g][:2] == ["owner", "assistant"]
    assert any(x.get("warning") == "no timestamp" for x in g)


def test_malformed_line_and_broken_file_are_recorded_not_fatal(env):
    open(os.path.join(env["data"], "..", "inbox_raw", "broken.json"), "w").write("{ nope")
    r = history.run_import(env)
    assert any(l["error"] for l in r["ledger"] if "broken.json" in l["source"])
    assert r["records"] > 0


def test_dry_run_writes_nothing(env):
    history.run_import(env, dry=True)
    assert not os.path.exists(os.path.join(env["data"], "history", "records.jsonl"))


def test_review_notes_keep_roles_apart_and_are_not_approved(env):
    history.run_import(env)
    history.pages(env)
    d = os.path.join(env["vault"], "13 - Automation Inbox", "History review")
    note = open(os.path.join(d, os.listdir(d)[0]), encoding="utf-8").read()
    assert "**Owner said**" in note and "approved: false" in note


def test_schema_dictionary_has_tables_and_foreign_keys(env):
    history.run_import(env)
    history.pages(env)
    dd = open(os.path.join(env["vault"], "06 - Database", "Database-Data-Dictionary.md"), encoding="utf-8").read()
    assert "`labs`" in dd and "`lab_id` -> `labs.id`" in dd and "labs ||--o{ bookings" in dd


def test_approve_marks_source(env):
    history.run_import(env)
    src = next(x["source"] for x in history.load_records(env) if x["source"].startswith("chatgpt"))
    history.approve(env, src)
    assert src in history.approved(env)
