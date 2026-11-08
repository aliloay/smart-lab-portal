# GitHub release report (9 November 2026)

| Item | Value |
|---|---|
| Repository | https://github.com/aliloay/smart-lab-portal (public) |
| Branch pushed | `release/repo-audit-2026-11-09` (new; no force push, no history rewrite) |
| Release commit | `ee4310fc9326eba7af04f71bd290e8ed2b59e713`, verified on the remote with `git ls-remote` |
| Pull request | https://github.com/aliloay/smart-lab-portal/pull/13 → `main` (not merged automatically; `main` is not protected) |
| Base | `origin/main` at `616bc32` was an ancestor: 307 earlier local commits plus this release, 0 behind, no conflicts |
| Local branches | `offline-router-door-photos` and all `backup/`, `snapshot/` branches unchanged; no tags created or pushed; no GitHub Release created |

## Files

352 paths in the release commit (19,429 lines added, 376 removed): 103 modified tracked files, 18 deleted SolidWorks lock files, and the reviewed untracked project files. Lists: `git show --stat ee4310f`.

| Added | |
|---|---|
| Launch | `launch.ps1`, `stop.ps1` |
| Docs | `docs/release/REPOSITORY_PRE_UPDATE_AUDIT.md`, `PROJECT_COMPONENT_INVENTORY.md`, `CODE_OPTIMIZATION_REPORT.md`, this report; `docs/automation/N8N_WORKFLOWS.md`; README top section |
| Code | Migration `f1a7c3d9e250_pc_account_keys.py`, `agent_bundle.py`, `test_pc_keys.py`, PC-agent tools, `tools/relay`, `lib/visibleInterval.ts`, `WatchShare.tsx`, training and evaluation scripts |
| Media and models | Robot meshes (BSD/permissive, `frontend/public/models/README.md`), lab images used by the portal, enclosure CAD sources and release STLs, `lab_detector.onnx` (10.6 MB) |

## Tests run

| Suite | Result |
|---|---|
| Backend (Docker, `smartlab_test`) | First run: 752 passed, 2 skipped, 1 failed (`test_agent.py::test_new_instant_answers_come_from_the_records`, a midnight-boundary test bug). After the test fix: **753 passed, 2 skipped** (24 min) |
| tools/security_vision | 297 passed |
| tools/knowledge | 49 passed |
| tools/robot_monitor | 43 passed |
| tools/pc_agent | 40 passed |
| tools/relay | 5 passed |
| Frontend | `tsc --noEmit` OK, `vite build` OK (chunk-size warning only) |
| Launch scripts | PowerShell parser: 0 errors. Not executed on the dev PC (execution policy is disabled there and was not bypassed) |

## Fresh-clone validation

A clean clone of the release branch (no `.env`, no `node_modules`, no Docker volumes):

| Step | Result |
|---|---|
| `copy .env.example .env` + the three required keys | `docker compose config` valid |
| Model files the backend lists (`detectors.json`) | All present in the clone |
| `npm ci`, `tsc --noEmit`, `vite build` in `frontend/` | OK |
| Full `launch.ps1` start of a second stack | **Not run:** it would compete for ports 80/443/8000 and the database with the live lab stack on the same PC. The live stack (same compose file) is healthy, API health 200 |
| Hardware | Not testable on a software-only clone; ESP32 nodes, cameras and robots appear offline |

## Secrets audit

- 2,321 blobs in the newly published history and every staged file were scanned (tokens, API keys, private keys, passwords, Wi-Fi credentials, `.env`, dumps, private image folders). Nothing found apart from documented placeholders and the test suite's dummy key.
- Excluded and git-ignored: `lab_usb_kit/` (contains `enroll.key`), `backend/data/pc_agent_bundle/`, local tool folders, logs.
- Known exposure, already public before this release: seed passwords in tests and `briefing.py`. Action for the owner: confirm no live account uses them.

## Remaining issues

| Type | Item |
|---|---|
| Software | Migration `f1a7c3d9e250` is in the repo but not applied to the live database (deploy with the owner's password) |
| Software | Frontend chunk-size warning (3D twin, charts); splitting further is a future optimisation |
| Hardware | ESP32 nodes, cameras and robots were not exercised in this release; the door repair of 8 Nov is the latest hardware evidence |
| Configuration | A new user must create `.env`, run the face server, camera services and Ollama separately (`launch.bat`, docs/How_To_Run_System.md) |
| Administrative | Merge PR #13 after review; rotate seed passwords if still in use |
| Not implemented | PLC, MQTT broker, Raspberry Pi (early proposals only) |
