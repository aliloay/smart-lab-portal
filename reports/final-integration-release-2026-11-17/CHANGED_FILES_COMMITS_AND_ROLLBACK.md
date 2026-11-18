# Changed files, commits and rollback

## Totals vs the owner base 4e58b52 (excluding reports)
53 files, +749 / -99 lines. Commits: e70db0e (merge, Claude), c49fa07 (merge, Argon), 35f8cb4, bdc41aa, b685a43, df3407f, plus this report commit.

## Files changed by the integration fixes (35f8cb4, bdc41aa, b685a43)
backend/.dockerignore · backend/Dockerfile · backend/app/main.py · backend/app/api/routes/incidents.py ·
backend/tests/test_build_stamp.py (new) · backend/tests/test_camera_activity.py · backend/tests/test_incidents.py ·
firmware/face_server/test_auto_enroll.py · frontend/Dockerfile · frontend/app_locations.conf · frontend/src/lib/api.ts ·
frontend/src/lib/warm.ts · frontend/src/pages/Incidents.tsx · tools/deploy/build_images.ps1 (new) · tools/deploy/deploy.py ·
tools/security_vision/activity.py · tools/security_vision/labmap.py · tools/security_vision/test_activity.py ·
tools/security_vision/test_labmap.py

The merged branches' files are listed in reports/final-optimization-2026-11-17/ARGON_CHANGED_FILES_AND_ROLLBACK.md
and in commits d085b73 / 5314195.

## Local deployment done (2026-11-18 ~09:50)
| Step | Result |
|---|---|
| DB dump before deploy | backups/predeploy_rc_20261118_0939.dump (4.4 MB; `pg_restore -l`: 43 table-data entries) |
| Rollback tags | smart-lab-portal-backend:pre-rc-20261118 = bd9625614072; smart-lab-portal-frontend:pre-rc-20261118 = ed4c16b9d8d5 (the images that were running) |
| Rollback images verified | backend imports, 34 routes; frontend `nginx -t` successful (isolated, --network none) |
| Release images | backend efd3e6c374cd, frontend 86c0df1dc030, stamp df3407f-20261118094636 |
| Pre-check in isolation | release backend image on its own network + in-memory DB: navigation 98/0, workflows 30/0, live bin 30/0 |
| Deploy | `docker compose up -d --no-deps backend frontend`: both healthy; db, n8n, backup untouched; no migration |
| Live verify | /api/health and /version.json = df3407f-20261118094636 |
| Second deploy (~10:20): assistant fixes 89ba1be + 279c625, backend only | after the full suite 828 passed / 0 failed. Rollback tag smart-lab-portal-backend:pre-assist-20261118 = efd3e6c374cd. New backend 7e3ed3b46b8e, stamp 279c625-20261118101511. Frontend unchanged (86c0df1dc030, df3407f). Live: stock / door / capability questions instant (9-33 ms). |

## Rollback (run from C:\Projects\smart-lab-portal)
To undo only the assistant fixes, re-tag `pre-assist-20261118` as the backend `latest`. To return to the pre-integration
portal, use the commands below.
```powershell
docker tag smart-lab-portal-backend:pre-rc-20261118 smart-lab-portal-backend:latest
```
```powershell
docker tag smart-lab-portal-frontend:pre-rc-20261118 smart-lab-portal-frontend:latest
```
```powershell
docker compose up -d --no-deps backend frontend
```
Then check http://localhost:8000/api/health. The database needs no rollback: no migration was made. The older
rollback tags (pre-incidents-20261117, pre-lazymotion-20261117, ...) are kept.

## Not touched
Main checkout files and branch, the Claude and Argon worktrees, live database rows (read-only queries only), n8n
workflows, camera services, firmware on boards, GitHub.
