#!/usr/bin/env python3
"""
Project history for the knowledge platform - local, read-only on every source.

    py tools/knowledge/history.py import            # all connectors -> data/history/records.jsonl
    py tools/knowledge/history.py import --dry-run  # count only, write nothing
    py tools/knowledge/history.py pages             # timeline, review digests, data dictionary, gaps
    py tools/knowledge/history.py approve <source>  # owner: let a reviewed source into search

Connectors (allowlist; nothing else is read):
  git        commits of every local branch (hash, date, author, subject, files changed)
  claude     Claude Code transcripts in ~/.claude/projects/*smart-lab*/ and the home project
             (owner text messages + assistant prose; tool calls / outputs are skipped)
  chatgpt    files placed in <knowledge>/inbox_raw/: ChatGPT exports (conversations.json) and
             decoded share pages (*.json written by the share decoder)
  schema     backend/app/models/tables.py (table / column names only - no data)

Every record keeps provenance (source, conversation, index, timestamp, role) and is redacted
before it is written. Conversation records are STAGED for owner review: they appear in the
vault's "13 - Automation Inbox/History review" and are not searchable until approved.
"Owner said" and "Assistant proposed" are kept apart; neither is treated as verified fact.
"""
from __future__ import annotations

import argparse
import ast
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kb  # noqa: E402

HOME = os.path.expanduser("~")


def secret_literals(cfg: dict) -> list[str]:
    """Values of secret-looking variables in the local secret files - used ONLY to redact, never printed."""
    out = []
    for rel in cfg.get("redact_from_files", [".env", "tools/security_vision/camera.env", "tools/robot_monitor/robot.env"]):
        p = os.path.join(cfg["repo"], rel)
        if not os.path.isfile(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            m = re.match(r"\s*(?:set\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", line)
            if not m:
                continue
            name, val = m.group(1).upper(), m.group(2).strip().strip('"').strip("'")
            if re.search(r"KEY|PASS|SECRET|TOKEN|SOURCE|DSN|URL", name) and len(val) >= 6:
                out.append(val)
                cred = re.match(r"\w+://([^:@/\s]+):([^@/\s]+)@", val)
                if cred:
                    out += [cred.group(2), cred.group(2).replace("%40", "@")]
    return sorted({x for x in out if len(x) >= 4}, key=len, reverse=True)


def redact(text: str) -> tuple[str, int]:
    t, kinds = kb.sanitise(text)
    return t, len(kinds)


def rid(*parts) -> str:
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:16]


# ------------------------------------------------------------- connectors ---
def from_git(cfg: dict) -> list[dict]:
    fmt = "%H%x1f%ad%x1f%an%x1f%s"
    r = subprocess.run(["git", "log", "--all", "--date=iso-strict", f"--format={fmt}", "--shortstat"],
                       cwd=cfg["repo"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    out, cur = [], None
    for line in r.stdout.splitlines():
        if "\x1f" in line:
            h, date, author, subj = line.split("\x1f", 3)
            cur = {"id": rid("git", h), "source": "git", "kind": "commit", "ref": h[:10], "time": date,
                   "role": "repository", "author": author, "text": subj, "status": "verified-historical"}
            out.append(cur)
        elif cur and "changed" in line:
            cur["files_changed"] = int(re.match(r"\s*(\d+)", line).group(1))
    return out


def claude_files() -> list[str]:
    base = os.path.join(HOME, ".claude", "projects")
    fs = glob.glob(os.path.join(base, "*smart-lab*", "*.jsonl")) + glob.glob(os.path.join(base, "C--Users-dell", "*.jsonl"))
    return sorted(set(fs))


IDE_TAGS = re.compile(r"<(ide_opened_file|ide_selection|system-reminder)>.*?</\1>", re.S)   # editor context, not the owner's words
SKIP_TEXT = re.compile(r"^\s*<(system-reminder|command-|local-command|task-notification)|^\s*\[Request interrupted")


def from_claude(path: str) -> list[dict]:
    sess = os.path.basename(path)[:8]
    out, n = [], 0
    for line in open(path, encoding="utf-8", errors="ignore"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        typ = d.get("type")
        if typ not in ("user", "assistant") or d.get("isMeta") or d.get("isCompactSummary"):
            continue
        c = (d.get("message") or {}).get("content")
        if isinstance(c, str):
            texts = [c]
        elif isinstance(c, list):
            texts = [x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"]
        else:
            continue
        text = IDE_TAGS.sub("", "\n".join(t for t in texts if t and not SKIP_TEXT.match(t))).strip()
        if not text or text.startswith("This session is being continued from a previous conversation"):
            continue
        n += 1
        out.append({"id": rid("claude", sess, d.get("uuid") or n), "source": f"claude:{sess}", "kind": "message",
                    "conversation": f"Claude Code session {sess}", "index": n, "time": d.get("timestamp"),
                    "role": "owner" if typ == "user" else "assistant", "text": text, "status": "reported"})
    return out


def from_chatgpt(path: str) -> list[dict]:
    d = json.load(open(path, encoding="utf-8"))
    convs = d if isinstance(d, list) else [d]
    out = []
    for conv in convs:
        title = conv.get("title") or os.path.basename(path)
        msgs = conv.get("messages")
        if msgs is None and "mapping" in conv:             # official export format
            msgs = []
            for node in conv["mapping"].values():
                m = node.get("message") or {}
                parts = (m.get("content") or {}).get("parts") or []
                msgs.append({"role": (m.get("author") or {}).get("role"), "time": m.get("create_time"),
                             "text": "\n".join(p for p in parts if isinstance(p, str))})
            msgs.sort(key=lambda m: (m.get("time") is None, m.get("time") or 0))   # untimed last, not first
        key = rid("chatgpt", title, os.path.basename(path))[:8]
        for i, m in enumerate(msgs or []):
            if m.get("role") not in ("user", "assistant") or not (m.get("text") or "").strip():
                continue
            t = m.get("time")
            iso = datetime.fromtimestamp(t, timezone.utc).isoformat() if isinstance(t, (int, float)) else None
            out.append({"id": rid("chatgpt", title, i, m["text"][:200]), "source": f"chatgpt:{key}", "kind": "message",
                        "conversation": f"ChatGPT - {title}", "index": i, "time": iso,
                        "role": "owner" if m["role"] == "user" else "assistant", "text": m["text"], "status": "reported",
                        **({} if iso else {"warning": "no timestamp"})})
    return out


def from_schema(cfg: dict) -> list[dict]:
    p = os.path.join(cfg["repo"], "backend", "app", "models", "tables.py")
    tree = ast.parse(open(p, encoding="utf-8").read())
    out = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        table, cols, doc = None, [], ast.get_docstring(node) or ""
        for st in node.body:
            if isinstance(st, ast.Assign) and getattr(st.targets[0], "id", "") == "__tablename__":
                table = getattr(st.value, "value", None)
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                src = ast.get_source_segment(open(p, encoding="utf-8").read(), st) or ""
                if "mapped_column" in src:
                    fk = re.search(r'ForeignKey\("([^"]+)"', src)
                    cols.append({"name": st.target.id, "fk": fk.group(1) if fk else None,
                                 "pk": "primary_key=True" in src})
        if table:
            out.append({"id": rid("schema", table), "source": "schema", "kind": "table", "ref": f"{node.name} line {node.lineno}",
                        "table": table, "class": node.name, "doc": doc.strip().split("\n\n")[0][:400], "columns": cols,
                        "time": None, "role": "repository", "text": doc[:200], "status": "verified-current"})
    return out


# ----------------------------------------------------------------- import ---
def run_import(cfg: dict, dry: bool = False) -> dict:
    kb.REDACT_LITERALS[:] = sorted(set(kb.REDACT_LITERALS) | set(secret_literals(cfg)), key=len, reverse=True)
    ledger, records = [], []
    sources = [("git", lambda: from_git(cfg), "git log --all")]
    for f in claude_files():
        sources.append((f"claude:{os.path.basename(f)[:8]}", lambda f=f: from_claude(f), f))
    for f in sorted(glob.glob(os.path.join(cfg["data"], "..", "inbox_raw", "*.json"))):
        sources.append((f"chatgpt-file:{os.path.basename(f)}", lambda f=f: from_chatgpt(f), f))
    sources.append(("schema", lambda: from_schema(cfg), "backend/app/models/tables.py"))
    for name, fn, path in sources:
        try:
            recs = fn()
            red = 0
            for r in recs:
                r["text"], k = redact(r.get("text", ""))
                red += k
            ledger.append({"source": name, "path": path.replace(HOME, "~"), "records": len(recs), "redactions": red,
                           "checksum": hashlib.sha256(open(path, "rb").read()).hexdigest()[:16] if os.path.isfile(path) else None,
                           "processed": kb.now_iso(), "error": None})
            records += recs
        except Exception as e:                         # a broken source is recorded, never silently lost
            ledger.append({"source": name, "path": path.replace(HOME, "~"), "records": 0, "error": f"{e.__class__.__name__}: {str(e)[:120]}",
                           "processed": kb.now_iso()})
    seen, uniq = set(), []
    for r in records:                                  # duplicate import -> one record
        if r["id"] not in seen:
            seen.add(r["id"])
            uniq.append(r)
    res = {"records": len(uniq), "duplicates_dropped": len(records) - len(uniq), "ledger": ledger}
    if dry:
        return res
    d = os.path.join(cfg["data"], "history")
    os.makedirs(d, exist_ok=True)
    kb.safe_write(os.path.join(d, "records.jsonl"), "\n".join(json.dumps(r, ensure_ascii=False) for r in uniq) + "\n", cfg["data"])
    kb.safe_write(os.path.join(d, "import_ledger.json"), json.dumps(res["ledger"], indent=1), cfg["data"])
    return res


def load_records(cfg: dict) -> list[dict]:
    p = os.path.join(cfg["data"], "history", "records.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.isfile(p) else []


def approved(cfg: dict) -> set:
    p = os.path.join(cfg["data"], "history", "approved_sources.json")
    return set(json.load(open(p, encoding="utf-8"))) if os.path.isfile(p) else set()


# ------------------------------------------------------------------ pages ---
def day(t):
    return (t or "")[:10] or "undated"


def pages(cfg: dict) -> dict:
    recs, v, now = load_records(cfg), cfg["vault"], kb.now_iso()
    commits = sorted((r for r in recs if r["kind"] == "commit"), key=lambda r: r["time"])
    msgs = [r for r in recs if r["kind"] == "message"]
    tables = [r for r in recs if r["kind"] == "table"]
    written = []

    # Timeline: commits (verified) + conversation activity per day (counts only, details in review)
    by_day = defaultdict(lambda: {"commits": [], "owner": 0, "assistant": 0, "sources": set()})
    for c in commits:
        by_day[day(c["time"])]["commits"].append(c)
    for m in msgs:
        b = by_day[day(m["time"])]
        b["owner" if m["role"] == "owner" else "assistant"] += 1
        b["sources"].add(m["conversation"])
    lines = [kb.fm(type="timeline", generated=True, updated=now, sources=["git log --all", "conversation records (counts)"]),
             "# Project timeline\n",
             "> Generated. Commits are **verified historical** (from git). Conversation counts show when the project "
             "was discussed; what was said is in *History review* until you approve it.\n"]
    for dname in sorted(by_day):
        b = by_day[dname]
        lines.append(f"## {dname}")
        if b["owner"] or b["assistant"]:
            lines.append(f"- Conversations: {b['owner']} owner / {b['assistant']} assistant messages in "
                         + ", ".join(sorted(b["sources"])))
        for c in b["commits"]:
            lines.append(f"- `{c['ref'][:7]}` {c['text'][:140]}" + (f" ({c.get('files_changed')} files)" if c.get("files_changed") else ""))
        lines.append("")
    kb.safe_write(os.path.join(v, "00 - Home", "Project-Timeline.md"), "\n".join(lines), v); written.append("Project-Timeline")

    # Review digests: one note per conversation, chronological, roles kept apart
    rdir = os.path.join(v, "13 - Automation Inbox", "History review")
    convs = defaultdict(list)
    for m in msgs:
        convs[m["conversation"]].append(m)
    ok = approved(cfg)
    for name, ms in convs.items():
        ms.sort(key=lambda m: (m["time"] or "", m["index"]))
        src = ms[0]["source"]
        out = [kb.fm(type="history-review", source=src, conversation=name, messages=len(ms),
                     first=ms[0]["time"], last=ms[-1]["time"], approved=src in ok, generated=True, updated=now),
               f"# {name}\n",
               "> Imported locally, redacted. **Owner said** = your words. **Assistant proposed** = suggestions, not "
               "verified facts. Not searchable until approved: `py tools\\knowledge\\history.py approve " + src + "`\n"]
        cur = None
        for m in ms:
            if day(m["time"]) != cur:
                cur = day(m["time"])
                out.append(f"\n## {cur}\n")
            who = "**Owner said**" if m["role"] == "owner" else "*Assistant proposed*"
            body = m["text"] if m["role"] == "owner" else m["text"][:600] + (" …" if len(m["text"]) > 600 else "")
            out.append(f"{who} ({(m['time'] or '')[11:16]}, #{m['index']}):\n{body.strip()}\n")
        kb.safe_write(os.path.join(rdir, kb.note_name(name) + ".md"), "\n".join(out), v); written.append(name)

    # Data dictionary from the models (verified current, names only)
    dd = [kb.fm(type="data-dictionary", generated=True, updated=now, source_path="backend/app/models/tables.py"),
          "# Database data dictionary\n", "> Generated from the SQLAlchemy models (structure only, no data). "
          f"{len(tables)} tables. Migrations: `backend/alembic/versions/`.\n"]
    for t in sorted(tables, key=lambda t: t["table"]):
        dd.append(f"## `{t['table']}` ({t['class']}, {t['ref']})")
        if t["doc"]:
            dd.append(t["doc"].replace("\n", " ") + "\n")
        dd += [f"- `{c['name']}`" + (" (primary key)" if c["pk"] else "") + (f" -> `{c['fk']}`" if c["fk"] else "") for c in t["columns"]]
        dd.append("")
    erd = ["```mermaid", "erDiagram"]
    for t in tables:
        for c in t["columns"]:
            if c["fk"]:
                erd.append(f"  {c['fk'].split('.')[0]} ||--o{{ {t['table']} : {c['name']}")
    erd.append("```")
    dd[3:3] = ["## Relationships (foreign keys)", *erd, ""]
    kb.safe_write(os.path.join(v, "06 - Database", "Database-Data-Dictionary.md"), "\n".join(dd), v); written.append("Database-Data-Dictionary")

    # Gaps
    ledger = json.load(open(os.path.join(cfg["data"], "history", "import_ledger.json"), encoding="utf-8"))
    first_msg = min((m["time"] for m in msgs if m["time"]), default=None)
    gaps = [kb.fm(type="gaps", generated=True, updated=now), "# Missing history and knowledge gaps\n",
            f"Earliest conversation record found: **{first_msg or 'none'}**. First commit: **{commits[0]['time'] if commits else 'none'}**.\n",
            "## Known missing", "- Any ChatGPT chat not shared yet: put its decoded share JSON or a `conversations.json` "
            "export in `C:\\Users\\dell\\SmartLabKnowledge\\inbox_raw`, then run `history.py import`.",
            "- Screenshots shared in the first Claude Code session (24 Sep): only their file names are in the transcript.",
            "- Live database contents: not read (only the model definitions).", "- Application logs: no log files found in the repository.",
            "", "## Import ledger", "| Source | Records | Redactions | Error |", "|---|---|---|---|"] + [
            f"| {l['source']} | {l['records']} | {l.get('redactions', '-')} | {l.get('error') or ''} |" for l in ledger]
    kb.safe_write(os.path.join(v, "00 - Home", "Missing-History-and-Knowledge-Gaps.md"), "\n".join(gaps) + "\n", v)
    written.append("Missing-History")
    return {"written": len(written), "conversations": len(convs), "commits": len(commits), "tables": len(tables)}


def approve(cfg: dict, source: str) -> None:
    ok = approved(cfg) | {source}
    kb.safe_write(os.path.join(cfg["data"], "history", "approved_sources.json"), json.dumps(sorted(ok)), cfg["data"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["import", "pages", "approve"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = kb.load_config(a.config)
    if a.cmd == "import":
        r = run_import(cfg, a.dry_run)
        print(json.dumps({"records": r["records"], "duplicates_dropped": r["duplicates_dropped"],
                          "sources": [{k: l.get(k) for k in ("source", "records", "redactions", "error")} for l in r["ledger"]]}, indent=1))
    elif a.cmd == "pages":
        print(json.dumps(pages(cfg)))
    elif a.cmd == "approve":
        approve(cfg, a.arg)
        print(f"approved {a.arg} - it will be searchable after the next kb.py build")


if __name__ == "__main__":
    sys.exit(main())
