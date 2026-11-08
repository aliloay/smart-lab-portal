"""
Smart Lab knowledge graph - native, deterministic, no new dependencies (owner-approved 2026-10-14,
see docs/knowledge-platform/GRAPHIFY_ASSESSMENT.md option C).

Every edge is EXTRACTED from something we can point at - never guessed by a model:

    imports     python file -> python file      `import` / `from` line         (ast, stdlib)
    tests       test file   -> module            a test file's import line
    changed     commit      -> file              `git log --name-only`
    mentions    doc chunk   -> file              the path written in the document text
    calls_api   n8n workflow -> backend route    /api/<prefix> in the workflow's HTTP nodes

Each edge: {"src", "dst", "kind", "evidence": "path:line" | "git:<sha>" | "doc:<path>#<heading>",
"status": "verified_current" (read from the files now) | "historical" (git) | for mentions, the trust
of the text they appear in: documented, tested, reported_unverified (owner said), proposal (assistant)}.
A relationship is a pointer to evidence, not proof that a claim is true.

Output: <data>/graph.json, written to a temp file and renamed (a failed build leaves the old graph).
Built from the registry's current sources; rebuild is idempotent (same inputs -> same file).
Nothing here runs commands from the content, touches the vault, devices, the database or n8n.

    py tools/knowledge/graph.py build
    py tools/knowledge/graph.py related backend/app/api/routes/robots.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kb  # noqa: E402

PATH_RE = re.compile(r"(?<![\w/.-])((?:backend|frontend|tools|firmware|automation|docs|scripts)/[\w./-]+\.\w{1,5})")


# A mention is only as trustworthy as the text it is written in.
MENTION_STATUS = {"source-code": "verified_current", "test-code": "verified_current", "n8n-workflow": "verified_current",
                  "documentation": "documented", "benchmark-report": "tested", "git-commit": "historical",
                  "owner-statement": "reported_unverified", "assistant-proposal": "proposal"}


def _sources(cfg) -> dict:
    reg = json.load(open(os.path.join(cfg["data"], "registry.json"), encoding="utf-8"))
    return {k: v for k, v in reg["sources"].items() if v.get("status") == "present"}


TRACKED_RE = re.compile(r"^(backend|frontend/src|tools|firmware|automation/n8n/json|docs|scripts)/.+\.(py|ts|tsx|md|json|ino|h|cpp)$")


def _tracked(repo) -> list:
    """Git-tracked code/doc paths under the project folders (paths only; .env etc. are not tracked)."""
    try:
        r = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    return [p for p in r.stdout.splitlines() if TRACKED_RE.match(p) and "node_modules" not in p]


def _module_index(paths) -> dict:
    """dotted module name -> repo path, for the python files we know."""
    idx = {}
    for p in paths:
        if not p.endswith(".py"):
            continue
        parts = p[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        for i in range(len(parts)):                      # app.api.routes.robots, robots, ...
            idx.setdefault(".".join(parts[i:]), p)
    return idx


def python_edges(repo, paths) -> list:
    idx, out = _module_index(paths), []
    for p in sorted(x for x in paths if x.endswith(".py")):
        try:
            tree = ast.parse(open(os.path.join(repo, p), encoding="utf-8").read())
        except (OSError, SyntaxError, ValueError):
            continue
        is_test = os.path.basename(p).startswith("test_")
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for n in names:
                dst = idx.get(n)
                if dst and dst != p:
                    out.append({"src": p, "dst": dst, "kind": "tests" if is_test else "imports",
                                "evidence": f"{p}:{node.lineno}", "status": "verified_current"})
    return out


def git_edges(repo, paths, limit=400) -> list:
    try:
        log = subprocess.run(["git", "log", f"-{limit}", "--name-only", "--format=@@%h %ad %s", "--date=short"],
                             cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    out, sha, label = [], None, ""
    for line in log.splitlines():
        if line.startswith("@@"):
            sha, label = line[2:].split(" ", 1)[0], line[2:]
        elif line.strip() in paths and sha:
            out.append({"src": f"commit:{sha}", "dst": line.strip(), "kind": "changed", "evidence": f"git:{sha}",
                        "status": "historical", "label": label[:140]})
    return out


def doc_edges(cfg, paths) -> list:
    idx = json.load(open(os.path.join(cfg["data"], "index.json"), encoding="utf-8"))
    out, seen = [], set()
    for d in idx["docs"]:
        for m in PATH_RE.findall(d["text"]):
            m = m.rstrip(".")
            if m in paths and m != d["source"] and (d["source"], m) not in seen:
                seen.add((d["source"], m))
                out.append({"src": d["source"], "dst": m, "kind": "mentions",
                            "evidence": f"doc:{d['source']}#{d.get('heading') or ''}"[:200],
                            "status": MENTION_STATUS.get(d.get("kind"), "unknown")})
    return out


def workflow_edges(repo, paths) -> list:
    out = []
    for p in sorted(x for x in paths if x.startswith("automation/n8n/json/") and x.endswith(".json")):
        try:
            wf = kb.parse_workflow(open(os.path.join(repo, p), encoding="utf-8").read())
        except Exception:                                 # malformed export: skip, never fail the build
            continue
        for dst in sorted(kb.route_files(wf, paths)):
            out.append({"src": p, "dst": dst, "kind": "calls_api", "evidence": p, "status": "verified_current"})
    return out


def build(cfg=None) -> dict:
    cfg = cfg or kb.load_config()
    src = _sources(cfg)
    for p in _tracked(cfg["repo"]):                    # code the registry does not index (e.g. tools/knowledge)
        src.setdefault(p, {"kind": "tracked-file", "sha256": None})
    paths = set(src)
    edges = (python_edges(cfg["repo"], paths) + workflow_edges(cfg["repo"], paths)
             + doc_edges(cfg, paths) + git_edges(cfg["repo"], paths))
    edges.sort(key=lambda e: (e["kind"], e["src"], e["dst"], e["evidence"]))
    uniq, seen = [], set()
    for e in edges:
        k = (e["kind"], e["src"], e["dst"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    nodes = {p: {"kind": v.get("kind"), "sha256": v.get("sha256")} for p, v in sorted(src.items())}
    g = {"version": 1, "sources_policy": "registry present sources only", "nodes": nodes, "edges": uniq}
    path = os.path.join(cfg["data"], "graph.json")
    fd, tmp = tempfile.mkstemp(dir=cfg["data"], prefix=".graph-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(g, f, indent=0, sort_keys=True)
    os.replace(tmp, path)
    counts = defaultdict(int)
    for e in uniq:
        counts[e["kind"]] += 1
    return {"nodes": len(nodes), "edges": len(uniq), **counts}


_cache: dict = {}


def load(cfg) -> dict | None:
    path = os.path.join(cfg["data"], "graph.json")
    try:
        m = os.path.getmtime(path)
    except OSError:
        return None                                       # no graph: callers fall back to plain search
    if _cache.get("m") != m:
        g = json.load(open(path, encoding="utf-8"))
        by = defaultdict(list)
        for e in g["edges"]:
            by[e["src"]].append(e)
            by[e["dst"]].append(e)
        _cache.update(m=m, g=g, by=by)
    return _cache


def related(cfg, path: str, kinds=None, limit=12) -> list:
    """Edges touching `path` (1 hop), newest commits first, each with its evidence."""
    c = load(cfg)
    if not c:
        return []
    es = [e for e in c["by"].get(path, []) if not kinds or e["kind"] in kinds]
    es.sort(key=lambda e: (e["kind"] != "tests", e["kind"] == "changed", e["evidence"]))
    return es[:limit]


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    cfg = kb.load_config()
    if a[:1] == ["build"]:
        print(json.dumps(build(cfg)))
    elif a[:1] == ["related"] and len(a) == 2:
        for e in related(cfg, a[1], limit=40):
            other = e["dst"] if e["src"] == a[1] else e["src"]
            print(f"{e['kind']:9} {other:60} {e['status']:16} {e['evidence']}  {e.get('label', '')}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
