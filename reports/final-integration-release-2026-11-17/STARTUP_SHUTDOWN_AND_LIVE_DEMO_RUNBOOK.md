# Startup, shutdown and live demo runbook (release candidate)

## Start (lab laptop)
1. Check memory first: close Chrome/VS Code extras. Target at least 2.5 GB free before cameras + AI; Argon saw 0.9-1.5 GB with agents running.
2. Double-click `launch.bat` (repo root). It starts Docker Desktop, the portal stack (db, backend, frontend, n8n, backup), Ollama, the face server, both cameras (camera 2 only once: it refuses when :5101 already listens), knowledge, voice and the helpers (hidden; logs in logs/).
3. Status: `powershell -ExecutionPolicy Bypass -File scripts\status.ps1`, or the watchdog `py tools\ops\watchdog.py` (monitor only).
4. Verify the build that is running:
   - http://localhost:8000/api/health -> `version.id` (this release: df3407f-20261118094636)
   - https://localhost/version.json -> the same id

## Deploy a new portal build (owner's standing local-deploy OK)
```powershell
powershell -ExecutionPolicy Bypass -File tools\deploy\build_images.ps1
```
```powershell
docker compose up -d --no-deps backend frontend
```
The script tags the running images as rollback points (`pre-<date>`), builds both images with the version stamp and
prints their creation time. Never use `docker compose build`: since Compose v5 it exits 0 without building.
Take a DB dump before any deploy that includes a migration:
`docker exec smart-lab-portal-db-1 pg_dump -U smartlab -d smartlab -Fc > backups\predeploy_<date>.dump`

## Rollback
See CHANGED_FILES_COMMITS_AND_ROLLBACK.md (re-tag `pre-rc-20261118`, then `up -d --no-deps backend frontend`).

## Shutdown
Ctrl+C in the launch window stops the portal and closes the face server. Camera, knowledge and voice windows close
with their own windows. `docker compose stop` keeps all data; never use `down -v`.

## Tests (run serially; from this worktree, add the owner's .env for compose)
```powershell
$env:COMPOSE_ENV_FILES = 'C:\Projects\smart-lab-portal\.env'; powershell -ExecutionPolicy Bypass -File tools\ops\test_backend_fast.ps1
```
- Tools: `py -m pytest -q tools/security_vision`, and likewise knowledge, relay, pc_agent, lan_presence, ops, voice.
- Python 3.12 suites: `py -3.12 -m pytest -q tools/robot_monitor tools/ur5e_control tools/opcua`.
- MCP: `tools\mcp_server\.venv\Scripts\python tools\mcp_server\test_mcp_e2e.py` (needs SMARTLAB_URL and a staff token).
- Frontend (in frontend/): `npx tsc --noEmit -p .`, `npx vite build`, `npm run test:unit`.

## Live demo order (on campus, Smart_Lab LAN)
1. Portal sign-in as staff -> Command Center (devices, cameras, robots).
2. Door: RFID/QR at the Master; the access event appears live in the portal.
3. Consumables bin: take an item; the card updates without a reload.
4. Reusable bin: NFC scan -> lid -> checkout on the card.
5. Cameras: both feeds; one person crossing the views keeps one lab number. Show the "?" hints as hints.
6. UR5e twin: live joint mirror (read-only).
7. Assistant: an instant factual question (alarms / stock), then one LLM question.
Never press door, robot or emergency controls in a demo unless that is the demo itself and the owner runs it.
