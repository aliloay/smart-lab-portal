# System architecture and data flows (release candidate)

Machine-readable service list: `service_inventory.csv`. Status is what was observed on 2026-11-18 at home (off-site,
no GIU LAN, no COM ports attached).

## Services
| Service | Path | Runtime | Port / bind | Health | 18 Nov status |
|---|---|---|---|---|---|
| PostgreSQL 16 | docker-compose `db` | container | 127.0.0.1:5433 | pg_isready | up (healthy) |
| Backend API | backend/ | container, uvicorn (1 process) | :8000 (behind nginx) | /api/health (version = image build args) | up, **release df3407f** |
| Web portal + nginx | frontend/ | container | 80/443/8080/8443 | /, /version.json | up, **release df3407f** |
| n8n | docker-compose `n8n` (2.40.7) | container | 127.0.0.1:5678 | /healthz | up, 26 active workflows |
| DB backup | backup/ | container | - | own healthcheck | up |
| Security camera 1 / 2 | tools/security_vision | Windows Python 3.14, DirectML | 5100 / 5101 | /health | down (off-site) |
| Door face server | firmware/face_server | Python (Flask) | 5000 | /status | down (off-site) |
| Knowledge / RAG | tools/knowledge/serve.py | Python | 5199 | /health (new, no auth) | down |
| Voice | tools/voice | Python | 5320 | /health | down |
| Ollama | system | native | 127.0.0.1:11434 | /api/version | up (0.40.16; qwen2.5:1.5b, nomic-embed-text) |
| OPC UA feed | tools/opcua | Python 3.12 (asyncua) | 127.0.0.1:4840 | - | down |
| UR5e collector | tools/robot_monitor | Python 3.12 + ur_rtde | outbound to robot | - | not running (robot not reachable) |
| PC agents / relay | tools/pc_agent, tools/relay, lab_usb_kit | Python on lab PCs / Engineer PC | relay ports on S2PC136 | heartbeat | BLOCKED by GIU firewall for PC_01..16 |
| Watchdog | tools/ops/watchdog.py | Python, monitor only | - | - | probes /health on 5100/5101/5199/5320 (Argon) |

## Main data flows
1. **ESP32 nodes -> backend.** MASTER_LAB01 (door: RFID/QR/fingerprint/face, relay, TFT, tablet page), ENV_LAB01 (DHT22 C / %RH, MQ-2 0/1 state - not ppm, flame, motion), BIN_NODE_1 (HX711 grams; item count is a backend estimate), REUSE_BIN_1 (PN532, reed, servo, HX711, LCD). All use device keys over HTTP: /access/heartbeat, readings, bin events. The backend writes to PostgreSQL and pushes over the WebSocket (env_update, inventory_update, reusable_update, security_state).
2. **Cameras -> backend.** security_vision posts /security/state every 2 s (people, named, activity lines with an allow-listed set of fields, zones, calibration) and events with snapshots. The two cameras share lab numbers through the register file (labmap) and pair tracks peer-to-peer (crosscam). The backend pushes only when the state changes.
3. **Portal.** React reads REST and receives pushes on /ws/activity (one-time ticket). Pages refetch on push; heavy lists are polled (incidents 20 s, now summary rows).
4. **Robots.** UR5e via ur_rtde, read-only, into robot telemetry and the digital twin. FANUC monitoring and twin are read-only. Robot control stays off (`ROBOT_CONTROL=off`, adapters UNAVAILABLE until owner commissioning). The OPC UA server republishes a read-only snapshot on loopback.
5. **AI.** The portal assistant (backend ai.py) gives deterministic instant answers for access, alarms and stock. Other questions go to Ollama qwen2.5:1.5b with read-only tools (tool_gateway forbids physical actions). The GPU gate (knowledge /gpu-gate) keeps cameras first; Argon fixed it to recognise the camera state STREAMING.
6. **n8n.** Schedules call /api/automation/* with an automation key (alerts, reports, readiness). They never move the door or robots.
7. **Knowledge.** kb.py builds the Obsidian vault from approved repo sources; n8n Knowledge 1-3 sync, check and summarise it.

## Contracts checked in this integration
- **Camera activity:** the new keys `partial` / `pose_visibility` are accepted and dropped (test).
- **GPU gate:** camera state STREAMING counts as live (test_gpu_gate). security_vision reports `source_ok` only when the camera status is STREAMING.
- **Model names:** qwen2.5:1.5b in compose, .env, backend config, knowledge config, kb.py, serve.py, agent.py and ollama_models.bat.
- **Incidents:** the old default contract is kept for scripts and smoke tests; the portal uses summary rows plus the cursor.
- **Version:** backend /api/health and web /version.json report the same build id.
