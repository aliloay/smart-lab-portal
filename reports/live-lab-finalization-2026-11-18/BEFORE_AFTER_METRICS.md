# BEFORE_AFTER_METRICS.md

Machine-readable benchmark data is saved in:
- `reports/live-lab-finalization-2026-11-18/raw/benchmarks_live.json`
- `reports/live-lab-finalization-2026-11-18/raw/camera_metrics_live.json`
- `D:\SmartLabData\live-lab-finalization-2026-11-18\raw\benchmarks_live.json`

---

## 1. Multi-Camera Vision & Calibration: 17 Nov Baseline vs 18 Nov Live at GIU (`LIVE_PHYSICAL`)

| Metric | 17 Nov Live Lab (Before Argon) | 18 Nov Live Lab at GIU (After Argon + Today's Calibration) | Measured Improvement | Evidence Class |
|---|---:|---:|---|---|
| `SECCAM_LAB01` `CROSSCAM_CONFLICT` Count | `1,545` | **`5`** | **`-99.68%`** | `LIVE_PHYSICAL` |
| `SECCAM_LAB02` `CROSSCAM_CONFLICT` Count | `1,524` | **`7`** | **`-99.54%`** | `LIVE_PHYSICAL` |
| Total `CROSSCAM_CONFLICT` Log Entries | `3,069` | **`12`** | **`-99.61%`** | `LIVE_PHYSICAL` |
| `SECCAM_LAB01` `NAMED_BY_DESK` Log Flood | `1,191` | **`0`** | **`-100.0%`** | `LIVE_PHYSICAL` |
| `SECCAM_LAB01` Floor Map Leave-One-Out Max Error | `0.500 m` (`UR5e_front`) | **`0.419 m`** (`median = 0.197 m`) | **`-16.2%` max error; 7/8 today's spots `< 0.70 m` gate (was `1/8`)** | `LIVE_PHYSICAL` |
| `SECCAM_LAB02` Floor Map Leave-One-Out Median / Max Error | `0.340 m` max (7 pts) | **`0.214 m` median / `0.625 m` max** (31 pts) | All 26 unique points `< 0.70 m` gate | `LIVE_PHYSICAL` |
| Global Person Number Merges (`LAB_NUMBER_MERGED`) | `84` | **`162`** (`67` Cam 1 + `95` Cam 2) | **`+92.9%`** cross-camera number convergence | `LIVE_PHYSICAL` |
| Duplicate `USER6` Entries in `lab_people_LAB_01.json` | `8` (`'3','4','5','6','9','16','22','34'`) | **`1`** (Single-owner invariant in `labmap.py`) | Eliminates split identity (`nour ramy` on both `Person 3` and `Person 4`) | `LIVE_PHYSICAL` + `UNIT_TEST` |
| Seated-at-PC Short-Box Posture (`SECCAM_LAB02` at `PC-09`) | `"lying down - at PC-09"` (`0%` accurate) | **`"seated or leaning - at PC-09"` (`100%` accurate)** | Eliminates false `"lying down"` description at PC desks | `LIVE_PHYSICAL` + `UNIT_TEST` |

---

## 2. Lab PC Relay, AI Runtime, Voice & Portal Metrics (`LIVE_PHYSICAL` + `LIVE_SERVICE`)

| Metric | 17 Nov Baseline | 18 Nov Live at GIU | Measured Improvement | Evidence Class |
|---|---:|---:|---|---|
| Student Lab PCs (`10.40.20.x`) Online via `S2PC136` Relay | **`0`** (Relay down + Firewall blocked) | **`6` Student PCs (`PC4, PC13, PC14, PC17, PC18, PC19`) + `PC_ENG` + `PC_ADMIN_LAPTOP` = `8` PCs Live** | Full multi-subnet relay (`10.40.20.x` $\rightarrow$ `10.30.11.136:8000` $\rightarrow$ `192.168.1.200:8000`) verified live | `LIVE_PHYSICAL` |
| `lab_usb_kit` SHA-256 Manifest Verification | `7 / 859` failed (CRLF mismatch) | **`859 / 859` passed (`0` wrong)** | `100%` pass rate across LF & CRLF | `LIVE_SERVICE` |
| Disconnected Robot (`UR5E_01` / `FANUC_01`) False Online Rate | `100%` (`online: true, state: IDLE` while unplugged) | **`0%`** (Skip `UNKNOWN`, post `TELEMETRY_STALE` once then expire) | Eliminates phantom `ONLINE / IDLE` robots when controllers are off | `UNIT_TEST` + `LIVE_SERVICE` |
| Ollama `nomic-embed-text` Latency (with Cameras Live) | `> 90,000 ms` timeout (when `num_gpu=0` omitted on `/api/embeddings`) | **`3,952.4 ms` cold / `116.1 ms` warm** (`num_gpu=0` on `/api/embed`) | Zero CUDA/DirectML deadlock; `116 ms` warm embedding | `LIVE_SERVICE` |
| Ollama `qwen2.5:1.5b` CPU Inference (with Cameras Live) | Timed out after embed stall | **Cold**: `6,963 ms` first token / `10,031 ms` total<br>**Warm**: **`390.1 ms` first token / `3,620.2 ms` total** (`6.82 tok/s`) | Sub-400 ms warm first-token latency on CPU while both cameras hold GPU | `LIVE_SERVICE` |
| Knowledge `/ask` (`route="lookup"`) Latency | `25,800 ms` (LLM fallback on stock/door/node questions) | **`6.1 ms – 95.1 ms`** | **`> 270x` faster** instant grounded answers | `LIVE_SERVICE` |
| Voice Service (`:5320`) TTS / STT Latency | Not measured at GIU on 17 Nov | **TTS (`Piper`)**: `685.9 ms` (`2.52 s` audio)<br>**STT (`Whisper tiny.en`)**: `3,535.1 ms` | Verified live under concurrent dual-camera load | `LIVE_SERVICE` |
| `/api/incidents` Payload & Latency (Commit `b685a43`) | `269 KB` (`134.4 KB` filtered), `23.4 ms` p50 | **`81.4 KB` raw (`7.0 KB` gzip), `20.0 ms` p50** | `-39.4%` payload, keyset pagination + SQL-side filtering | `LIVE_SERVICE` |
| Frontend Motion Bundle Chunk (Commit `d085b73`) | `38.5 KB` gzip | **`26.3 KB` gzip** (`motion-TaJcjnZ4.js` verified in live `index.html`) | `-31.7%` gzip bundle size | `LIVE_SERVICE` |
