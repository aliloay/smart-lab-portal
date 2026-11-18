# GEMINI_EXECUTIVE_SUMMARY.md

- **Agent**: Gemini / Argon Max — Independent Full Smart Lab Live University Auditor & Systems/Vision/Devices/AI Implementation Owner
- **Date & Location**: `2026-11-18 16:41–17:25 +02:00` — **On-Site at German International University (GIU) Robotics Lab (`LAB_01`)**
- **Main Checkout**: `C:\Projects\smart-lab-portal` (`fix/pre-lab-hardening`, `HEAD = 610279e`, untouched by Gemini)
- **Gemini Isolated Worktree**: `C:\Projects\smart-lab-argon` (branch `opt/gemini-live-lab-finalization-2026-11-18`, based on `610279e`)
- **Raw Data & Reports**: Saved in `C:\Projects\smart-lab-argon\reports\live-lab-finalization-2026-11-18\`, `C:\Projects\smart-lab-portal\reports\live-lab-finalization-2026-11-18\`, and `D:\SmartLabData\live-lab-finalization-2026-11-18\`.

---

## 1. Executive Summary of On-Site GIU Live Verification (`LIVE_PHYSICAL` + `LIVE_SERVICE`)

While physically connected to the GIU Smart Lab network (`192.168.1.200/24`) today, we independently audited and tested the live university hardware, dual Tapo C200 RTSP cameras, calibrated floor maps, Engineer PC (`S2PC136`) dual-NIC TCP relay, 6 student lab PCs (`10.40.20.x`), Docker services, Ollama/RAG/GPU-gate, Voice (`Whisper` + `Piper`), OPC UA (`:4840`), and n8n (`26/26` workflows).

### Major Live Achievements Verified at GIU Today (`LIVE_PHYSICAL`)
1. **Two-Camera Global Tracking & UR5e Conflict Storm Eliminated Live (`-99.61%`)**:
   - Both physical cameras (`SECCAM_LAB01` at `192.168.1.155` and `SECCAM_LAB02` at `192.168.1.156`) streamed continuously at **`13.85–14.96 fps`** capture and **`5.33–6.00 fps`** DirectML GPU analysis with **`0` reconnects**.
   - Across today's live session (`1,008` identity log events), `CROSSCAM_CONFLICT` dropped from **`3,069`** (on 17 Nov) to **`12` total (`5` Cam 1 + `7` Cam 2 = `-99.61%`)**, `NAMED_BY_DESK` flood dropped from **`1,191` to `0` (`-100.0%`)**, and the cameras executed **`28` live `CROSSCAM_NAME` handoffs** and **`162` `LAB_NUMBER_MERGED` global person convergences**.
2. **Floor Map Refit Verified (`7/8` Spots Within `0.70 m` Gate)**:
   - With today's 8 new two-camera standing pairs (`commit 6606ed5`), `SECCAM_LAB01` leave-one-out (`LOO`) max error dropped from `0.500 m` to **`0.419 m`** (`LOO median = 0.197 m`), and `SECCAM_LAB02` achieved **`LOO median = 0.214 m`** (`max = 0.625 m`).
3. **Engineer PC (`S2PC136`) Relay & 6 Student Lab PCs (`10.40.20.x`) Verified Online (`LIVE_PHYSICAL`)**:
   - The GIU firewall blocker from 17 Nov is resolved: `PC_ENG` (`S2PC136`, `10.30.11.136` $\leftrightarrow$ `192.168.1.100`) is live and actively relaying **6 Student Lab PCs (`PC_GIULAB20-PC4`, `PC13`, `PC14`, `PC17`, `PC18`, `PC19` on `10.40.20.0/24`)** plus `PC_ADMIN_LAPTOP` (`8` workstations online simultaneously).
4. **Ollama, RAG, GPU Gate & Voice Verified Under Live Dual-Camera Load (`LIVE_SERVICE`)**:
   - Diagnosed the root cause of the 17 Nov Ollama timeout: calling `/api/embeddings` without `"num_gpu": 0` loaded `nomic-embed-text` onto `CUDA0` against two active DirectML camera processes on the 4 GB GTX 1650.
   - With CPU gating (`num_gpu=0`, enforced by `:5199/gpu-gate` returning `"cpu"` in `6 ms`): warm embedding takes **`116.1 ms`**, warm `qwen2.5:1.5b` first token takes **`390.1 ms`** (`total = 3,620.2 ms`, `6.82 tok/s`), `/ask` `lookup` takes **`6.1–95.1 ms`**, Piper TTS takes **`685.9 ms`**, and Whisper `tiny.en` STT takes **`3,535.1 ms`**.

---

## 2. Six New Live Defects Discovered at GIU Today & Fixed Immediately (`opt/gemini-live-lab-finalization-2026-11-18`)

By challenging prior claims against live GIU telemetry, we discovered and immediately fixed **6 real defects**:
1. **`P1` — `tools/security_vision/labmap.py` (Multi-Entry `USER6` Contamination & Split Naming Across Cameras)**:
   - Live `lab_people_LAB_01.json` had accumulated **8 different numbers (`'3','4','5','6','9','16','22','34'`) all carrying `who.auth_subject == "USER6"`**, causing Camera 1 to restore `nour ramy` onto `Person 3` (at UR5e) while Camera 2 restored `nour ramy` onto `Person 4` (at `PC-09`) at the exact same second!
   - **Fix**: Enforced a strict **Single-Owner Invariant** in `people`, deleted `merged_away` ghost numbers on merge, guarded `names_by_number` with `peer_held_no` and `self.restored_once`, deduplicated `_confirmed_back()` by `auth_subject`, and added a `ready_need` pre-check to eliminate `500 ms` lock-contention spikes during `LOOK_WAIT_S`.
2. **`P1` — `tools/security_vision/identity.py` (`REACQUIRE_HOW` Missing `"came back (same look)"`)**:
   - **Fix**: Added `"came back (same look)"` to `REACQUIRE_HOW` so look-based restores emit `PERSON_TRACK_REACQUIRED` at `0.65` instead of `PERSON_IDENTITY_CONFIRMED` at `0.80`.
3. **`P1` — `tools/security_vision/activity.py` (`"nour ramy - lying down - at PC-09"` Live Posture Bug)**:
   - Because `PC-09`'s monitor/desk occluded the seated person's legs in the middle of Camera 2's frame (`r = h/w < 0.8`), `posture()` reported `"lying down - at PC-09"`.
   - **Fix**: When `at_pc` is `True` (`at PC-xx`) and `r < 2.2`, `posture()` now reports `"seated or leaning"` (never `"lying down"`), suppresses `legs` colour when `r < 1.4`, and marks lower-body joints `OCCLUDED`.
4. **`P1` — `tools/robot_monitor/robot_collector.py` (Unplugged Robots Falsely Reported `online: true, state: IDLE`)**:
   - Both `UR5E_01` and `FANUC_01` were powered off/unreachable today, yet `robot_collector.py` posted `/robots/telemetry` and `/equipment/state` (`state="IDLE"`) when `snap["state"] == "UNKNOWN"`, keeping both robots `online: true` in DB and OPC UA.
   - **Fix**: Skip reporting when `snap["state"] == "UNKNOWN"`, post `TELEMETRY_STALE` only once per drop, and only post `/equipment/state` when `snap["state"] in ("MOVING", "STATIONARY")`.
5. **`P2` — `tools/knowledge/kb.py` (`120 s` Interactive Embedding Timeout)**:
   - **Fix**: Bounded interactive single-query `search()` embedding timeout to `4.0 s` (`query_embed_timeout_s`) with instant BM25 fallback.
6. **`P2` — `launch.bat` (`line 242` Overwrote Build Stamp with `"unstamped"`)**:
   - **Fix**: Delegated `launch.bat` image builds to `tools\deploy\build_images.ps1` so `--build-arg BUILD_COMMIT` and `BUILD_TIME` are always stamped.

---

## 3. Deliverable Package Index (`reports/live-lab-finalization-2026-11-18/`)

1. [GEMINI_EXECUTIVE_SUMMARY.md](./GEMINI_EXECUTIVE_SUMMARY.md)
2. [SYSTEM_INVENTORY_LIVE.md](./SYSTEM_INVENTORY_LIVE.md)
3. [DEVICE_AND_FIRMWARE_TEST_RESULTS.md](./DEVICE_AND_FIRMWARE_TEST_RESULTS.md)
4. [CAMERA_GLOBAL_TRACKING_LIVE_TESTS.md](./CAMERA_GLOBAL_TRACKING_LIVE_TESTS.md)
5. [FLOOR_MAP_CALIBRATION_AND_DESK_MAPPING.md](./FLOOR_MAP_CALIBRATION_AND_DESK_MAPPING.md)
6. [PC_AGENTS_RELAY_USB_KIT_AND_FIREWALL.md](./PC_AGENTS_RELAY_USB_KIT_AND_FIREWALL.md)
7. [UR5E_FANUC_DIGITAL_TWIN_OPCUA.md](./UR5E_FANUC_DIGITAL_TWIN_OPCUA.md)
8. [AI_OLLAMA_RAG_VOICE_BENCHMARK.md](./AI_OLLAMA_RAG_VOICE_BENCHMARK.md)
9. [N8N_OBSIDIAN_AND_TABLET.md](./N8N_OBSIDIAN_AND_TABLET.md)
10. [RUNTIME_TERMINAL_DOCKER_OPTIMIZATION.md](./RUNTIME_TERMINAL_DOCKER_OPTIMIZATION.md)
11. [FIXES_AND_CHANGED_FILES.md](./FIXES_AND_CHANGED_FILES.md)
12. [TEST_MATRIX_WITH_EVIDENCE.md](./TEST_MATRIX_WITH_EVIDENCE.md)
13. [BEFORE_AFTER_METRICS.md](./BEFORE_AFTER_METRICS.md)
14. [BLOCKERS_AND_GIU_IT_ACTIONS.md](./BLOCKERS_AND_GIU_IT_ACTIONS.md)
15. [CLAUDE_HANDOFF_CONTRACT_ISSUES.md](./CLAUDE_HANDOFF_CONTRACT_ISSUES.md)
16. [ROLLBACK_AND_NEXT_SESSION_RUNBOOK.md](./ROLLBACK_AND_NEXT_SESSION_RUNBOOK.md)
17. Machine-Readable Raw Artifacts (`raw/`):
    - `device_inventory_live.csv` & `device_inventory_live.json`
    - `service_health_live.csv` & `service_health_live.json`
    - `camera_metrics_live.json`
    - `test_outcomes.csv`
    - `benchmarks_live.json`
    - `blockers.csv`
