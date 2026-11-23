# GitHub and deployment status - 23 Nov 2026, 06:36

## Source control (read-only remote check, fetched 23 Nov)
| Item | Value |
|---|---|
| Main checkout | `C:\Projects\smart-lab-portal`, branch `fix/pre-lab-hardening`, HEAD `d023e98` |
| vs `origin/fix/pre-lab-hardening` | 1 ahead / 0 behind (`d023e98` not pushed; the remote tip dates from 22 Nov 14:38 +0200) |
| vs `origin/main` | 1 ahead / 0 behind |
| Uncommitted, tracked (main checkout) | `backend/app/api/routes/face_submissions.py`, `docs/faq/lab-and-access.md`, `tools/knowledge/agent.py`, `tools/knowledge/test_agent.py`, `tools/security_vision/test_ultracode_2026_11_22.py` |
| Uncommitted, new (main checkout) | `backend/tests/test_closure_2026_11_23.py`, `tools/perf/vf9_pose_bench.py`, `tools/perf/kb_latency_bench.py`, this report folder |
| Closure worktree | `C:\Projects\smart-lab-claude-closure`, branch `claude/final-closure-2026-11-23` (base `d023e98`), same changes, uncommitted |
| Secrets tracked? | none: no `.env`, `camera.env`, `camera2.env` or `robot.env` in `git ls-files` |
| Owner files | untracked reports and the V1/V2 showcase videos left untouched |

**To publish:** review, commit on `fix/pre-lab-hardening`, push. All of that is the owner's call; nothing was committed or pushed in this round.

## Deployment (local, owner's standing local-deploy OK)
| Step | Result |
|---|---|
| Backup | `backups/predeploy_closure_20261123_0214.dump`, 5,694,196 bytes, `pg_restore --list` shows 44 TABLE DATA entries |
| Tests before deploy | backend 903 passed / 3 skipped / 0 failed (22 min 43 s, throw-away in-memory PostgreSQL) |
| Migrations | none in this release |
| Build | `tools/deploy/build_images.ps1 -Tag pre-closure-20261123`; rollback points `backend:pre-closure-20261123 = beb55bcf6f14`, `frontend:pre-closure-20261123 = 54a6a30d0d64` |
| New images | backend `1f86beeafacb` (created 04:32 UTC), frontend `85c4327e0bfb` (04:35 UTC) |
| Restart | `docker compose up -d --no-deps backend frontend` (db, n8n and backup not touched) |
| **Live check** | `/api/health`: `status ok`, `database true`, `version.id d023e98-dirty-20261123063157` (was `unstamped`); `/version.json` (frontend) has the same id; login page 200; backend healthy |
| Knowledge service | restarted twice on 23 Nov (C-03, then C-06) as an independent process; `/health` 200; live answers checked |
| Camera services | running `d023e98` code since 23 Nov 01:27; not restarted (no code change for them; tests only) |

The stamp says `-dirty` because the release is `d023e98` plus the uncommitted closure fixes. After the owner commits, a rebuild with the same script gives a clean stamp.

**Rollback:** `FINAL_RELEASE_AND_ROLLBACK_RUNBOOK.md`.
