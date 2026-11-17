# ARGON_RUNTIME_AND_TERMINAL_GUIDE.md

This guide provides the canonical, deterministic terminal commands to launch, inspect, verify, and stop the Smart Lab runtime on the portal laptop (`DESKTOP-61G2S1I`).

---

## 1. Pre-Flight & Memory Guard (`16 GB` Host RAM Budget)

Because the portal laptop has **16,213 MB RAM** and a **4 GB NVIDIA GTX 1650**, follow this memory budget before starting all 11 host services + 5 Docker containers:
- **Minimum Free RAM before `launch.bat`**: `>= 1,500 MB` (`>= 700 MB` hard floor enforced by `scripts/bg.ps1`).
- **If Free RAM is `< 1,500 MB`**:
  1. Close unused Chrome/Edge tabs and extra VS Code windows.
  2. If `vmmemWSL` exceeds `3.5 GB` while containers only use `~860 MB`, cap WSL2 memory in `%USERPROFILE%\.wslconfig`:
     ```ini
     [wsl2]
     memory=4GB
     swap=2GB
     ```
  3. Never run two heavy AI coding CLIs simultaneously during live camera + voice + LLM lab demonstrations.

---

## 2. Canonical Startup, Status & Shutdown Commands

| Task | Command (from Repository Root) | What It Does |
|---|---|---|
| **1. Pre-Lab Readiness Check** | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lab_preflight.ps1` | Verifies LAN IP (`192.168.1.200`), free RAM, GPU VRAM, disk space, Docker containers, and pings all lab devices without changing state. |
| **2. Start Full Stack (Quiet Background Mode — Recommended)** | `powershell -ExecutionPolicy Bypass -File launch.ps1 -Quiet` | Starts Docker containers (`db`, `backend`, `frontend`, `n8n`, `backup`) and all configured host helpers (`face_server`, `security_camera`, `security_camera2`, `ur5e_monitor`, `fanuc_monitor`, `knowledge`, `voice`, `opcua`, `pc_agent`, `lan_presence`, `mdns`) as hidden background processes logging to `logs\<service>.log`, then opens the live status table. |
| **3. Start Full Stack (Classic Windowed Mode)** | `.\launch.bat` | Starts each host service in its own minimized `cmd` window and brings up Docker containers.Idempotent: running it again starts only missing services (now with port `:5100` and `:5101` singleton guards on both cameras). |
| **4. Live Status & Resource Dashboard** | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\status.ps1` *(add `-Watch` for 5 s refresh)* | Shows `/api/health`, free RAM, GPU VRAM, CPU %, paging rate (`pages/s`), disk latency (`ms`), top CPU processes, Docker container states, and all 12 host services (`UP` / `STARTING` / `DOWN`) with last log line. |
| **5. One-Shot Watchdog Health Check** | `py tools\ops\watchdog.py --once` | Probes HTTP `/health` (or `/api/health`, `/healthz`, `/api/version`) on all 11 ports (`80`, `8000`, `5433`, `5678`, `5000`, `5100`, `5101`, `5199`, `5320`, `11434`, `4840`) and prints JSON status + response time in `ms`. |
| **6. Capture Runtime Telemetry Snapshot** | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\lab_snapshot.ps1 -Once` | Appends a timestamped CSV row of host RAM, paging, disk latency, GPU VRAM/util, top processes, and service latencies to `logs\lab_snapshot-*.csv`. |
| **7. Stop All Host Services & Containers Safely** | `.\stop_all.bat` *(or `powershell -ExecutionPolicy Bypass -File stop.ps1 -Docker`)* | Stops all Smart Lab host Python helpers (`face_server`, `security_vision`, `robot_collector`, `serve.py`, `voice_service`, `opcua_server`, `pc_agent`, `lan_presence`, `announce.py`) and runs `docker compose stop` (**never** `down -v`, preserving all database volumes). |

---

## 3. Service Port & Health Map

| Service | Local Address | Health Endpoint | Log File (Quiet Mode) |
|---|---|---|---|
| Frontend (Nginx) | `http://127.0.0.1:80` / `https://127.0.0.1:443` | `GET /` | `docker logs smart-lab-portal-frontend-1` |
| Backend (FastAPI) | `http://127.0.0.1:8000` | `GET /api/health` | `docker logs smart-lab-portal-backend-1` |
| PostgreSQL (`smartlab`) | `127.0.0.1:5433` | TCP `:5433` | `docker logs smart-lab-portal-db-1` |
| n8n Automation | `http://127.0.0.1:5678` | `GET /healthz` | `docker logs smart-lab-portal-n8n-1` |
| Door Face Server | `http://127.0.0.1:5000` | TCP `:5000` | `logs\face_server.log` |
| Security Camera 1 (`SECCAM_LAB01`) | `http://127.0.0.1:5100` | `GET /health` | `logs\security_camera.log` |
| Security Camera 2 (`SECCAM_LAB02`) | `http://127.0.0.1:5101` | `GET /health` | `logs\security_camera2.log` |
| Knowledge & GPU Gate Service | `http://127.0.0.1:5199` | `GET /health` (unauth) / `GET /status` (`X-KB-Key`) | `logs\knowledge.log` |
| Voice Service (Whisper + Piper) | `http://127.0.0.1:5320` | `GET /health` | `logs\voice.log` |
| Local AI (Ollama) | `http://127.0.0.1:11434` | `GET /api/version` | `%LOCALAPPDATA%\Ollama\server.log` |
| OPC UA Server | `opc.tcp://127.0.0.1:4840` | TCP `:4840` | `logs\opcua.log` |

---

## 4. Deploying the USB Kit on Engineer PC (`S2PC136`) & Lab PCs (`PC_01..PC_16`)

1. Copy the updated `lab_usb_kit\` folder to the USB drive (or run `py tools\pc_agent\make_kit.py --no-bundle --stick E:`).
2. On **Engineer PC (`S2PC136`)**:
   - Right-click `Install-CurrentUser.ps1` -> **Run with PowerShell** (or run `.\Install-CurrentUser.ps1 -Role Engineer`).
   - Run `.\Check-CurrentUser.ps1 -Full` and verify:
     - `OK    kit: 859 files checked, 0 wrong`
     - `OK    supervisor running`
     - `OK    agent running (1 copy)`
     - `OK    relay running (1 copy)` (now automatically falls back to `0.0.0.0` if `10.30.11.136` is not bound yet).
3. On **Student Lab PCs (`PC_01..PC_16`)** (once GIU IT enables inbound TCP `8000, 443, 80` on `S2PC136`):
   - Run `.\Install-CurrentUser.ps1 -Role Lab` under each authorized account.
