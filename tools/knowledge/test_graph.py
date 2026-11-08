"""Native knowledge graph (graph.py): deterministic edges with evidence, safe failure."""
import json
import os
import subprocess

import graph


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tools" / "x").mkdir(parents=True)
    (repo / "tools" / "x" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "tools" / "x" / "user.py").write_text("import os\nfrom core import VALUE\n", encoding="utf-8")
    (repo / "tools" / "x" / "test_core.py").write_text("import core\n", encoding="utf-8")
    (repo / "tools" / "x" / "broken.py").write_text("def (:\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "first"], cwd=repo, check=True)
    data = tmp_path / "data"
    data.mkdir()
    srcs = {p: {"status": "present", "kind": "source-code", "sha256": "x"} for p in
            ("tools/x/core.py", "tools/x/user.py", "tools/x/test_core.py", "tools/x/broken.py", "docs/A.md")}
    (data / "registry.json").write_text(json.dumps({"sources": srcs}), encoding="utf-8")
    docs = [{"source": "docs/A.md", "heading": "Design", "kind": "documentation", "text": "see tools/x/core.py."},
            {"source": "chat #1", "heading": "Assistant proposed", "kind": "assistant-proposal", "text": "edit tools/x/user.py"}]
    (data / "index.json").write_text(json.dumps({"docs": docs}), encoding="utf-8")
    return {"repo": str(repo), "data": str(data)}


def test_edges_carry_evidence_and_honest_status(tmp_path):
    cfg = _repo(tmp_path)
    stats = graph.build(cfg)
    g = json.load(open(os.path.join(cfg["data"], "graph.json"), encoding="utf-8"))
    kinds = {(e["kind"], e["src"], e["dst"]): e for e in g["edges"]}
    assert kinds[("imports", "tools/x/user.py", "tools/x/core.py")]["evidence"] == "tools/x/user.py:2"
    assert ("tests", "tools/x/test_core.py", "tools/x/core.py") in kinds
    assert kinds[("mentions", "docs/A.md", "tools/x/core.py")]["status"] == "documented"
    assert kinds[("mentions", "chat #1", "tools/x/user.py")]["status"] == "proposal"   # never verified
    changed = [e for e in g["edges"] if e["kind"] == "changed"]
    assert changed and all(e["status"] == "historical" and e["evidence"].startswith("git:") for e in changed)
    assert stats["edges"] == len(g["edges"])


def test_rebuild_is_idempotent(tmp_path):
    cfg = _repo(tmp_path)
    graph.build(cfg)
    a = open(os.path.join(cfg["data"], "graph.json"), "rb").read()
    graph.build(cfg)
    assert open(os.path.join(cfg["data"], "graph.json"), "rb").read() == a


def test_failed_build_keeps_the_old_graph(tmp_path):
    cfg = _repo(tmp_path)
    graph.build(cfg)
    before = open(os.path.join(cfg["data"], "graph.json"), "rb").read()
    os.remove(os.path.join(cfg["data"], "index.json"))          # a source of the build disappears
    try:
        graph.build(cfg)
    except OSError:
        pass
    assert open(os.path.join(cfg["data"], "graph.json"), "rb").read() == before
    assert not [f for f in os.listdir(cfg["data"]) if f.endswith(".tmp")]


def test_related_without_a_graph_is_empty_not_an_error(tmp_path):
    assert graph.related({"data": str(tmp_path)}, "tools/x/core.py") == []
