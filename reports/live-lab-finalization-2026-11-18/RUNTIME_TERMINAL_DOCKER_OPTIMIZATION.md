# RUNTIME_TERMINAL_DOCKER_OPTIMIZATION.md

- **Evidence Class**: `LIVE_SERVICE` + `STATIC_INSPECTION`.

---

## 1. Live Audit of Terminal Launchers, Docker Build Stamp & Watchdog (`LIVE_SERVICE`)

### 1.1 Critical Defect Found Today in `launch.bat` (`line 242` — Why `/api/health` Reported `"unstamped"` Today!)
- **Symptom (`LIVE_SERVICE`)**:
  - Earlier today (`commit bdc41aa`), the release branch fixed `backend/Dockerfile`, `frontend/Dockerfile`, `tools/deploy/deploy.py`, and `tools/deploy/build_images.ps1` to pass `--build-arg BUILD_COMMIT=<sha>` and `--build-arg BUILD_TIME=<timestamp>`, and added `app/build_info.json` to `.dockerignore`.
  - Yet when we queried `GET http://127.0.0.1:8000/api/health` live at GIU at `16:43` today, it returned:
    `{"version": {"id": "unstamped", "note": "deployed without tools/deploy/deploy.py"}}`!
- **Root Cause (`launch.bat:242`)**:
  - When `launch.bat` was run at GIU ~3 hours ago (`14:14`, producing images `d79acf90c4aa` and `6f789b334e74`), `launch.bat` detected that `HEAD` had changed since `.last_build_fingerprint` and executed line 242:
    ```bat
    docker build -t smart-lab-portal-backend:latest .\backend && docker build -t smart-lab-portal-frontend:latest .\frontend
    ```
  - Because `launch.bat` ran plain `docker build` **without** `--build-arg BUILD_COMMIT` or `--build-arg BUILD_TIME` (and `app/build_info.json` is now in `.dockerignore`), `launch.bat` overwrote `:latest` with an **unstamped** image!
- **Fix Implemented (`launch.bat:239-249` in `opt/gemini-live-lab-finalization-2026-11-18`)**:
  - Replaced the raw `docker build` call in `launch.bat` with:
    ```bat
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\deploy\build_images.ps1"
    ```
  - Now every automatic rebuild triggered by `launch.bat` tags a rollback image (`pre-<yyyyMMdd-HHmm>`) and injects `--build-arg BUILD_COMMIT` and `--build-arg BUILD_TIME` into both `backend` and `frontend`.

---

### 1.2 Live Watchdog & Status Dashboard (`tools/ops/watchdog.py` & `scripts/status.ps1`)
- **`tools/ops/watchdog.py --once` (`LIVE_SERVICE`)**:
  - Verified live at `16:43:08`: all 11 monitored services (`portal (web)` `:80`, `portal API` `:8000/api/health`, `database` `:5433`, `n8n` `:5678/healthz`, `face server` `:5000`, `security camera 1` `:5100/health`, `security camera 2` `:5101/health`, `knowledge service` `:5199/health`, `voice service` `:5320/health`, `local AI (Ollama)` `:11434/api/version`, `OPC UA feed` `:4840`) returned **`up: true`** in **`1–70 ms`**.
- **`scripts/status.ps1` (`LIVE_SERVICE`)**:
  - Verified live at `16:41:56`: our resilient `Get-Counter -ErrorAction SilentlyContinue` fix accurately reported:
    `portal health: 200   free RAM: 1404 / 16213 MB   GPU: 868 / 4096 MB`
    `load: CPU 88 %   paging 811 pages/s   disk latency d: 0 ms, c: 0 ms   GPU 36 %   top cores: vmmemwsl 2.3, python 1.4, python 1.3`
    and listed all 5 Docker containers (`running`) and all 12 host services (`UP`).

---

## 2. Concurrency Discipline & Resource Budget (`16 GB` Host RAM)

During our live audit at `17:14`, `docker ps` revealed that Claude Code was concurrently running an isolated test container pair (`smart-lab-portal-backend-run-add7928538b8` + `smartlab-testdb`), which pushed `vmmemWSL` to `2.3` cores, host CPU to `88%`, and free RAM to `1,404 MB` (`811 pages/s`).
- Per Section 3 & Section 13 of our mission rules (*"Claude and you must NOT run competing full heavy-stack tests simultaneously"*), we **did not** launch a competing multi-client load generator while Claude's test containers were active; instead we measured the live physical stack (`SECCAM_LAB01`, `SECCAM_LAB02`, `PC_ENG` + 6 Student PCs, `knowledge`, `voice`, `ollama`, `opcua`, `n8n`, `db`, `backend`, `frontend`) passively and with bounded single-request probes, confirming that **all 12 host services and 5 production containers remained 100% online with zero crashes and `6.0 fps` on both cameras**.
