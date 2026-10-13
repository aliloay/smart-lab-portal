# Knowledge platform runbook

## Set up (once)

1. `copy tools\knowledge\config.example.json tools\knowledge\config.json` (git-ignored).
   Optional: add `"redact_literals": ["<a password that appears in docs>"]` — removed from every note.
2. `py tools\knowledge\kb.py build` — scans, writes the vault, builds the index (~2–4 s).
3. Obsidian (when installed): *Open folder as vault* → `C:\Users\dell\SmartLabKnowledge\vault`.
   No community plugins are needed. Start at `00 - Home/Home.md`.

## Daily use

| Command | What it does |
|---|---|
| `py tools\knowledge\kb.py build` | incremental: only changed sources are re-processed; notes regenerated |
| `py tools\knowledge\kb.py search "question"` | evidence only, ~10–20 ms warm (no LLM) |
| `py tools\knowledge\kb.py ask "question"` | evidence + local LLM answer with [n] citations (24–68 s on CPU) |
| `py tools\knowledge\kb.py health` | broken links, stale generated notes, removed sources |
| `py tools\knowledge\kb.py drift` | workflow changes since the baseline; `--accept` makes the current state the baseline |
| `py tools\knowledge\kb.py eval` | evaluation set (`eval_questions.json`); `--no-llm` for retrieval only |

Generated folders (overwritten on build): `00 - Home`, `05 - n8n Workflows`, `12 - Generated Reports`,
`14 - Sources`. Your own folders (never overwritten): `07 - Runbooks`, `09 - Incidents and Lessons`,
`10 - Decisions`, `13 - Automation Inbox`, `99 - Templates`.

## Backup and restore

* `py tools\knowledge\kb.py backup` → `C:\Users\dell\SmartLabKnowledge\backups\knowledge-<time>.zip`
  (vault + registry + inventories, SHA-256 manifest; the index is rebuilt, not backed up). Old
  backups are never deleted by the tool.
* `py tools\knowledge\kb.py verify-restore` → restores the newest zip into a temp folder and
  compares every file with the manifest (verified 2026-10-13: 168 files, 0 mismatches).
* Full restore: unzip `vault/` and `data/` into `C:\Users\dell\SmartLabKnowledge`, then `kb.py build`.
* Removing the platform: delete `C:\Users\dell\SmartLabKnowledge` and `tools\knowledge\config.json`.
  Nothing else in the Smart Lab uses it.

## Approvals needed for the next steps (not done)

1. **Embedding model** for semantic search (e.g. a small Ollama embedding model): a model download.
   Then add vectors next to BM25 and re-run `kb.py eval` to prove it beats 9/10 hit@5.
2. **n8n workflows** (Source sync, Workflow catalogue, Health check, Weekly digest): n8n cannot
   run the host's Python by itself; options: (a) Windows Task Scheduler runs `kb.py build/health/drift`
   — simplest, no n8n change; (b) mount `C:\Users\dell\SmartLabKnowledge` into the n8n container
   (Docker Compose change). Created inactive, tested, then activated one by one.
3. **Live n8n read**: with n8n running, `docker compose exec n8n n8n export:workflow --all --output=...`
   into the private data folder (never the repo) for live-vs-file drift, and `n8n audit`.
4. **Obsidian install** (owner) — optional; the vault works as plain Markdown without it.
5. **LLM on the GPU** — only after a combined test with SecurityCam running.
