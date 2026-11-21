# FAQ fast-answer proposal (DRAFT, not installed)

**This is a draft only.** Nothing was added to the live vault, the knowledge index or the backend.

## How the answers were checked

- Every answer was checked against the source named in its row during this audit (DB SELECT at about 19:10, live `/health` endpoints, or source code).
- Live answers (L) must be fetched at question time and never served from this table.
- "UNKNOWN" means I found no reliable source.

## Column legend

| Column | Meaning |
|---|---|
| S/L | Static (S) or Live (L) |
| Path | FAQ = curated static answer; LIVE = typed DB/API query; RAG = knowledge retrieval; LOOKUP = evidence-only retrieval |
| Auth | Public = any signed-in user; Staff = staff or admin; Admin = admin only |
| Conf | Confidence |

## Proposed routing

1. **Normalise the question.** Detect intent words (where, what, which, is, how many, status, IP, port, version) and a **known entity** from a closed list: device UIDs, lab codes, port numbers, file names and service names, all taken from the DB and the repo.
2. **Answer from the cheapest reliable source:**
   - Intent and entity both match an FAQ row → curated answer plus its source. For live rows, run the typed query.
   - Only one of the two matches, or the match is ambiguous → the LOOKUP route (0.1 s, citations), with "Here is what the documents say".
   - "Why" or "how does" questions → RAG synthesis.
3. **Check permissions** on the API side for Staff/Admin rows. The assistant's role context must match the portal role.
4. **Release check:** a test that re-reads every S row's source and fails when the fact changes.

## Questions

| # | Canonical question | Alternatives | Short supported answer | Source | S/L | Path | Auth | Conf |
|---|---|---|---|---|---|---|---|---|
| 1 | Where is the Robotics Lab? | "where is LAB_01", "robotics lab location" | LAB_01 "Robotics Lab". Room or building location: read `labs.location` at question time | `labs` table; admin can edit location (checkpoint 20/21 Nov) | L | LIVE | Public | High (code) / location value not checked |
| 2 | How many labs are there? | "number of labs" | 11 registered, 10 active (LAB_10 CAD inactive) | `labs` table 19:10 | L | LIVE | Public | High |
| 3 | Which labs are inactive? | "closed labs" | LAB_10 CAD & Digital Design Laboratory | `labs.is_active` | L | LIVE | Public | High |
| 4 | What is the IP of the door controller? | "master IP", "MASTER_LAB01 address" | 192.168.1.151 (Smart_Lab LAN) | `devices` + ping 0 % loss | L | LIVE | Staff | High |
| 5 | What is the IP of the environment node? | "ENV_LAB01 IP" | 192.168.1.152 | `devices`, `docs/hardware/environment-node.md` | L | LIVE | Staff | High |
| 6 | What is the IP of the consumables bin? | "BIN_NODE_1 IP" | 192.168.1.153 | `devices` | L | LIVE | Staff | High |
| 7 | What is the IP of the reusable bin? | "REUSE_BIN_1 IP" | 192.168.1.154 | `devices` | L | LIVE | Staff | High |
| 8 | What is the IP of the entry camera? | "ESP32-CAM IP", "CAM_LAB01" | 192.168.1.150 | `devices` | L | LIVE | Staff | High |
| 9 | Which firmware does the door controller run? | "master version" | portal-1.2 | `devices.firmware_version`; `SmartLab_Master_Portal.ino:1817` | L | LIVE | Staff | High |
| 10 | Which firmware does the consumables bin run? | "bin version" | bin-0.6 | `devices`; firmware source | L | LIVE | Staff | High |
| 11 | Which firmware does the reusable bin run? | | reuse-mod-0.5 | `devices`; `SmartLab_Reusable_Bin_Modular` | L | LIVE | Staff | High |
| 12 | Which firmware does the environment node run? | | env-0.1.1 (FIRMWARE_VERSION "0.1.1") | `env_config.h:16` | L | LIVE | Staff | High |
| 13 | Which ESP32 boards are online? | "are the nodes up", "ESP32 status" | List `devices` where type in (MASTER, SENSOR_NODE, CAMERA) with `device_out` state | `devices` + `device_out()` | L | LIVE | Public | High (exists in `agent_live.py`) |
| 14 | Which ESP32 opens the door? | "what controls the lock" | Only the Master ESP32 (MASTER_LAB01) drives the lock relay; the backend never drives it | CLAUDE.md; `deps.py` docstring | S | FAQ | Public | High |
| 15 | Which ESP32 measures temperature and gas? | "what does the environment node do" | ENV_LAB01 monitors only (sensors to the portal) | `SmartLab_Environment_Node.ino` header | S | FAQ | Public | Medium (sensor list: read the README) |
| 16 | How does the consumables bin count stock? | "how is stock calculated" | Stock = (scale mass − item tare) ÷ unit mass of the selected item | `inventory_bin_items` columns; `services/inventory.py` | S | FAQ | Public | High |
| 17 | How much stock is in the consumables bin? | "how many screws left" | Live: (last_mass_g − tare_g) / unit_mass_g for the selected item; must say "sensor unavailable" if `hx711` is false or the node is offline | `inventory_bins`, `inventory_bin_items`, BIN_NODE_1 `component_state` | L | LIVE | Public | High (logic) – today's value disputed (F-10) |
| 18 | Is the consumables scale working? | "is the load cell ok" | Live `component_state.hx711` and `calibrated` of BIN_NODE_1 | `devices.component_state` | L | LIVE | Staff | High |
| 19 | What does the reusable bin do? | "NFC bin" | NFC check-out bin with a servo lid and a load cell; scan → lid opens → item taken or returned | `docs/hardware/reusables-node.md` | S | FAQ | Public | High |
| 20 | Is the door open? | "door state" | Live `devices.door_closed` of MASTER_LAB01 | `devices` | L | LIVE | Staff | High |
| 21 | Who entered the lab today? | "access log today" | Live `access_events` for today | `access_events` | L | LIVE | Staff | High |
| 22 | How can I open the lab door? | "access methods" | RFID card, fingerprint, face, or booking/personal QR at the Master node; access is decided by the portal rules | `docs/ACCESS_FLOW.md`, `DOOR_SYSTEM.md` | S | FAQ | Public | Medium (wording to confirm with ACCESS_FLOW) |
| 23 | Can I use my booking QR outside my booking time? | "QR expired" | No: valid from `valid_from` to `valid_until` (grace `BOOKING_GRACE_MINUTES` = 0 by default) | `services/access.py:validate_qr`; `config.py:75` | S | FAQ | Public | High |
| 24 | How long does a sign-in last? | "session length" | 8 hours (ACCESS_TOKEN_EXPIRE_MINUTES = 480) unless .env overrides | `config.py:25` | S | FAQ | Public | High (default) |
| 25 | Why can't I sign in after signing up? | "account pending" | New sign-ups need an administrator's approval (SIGNUP_REQUIRES_APPROVAL = true) | `auth.py:signup`; `config.py:268` | S | FAQ | Public | High |
| 26 | Who approves new accounts? | "approval" | Administrators, on Users & roles (lab staff cannot activate accounts) | `admin.py:update_user` (STAFF_EDITABLE) | S | FAQ | Public | High |
| 27 | Is the UR5e online? | "UR5e status", "robot connected" | Live robot state; today OFFLINE, last data 2026-11-18 16:39 UTC | `devices` UR5E_01 + `robotLive` | L | LIVE | Public | High |
| 28 | Is the FANUC online? | | Live; today OFFLINE, last data 2026-11-18 16:39 UTC | `devices` FANUC_01 | L | LIVE | Public | High |
| 29 | Can the portal move the robots? | "robot control", "home the robot" | No. Robot control is off; every adapter returns UNAVAILABLE until a commissioning step is signed off | `ROBOT_CONTROL=off`; `services/robot_control.py` | S+L | FAQ (+ env check) | Public | High |
| 30 | What is the UR5e's IP? | | 192.168.1.102 (static, pendant) | `docs/LAB_TEST_2026-10-15.md:170` | S | FAQ | Staff | High |
| 31 | What is the FANUC's IP? | | 192.168.1.100 (read-only web page) | `docs/FANUC_LIVE_TWIN.md:3` | S | FAQ | Staff | High (note the conflict F-03) |
| 32 | Which lab PCs are online? | "PC status" | Live `devices` type PC with state; GIU PCs last reported 2026-11-18 | `devices` | L | LIVE | Staff | High |
| 33 | Which PC is Hemaly's? | "engineer PC" | PC_ENG "HEMALY - ENGINEER PC", hostname S2PC136 | `devices` id 18 | S | FAQ | Staff | High |
| 34 | Which agent version is on PC-10? | | 0.9 (others 1.0) | `devices.firmware_version` | L | LIVE | Staff | High |
| 35 | How many lab PCs are registered? | | 14 PC rows: 9 GIU lab PCs + Hemaly + admin laptop + 3 retired TEST cards | `devices` | L | LIVE | Staff | High |
| 36 | Are the security cameras working? | "camera status" | Live `/health` per camera; today services up, no picture (OFFLINE) | :5100/:5101 `/health`; `device_out` DEGRADED | L | LIVE | Staff | High |
| 37 | Does the camera system do full-body pose? | "skeleton", "keypoints" | No keypoint model. Body parts are estimated from the person box (PREDICTED), never measured | `activity.py:51-90` | S | FAQ | Public | High |
| 38 | Which detector do the security cameras use? | | YOLO26s ONNX through DirectML on the GTX 1650 (fallbacks: OpenVINO/CPU) | `vision.py:112-240`; `models/` | S | FAQ | Public | High |
| 39 | Which model does AR Scan use? | "AR detector version" | lab_detector.onnx v8 "ft_y11s" (YOLO11s, 12 classes), server-side | `backend/data/models/detectors.json` | S | FAQ | Public | High |
| 40 | Which objects can AR Scan recognise? | | reusable bin, consumables node, environment node, master node, switch, router, UR5e, UR5e pendant, FANUC, FANUC pendant, lab PC, door | `detectors.json` | S | FAQ | Public | High |
| 41 | Why does AR not tell which PC it sees? | | The lab_pc class has no per-PC identity; scan the PC's QR marker | `detectors.json` (code null) | S | FAQ | Public | High |
| 42 | Which AI model answers in the portal? | "model in use" | qwen2.5:1.5b (portal), qwen3:1.7b (knowledge), via local Ollama | backend env; `config.json`; `/api/ps` | L | LIVE | Public | High |
| 43 | Is the AI on the GPU? | | Live: gate decision + Ollama `size_vram`; today CPU | `/gpu-gate`; `/api/ps` | L | LIVE | Staff | High |
| 44 | Where does the assistant get its knowledge? | "sources" | Obsidian vault mirrored from the repo docs/code + live DB export; local only | `tools/knowledge/kb.py`, `serve.py` jobs | S | FAQ | Public | High |
| 45 | When was the knowledge index last rebuilt? | | Live `GET :5199/status` → index_built (today 18:01) | knowledge `/status` | L | LIVE | Staff | High |
| 46 | Which n8n workflows exist? | "automations" | 23 operational (01-23) + 3 knowledge (sync, health, weekly summary) | `automation/n8n/json` | S | FAQ | Staff | High |
| 47 | Which n8n workflows ran today? | | Live `audit_logs` AUTOMATION_RUN by entity | `audit_logs` | L | LIVE | Staff | High |
| 48 | When does the database back up? | "backup schedule" | Every 6 h (BACKUP_EVERY_HOURS), pg_dump checked with pg_restore --list; last success in `backups/backup_status.json` | `docker-compose.yml` backup service | S+L | FAQ+LIVE | Admin | High |
| 49 | What port does the portal API use? | | 8000 (backend); web 80/443 (also 8080/8443) | `docker compose ps` | S | FAQ | Staff | High |
| 50 | Which port is the knowledge service on? | | 127.0.0.1:5199 | `serve.py`; port list | S | FAQ | Staff | High |
| 51 | Which ports do the camera services use? | | 5100 (camera 1), 5101 (camera 2), loopback only | process args | S | FAQ | Staff | High |
| 52 | Where is the face server? | | Laptop, port 5000, engine SFace | `:5000/health` | S | FAQ | Staff | High |
| 53 | Why is a device shown orange (DEGRADED)? | | Its reporting service runs, but the hardware behind it is not delivering (camera without picture / collector without robot data) | `devices.py:_derived_state` | S | FAQ | Public | High |
| 54 | How long until a silent device is offline? | | 90 s without a report (DEVICE_STALE_SECONDS) | `config.py:90` | S | FAQ | Public | High |
| 55 | Why is the door RFID sometimes frozen after relocking? | | Suspected lock-coil back-EMF; a software relock guard helps (7/8 in one test); fix = 1N4007 diode (pending) | `MEASUREMENTS_2026-11-21.md`; `.ino:1106` | S | FAQ | Staff | Medium (HISTORICAL) |
| 56 | What is the Wi-Fi password? | any secret | Refuse: secrets are excluded from the knowledge base | knowledge guard (measured 0.02 s) | S | GUARD | – | High |
| 57 | When is my next booking? | | Live `bookings` for the signed-in user | `bookings` | L | LIVE | Public (own) | High |
| 58 | Who is in the lab right now? | | Live `access_sessions` open; camera counts only when the cameras are live | `access_sessions`; camera `/health` | L | LIVE | Staff | Medium (cameras offline today) |

### UNKNOWN or not answerable from sources

- Exact room numbers for each lab: only an admin-editable field; values not verified.
- ESP32 RSSI: not reported by the firmware.
- Pending owner action: "Room 224" is mentioned in owner memory; not verified in the DB.
