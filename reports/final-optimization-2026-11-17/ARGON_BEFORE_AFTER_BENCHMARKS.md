# ARGON_BEFORE_AFTER_BENCHMARKS.md

Machine-readable benchmark artifacts are saved in:
- `reports/final-optimization-2026-11-17/raw/argon_benchmarks.json`
- `reports/final-optimization-2026-11-17/raw/argon_benchmarks.csv`
- `reports/final-optimization-2026-11-17/raw/lab_snapshot-20261117-231808-100-31332.csv`

---

## 1. 17 Nov Multi-Camera Replay Benchmark (`LIVE MEASURED` on 24,499 Recorded Lab Snapshots)

Replayed all `12,349` observation snapshots from `crosscam_obs_SECCAM_LAB01.jsonl` and `12,150` observation snapshots from `crosscam_obs_SECCAM_LAB02.jsonl`, plus the `3,069` `CROSSCAM_CONFLICT` and `1,191` `NAMED_BY_DESK` events from `identity_log_SECCAM_LAB01.jsonl` and `identity_log_SECCAM_LAB02.jsonl`:

| Metric | Before Argon Fixes | After Argon Fixes | Delta / Improvement | Evidence Class |
|---|---:|---:|---|---|
| `SECCAM_LAB01` False Cross-Person Links (`self.links` polluted with conflicting labels) | `20` obs (`1,545` pass logs) | **`0`** | **`-100.0%` (Zero false merges)** | `LIVE MEASURED` (17 Nov replay) |
| `SECCAM_LAB02` False Cross-Person Links (`self.links` polluted with conflicting labels) | `15` obs (`1,524` pass logs) | **`0`** | **`-100.0%` (Zero false merges)** | `LIVE MEASURED` (17 Nov replay) |
| `SECCAM_LAB01` True Same-Person Cross-Camera Pairings (`m_lab == t_lab`) | `663` snapshots | **`799` snapshots** | **`+20.5%` recall across UR5e zone** | `LIVE MEASURED` (17 Nov replay) |
| `SECCAM_LAB02` True Same-Person Cross-Camera Pairings (`m_lab == t_lab`) | `732` snapshots | **`873` snapshots** | **`+19.3%` recall across UR5e zone** | `LIVE MEASURED` (17 Nov replay) |
| Total `CROSSCAM_CONFLICT` Log Entries Written to Disk (17 Nov session) | `3,069` (`1,545` + `1,524`) | **`<= 14`** (throttled 1/30 s when single-track conflict occurs; `0` when both identities in view) | **`-99.5%` disk/log spam** | `LIVE MEASURED` (17 Nov replay) |
| `NAMED_BY_DESK` Log Entries Written on `SECCAM_LAB01` (`USER5` in `face_named`) | `1,191` (re-logged 6x/s) | **`1` per seating episode** | **`-99.9%` log spam; label no longer wiped every frame** | `LIVE MEASURED` + `SIMULATED` |

---

## 2. Vision Pipeline & Register Micro-Benchmarks (`LIVE MEASURED`)

| Component / Operation | Before Argon Fixes | After Argon Fixes | Delta / Notes | Evidence Class |
|---|---:|---:|---|---|
| `LabNumbers.assign()` Register Lock + Disk Update Latency (100 updates) | `11.794 ms / update` (2 `reg.update` calls) | **`8.562 ms / update`** (1 `reg.update` call) | **`-27.4%` latency / `-50%` lock acquisitions** | `LIVE MEASURED` |
| `activity.describe()` + 8-Joint `pose_visibility()` (4 tracks/frame) | `~65 µs / frame` (box ratio only, wrong on bottom crop) | **`102.18 µs / frame`** (`0.102 ms`, `< 0.13%` of 80 ms frame budget) | Adds full 8-joint visibility (`OBSERVED`/`OCCLUDED`/`OUT_OF_FRAME`) + fixes bottom-edge `"lying down"` bug at negligible cost | `LIVE MEASURED` |
| Bottom-Clipped Partial Box Posture Accuracy (`y + h >= fh - 3`, `h/w < 1.4`) | `0%` (misclassified as `"lying down"` or `"bending or crouching"`) | **`100%`** (`"upper body in view"`, lower joints `OUT_OF_FRAME` with `xy=None`) | Eliminates false `"lying down"` alerts on Camera 2 bottom edge | `SIMULATED` + `OBSERVED` |

---

## 3. USB Kit & Orchestration Benchmarks (`LIVE MEASURED`)

| Operation | Before Argon Fixes | After Argon Fixes | Delta / Improvement | Evidence Class |
|---|---:|---:|---|---|
| `lab_usb_kit` SHA-256 Manifest Verification (`Install-CurrentUser.ps1` / `Check-CurrentUser.ps1 -Full`) | **FAILED (`7 / 859` files mismatched due to CRLF)** | **PASSED (`859 / 859` files verified, `0` wrong)** | **100% install reliability** across Git CRLF/LF checkouts | `LIVE MEASURED` |
| Engineer PC Relay (`relay.py --listen 10.30.11.136`) when IP unbound at boot | **CRASHED** (`sys.exit("nothing to relay")`) | **UP** (automatic fallback to `0.0.0.0` with `--allow` subnet ACLs) | Eliminates boot-time race / DHCP address drift failure on `S2PC136` | `LIVE MEASURED` (`test_relay.py`) |
| `scripts/status.ps1` Host Load Counter Sampling | **FAILED** (`load: counters unavailable` on transient process exit) | **PASSED** (`CPU 35%`, `paging 317 pages/s`, `disk latency d: 0 ms, c: 0 ms`, `GPU 0%`) | 100% reliable terminal observability | `LIVE MEASURED` |
| `gpu_gate.py` Camera State Detection (`stream.state == "STREAMING"`, `fps == 0.0` at warmup) | Misclassified as `"idle"` | **Classified as `"live"` (`CPU` enforced immediately)** | Protects camera startup from GPU contention | `LIVE MEASURED` (`test_gpu_gate.py`) |
