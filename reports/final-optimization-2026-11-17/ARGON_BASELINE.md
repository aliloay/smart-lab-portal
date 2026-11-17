# ARGON_BASELINE.md

- **Timestamp Captured**: `2026-11-17T23:18:08+02:00`
- **Raw Snapshot File**: `reports/final-optimization-2026-11-17/raw/lab_snapshot-20261117-231808-100-31332.csv`

---

## 1. Host Memory, CPU, Disk & GPU Baseline (`LIVE MEASURED`)

| Metric | Baseline Value | Threshold / Target | Status |
|---|---|---|---|
| Total Physical RAM | `16,213 MB` | — | `LIVE MEASURED` |
| Free Physical RAM | `884 MB – 1,258 MB` | `> 1,500 MB` warning / `> 700 MB` stop line | **WARNING (Memory Pressure)** |
| Committed Memory | `23.6 GB / 37.6 GB` (`62%`) | `< 80%` | `LIVE MEASURED` |
| Top RAM Consumers (Working Set / Private) | `vmmemWSL`: `3,162 MB / 4,090 MB`<br>`chrome` (23 procs): `2,210 MB / 2,844 MB`<br>`Code` (27 procs): `1,829 MB / 2,681 MB`<br>`claude` (13 procs): `1,729 MB / 1,924 MB`<br>`svchost` (93 procs): `1,555 MB / 1,458 MB` | WSL + IDE + Browser + dual AI agents consume ~10.5 GB | `LIVE MEASURED` |
| GPU (NVIDIA GTX 1650) | `385 MiB / 4,096 MiB` (`9.4%`), Util `4–19%`, `41 °C` | `< 3,500 MiB` | Healthy (`LIVE MEASURED`) |
| Disk `C:` Free Space | `22.02 GB / 222.92 GB` (`9.9%` free) | `> 15 GB` | Watch closely (`LIVE MEASURED`) |
| Disk `D:` Free Space | `796.65 GB / 931.51 GB` (`85.5%` free) | — | Healthy (`LIVE MEASURED`) |

---

## 2. Baseline Endpoint & Service Latency (`LIVE MEASURED` via `lab_snapshot.ps1`)

| Probe Target | HTTP Code | Latency (`ms`) | Evidence Class |
|---|---|---|---|
| `GET http://127.0.0.1:8000/api/health` | `200` | `15 ms` | `LIVE MEASURED` |
| `GET http://127.0.0.1:5100/health` (Camera 1) | `0` (DOWN) | `2,043 ms` (conn refused) | `LIVE MEASURED` |
| `GET http://127.0.0.1:5101/health` (Camera 2) | `0` (DOWN) | `2,035 ms` (conn refused) | `LIVE MEASURED` |
| `GET http://127.0.0.1:5199/status` (Knowledge) | `0` (DOWN) | `2,068 ms` (conn refused) | `LIVE MEASURED` |
| `GET http://127.0.0.1:5320/health` (Voice) | `0` (DOWN) | `2,039 ms` (conn refused) | `LIVE MEASURED` |
| `GET http://127.0.0.1:11434/api/tags` (Ollama) | `200` | `8 ms` | `LIVE MEASURED` |

---

## 3. Baseline 17 Nov Live Lab Session Metrics (`OBSERVED` from 17 Nov Logs & Reports)

From `recordings/identity_log_SECCAM_LAB01.jsonl`, `identity_log_SECCAM_LAB02.jsonl`, `crosscam_obs_*.jsonl`, and `docs/reports/local-only-2026-11-17/FULL_CONCURRENT_SYSTEM_TEST.md`:

| Subsystem / Metric | 17 Nov Lab Baseline | Root Bottleneck / Issue Identified |
|---|---|---|
| Full Concurrent Stack (10/10 devices + 5 containers + 11 host services) | `54%` CPU, `0 pages/s` paging, `0 ms` disk latency, `28%` GPU (`1,472 / 4,096 MB`), `/api/health` `7 ms` p50 | Concurrent steady-state compute fits comfortably when IDE/browser bloat is controlled |
| Security Camera 1 (`SECCAM_LAB01`) | `6.1 fps` stream, `5.9 fps` analysis, `82.6 ms` pass (`31.8 ms` detector + `46.5 ms` ReID + `3.7 ms` naming) | ReID (`person_reid_youtu_2021nov.onnx` on CPU) is 56% of pass time |
| Security Camera 2 (`SECCAM_LAB02`) | `14.1 fps` stream, `6.1 fps` analysis, `73.7 ms` pass (`33.3 ms` detector + `37.0 ms` ReID + `3.2 ms` naming) | Stable 6 fps analysis |
| Cross-Camera `CROSSCAM_CONFLICT` Count (17 Nov) | **3,069 logged conflicts** (`1,545` on Cam 1 + `1,524` on Cam 2 across 7 episodes) | Missing confirmed-identity veto + UR5e perspective floor gap (`0.7–1.3 m`) + unthrottled 6 Hz logging |
| `NAMED_BY_DESK` Log Count on Cam 1 (17 Nov) | **1,191 logged events** in 3 hours for `USER5` | `Labeler.assign()` wiped `t.source == "desk"` every frame when `t.label in self.face_named` |
| Global Person Numbering (`lab_people_LAB_01.json`) | Reached **`Person 230`** for ~5 real people in one afternoon | Confirmed identities did not reuse their existing `lab_no` across breaks/restarts within `PRESENT_S`, and `assign()` locked/wrote disk twice per pass |
| Partial Body Posture at Cam 2 Bottom Edge | Reported `"lying down"` or `"bending or crouching"` | `activity.posture()` ignored frame-bottom clipping (`y + h >= fh - 3`) |
| Engineer PC (`S2PC136`) Relay Startup | `0 copies` running during lab install | Unescaped `\r` in `INSTALL_SMARTLAB_v17nov.ps1` (`$dst\relay\relay.py`) + no fallback to `0.0.0.0` in `relay.py` when `--listen` IP is unavailable |
| `lab_usb_kit/MANIFEST.json` Verification | **7 of 859 files failed SHA-256** (`Install-CurrentUser.ps1`, `Check-CurrentUser.ps1`, etc.) | Git CRLF checkout altered hashes of `.ps1` and `.md` files, causing `Install-CurrentUser.ps1` to abort with `"The kit is damaged"` |

---

## 4. Baseline Test Suite Execution (`LIVE MEASURED` before edits)

- Command: `py -m pytest -q tools/security_vision tools/robot_monitor tools/knowledge tools/pc_agent/test_pc_agent.py tools/pc_agent/test_agent_update.py tools/pc_agent/test_exam_lockdown.py tools/relay/test_relay.py`
- Result: **`489 passed, 26 skipped in 54.22s`**
