# Repository pre-update audit (9 November 2026)

Recorded before any commit of this release. All inspection commands were read-only.

## Repository

| Item | Value |
|---|---|
| Local path | `C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-portal` |
| Remote | `origin` → https://github.com/aliloay/smart-lab-portal.git (public) |
| Default branch | `main` (not protected) |
| Current branch | `offline-router-door-photos`, no upstream; last commit `0985cd4` |
| Relation to `origin/main` | 307 commits ahead, 0 behind: `origin/main` (`616bc32`) is an ancestor, so no divergence and no merge conflict |
| Tags | `checkpoint-2026-10-06`, `handoff-2026-10-09` (local only) |
| Other branches | 22 local `backup/`, `snapshot/` and feature branches, plus a `review/gemini` worktree. None is modified by this release |
| Working tree | 103 modified, 18 deleted, 182 untracked entries |

## Uncommitted work found

| Group | What it is | Decision |
|---|---|---|
| 103 modified tracked files (backend, frontend, firmware, tools, docs) | The owner's and earlier sessions' work from 3-8 Nov: PC-account keys, bin and lab detector updates, robot routes, door firmware relay fix, Scan page, PC agent, docs | Committed after the full test run (see GITHUB_RELEASE_REPORT.md) |
| 18 deleted files | SolidWorks lock files `tools/cad/door_enclosure/out/~$*.SLDPRT` committed by accident | Deletion committed; `~$*` added to .gitignore |
| Untracked project sources | Migration `f1a7c3d9e250_pc_account_keys.py`, `agent_bundle.py`, `test_pc_keys.py`, PC-agent tools, relay, CAD sources and the 2026-10-25 release STLs, robot meshes (BSD/permissive licences in `frontend/public/models/README.md`), lab images, scripts, training scripts, docs, firmware headers | Committed |
| `lab_usb_kit/` | PC install kit including **`enroll.key`**, `site.json` and a bundled Python | **Excluded** and git-ignored (secret). Rebuilt by `tools/pc_agent/make_kit.py` |
| Local tooling | `.agents/`, `.aider-desk/`, `.claude/`, `.vscode/`, `.perf-dist-*`, `skills-lock.json`, `logs/` | Excluded, git-ignored |
| Debug captures | `frontend/*.png`, `frontend/e2e/_*.mjs` probe scripts | Excluded, git-ignored |
| Large or derived data | YOLO datasets and results (`tools/vision_train/raw`, `results`, `colab_object/*_dataset`, zips: about 1.8 GB), CAD build outputs, backups and zips (most of 291 MB), generated status PDFs and evidence JSON (`docs/reports`), `docs/paper_figures` (45 MB) | Excluded, kept on the owner's PC; the README lists where they are |

## Safety measures taken

- No reset, checkout of files, stash, clean or history rewrite. Local branches and tags untouched.
- The original `.gitignore` was copied to the session scratchpad before it was extended.
- History check of all 2,321 blobs in the 307 unpushed commits: no file over 20 MB, no `.env`, keys, dumps or `docs/paper_images_private` content. The two camera screenshots in history (`docs/screenshots/security-camera-*.jpg`) were inspected: faces blurred.
- Credential scan of the unpushed diff and of every file to be added: Wi-Fi credentials live in git-ignored `secrets.h` (only placeholders committed); the only literal found is the test suite's dummy device key.
- **Known exposure, not new:** the published seed passwords (`Admin#2026`, `Staff#2026`, `Student#2026`) are hard-coded in about 23 tracked files and are already public on `origin/main`. `backend/app/services/briefing.py` uses them on purpose to warn when an account still has its default password. Recommendation: make sure no live account still uses them (rotate if so). History is not rewritten.
- The live `smartlab` database was not touched; backend tests run against `smartlab_test` (forced by `backend/tests/conftest.py`).
