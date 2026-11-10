---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/knowledge-platform/NEXT_PHASE_2026-10-13.md"
source_hash: "68dee279bd71b2288e2cdfd15bab9689a5f6066f6cdc384b8650ed346887f7df"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/knowledge-platform/NEXT_PHASE_2026-10-13.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_DEMO.md]] - mentioned by docs
- [[docs_How_To_Run_System.md]] - mentioned by docs

# Knowledge platform — next phase review (2026-10-13, evening)

Read-only audit first; changes listed in "Done". Nothing pushed, nothing activated.

## 1. Inspected and verified

| Item | Finding (how verified) |
|---|---|
| Repository | branch `offline-router-door-photos`, HEAD 1b4e268 before this report; branch not on the remote (`git ls-remote` empty) |
| Docker | backend, db, frontend, n8n, backup running (`docker compose ps`) |
| n8n | **2.40.7** (`n8n --version`); **all 23 workflows active** (`n8n list:workflow --active=true`) although every repo file says `"active": false` |
| Live vs file | Read-only export (`n8n export:workflow`, private folder `C:\Users\dell\SmartLabKnowledge\data\n8n_live`). After ignoring n8n's own default values (responseMode onReceived, hoursInterval 1, minutesInterval 5, method GET, contentType json, internal ids): 19 match; **01, 03, 05** — IF node `typeValidation` loose → **strict** (behaviour can differ); **07** — "AI Summary (optional)" node removed in the editor; 23 — same workflow, different id (`smartlab-23` file / `SmartLab23Emerge` live). |
| n8n audit | `n8n audit` (saved privately): 76 HTTP Request nodes flagged as "risky node type" (generic: they can call any URL; ours call only `http://backend:8000`), "Outdated instance" and "Security settings" sections. No change made. |
| Obsidian | installed and running; its registered vault is `C:\Users\dell\OneDrive\Documents\Obsidian Vault` (**inside OneDrive — synced**). The Smart Lab vault is **not** registered yet. |
| Ollama | 0.40.3; `qwen2.5:3b`, `qwen2.5:1.5b`; **`nomic-embed-text` (274 MB) was pulled at ~23:00 before the approval gate in the later instruction — see 3.** |

## 2. Exposed demo admin password — remediation plan (awaiting approval)

Verified (password not reproduced here):
* `backend/seed.py` creates four demo accounts (admin, staff, two students) with fixed passwords,
  **only if the account does not exist** (`get_or_create`). It runs on every backend start
  (`SEED_DEMO_DATA` defaults to true; not set in `.env`).
* The admin password appears in `README.md`, `docs/DEMO.md`, `docs/How_To_Run_System.md`,
  `backend/seed.py`, `backend/tests/e2e_booking_to_door.py` and 13 `frontend/e2e/*.mjs` scripts
  (which already accept `E2E_PASSWORD` from the environment).
* An admin endpoint exists to set any user's password: `PUT /admin/users/{id}/password`.
* Deleting the README text does **not** invalidate the credential; it is also in git history.

Safest rotation (no database edits, no lock-out):
1. Owner logs in, opens Users & roles, sets a new strong password for the admin account
   (and the three other demo accounts, or disables them). Store it in a password manager only.
2. Confirm the new password works in a second browser **before** logging out.
3. Code change (needs approval): `seed.py` reads demo passwords from env vars (e.g. `SEED_ADMIN_PASSWORD`)
   or generates a random one printed once; docs reference the env var instead of a literal;
   e2e scripts use `E2E_PASSWORD` only. Prevents re-creation with the public password if an account is ever deleted.
4. Optionally set `SEED_DEMO_DATA=false` in `.env` once the lab no longer needs demo data.

Verification checklist: old password → login refused (401); new password → login works; seed.py
restart does not change the hash; `git grep` for the old literal → only history; e2e scripts run
with `E2E_PASSWORD`.

## 3. Semantic search — model and benchmark design (implementation paused)

* Model: **nomic-embed-text** (Ollama library; 274 MB; 768-dim; Apache-2.0 per its model card —
  verify on https://ollama.com/library/nomic-embed-text before relying on it). Stored by Ollama
  in its own model folder (outside the repo). Offline after download. Measured: one embedding on
  CPU (`num_gpu: 0`) ~1.8 s cold. Estimated full index: 2,054 chunks.
* **It is already downloaded** (pulled before the later "wait for approval" instruction).
  Options: approve its use, or remove it with `ollama rm nomic-embed-text`.
* Design: vectors stored next to the BM25 index in the private data folder, keyed by chunk hash
  (re-embed only changed chunks); hybrid score = BM25 + cosine, BM25 alone when Ollama or the
  model is missing; same citations.
* Benchmark: the 10-question set plus 5 re-worded questions (e.g. "What address does the door
  controller use?" expecting the documents that contain 192.168.1.151): hit@5 and rank for BM25
  vs hybrid, retrieval latency, embedding time for a full and an incremental build.

## 4. Draft n8n workflows (files only, not imported, unverified in n8n)

`docs/knowledge-platform/n8n-drafts/`: KB-1 source sync (every 6 h), KB-2 vault health + drift
(daily 07:00), KB-3 weekly summary (Mon 08:00). All `"active": false`, local URL
`http://host.docker.internal:5199`, header-auth credential **alias** only (`REPLACE_ON_IMPORT`).
They need a small local service (`kb.py serve`, not built yet) bound to 127.0.0.1 with a token
and a lock file (409 while a run is in progress → no concurrent or recursive runs; writes only
to the vault/data folders). Deployment options:
* **A — Windows Task Scheduler** runs `kb.py build/health/drift` directly. Simplest; no n8n,
  no new port. Recommended.
* **B — n8n + `kb.py serve`**: keeps scheduling in n8n's UI; adds a local HTTP service and a credential.
Both need approval. Import (B) only after: service built + tested, `n8n import:workflow` of each
draft, check it stays inactive, one manual run with the editor open.

## 5. Obsidian (no plugins needed)

1. Obsidian → vault switcher (bottom-left) → **Open folder as vault** → `C:\Users\dell\SmartLabKnowledge\vault`.
2. Graph view: **Ctrl+G** (or the graph icon). It is part of the desktop app: no web server, no IP, no port.
   Obsidian reopens the last vault automatically afterwards.
3. Settings: keep **Restricted mode on** (no community plugins); Files & links → "Detect all file
   extensions" off; do not enable Obsidian Sync for this vault.
4. Do not move the vault into OneDrive. Generated folders are overwritten by `kb.py build`;
   write your own notes in Decisions / Runbooks / Incidents / Inbox. Back up with `kb.py backup`.
5. Graph is meaningful now: notes link through 9 generated system hubs (Door and access,
   SecurityCam, Robots, Consumables bin, Reusables bin, Environment, Bookings and labs, n8n,
   Backend and data), each listing the path rule that put a note there; workflows link to the
   backend route file they call; links between docs became Obsidian links.

## 6. Locality, privacy, security

* All knowledge data stays in `C:\Users\dell\SmartLabKnowledge` (not under OneDrive). Network:
  Ollama on 127.0.0.1 only; the tool refuses any other LLM URL. The live n8n export is private.
* 0 of 10 known secret values found in the vault or index; the demo password is removed by the
  private redaction list.
* Notion / Notion Calendar are cloud services: no Smart Lab knowledge is sent there.

## 7. Approval gates

1. Rotate the demo passwords (owner, in the portal) + the `seed.py`/docs change.
2. Use (or remove) the downloaded embedding model; then implement hybrid search.
3. Deployment option A or B for the three automations; for B, build `kb.py serve` and import inactive.
4. Whether to re-sync the 4 workflows that differ live (01, 03, 05, 07) back into the repo files.

