# TEST_MATRIX_WITH_EVIDENCE.md

Every test and verification item below is explicitly labeled with its evidence class (`LIVE_PHYSICAL`, `LIVE_SERVICE`, `HISTORICAL_REPLAY`, `SIMULATED`, `UNIT_TEST`, `STATIC_INSPECTION`, `BLOCKED`, or `NOT_RUN`).

---

## Complete Verification Matrix (18 November 2026)

| ID | Subsystem / Test Case | Evidence Class | Result | Quantitative Evidence / Proof |
|---|---|---|---|---|
| **T-01** | **Camera 1 (`SECCAM_LAB01`) Live RTSP + DirectML Detection/ReID** | `LIVE_PHYSICAL` | **PASS** | IP `192.168.1.155` (`8 ms` ping), `:5100/health` `STREAMING`, capture `13.85 fps`, analysis `5.4–6.0 fps`, `frame_age_ms` p50 `32 ms` / p95 `106 ms`, `0` reconnects. |
| **T-02** | **Camera 2 (`SECCAM_LAB02`) Live RTSP + DirectML Detection/ReID** | `LIVE_PHYSICAL` | **PASS** | IP `192.168.1.156` (`5–22 ms` ping), `:5101/health` `STREAMING`, capture `14.85 fps`, analysis `5.3–6.0 fps`, `frame_age_ms` p50 `36 ms` / p95 `98 ms`, `0` reconnects. |
| **T-03** | **Two-Camera Cross-Camera Conflict Veto & UR5e Wide Gate (18 Nov Live)** | `LIVE_PHYSICAL` | **PASS** | `CROSSCAM_CONFLICT` dropped from **`3,069`** (17 Nov) to **`12`** total today (`5` Cam 1 + `7` Cam 2 = **`-99.61%`**); `28` live `CROSSCAM_NAME` handoffs; `162` `LAB_NUMBER_MERGED` convergences. |
| **T-04** | **Desk Naming Stability (`NAMED_BY_DESK` Flood Elimination — 18 Nov Live)** | `LIVE_PHYSICAL` | **PASS** | `NAMED_BY_DESK` dropped from **`1,191`** (17 Nov) to **`0`** today (`-100.0%`). |
| **T-05** | **Floor Map Homography Refit (8 New Two-Camera Pairs on 18 Nov)** | `LIVE_PHYSICAL` | **PASS** | `SECCAM_LAB01` LOO median `0.197 m`, LOO max `0.419 m` (down from `0.500 m`); `SECCAM_LAB02` LOO median `0.214 m`, LOO max `0.625 m`; today's spots within `0.70 m` gate improved **`1/8` $\rightarrow$ `7/8`**. |
| **T-06** | **Global Register Single-Owner Invariant & Merge Ghost Cleanup (`labmap.py`)** | `UNIT_TEST` + `LIVE_PHYSICAL` | **PASS** | Fixed live `Person 3` vs `Person 4` duplicate `USER6` assignment; `test_single_owner_invariant_prevents_one_name_on_multiple_numbers` & `test_merged_number_is_removed_and_restore_does_not_loop_on_same_track` pass (`22/22` in `test_labmap.py`). |
| **T-07** | **Seated-at-PC Posture & Partial-Body Keypoint Visibility (`activity.py`)** | `UNIT_TEST` + `LIVE_PHYSICAL` | **PASS** | Fixed live `"nour ramy - lying down - at PC-09"` bug on `SECCAM_LAB02`; `test_person_seated_at_pc_desk_with_short_occluded_box_is_never_lying_down` passes; 8 body parts labeled `PREDICTED` / `OCCLUDED` / `OUT_OF_FRAME` (never `OBSERVED`). |
| **T-08** | **Multi-Camera & Identity 17-Scenario Benchmark (`scenario_bench.py`)** | `SIMULATED` | **PASS** | `17 / 17` scenarios in `2.0 s`: `false_names = 0`, `name_switches = 0`, `false_merges = 0` (`IDF1 = 0.833–0.997`). |
| **T-09** | **Full `tools/security_vision` Pytest Suite** | `UNIT_TEST` | **PASS** | **`393 passed, 22 skipped, 0 failed`**. |
| **T-10** | **Engineer PC (`S2PC136`) Dual-NIC Relay + 6 Student Lab PCs (`10.40.20.x`)** | `LIVE_PHYSICAL` | **PASS** | `PC_ENG` (`192.168.1.100` / `10.30.11.136`) + `PC_GIULAB20-PC4`, `PC13`, `PC14`, `PC17`, `PC18`, `PC19` (`10.40.20.x`) + `PC_ADMIN_LAPTOP` (`192.168.1.200`) all **`ONLINE`** (`last_seen` `1.5–13.0 s` ago). |
| **T-11** | **USB Kit 859/859 Hash Verification (LF & CRLF) + Relay Fallback** | `UNIT_TEST` + `LIVE_SERVICE` | **PASS** | `make_kit.py --no-bundle` verified `859 files, secret scan clean`; `test_relay.py` `6/6 passed`; `test_pc_agent` `14/14 passed`. |
| **T-12** | **Robot Collector False-Online Fix & Read-Only Verification** | `UNIT_TEST` + `STATIC_INSPECTION` | **PASS** | Fixed `robot_collector.py` posting `UNKNOWN` as `online: true, state: IDLE`; `tools/robot_monitor` `28 passed, 4 skipped, 0 failed`. |
| **T-13** | **Physical UR5e (`.102`) & FANUC (`.101`) Live Controller Motion** | `BLOCKED` | **BLOCKED** | Physical robot controllers were powered off / unplugged from `192.168.1.x` switch during the afternoon audit window (`.100` occupied by `PC_ENG`). |
| **T-14** | **Camera-First GPU Gate (`:5199/gpu-gate`) Under Live Dual-Camera Load** | `LIVE_SERVICE` | **PASS** | Returned `{"device": "cpu", "reason": "camera 5100 live, 5101 live - cameras first"}` in `6 ms`; `test_gpu_gate.py` `9/9 passed`. |
| **T-15** | **Ollama (`qwen2.5:1.5b` + `nomic-embed-text`) & Knowledge RAG (`:5199/ask`)** | `LIVE_SERVICE` | **PASS** | With `num_gpu=0`: warm embed `116.1 ms` (cold `3,952 ms`); warm `qwen2.5:1.5b` first token **`390.1 ms`**, total `3,620 ms` (`6.5–6.8 tok/s`); `/ask` `lookup` **`6.1–95.1 ms`**; `tools/knowledge` `88/88 passed`. |
| **T-16** | **Voice Service (`:5320/speak` Piper TTS + `:5320/transcribe` Whisper STT)** | `LIVE_SERVICE` | **PASS** | Piper TTS synthesized `2.52 s` WAV (`111 KB`) in **`685.9 ms`**; Faster-Whisper `tiny.en` transcribed it in **`3,535.1 ms`**. |
| **T-17** | **OPC UA Read-Only Server (`:4840`) & `/api/opcua/snapshot`** | `LIVE_SERVICE` | **PASS** | `:4840` open (`1 ms`), mirroring `LAB_01` devices & environment from `/api/opcua/snapshot`. |
| **T-18** | **n8n Workflows (`26/26`) & Obsidian Vault Link Integrity** | `LIVE_SERVICE` | **PASS** | `26/26` workflows listed in `smart-lab-portal-n8n-1`; `5x/5s` retries on 22 read/job nodes; `0` broken Obsidian links. |
| **T-19** | **ESP32 / ESP-CAM Firmware Compilation (`7/7` sketches)** | `STATIC_INSPECTION` | **PASS** | All 7 firmware sketches compiled cleanly (including `ESP32CAM_Vision_FAST` on `esp32@3.2.1`); physical flashing `NOT_RUN` (0 COM ports attached; nodes at home by plan). |
