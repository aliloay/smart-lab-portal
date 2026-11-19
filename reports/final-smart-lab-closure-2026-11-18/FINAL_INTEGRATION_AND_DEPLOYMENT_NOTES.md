# Integration and deployment notes (19 Nov 2026)

## What is running (live-verified 19 Nov)
| Part | Version | How checked |
|---|---|---|
| Backend | `1456d9e-20261119140546` (19 Nov 14:06; includes the other session's `66ff251`) | `curl -sk https://127.0.0.1/api/health` |
| Frontend | `ecbb167-20261118231702` (no frontend code changed since) | `curl -sk https://127.0.0.1/version.json` |
| Database, backup | `db` healthy; `backup` recreated 19 Nov 14:06 with the wall-clock wait (dump `auto_smartlab_20261119_1406`); it had stopped on 18 Nov and skipped 14 h overnight | `docker compose ps`, `docker logs` |
| n8n | stopped (Exited 0); not touched | `docker compose ps` |

Branch `fix/pre-lab-hardening` in `C:\Projects\smart-lab-portal`. **Not pushed to GitHub.**

## Branches and worktrees
| Path | Branch | State |
|---|---|---|
| `C:\Projects\smart-lab-portal` | `fix/pre-lab-hardening` | main checkout; the owner's untracked files are untouched |
| `C:\Projects\smart-lab-claude-final` | `claude/final-closure-2026-11-19` | Claude's worktree; merged into the main checkout |
| `C:\Projects\smart-lab-argon` | detached `7619717` | Gemini's read-only inspection; not modified |
| `C:\Projects\smart-lab-portal-opt`, `C:\Projects\smart-lab-release` | older branches | already merged; kept |

## Deploy procedure used (repeat it the same way)
1. Dump the live database: `docker compose exec -T db sh -c 'pg_dump -U smartlab -d smartlab -Fc' > D:\SmartLabData\db_dumps\<name>.dump`
2. Tag the running images as a rollback point.
3. `powershell -ExecutionPolicy Bypass -File tools\deploy\build_images.ps1 -Only backend` (never `docker compose build`:
   since Compose v5 it exits 0 without building on this laptop).
4. `docker compose up -d --no-deps backend`, then check that `/api/health` shows the new commit id.

Rollback points: `smart-lab-portal-backend:pre-share-20261119` (= `c4848e2`), `pre-retired-20261119` (= `ecbb167`), plus older `pre-*` tags.
Dumps: `D:\SmartLabData\db_dumps\predeploy_2026-11-19.dump`, `predeploy_retired_2026-11-19.dump`, `predeploy_share_2026-11-19.dump`.

## Changes in this round
See `GEMINI_RECONCILIATION_AND_FIXES_2026-11-19.md`. A second round, made after that report, adds:
- `pc_control.broadcast_put(..., session)` + both frame-upload routes: a frame checked against one share is refused if
  another share started while its body was being read (the old presenter could appear in the new share).
- `devices._face_server_up()`: the face server counts as up only on `/health` 200 with `{"status": "ok"}` (it was any
  reply under 500 from `/users`); timeouts, refused connections and malformed bodies count as down.
- Doc corrections: DEFENSE_BRIEF (WSL 4 GB, vault size, workflow count), AUTOMATION (workflow count, when launch.bat
  starts n8n), DOOR_SYSTEM (out-of-date banner: PN532, NO contact, 8 Nov relay stage, ESP32-CAM core 3.2.1).

## Safety checks on this round
- Robot routes, door firmware, device keys, RBAC and subnet checks: not changed.
- Live database: read-only SELECTs only (the deploy's liveness refresh writes as it always does). Nothing deleted.
- n8n live workflows: not touched; only the repo copies changed.
- Before any push to the public GitHub: `reports/` holds lab evidence. The tracked raw files were checked (no account
  names), the Gemini raw folder is git-ignored, and the film stays untracked (people in frame).
