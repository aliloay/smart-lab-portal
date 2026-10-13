#!/usr/bin/env python3
"""
Weekly knowledge summary -> vault "12 - Generated Reports/Weekly digest <date>.md".
Facts only from local evidence: git (last 7 days), the latest health report, workflow drift,
index status. No LLM, no network.      py tools/knowledge/digest.py [--days 7]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kb  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args(argv)
    cfg = kb.load_config()
    since = (datetime.now() - timedelta(days=a.days)).strftime("%Y-%m-%d")
    log = subprocess.run(["git", "log", "--all", f"--since={since}", "--date=short", "--format=%h %ad %s"],
                         cwd=cfg["repo"], capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout.strip().splitlines()
    reg = json.load(open(os.path.join(cfg["data"], "registry.json"), encoding="utf-8"))
    health = kb.health(cfg, reg)
    try:
        drift = kb.drift(cfg)
    except FileNotFoundError:
        drift = {"new": [], "deleted": [], "changed": []}
    now = kb.now_iso()
    lines = [kb.fm(type="report", generated=True, updated=now, period=f"{since} to {now[:10]}",
                   sources=["git log --all", "registry.json", "Documentation health", "Workflow drift"]),
             f"# Weekly digest {now[:10]}\n",
             f"> Generated {now} from local evidence only (no AI). Period: {since} → {now[:10]}.\n",
             f"## Commits ({len(log)}) — verified historical"] + [f"- `{l[:7]}` {l[8:][:150]}" for l in log[:60]] + [
             "", "## Knowledge base",
             f"- Sources indexed: {sum(1 for s in reg['sources'].values() if s.get('status') == 'present')}",
             f"- Broken links: {len(health['broken_links'])} · stale notes: {len(health['stale_mirrors'])} · removed sources: {len(health['removed_sources'])}",
             "", "## n8n workflow drift (repo files vs live export)",
             f"- New: {drift['new'] or 'none'} · deleted: {drift['deleted'] or 'none'}"] + [
             f"- Changed: {c['name']} ({', '.join(c['what'])})" for c in drift["changed"]] + [
             "", "## Still open", "- See [[Pending-Approvals]] and [[Known-Bugs-and-Risks]] (curated, not regenerated here).", ""]
    path = os.path.join(cfg["vault"], "12 - Generated Reports", f"Weekly digest {now[:10]}.md")
    kb.safe_write(path, "\n".join(lines), cfg["vault"])
    print(json.dumps({"written": path, "commits": len(log)}))


if __name__ == "__main__":
    sys.exit(main())
