# Audit and plan, 2026-10-08: vision, robots, security, Command Center

This document covers Phase 0 (audit) and the plan for the three master prompts
(vision and robot monitoring, security hardening, IoT Command Center). Nothing
in it has been implemented yet. "NOT VERIFIED" means it has not been checked
on the real hardware or network.

Backups taken before anything was changed:
- the git branch `backup/before-session-2026-10-08`;
- `smart-lab-backups/db-2026-10-08.dump`;
- `smart-lab-backups/full-project-2026-10-08.zip`, which includes the
  git-ignored secrets, face sets and recordings.

## 1. Current architecture (inspected, not assumed)

| Layer | Where | What it does today |
|---|---|---|
| Backend | `backend/app` (FastAPI, 203 routes in 22 route files) | One source of truth. PostgreSQL in Docker. JWT bearer auth (token in memory/sessionStorage). Roles: STUDENT, LAB_STAFF, ADMIN. Device API key for nodes. |
| Live push | `backend/app/ws/manager.py`, `/ws/activity?token=` | One WebSocket. Message types: hazard, emergency_broadcast, notification, staff, security_state… |
| Frontend | `frontend/` React 18, Vite 6, TypeScript 5.7, Tailwind 3.4, recharts, framer-motion, lucide | 30 pages incl. Monitor (wall), Security, Devices, Equipment, Inventory, Emergency, Reports, dashboards per role. No 3D library. |
| Camera service | `tools/security_vision/security_vision.py` (+ `vision.py`, `equipwatch.py`, `realign.py`, `recorder.py`, `dataset.py`) | MC210 RTSP stream2 (960 px), OpenCV/FFmpeg reader thread keeps only the newest frame; YOLOX-S 416 on CPU; IoU+appearance tracker; Labeler (door names, face votes, look lock, crossing fix, hand-back); zones (OK/IN_USE/CHANGED/MOTION, robot-aware); door open/closed from the red leaf; view re-align; equipment watch; recorder (FFmpeg, stream1); training-picture collector. Flask/waitress on 127.0.0.1:5100. |
| Face server | `firmware/face_server/face_server.py` | YuNet + SFace templates (USER1, 2, 3, 5, 6 enrolled), `/identify` for the camera, `/recognize` for the door. Port 5000. |
| Door | `firmware/SmartLab_Master_Portal` (ESP32 at .151) + ESP32-CAM (.150) | Final physical authority. Tablet UI is served by the ESP32 itself. Not touched by this plan. |
| Environment | `firmware/SmartLab_Environment_Node` (.152) | Flame, gas, temperature, humidity → `/api/...` on the laptop. |
| PCs | `tools/pc_agent/pc_agent.py` | CPU/RAM/disk/network, session open, modes, screen view, exam program list. Not yet installed on the lab PCs. |
| UR5e | `tools/ur5e_collector/ur5e_rtde_collector.py` | Read-only `ur_rtde` receive interface → `/api/equipment/state` every 5 s (RUNNING/IDLE/FAULT, joints every 60 s). **Never run against the robot.** |
| FANUC | none | No interface code. Controller model and protocol unknown. |
| Automation | n8n (127.0.0.1:5678), `backend/app/services/robotics_watch.py` | Workflows 13-23 incl. robot offline/fault, robot running without booking. |
| AI | Ollama 127.0.0.1:11434, `backend/app/services/agent.py` | Read-only, grounded answers. |

## 2. Service, IP and port map (discovered 2026-10-08, laptop at home)

| Service | Address | How it was found |
|---|---|---|
| Lab router Smart_Lab | 192.168.1.1 | memory note (admin password unknown) |
| Laptop on the lab cable | 192.168.1.200 (static, no gateway) | memory; the cable is not plugged in at home right now |
| Laptop on home Wi-Fi | 192.168.1.8 | `ipconfig` today; **same subnet as the lab** |
| Portal (nginx) | 0.0.0.0:80, HTTP only | `docker-compose.yml`, `netstat` |
| Backend (FastAPI) | 0.0.0.0:8000, HTTP | open on every interface, because the ESP32 nodes post to `192.168.1.200:8000` |
| Project PostgreSQL | 127.0.0.1:5433 | compose |
| **Other PostgreSQL (Windows service `postgres.exe`, not the project's)** | **0.0.0.0:5432** | `netstat`. It is reachable from the network. NOT VERIFIED what uses it. |
| n8n | 127.0.0.1:5678 | compose |
| Ollama | 127.0.0.1:11434 | `netstat` |
| Face server | :5000 | not running at home |
| Camera service | 127.0.0.1:5100 | not running at home |
| Door ESP32 / tablet UI | 192.168.1.151 | firmware, memory |
| ESP32-CAM | 192.168.1.150 | firmware |
| Environment node | **192.168.1.152** | memory. The address the prompt suggested for the Command Center is already taken. |
| MC210 camera | 192.168.1.155 (lab) | earlier sessions |
| UR5e | 192.168.1.102 static, External Control host 192.168.1.101 | read from the pendant photo; NOT VERIFIED on the network |
| FANUC (two Ethernet ports) | unknown | NOT VERIFIED |
| Lab PCs | unknown | waiting for IT approval |

## 3. Limitations found

1. **Camera latency:** never measured stage by stage. The baseline run failed today because the camera is in the lab (RTSP timed out after 30 s). The live view polls one JPEG at a time through the backend (`LiveCameraFeed.tsx`, `frame.jpg` proxy). The analysis rate measured on 2026-10-07 was 1.2-2.9 analyses a second (YOLOX 416, CPU, about 236 ms a pass).
2. **Identity:** the Labeler keeps names by look, face votes and place, but it has no explicit state machine, no confidence value, no decay, no stored evidence and no conflict events. Wrong hand-offs were seen on 2026-10-07 and patched case by case (d2f2966, 6bb2523). That shows the model needs restructuring rather than more patches.
3. **Robots:**
   - UR5e collector: not run; 5 s polling; no per-joint movement events, home calibration, watchdog or events.
   - FANUC: nothing.
   - Camera robot boxes: whole-box movement only, no link regions.
4. **Security:**
   - Good: bcrypt hashes, CORS allowlist, no SQL built from strings, no raw HTML rendering, no secret ever committed (history checked).
   - Missing:
     - HTTPS/TLS anywhere;
     - security headers and CSP (nginx sets none);
     - rate limiting on login (only the AI has one);
     - a global error handler with error IDs.
   - Exposed: the backend on 0.0.0.0:8000, and the foreign PostgreSQL on 0.0.0.0:5432.
5. **Network:** the lab and home networks are both 192.168.1.0/24, so addresses can clash. The router admin password is unknown, so the DHCP range is unknown. A free address can only be confirmed in the lab by ARP and ping.

## 4. Proposed architecture

- **Command Center:** a new section of the existing frontend (route `/command`, the robot pages `/robots/:id`, and so on), served by the same nginx container. It gets its own LAN endpoint (a second nginx `server` on port 8080, or a second static IP on the laptop's lab cable, once one is proven free). No second backend or database.
- **Identity engine:** `tools/security_vision/identity.py`, a typed `PersonTrack` holding the evidence: face observations, look, door association, place. It has explicit states (UNKNOWN … FUSED_CONFIRMED, IDENTITY_UNCERTAIN, LOST), configurable weights, hysteresis and decay, and emits IDENTITY_CONFLICT events. It replaces the Labeler's internals behind the same interface, and the existing tests stay.
- **Robot state:** `tools/ur5e_collector/robot_state.py`, a pure state machine with per-joint deltas and velocity, start/stop hysteresis, home calibration (versioned), and a watchdog (STALE ≠ STATIONARY). It is fed by RTDE in the lab and by recorded or synthetic RTDE in tests. Backend: robot state and events tables (Alembic), `/api/robots/...`, a `robot_state` WebSocket message.
- **Robot vision:** polygonal link regions per robot in the camera service, with motion per region and occlusion handling. Fusion with telemetry happens in the backend.
- **Kinematic check:** UR5e forward kinematics from the official DH parameters, projected with a calibrated camera pose. **Last step:** it needs a calibration session with the robot moving.
- **FANUC:** an audit procedure first, no code until the controller and its options are known.

## 5. Phases (recommended order)

| # | Phase | Can be done at home? | Verified how |
|---|---|---|---|
| 1 | Security hardening: headers, CSP, login rate limit, error IDs, nginx; decide on the foreign Postgres | yes | tests + curl checks |
| 2 | Identity engine with evidence, states and conflicts | yes (unit tests, synthetic tracks) | unit tests; lab replay on Monday |
| 3 | Latency instrumentation: stage timestamps, frame age, `/metrics`, browser timing | code yes, numbers Monday | measured in the lab |
| 4 | UR5e robot state + backend + events | code + simulated tests yes | NOT PHYSICALLY VERIFIED until the switch is in place |
| 5 | Command Center UI + design system + Robot page with a 3D twin (placeholder model unless official meshes are used) | yes | e2e + screenshots |
| 6 | Robot link regions + visual motion + fusion | partly | lab |
| 7 | Kinematic ↔ visual verification | no | lab calibration |
| 8 | FANUC | no | controller inspection |

**Monday in the lab:**
- Record raw test sessions with the Record button (stream1), one per item of the human test matrix. All identity benchmarks are then replayed from those files, repeatably.
- Measure latency.
- Find a free IP.
- Run the UR5e RTDE read-only check.

## 6. Packages recommended

| Package | Why | Notes |
|---|---|---|
| `three`, `@react-three/fiber@8`, `@react-three/drei@9` | 3D robot twin | Versions compatible with React 18; lazy-loaded so other pages don't get heavier |
| `ur_rtde` (Python, on the laptop) | already the collector's dependency | install only when the robot is reachable |
| (optional) `argon2-cffi` | Argon2id for new hashes, bcrypt still verified | passlib handles the migration transparently |
| **Not recommended now:** Ultralytics BoT-SORT | AGPL-3.0 licence + PyTorch (~2 GB) on a CPU-only laptop that already runs YOLOX at 1-3 analyses a second | benchmark it offline on the Monday recordings first, then decide |
| **Not adding:** shadcn/ui, TanStack Query, ECharts | the app already has its own Tailwind components, fetch layer and recharts | a second UI system would duplicate them |

## 7. Risks

- **Scope:** the three prompts together are several weeks of work. Each phase is finished and measured before the next one starts.
- **The suggested 192.168.1.152 is the environment node.** A dedicated IP is chosen only after an ARP/ping check in the lab.
- **TLS:** browsers need a local CA (for example mkcert) installed on every lab PC and phone. The ESP32 nodes and the door tablet stay on HTTP port 8000/ESP32, because changing them means reflashing the door. The door path is not touched.
- The foreign PostgreSQL on 0.0.0.0:5432 is reachable from the network (owner decision: firewall it or stop the service).
- **Identity accuracy cannot be claimed** until the Monday recordings are labelled and replayed.
