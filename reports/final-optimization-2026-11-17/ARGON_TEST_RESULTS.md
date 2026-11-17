# ARGON_TEST_RESULTS.md

All test suites below were executed in `C:\Projects\smart-lab-argon` (`LIVE MEASURED` / `SIMULATED` as noted).

---

## 1. Automated Unit & Regression Test Suites (`LIVE MEASURED`)

| Test Suite / Command | Before Argon Fixes | After Argon Fixes | New Tests Added | Status |
|---|---|---|---|---|
| `tools/security_vision` (`pytest`) | `351 passed, 22 skipped` | **`360 passed, 22 skipped`** | `+4` (`test_ur5e_zone_two_confirmed_people_never_cross_pair_or_conflict`, `test_conflicting_labels_never_merge_lab_numbers`, `test_confirmed_person_reuses_lab_number_immediately_after_restart`, `test_bottom_clipped_partial_box_reports_upper_body_and_explicit_joint_visibility`, `test_desk_named_face_occupant_is_not_wiped_every_pass`) | **PASS (`0 failed`)** |
| `tools/knowledge` (`pytest`) | `87 passed` | **`88 passed`** | `+1` (`STREAMING` state check in `test_live_camera_metrics_parse`) | **PASS (`0 failed`)** |
| `tools/relay/test_relay.py` | `5 passed` | **`6 passed`** | `+1` (`test_serve_falls_back_to_all_interfaces_when_specific_ip_is_unavailable`) | **PASS (`0 failed`)** |
| `tools/robot_monitor` (`pytest`) | `27 passed, 4 skipped` | **`27 passed, 4 skipped`** | — | **PASS (`0 failed`)** |
| `tools/pc_agent` (`test_pc_agent.py`, `test_agent_update.py`, `test_exam_lockdown.py`) | `14 passed` | **`14 passed`** | — | **PASS (`0 failed`)** |
| `tools/ops/test_watchdog.py` | `3 passed` | **`3 passed`** | — | **PASS (`0 failed`)** |
| **Total Argon Pytest Suite** | **`487 passed, 26 skipped`** | **`498 passed, 26 skipped` in `65.15s`** | **All new & existing tests green** | **PASS (`100%`)** |

---

## 2. Multi-Camera & Identity Scenario Benchmark (`tools/security_vision/scenario_bench.py` — `SIMULATED`)

Executed: `py tools/security_vision/scenario_bench.py` (`17 scenarios in 2.0 s`):

| Scenario | `id_switches` | `false_names` | `name_switches` | `false_merges` | `fragments` | `idf1` | `named_share` | `review` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `01 one person enters` | 0 | 0 | 0 | 0 | 0 | `0.992` | `0.927` | 0 |
| `02 two enter together, one badge` | 0 | 0 | 0 | 0 | 0 | `0.992` | `0.000` | 2 |
| `02b two enter together, two badges, faces later` | 0 | 0 | 0 | 0 | 0 | `0.995` | `0.601` | 2 |
| `03 two side by side 60 s` | 0 | 0 | 0 | 0 | 0 | `0.997` | `0.981` | 0 |
| `04 two cross 4x` | 0 | 0 | 0 | 0 | 0 | `0.996` | `0.968` | 0 |
| `04b two cross 4x, similar clothes` | 0 | 0 | 0 | 0 | 0 | `0.996` | `0.968` | 0 |
| `06 sit / bend / crouch / lie / stand` | 0 | 0 | 0 | 0 | 0 | `0.996` | `0.962` | 0 |
| `07 hidden 1.5 s, reappears` | 0 | 0 | 0 | 0 | 0 | `0.995` | `0.965` | 0 |
| `07b hidden 4 s, reappears` | 0 | 0 | 0 | 0 | 0 | `0.995` | `0.964` | 0 |
| `07c dead zone 25 s` | 1 | 0 | 0 | 0 | 1 | `0.833` | `0.972` | 0 |
| `07d dead zone 25 s, look-alike walks there` | 1 | 0 | 0 | 0 | 1 | `0.833` | `0.972` | 0 |
| `11 leaves view 3 min, returns` | 1 | 0 | 0 | 0 | 1 | `0.916` | `0.975` | 0 |
| `08 running, sharp turns` | 0 | 0 | 0 | 0 | 0 | `0.985` | `0.953` | 0 |
| `09 camera off 10 s` | 0 | 0 | 0 | 0 | 0 | `0.995` | `0.954` | 0 |
| `10 lighting drops to 55 %` | 0 | 0 | 0 | 0 | 0 | `0.996` | `0.966` | 0 |
| `05 two cameras - camera 1` | 0 | 0 | 0 | 0 | 0 | `0.991` | `0.895` | 0 |
| `05 two cameras - camera 2` | 0 | 0 | 0 | 0 | 0 | `0.990` | `0.817` | 0 |

- **Result**: **`false_names = 0`, `name_switches = 0`, `false_merges = 0` across all 17 scenarios.**

---

## 3. USB Kit Integrity & Secret Scan Verification (`LIVE MEASURED`)

- Command: `py tools/pc_agent/make_kit.py --no-bundle`
- Output: `kit 1.1 bundle e8e7e4fc890e: 859 files, 0 MB, secret scan clean`
- Verified `Test-KitFile` in `Install-CurrentUser.ps1` and `Check-CurrentUser.ps1` passes 100% of files across both LF and CRLF line endings while rejecting tampered files.

---

## 4. What Could Not Be Run Live Tonight (`NOT RUN` / `BLOCKED` with Reason)

| Test / Verification | Status | Reason |
|---|---|---|
| Live RTSP stream from `SECCAM_LAB01` (`.106`) & `SECCAM_LAB02` (`.119`) | `BLOCKED` (Off-site) | Laptop is currently on home Wi-Fi (`192.168.1.8`), not connected to the GIU Smart Lab router (`192.168.1.200` Ethernet disconnected). Replayed 17 Nov recorded JSONL observations instead (`24,499` snapshots). |
| Live TCP/HTTP poll of `UR5E_01` (`.102`) & `FANUC_01` (`.101`) | `BLOCKED` (Off-site) | Physical robot controllers are at GIU lab; verified via 27 unit/replay tests in `tools/robot_monitor`. |
| Physical ESP32 board flashing (`BIN_NODE_1`, `REUSE_BIN_1`, `CAM_DOOR_01`) | `NOT RUN` (By rule & hardware absence) | No COM ports attached, and prompt safety rules forbid flashing physical ESP boards without explicit owner approval. |
