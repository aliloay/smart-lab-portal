# Graphify assessment for Smart Lab Knowledge - 2026-10-14

Read-only evaluation: README, `pyproject.toml` and `ARCHITECTURE.md` of
https://github.com/Graphify-Labs/graphify (branch `v8`) read over the web. **Nothing installed, no script run,
no project data sent anywhere.** Claims below marked *(README)* are the project's own words, not verified by running it.

## 1. Current platform (verified in this repo)
* Vault `C:\Users\dell\SmartLabKnowledge\vault` (Markdown, human source of truth) + private data dir.
* `tools/knowledge/kb.py`: source registry, redaction, 6,285 chunks, BM25 + `nomic-embed-text` hybrid search
  (embeddings built 2026-10-14 in 34 min), health/drift, backup/verify-restore, eval.
* `history.py`: git, Claude transcripts, ChatGPT share imports, owner review gate, timeline, gaps page.
* `agent.py`: lookup/answer/investigate routes, evidence labels (VERIFIED_CURRENT, DOCUMENTED, TESTED, HISTORICAL,
  REPORTED, PROPOSAL), read-only tools, citations, qwen2.5:1.5b on CPU; `serve.py` + portal "Project knowledge".
* Tests: 36 knowledge tests pass. Gaps: no explicit relationship layer (file↔commit↔bug↔test↔workflow), only wikilinks.

## 2. Verified findings about Graphify
| Question | Finding | Source |
|---|---|---|
| What it does | "Turn any codebase, with its docs, SQL schemas, configs, and PDFs, into a queryable knowledge graph"; ships as an assistant skill + `graphify` CLI + `graphify-mcp` | README, pyproject `[project.scripts]` |
| Graph construction | stages `detect → extract → build → cluster → analyze → report → export`; NetworkX graphs | ARCHITECTURE.md |
| Code | tree-sitter AST, "deterministic, no LLM, nothing leaves your machine" | README |
| Markdown / docs / PDFs | go through a **semantic pass by an LLM** (your assistant, or a backend: Ollama, Claude, OpenAI, Gemini, ...). Not parsed locally into facts | README; ARCHITECTURE does not describe local Markdown parsing |
| Conversations | no ChatGPT/Claude-transcript importer found in the docs read | - |
| Provenance | node: `source_file`, `source_location` ("L42"); edge confidence `EXTRACTED` / `INFERRED` / `AMBIGUOUS` | ARCHITECTURE.md |
| Incremental | AST + semantic cache, schema versions, `watch.py` rebuild on change; dedup only language-specific, no general dedup pass | ARCHITECTURE.md |
| Embeddings / cloud | "No embeddings, no vector store"; code-only "runs fully offline"; `--backend ollama` "fully local"; Graphify Cloud is a separate product | README |
| Telemetry | "No telemetry"; but **queries logged to `~/.cache/graphify-queries.log` by default** (`GRAPHIFY_QUERY_LOG_DISABLE=1`) | README |
| Dependencies | Python ≥3.10; core: networkx, numpy, rapidfuzz, **~28 tree-sitter grammar packages** (pinned ranges); extras for ollama (`openai` client), pdf, mcp, ... | pyproject.toml |
| Licence | Apache-2.0 and MIT files | repo |
| Maintenance | page shows 2,379 commits, 673 open issues, 804 open PRs; star count shown is unusually high - not relied on | repo page (unverified) |
| Runtime / memory / GPU | **not documented** in what was read; unknown until measured | - |

## 3. Options
| | Gains | Costs / risks |
|---|---|---|
| A. keep as is | nothing new; works, tested | relationships stay implicit |
| B. Graphify layer | code call/import graph for free (offline, tree-sitter) | Markdown - most of our evidence - needs an LLM pass: on this CPU (1.5B model, ~10 s a call) thousands of chunks = hours, and every edge is `INFERRED` by a small model; 30 new packages on Python 3.14 (wheel availability unverified); query log to disable; no conversation/n8n/DB-schema/test-result model; no status vocabulary like ours |
| C. native graph from our own pipeline | edges built **deterministically** from data we already parse: doc→wikilink, doc→file path, commit→file, test→module, workflow→node→endpoint, schema table→FK, history record→commit; every edge carries the exact citation + our status labels; no new dependency; incremental via existing source hashes | ~1-2 days work; no code call graph unless we add Python `ast` (stdlib) for our own Python |
| D. B + current RAG | code graph + our retrieval | all of B's costs; two systems to maintain |

## 4. Recommendation: **C**, with optional B in `--code-only` mode later
Our hardest questions (why was the re-ID bug happening, which fix was tested, which workflows drift, what is planned vs
implemented) are answered by docs, commits, tests and n8n state - exactly the material Graphify only handles through an
LLM. A native graph gives the same "follow the links" retrieval with deterministic edges, our evidence statuses
(verified_current ... superseded, unknown) and exact citations, and zero new dependencies. If a code call graph proves
useful, Graphify `--code-only` can be trialled separately (offline, no key) after approval.

## 5. Approval needed before anything is installed (none requested yet)
* Option C: no install. Needs only your go-ahead to build it.
* Option B trial: `uv tool install graphifyy` (or pipx) into an **isolated tool env** - ~30 packages; run
  `graphify extract --code-only` on a copy of `backend/` + `tools/` with `GRAPHIFY_QUERY_LOG_DISABLE=1`, output to scratch.

## 6. Plan for C and rollback
Files: `tools/knowledge/graph.py` (new: build edges from registry/history/n8n inventory/alembic models/tests),
`kb.py` (build step + `graph` command), `agent.py` (investigate route: expand evidence by 1 hop, still cite sources),
`test_graph.py` (new), `docs/knowledge-platform/README.md`. Output: `data/graph.json` (derived, rebuildable).
Failure isolation: graph build writes a temp file then renames; search falls back to hybrid when the graph is missing.
Rollback: delete `data/graph.json`, `git revert` the commit. Vault never written by the graph build.

## 7. Evaluation set and acceptance
Questions: original project goal; implemented devices/services; re-ID bug cause; tested fix + evidence; repo vs live n8n
drift; supported vs prohibited robot functions; planned vs implemented; missing history.
Measure per question: relevant sources in top 6 (with/without graph), citation correctness, factual accuracy (by hand),
abstention when evidence is missing, latency, memory, rebuild time after one changed file.
Accept C if: source recall improves on ≥3 of 8 questions, no accuracy loss, latency +<300 ms, all existing tests pass.
