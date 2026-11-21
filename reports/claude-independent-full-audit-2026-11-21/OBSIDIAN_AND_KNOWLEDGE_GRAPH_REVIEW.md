# Obsidian and knowledge graph review

- **Vault:** `C:\Users\dell\SmartLabKnowledge\vault`.
- **Access:** read-only. Nothing was modified, and no index or job was triggered.
- **Scanner:** `scratchpad/vault_audit.py` resolves `[[target]]` by path, by basename, and with or without `.md`, in the way Obsidian does. Attachments are excluded.

## Measured state (19:20)

| Metric | Value |
|---|---|
| Notes (.md, excluding `.obsidian`) | **810** (historical: 806) |
| Folders | 14 – Sources 740 · 05 – n8n Workflows 27 · 13 – Automation Inbox 18 · 02 – Systems 9 · 01 – Project 5 · 12 – Generated Reports 4 · 00 – Home 3 · 99 – Templates 3 · 06 – Database 1 |
| Wikilinks | 4,646 |
| **Broken wikilinks** | **199 (182 unique)** |
| Notes with frontmatter | 810/810 |
| Notes with tags | 74 |
| Notes with no inbound link | 335 |
| Duplicate basenames | 0 |
| Oldest / newest file modification | 2026-10-13 22:40 / 2026-11-21 18:01 |
| Index (`/status`) | built 2026-11-21 18:01:37, 13,292 chunks, embeddings present |

### Why "0 broken links" (18 Nov) and 182 are both true

- The kb `health` job (`kb.py:877`) checks broken **relative links inside the mirrored docs**, plus stale mirrors and removed sources.
- It does not check Obsidian wikilinks in the curated notes. These are different metrics.

## Findings

1. **Recursive self-ingestion (F-07).**
   - The repo tracks a snapshot of the vault at `docs/knowledge/obsidian/vault/` (329 files).
   - The source sync mirrors repo docs into `14 – Sources`, so **322 notes are copies of vault notes**, for example `docs_knowledge_obsidian_vault_00 - Home_Home.md.md`.
   - Effect: duplicated chunks compete in top-k retrieval, and stale copies of "Current-Truth" notes can be cited.
   - Fix: exclude `docs/knowledge/obsidian/**` in the sync include rules.
2. **Broken links in curated notes:**
   - `02 – Systems/*.md` and `n8n automation.md` link to `automation_n8n_json_XX-*.json` notes that do not exist. The JSON workflows are not mirrored.
   - `Current-Truth.md` and `Pending-Approvals.md` link to `LAB_TEST_2026-10-14.md` by a name that does not resolve.
   - Fix: mirror `automation/n8n/json/*.json` as notes, or relink them to the `05 – n8n Workflows` notes.
3. **Session transcripts as sources.**
   - Retrieval cited "Claude Code session 3b9b3107 #1870 – Owner said 2026-10-14", labelled `REPORTED (owner said)`.
   - The labelling is good. Still, chat history can contain outdated statements: it should rank below `VERIFIED_CURRENT` repo files. It already shows the label.
4. **Tags are sparse** (74 of 810 notes). Discoverability relies on folder and search. This is acceptable for RAG and weak for graph browsing.
5. **Coverage:** code files are mirrored (`backend_app_api_routes_*.py.md`, firmware `.ino`), and so are docs and the 3 knowledge workflows. Missing: the n8n JSON (above).
6. **Freshness:** the index is 1 h older than the latest commits (`ebd6758`, `f32d7b3`, both docs/checkpoint only). Acceptable.

## Retrieval quality (measured, see `AI_LATENCY...`)

- **Lookup questions** returned the correct primary source in about 100 ms (reusable bin firmware; environment node IP).
- **Synthesis:**
  - 1 correct answer (env IP).
  - 1 partly wrong answer (stock formula), although the correct sources exist in the repo (`inventory.py`, bin notes).
  - 1 garbled comparison.
  - Duplicates from finding 1 plausibly dilute the context.
  - The small model (1.7B) on long contexts is the other factor.

## Are new notes required?

**Mostly no.** Priorities:

1. Remove the mirrors.
2. Mirror the n8n JSON, or fix the links.
3. Add one curated "Facts" note per subsystem with exact values (IPs, ports, firmware, model versions, thresholds), each with a source path. These double as the FAQ answers (FAQ_FAST_ANSWER_PROPOSAL.md).
4. Add a short "What is historical vs live" note for the thesis demo.

## Knowledge workflows (n8n)

- **Workflows:**
  - `kbSourceSync0001` calls `POST :5199/jobs/build` on a schedule.
  - `kbVaultHealth002` calls `/jobs/drift` and `/jobs/health`.
  - `kbWeeklySumm003` calls `/jobs/digest`.
- Each has an HTTP timeout set but **no retry and no error workflow**.
- When a step fails, the service returns **HTTP 500** with `ok:false` and the last output (`serve.py:138`), and **409** while another job is running.
- The n8n HTTP node therefore fails the execution, so errors are visible in n8n's execution list.
- There is no error workflow, however, so nobody is notified (F-11).
- The jobs do not check content accuracy. That is limited to the drift and health reports.
- The last build job succeeded: 302 s, 162 new chunks, finished 18:05 (`/status`).
