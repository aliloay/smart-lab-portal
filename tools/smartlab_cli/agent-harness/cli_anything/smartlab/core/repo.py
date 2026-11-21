"""Read-only views over the Smart Lab repository: n8n workflow definitions, firmware versions, logs, reports, git."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..utils.errors import InvalidInput, NotFound, SmartlabError
from ..utils.redaction import redact_text


def _need_repo(repo: Optional[Path]) -> Path:
    if not repo:
        raise SmartlabError("Smart Lab repository not found.",
                            "Run inside the repo, or set SMARTLAB_REPO (or 'repo' in ~/.smartlab/config.json).")
    return repo


# --------------------------------------------------------------------------------------------- n8n --
def _trigger(n: dict) -> Optional[str]:
    t = n.get("type", "").split(".")[-1]
    p = n.get("parameters", {}) or {}
    if t == "scheduleTrigger":
        iv = (p.get("rule") or {}).get("interval") or [{}]
        i = iv[0] if iv else {}
        if i.get("field") == "cronExpression":
            return f"cron {i.get('expression')}"
        parts = [f"{k}={v}" for k, v in i.items() if k in ("field", "minutesInterval", "hoursInterval",
                                                            "triggerAtHour", "triggerAtMinute", "triggerAtDay")]
        return "schedule " + (" ".join(parts) or "default")
    if t == "webhook":
        return f"webhook /{p.get('path', '')}"
    if "trigger" in t.lower():
        return t
    return None


def workflows(repo: Optional[Path]) -> list[dict]:
    """Workflow DEFINITIONS from the repo copies (automation/n8n/json). Never calls the live n8n."""
    base = _need_repo(repo) / "automation" / "n8n" / "json"
    rows = []
    for f in sorted(base.rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict) or "nodes" not in d:
            continue
        trig = [t for t in (_trigger(n) for n in d["nodes"]) if t]
        http = [n for n in d["nodes"] if n.get("type", "").endswith("httpRequest")]
        rows.append({"id": d.get("id"), "name": d.get("name"), "file": f.relative_to(base).as_posix(),
                     "nodes": len(d["nodes"]), "triggers": "; ".join(trig) or "-", "http_calls": len(http),
                     "active_in_copy": d.get("active")})
    return rows


def workflow(repo: Optional[Path], key: str) -> dict:
    for w in workflows(repo):
        if key.lower() in ((w["id"] or "").lower(), (w["name"] or "").lower(), w["file"].lower()) or \
           key.lower() in (w["name"] or "").lower():
            f = _need_repo(repo) / "automation" / "n8n" / "json" / w["file"]
            d = json.loads(f.read_text(encoding="utf-8"))
            nodes = [{"name": n.get("name"), "type": n.get("type", "").split(".")[-1]} for n in d["nodes"]]
            urls = sorted({redact_text(str((n.get("parameters") or {}).get("url", ""))) for n in d["nodes"]
                           if n.get("type", "").endswith("httpRequest")} - {""})
            return {**w, "node_list": nodes, "endpoints_called": urls,
                    "note": "definition from the repo copy; the live n8n is not queried or run"}
    raise NotFound(f"No workflow matching {key!r}", "List them with: smartlab automation list")


# ---------------------------------------------------------------------------------------- firmware --
_FW_PATTERNS = [
    re.compile(r'#define\s+FIRMWARE_VERSION\s+"([^"]+)"'),
    re.compile(r'FIRMWARE_VERSION\s*=\s*"([^"]+)"'),
    re.compile(r'const\s+char\s*\*\s*FIRMWARE\s*=\s*"([^"]+)"'),
    re.compile(r'\\"firmware_version\\":\\"([^\\"]+)\\"'),
    re.compile(r'"firmware_version":"([^"]+)"'),
]


def firmware(repo: Optional[Path]) -> list[dict]:
    """Version strings declared in each firmware source folder (build/ artefacts ignored)."""
    base = _need_repo(repo) / "firmware"
    rows = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        found = None
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() not in (".ino", ".h", ".cpp") or "build" in f.parts:
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for pat in _FW_PATTERNS:
                m = pat.search(txt)
                if m:
                    found = (m.group(1), f.relative_to(base).as_posix())
                    break
            if found:
                break
        rows.append({"folder": d.name, "version": found[0] if found else None,
                     "declared_in": found[1] if found else None})
    return rows


def _norm(v: Optional[str]) -> str:
    return re.sub(r"^[a-z\-]*?(\d)", r"\1", (v or "").lower()).strip()


def firmware_compare(repo: Optional[Path], devices: list[dict]) -> list[dict]:
    """Source version vs what each ESP32 reports to the portal."""
    src = [r for r in firmware(repo) if r["version"]]
    out = []
    for d in devices:
        rep = d.get("firmware")
        match = next((s for s in src if rep and (s["version"] == rep or _norm(s["version"]) == _norm(rep))), None)
        out.append({"uid": d["uid"], "type": d["type"], "reported": rep,
                    "source_folder": match["folder"] if match else None,
                    "matches_source": bool(match) if rep else None})
    return out


# -------------------------------------------------------------------------------------------- logs --
def logs_list(repo: Optional[Path], serial_log: Optional[Path]) -> list[dict]:
    rows = []
    cands = []
    if repo:
        cands += [repo / "logs" / "watchdog.jsonl"]
        cands += sorted((repo / "logs").glob("*.log")) if (repo / "logs").is_dir() else []
    if serial_log:
        cands.append(serial_log)
    for p in cands:
        if p.is_file():
            st = p.stat()
            rows.append({"log": p.name, "path": str(p), "size_kb": round(st.st_size / 1024),
                         "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")})
    return rows


def logs_tail(path: Path, lines: int = 40, errors_only: bool = False) -> list[str]:
    if lines < 1 or lines > 2000:
        raise InvalidInput("lines must be 1..2000")
    if not path.is_file():
        raise NotFound(f"log not found: {path}")
    size = path.stat().st_size
    with open(path, "rb") as f:
        f.seek(max(0, size - 400_000))
        text = f.read().decode("utf-8", "replace").splitlines()
    pat = re.compile(r"(?i)\b(error|fail|failed|exception|traceback|timeout|offline|down|silent|warn)")
    sel = [l for l in text if pat.search(l)] if errors_only else text
    return [redact_text(l) for l in sel[-lines:]]


# ----------------------------------------------------------------------------------------- reports --
def reports(repo: Optional[Path], limit: int = 20) -> list[dict]:
    r = _need_repo(repo)
    files = [p for base in (r / "docs" / "reports", r / "reports", r / "docs" / "benchmarks") if base.is_dir()
             for p in base.rglob("*.md")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"report": p.name, "path": p.relative_to(r).as_posix(),
             "modified": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
             "size_kb": round(p.stat().st_size / 1024, 1)} for p in files[:limit]]


def report_read(repo: Optional[Path], rel: str, max_chars: int = 6000) -> dict:
    r = _need_repo(repo).resolve()
    p = (r / rel).resolve()
    if r not in p.parents or p.suffix.lower() != ".md":
        raise InvalidInput("only .md files inside the repository can be read")
    if not p.is_file():
        raise NotFound(f"no such report: {rel}")
    txt = p.read_text(encoding="utf-8", errors="replace")
    return {"path": p.relative_to(r).as_posix(), "chars": len(txt), "truncated": len(txt) > max_chars,
            "text": redact_text(txt[:max_chars])}


# --------------------------------------------------------------------------------------------- git --
def _git(repo: Path, *args: str) -> str:
    exe = shutil.which("git")
    if not exe:
        raise SmartlabError("git not found on PATH")
    r = subprocess.run([exe, "-C", str(repo), *args], capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        raise SmartlabError(f"git {' '.join(args)} failed: {r.stderr.strip()[:200]}")
    return r.stdout


def git_status(repo: Optional[Path]) -> dict:
    r = _need_repo(repo)
    branch = _git(r, "rev-parse", "--abbrev-ref", "HEAD").strip()
    head = _git(r, "log", "-1", "--format=%h %ad %s", "--date=short").strip()
    porcelain = [l for l in _git(r, "status", "--porcelain").splitlines() if l.strip()]
    out: dict[str, Any] = {"branch": branch, "head": head,
                           "modified": sum(1 for l in porcelain if not l.startswith("??")),
                           "untracked": sum(1 for l in porcelain if l.startswith("??"))}
    try:
        out["ahead_of_origin_main"] = int(_git(r, "rev-list", "--count", "origin/main..HEAD").strip())
        out["behind_origin_main"] = int(_git(r, "rev-list", "--count", "HEAD..origin/main").strip())
        out["note"] = "compared with the last fetched origin/main (no network fetch is done)"
    except SmartlabError:
        out["ahead_of_origin_main"] = None
    return out


def git_branches(repo: Optional[Path]) -> list[dict]:
    r = _need_repo(repo)
    rows = []
    for line in _git(r, "for-each-ref", "--sort=-committerdate", "--format=%(refname:short)\t%(committerdate:short)\t%(subject)",
                     "refs/heads").splitlines()[:30]:
        n, d, s = (line.split("\t") + ["", ""])[:3]
        rows.append({"branch": n, "date": d, "last_commit": s[:70]})
    wt = [l.split(" ", 1)[1] for l in _git(r, "worktree", "list", "--porcelain").splitlines() if l.startswith("worktree ")]
    return rows + [{"branch": "(worktree)", "date": "", "last_commit": p} for p in wt]


def git_compare(repo: Optional[Path], base: str = "origin/main", limit: int = 30) -> dict:
    r = _need_repo(repo)
    if not re.fullmatch(r"[A-Za-z0-9._/\-]{1,100}", base):
        raise InvalidInput("invalid ref name")
    commits = [l for l in _git(r, "log", "--oneline", f"{base}..HEAD").splitlines()]
    files = [l for l in _git(r, "diff", "--name-only", f"{base}..HEAD").splitlines()]
    return {"base": base, "commits_ahead": len(commits), "files_changed": len(files),
            "latest_commits": commits[:limit], "note": "local refs only; run 'git fetch' yourself to refresh origin"}
