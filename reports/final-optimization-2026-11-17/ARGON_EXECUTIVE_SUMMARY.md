# ARGON_EXECUTIVE_SUMMARY.md

- **Agent**: Argon Max (Antigravity) — Independent Systems, Vision, Devices, AI Runtime & Infrastructure Auditor & Implementation Owner
- **Date**: 2026-11-17 (Final Optimization & Upgrade Pass)
- **Worktree & Branch**: `C:\Projects\smart-lab-argon` (`opt/argon-systems-vision-2026-11-17`, branched from `c68adb0`)
- **Main Repo Status**: `C:\Projects\smart-lab-portal` (`fix/pre-lab-hardening`) left **100% untouched** while Claude Code Max worked concurrently.

---

## 1. Executive Mission Summary

Following the 17 Nov GIU Smart Lab live session (where all 10 hardware devices, 5 Docker containers, and 11 host services operated concurrently), Argon Max conducted an exhaustive, evidence-backed audit of the host runtime, multi-camera vision pipeline, global person numbering, AI/GPU admission gate, USB PC deployment kit, TCP relay, orchestration scripts, and ESP32 firmware.

Rather than stopping at a paper review, Argon Max **isolated a dedicated Git worktree (`C:\Projects\smart-lab-argon`), root-caused 9 concrete P1/P2 defects across the runtime and vision stack, implemented surgical fixes across 28 Argon-owned files, added 6 new regression test suites (`498 passed, 0 failed`), and validated the fixes against 24,499 real 17 Nov multi-camera observation snapshots.**

---

## 2. Key Breakthroughs & Quantified Before/After Results

| Domain | Defect / Bottleneck Found | Root Cause (`file:line`) | Quantified Before -> After Result |
|---|---|---|---|
| **1. Multi-Camera Vision (`crosscam.py`, `labmap.py`, `security_vision.py`)** | **3,069 `CROSSCAM_CONFLICT` logs** (`1,545` Cam 1 + `1,524` Cam 2) and false `Person N` merges between Ali (`USER1`), Nour (`USER6`), and Hemaly (`USER5`) near the UR5e table on 17 Nov. | `_share_live()` scored floor proximity without checking if two tracks already held different confirmed identities present in the views; UR5e perspective shifted same-person feet `0.7–1.3 m` (`> GATE_M = 0.7 m`); `self.links` included conflicting pairs before line 361 checked for conflicts. | - False cross-person links: **`35` (`3,069` pass logs) -> `0` (`-100%`)**<br>- True same-person pairings: **`+20.5%` on Cam 1 (`663 -> 799`)**, **`+19.3%` on Cam 2 (`732 -> 873`)**<br>- Conflict disk log spam: **`-99.5%`** (`LIVE MEASURED` on 17 Nov replay) |
| **2. Partial Body Posture & Keypoints (`activity.py`)** | Person at Camera 2 bottom edge (legs cut off) misclassified as `"lying down"` or `"bending or crouching"`; no explicit joint visibility states. | `activity.posture()` used raw `h / w` aspect ratio without checking bottom frame-edge clipping (`y + h >= fh - 3`). | - Bottom-clipped posture accuracy: **`0% -> 100%`** (`"upper body in view"`)<br>- Added 8-joint `pose_visibility` (`OBSERVED`, `OCCLUDED`, `PREDICTED`, `OUT_OF_FRAME`, `xy=None` for hidden joints) in **`102 µs/frame`** |
| **3. Desk Naming Stability (`vision.py`)** | **1,191 `NAMED_BY_DESK` logs** in 3 hours for `USER5` (Eng. Hemaly) on Camera 1. | `Labeler.assign()` (`vision.py:1124`) wiped `t.source == "desk"` every frame when `t.label` was in `self.face_named` (not door `inside`), causing `home_desk()` to re-name and re-log 6x/s. | - `NAMED_BY_DESK` log spam: **`1,191 -> 1` per seating episode (`-99.9%`)**<br>- Desk-named track label no longer flickers every pass |
| **4. Global Person Register (`labmap.py`)** | Lab numbers inflated to **`Person 230`** for ~5 people; double file lock/write per pass. | `assign()` called `reg.update()` twice per pass and did not reuse existing `lab_no` when a track already carried a confirmed `auth_subject` in `people`. | - Register lock/disk I/O latency: **`11.79 ms -> 8.56 ms` (`-27.4%`)**<br>- Confirmed identities immediately reclaim their existing `lab_no` across breaks/restarts |
| **5. PC USB Kit & Engineer Relay (`relay.py`, `lab_usb_kit/*`)** | Relay failed to start on `S2PC136` on 17 Nov; **7 of 859 files in `lab_usb_kit` failed SHA-256 check** on Windows due to Git CRLF line endings. | `relay.py` exited if `--listen 10.30.11.136` was unbound at boot (`WinError 10049`); `Install-CurrentUser.ps1` rejected CRLF text files against LF hashes in `MANIFEST.json`. | - `relay.py` automatically falls back to `0.0.0.0` (with `--allow` subnet ACLs)<br>- `Install-CurrentUser.ps1` & `Check-CurrentUser.ps1` verify **859 / 859 files (`0` wrong)** across LF & CRLF |
| **6. AI / GPU Gate & Watchdog (`gpu_gate.py`, `serve.py`, `status.ps1`, `watchdog.py`)** | `gpu_gate.py` checked `state == "LIVE"` while `security_vision.py` emits `"STREAMING"`; `kb.py`/`ollama_models.bat` defaulted to removed `qwen2.5:3b`; `status.ps1` printed `counters unavailable`. | State string mismatch (`"STREAMING"` vs `"LIVE"`); config drift after 27 Oct model switch to `qwen2.5:1.5b`; `Get-Counter -ErrorAction Stop` aborting on transient process exit. | - `gpu_gate.py` recognises `"STREAMING"` immediately<br>- Default model unified on `qwen2.5:1.5b`<br>- `serve.py` exposes `GET /health` for `watchdog.py`<br>- `status.ps1` reliably reports CPU, paging, disk latency, and GPU load |
| **7. ESP32 Firmware (`SmartLab_Consumable_Bin`, `ESP32CAM`, `Reusable_Bin`)** | Consumables Bin hammered HTTP POSTs with zero backoff on network failure; ESP32-CAM lacked Wi-Fi drop recovery in `loop()`. | `lastSentMs` only updated on `HTTP 200` in `SmartLab_Consumable_Bin.ino`; `ESP32CAM_Vision_FAST.ino` returned early in `setup()` and had an empty `loop()`. | - Added 5 s retry backoff (`lastFailMs`) in `SmartLab_Consumable_Bin.ino` to protect 10 Hz HX711 sampling<br>- Added non-blocking 10 s Wi-Fi reconnect + `WiFi.setSleep(false)` in `ESP32CAM` and `Reusable_Bin` |

---

## 3. Deliverable Package Index (`reports/final-optimization-2026-11-17/`)

1. [ARGON_EXECUTIVE_SUMMARY.md](./ARGON_EXECUTIVE_SUMMARY.md)
2. [ARGON_SYSTEM_INVENTORY.md](./ARGON_SYSTEM_INVENTORY.md)
3. [ARGON_BASELINE.md](./ARGON_BASELINE.md)
4. [ARGON_FINDINGS_ROOT_CAUSES.md](./ARGON_FINDINGS_ROOT_CAUSES.md)
5. [ARGON_FIXES_IMPLEMENTED.md](./ARGON_FIXES_IMPLEMENTED.md)
6. [ARGON_TEST_RESULTS.md](./ARGON_TEST_RESULTS.md)
7. [ARGON_BEFORE_AFTER_BENCHMARKS.md](./ARGON_BEFORE_AFTER_BENCHMARKS.md)
8. [ARGON_CAMERA_AND_DEVICE_RESULTS.md](./ARGON_CAMERA_AND_DEVICE_RESULTS.md)
9. [ARGON_RUNTIME_AND_TERMINAL_GUIDE.md](./ARGON_RUNTIME_AND_TERMINAL_GUIDE.md)
10. [ARGON_COORDINATION_MANIFEST.md](./ARGON_COORDINATION_MANIFEST.md)
11. [ARGON_REMAINING_GAPS.md](./ARGON_REMAINING_GAPS.md)
12. [ARGON_CHANGED_FILES_AND_ROLLBACK.md](./ARGON_CHANGED_FILES_AND_ROLLBACK.md)
13. Raw Data & Benchmarks:
    - `raw/lab_snapshot-20261117-231808-100-31332.csv`
    - `raw/argon_benchmarks.json`
    - `raw/argon_benchmarks.csv`
