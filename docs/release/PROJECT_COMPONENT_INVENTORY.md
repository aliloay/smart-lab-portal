# Project component inventory (9 November 2026)

Status words: **verified** (tested in this release or recorded live evidence), **implemented, not fully tested**, **partial**, **prototype**, **proposed**, **deprecated**. Hardware results come only from recorded measurements; the software checks below were run on 9 Nov 2026.

| Component | Location | Purpose | Status | Dependencies | Verification |
|---|---|---|---|---|---|
| Backend API | `backend/app` (FastAPI, 33 route modules) | Bookings, access, devices, equipment, inventory, robots (read-only), security, scan, AI, automation, reports | Verified | PostgreSQL 16, Python 3.12 | `backend/tests` suite in Docker on `smartlab_test` (result in GITHUB_RELEASE_REPORT.md) |
| Database and migrations | `backend/alembic` | Schema, applied by the API at start | Verified | PostgreSQL | Migrations run in the test suite; new `f1a7c3d9e250_pc_account_keys` is part of the tests but **not yet deployed live** |
| Portal | `frontend/src` (React 18, TypeScript, Vite 6, Tailwind 3.4; 40 pages) | Unified operations portal | Verified | Node 18+ | `tsc --noEmit` and `vite build` pass |
| Docker stack | `docker-compose.yml` | db, backup, backend, frontend (nginx, TLS), n8n | Verified | Docker Desktop | Running live (health 200); `launch.ps1` parse-checked |
| Master Node (door) | `firmware/SmartLab_Master_Portal` | NFC (PN532), fingerprint, TFT, relay lock, LEDs, HTTP to the API | Verified (hardware, 8 Nov 2026 repair) | ESP32, Arduino core | Owner's tests after the relay boot fix: no unlock on reset/replug, LEDs correct. Firmware change of 8 Nov is committed in this release |
| Environment Node | `firmware/SmartLab_Environment_Node` | DHT22, MQ-2, PIR readings over HTTP | Verified (earlier lab runs) | ESP32 | docs/BRINGUP_LOG.md |
| Consumables Node | `firmware/SmartLab_Consumable_Bin` | Load cell (HX711), parts count, LCD | Verified (earlier lab runs) | ESP32 | docs/BRINGUP_LOG.md |
| Reusables Node | `firmware/SmartLab_Reusable_Bin`, `_Modular` | NFC check-out, servo lid | Verified (earlier lab runs) | ESP32 | docs/BRINGUP_LOG.md |
| Robot stop node | `firmware/SmartLab_Robot_Stop` | Prototype | Prototype | ESP32 | Not commissioned; robot control adapters stay UNAVAILABLE (docs/ROBOT_CONTROL.md) |
| ESP32-CAM / face server | `firmware/ESP32CAM_Vision_FAST`, `firmware/face_server` | Face check at the door | Implemented, not fully tested | ESP32-CAM, Python | Earlier lab runs |
| Security vision | `tools/security_vision` | YOLO26s people detection, tracking, door cross-check, desk/PC occupancy | Verified | Python 3.14, OpenCV, DirectML | 297 tests pass |
| Bin and lab object detectors | `backend/app/services/bin_detector.py`, `backend/data/models/*.onnx` | Marker-free object recognition for Scan | Verified | onnxruntime | Backend tests (`test_bin_detector.py`) |
| Robot monitoring | `tools/robot_monitor`, `tools/ur5e_collector` | UR5e (RTDE) and FANUC read-only telemetry | Verified (read-only) | ur_rtde | 43 tests pass. **No motion commands** |
| Knowledge agent | `tools/knowledge` | Obsidian vault build, search, local LLM answers with sources | Verified | Ollama (qwen2.5), vault at `C:/Users/dell/SmartLabKnowledge/vault` | 49 tests pass; live answer recorded 8 Nov 2026 |
| Lab AI assistant | `backend/app/services/ai.py`, `agent.py` | "Ask the lab" in the portal | Verified | Ollama | Backend tests |
| n8n automation | `automation/n8n` | 23 workflow exports; backend decides, n8n schedules and hands off | Verified (exports, endpoints) | n8n (local) | docs/automation/workflow-inventory.md |
| PC agent and kit | `tools/pc_agent` | PC presence, screen wall, exam mode, PowerShell install kit | Implemented, not fully tested | Python | 40 tests pass; PowerShell kit only syntax-checked (execution policy on the dev PC) |
| LAN relay | `tools/relay` | Lets GIU lab PCs reach the portal through the engineer PC | Verified | Python | 5 tests pass |
| Scan the lab (AR) | `frontend/src/pages/Scan.tsx`, `backend/app/api/routes/scan.py` | Phone camera, QR markers, live records pinned to targets | Implemented, not fully tested | Phone browser | Earlier lab runs |
| Enclosure CAD | `tools/cad/*_enclosure`, `tools/cad/release_2026-10-25` | Four printed enclosures (SolidWorks API builds) | Verified (printed) | SolidWorks | Release STLs committed; build outputs excluded |
| OPC UA bridge | `tools/opcua`, `routes/opcua.py` | Local OPC UA server (loopback) | Partial | asyncua | Listening on loopback only |
| PLC, MQTT, Raspberry Pi | (none) | Early proposal | **Proposed, not implemented** | - | Devices talk HTTP to the API; no MQTT broker or PLC in the running system |
