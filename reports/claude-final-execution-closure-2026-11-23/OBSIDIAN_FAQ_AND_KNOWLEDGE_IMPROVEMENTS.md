# Obsidian, FAQ and knowledge improvements - 23 Nov 2026

## State (measured 23 Nov)
- **Vault:** `C:\Users\dell\SmartLabKnowledge\vault` has 503 Markdown files in 12 top-level folders (Home, Project, Systems, n8n Workflows, Database, Runbooks, Incidents and Lessons, Decisions, Generated Reports, Automation Inbox, Sources, Templates).
- **Index:** rebuilt 23 Nov 02:03 with `kb.py build`: 457 notes, 27 workflows, 13,365 chunks, **0 broken links**, 24 redactions, 0 errors.
- **FAQ:** `docs/faq/` has **61 curated Q&A entries** in 6 files. Each entry has "Also asked" variants and a source line.
- **n8n knowledge workflows:** "Knowledge 1 - Local source sync", "Knowledge 2 - Vault health check" and "Knowledge 3 - Weekly knowledge summary" are all active (read-only check through the n8n-lab MCP).
- **Models:** knowledge assistant `qwen3:1.7b` (`kb.answer_model()`, single source since K8); portal assistant `qwen2.5:1.5b` (`.env` `OLLAMA_MODEL`).

## Changes made on 23 Nov
| Change | Why | Evidence |
|---|---|---|
| Question-word / negation regex repaired (C-02) | The K1 protection was dead code (backspace characters) | knowledge suite 81 passed |
| "what time" read as "when" (C-03) | "What time does the lab close?" took 40 s through the model | live 1.89 s FAQ route |
| 3 hour variants added to the opening-hours entry | coverage | live check |
| Index rebuilt | FAQ text changed | `kb.py build` output above |

## Fast-answer layers (as built, verified 23 Nov)
1. **Guard** (fixed answers for robot control, door, secrets). It always runs, even on a forced route (K5).
2. **FAQ** (61 curated entries): answer in about 0.1-0.2 s warm. The question word, negation and ≥ 0.8 word coverage must agree.
3. **Lookup** (live values from the portal or records, such as the lab location): about 0.4 s.
4. **RAG + model** (`qwen3:1.7b`): complex questions. 18-72 s on CPU while the cameras or the video render are busy (see `AI_PERFORMANCE_BEFORE_AFTER.md`).

## Not done, and why
- **No bulk FAQ expansion was written into the vault or `docs/faq`.** Every entry must have a verified source, and the separate research session (`reports/smart-lab-next-generation-upgrade-research-2026-11-23/`) is producing the 100+ candidate question patterns. Adding unverified answers would undo K1/K7.
- **Missing facts that need the owner:** slot 2-4 times; the current room seat map after the room 224 check.
