# CAMERA_GLOBAL_TRACKING_LIVE_TESTS.md

- **Evidence Class**: `LIVE_PHYSICAL` (both physical Tapo C200 RTSP cameras running concurrently on GIU LAN `192.168.1.155` and `192.168.1.156`) + `UNIT_TEST` + `SIMULATED` (`scenario_bench.py`).
- **Consent Status**: All live camera testing at GIU was conducted exclusively with consenting project team members (`USER1`, `USER5`, `USER6`). No biometric templates, raw face crops, or personal photos are included in any report or committed file.

---

## 1. Live Physical Camera Stream & Inference Performance at GIU (`LIVE_PHYSICAL`)

Measured concurrently on `SECCAM_LAB01` (`192.168.1.155` $\rightarrow$ `127.0.0.1:5100`) and `SECCAM_LAB02` (`192.168.1.156` $\rightarrow$ `127.0.0.1:5101`) while the full Docker + host service stack was running:

| Metric | Camera 1 (`SECCAM_LAB01`, `:5100`) | Camera 2 (`SECCAM_LAB02`, `:5101`) | Evidence Class |
|---|---|---|---|
| Physical RTSP IP & Ping RTT | `192.168.1.155` (`8 ms` RTT) | `192.168.1.156` (`5–22 ms` RTT) | `LIVE_PHYSICAL` |
| Stream State & Uptime | `STREAMING` (`0` reconnects) | `STREAMING` (`0` reconnects) | `LIVE_PHYSICAL` |
| Capture FPS (RTSP Input) | **`13.85 – 14.18 fps`** (`read_ms` p50 `57.4 ms`, p95 `122.9 ms`) | **`14.85 – 14.96 fps`** (`read_ms` p50 `64.8 ms`, p95 `106.2 ms`) | `LIVE_PHYSICAL` |
| Analysis FPS (Target `6.0 fps`) | **`5.40 – 6.00 fps`** (`frame_age_ms` p50 `32.0 ms`, p95 `106.0 ms`) | **`5.33 – 6.00 fps`** (`frame_age_ms` p50 `36.0 ms`, p95 `98.0 ms`) | `LIVE_PHYSICAL` |
| Render / MJPEG Serve FPS | **`9.17 – 9.51 fps`** (`serve_age_ms` p50 `120.0 ms`, p95 `285.0 ms`) | **`9.25 – 9.56 fps`** (`serve_age_ms` p50 `112.0 ms`, p95 `262.0 ms`) | `LIVE_PHYSICAL` |
| Detector Engine & Latency | `directml-gpu1` (`detect_main` p50 `56.7 ms`, `zoom` p50 `19.3 ms`) | `directml-gpu1` (`detect_main` p50 `55.9 ms`, `zoom` p50 `21.2 ms`) | `LIVE_PHYSICAL` |
| ReID Engine & Latency | `directml-gpu1` (`reid` p50 `1.6 ms`, `12 ms/crop`) | `directml-gpu1` (`reid` p50 `3.0 ms`, `12 ms/crop`) | `LIVE_PHYSICAL` |
| View Calibration State | `calibrated` (`586` matching room features, `17` zones) | `calibrated` (`665` matching room features, `13` zones) | `LIVE_PHYSICAL` |
| Process Memory & GPU VRAM | `629 MB` RSS (`1,457 MB` private); shared GPU `868 / 4,096 MiB` (`30%` util) | `639 MB` RSS (`1,469 MB` private); shared GPU `868 / 4,096 MiB` (`33%` util) | `LIVE_PHYSICAL` |

---

## 2. Live 18 Nov Cross-Camera Tracking Results vs 17 Nov Baseline (`LIVE_PHYSICAL`)

Comparison of `recordings/identity_log_SECCAM_LAB01.jsonl` and `recordings/identity_log_SECCAM_LAB02.jsonl` between the 17 Nov GIU session (before Argon fixes) and today's 18 Nov GIU session (`t >= 1795000000`, with Argon's `fe126b7` fixes running live):

| Event Kind | 17 Nov Live Lab (Before Argon) | 18 Nov Live Lab Today (With Argon `fe126b7`) | Measured Live Improvement |
|---|---:|---:|---|
| **`CROSSCAM_CONFLICT` (Camera 1)** | `1,545` | **`5`** | **`-99.68%` (`LIVE_PHYSICAL`)** |
| **`CROSSCAM_CONFLICT` (Camera 2)** | `1,524` | **`7`** | **`-99.54%` (`LIVE_PHYSICAL`)** |
| **`NAMED_BY_DESK` Log Flood (Camera 1)** | `1,191` | **`0`** | **`-100.0%` (`LIVE_PHYSICAL`)** |
| **`CROSSCAM_NAME` (Verified Cross-Camera Handoffs)** | `31` | **`28`** (`11` Cam 1 + `17` Cam 2) | Clean cross-camera handoffs preserved |
| **`LAB_NUMBER_MERGED` (Global ID Convergences)** | `84` | **`162`** (`67` Cam 1 + `95` Cam 2) | **`+92.9%`** more global number convergences after floor map refit + wide gate |
| **`LAB_NUMBER_BACK` + `NAME_BACK_BY_LOOK`** | `19` | **`160`** (`75` Cam 1 + `85` Cam 2) | Reacquires global number & confirmed name after occlusion/walk-away |

---

## 3. New Live Defects Discovered On-Site Today & Immediately Fixed by Gemini (`LIVE_PHYSICAL` $\rightarrow$ Fixed in `opt/gemini-live-lab-finalization-2026-11-18`)

During live inspection of `SECCAM_LAB01` and `SECCAM_LAB02` at `16:44–16:54` today, we caught **three subtle live defects** that neither prior pass had seen:

### Defect 1 (`P1` — `labmap.py`): Multi-Entry `who` Contamination in `lab_people_LAB_01.json` Putting One Confirmed Name on Two Different People Across Cameras
- **Live Symptom (`LIVE_PHYSICAL` at `16:54:32`)**:
  - Camera 1 reported `track 13` (`lab_no: 3`, at the `UR5e`) as **`nour ramy (USER6)`** and `track 28` (`lab_no: 4`, at `PC-09`) as **`Person 4`**.
  - At the **exact same second**, Camera 2 reported `track 21` (`lab_no: 4`, at `PC-09`) as **`nour ramy (USER6)`** and `track 19` (`lab_no: 3`, at the `UR5e`) as **`Person 3`**.
- **Root Cause (`labmap.py:296`, `310`, `321`)**:
  - Whenever a track was numbered first (e.g. `Person 9`, `Person 22`, `Person 4`, `Person 16`, `Person 34`, `Person 6`, `Person 5`, `Person 3`) and later named `USER6`, `labmap.py:297` wrote `e["who"] = {"auth_subject": "USER6", ...}` onto `people[str(t.lab_no)]` **without removing `"who"` from previous numbers that held `USER6` and without deleting numbers that were merged away (`LAB_NUMBER_MERGED`)**.
  - Inspecting `lab_people_LAB_01.json` live showed **8 different entries** (`'3', '4', '5', '6', '9', '16', '22', '34'`) all carrying `who.auth_subject == "USER6"` simultaneously!
  - Consequently: (a) Camera 1 restored `USER6` from `people["3"]` onto `Person 3` while Camera 2 restored `USER6` from `people["4"]` onto `Person 4`; (b) `_confirmed_back()` saw `len(gone) > 1` (because multiple entries for `USER6` were not in `busy`) and refused to restore; and (c) when `Labeler._veto()` dropped a stale look on `track 10`, `labmap.py` forced `USER6` back onto `track 10` every 6 seconds!
- **Fix Implemented (`tools/security_vision/labmap.py` & `identity.py`)**:
  1. Enforced a strict **Single-Owner Invariant** in `people`: an `auth_subject` can sit on at most **one** entry in `people` at any time. Writing `e["who"]` strips that `auth_subject` from all other entries (deleting non-busy ghost entries).
  2. Deleted `merged_away` numbers from `people` immediately upon `LAB_NUMBER_MERGED` / `LAB_NUMBER_BACK`.
  3. Guarded `names_by_number` so it never restores an `auth_subject` onto `t.lab_no` if `peer_tracks` currently holds that `auth_subject` on a different `lab_no`, and never restores the same `(t.id, auth_subject)` twice on the same `t.id` (`self.restored_once`).
  4. Deduplicated `_confirmed_back()` candidates by `auth_subject`.
  5. Added `"came back (same look)"` to `REACQUIRE_HOW` in `identity.py:42` so look-based restores emit `PERSON_TRACK_REACQUIRED` at `reacquire_strength = 0.65`.

### Defect 2 (`P1` — `activity.py`): Person Seated at `PC-09` Reported as `"lying down - at PC-09"`
- **Live Symptom (`LIVE_PHYSICAL` at `16:54:32` on `SECCAM_LAB02`)**:
  - `track 21` at `PC-09` (`size: 0.207`) was described as: `"nour ramy (black top, black trousers) - lying down - at PC-09"`.
- **Root Cause (`activity.py:121-137`)**:
  - Our 17 Nov `is_bottom_clipped()` fix only checked if the box touched the bottom edge of the camera frame (`y + h >= fh - 3`).
  - However, `PC-09` is in the **middle** of Camera 2's frame (`y = 0.49 .. 0.75`). When a person sits at `PC-09`, the monitor and desk hide their lower body in the middle of the frame, leaving a short, wide upper-body box (`r = h / w < 0.8`), which `posture()` classified as `"lying down"` and `legs_colour()` sampled as `"black trousers"` (actually the black chair/desk).
- **Fix Implemented (`tools/security_vision/activity.py`)**:
  - When a person is at a PC desk (`at_pc = bool(nz and nz[1] and nz[0].upper().startswith("PC-"))`) with `r < 2.2`, `posture()` now reports `"seated or leaning"` (never `"lying down"` or `"bending or crouching"` at a PC desk), `legs` colour is suppressed (`None`) when `r < 1.4` (`desk_occluded`), and `pose_visibility()` marks lower-body joints as `OCCLUDED` (`xy=None`).

### Defect 3 (`P1` — `labmap.py`): `track_ms` p95 Spikes (`282.9 ms`, max `527.8 ms`) During `LOOK_WAIT_S`
- **Live Symptom (`LIVE_PHYSICAL` on `:5100/metrics` and `:5101/metrics`)**:
  - While `track_ms` p50 was `5.2 ms` (Cam 1) and `19.3 ms` (Cam 2), `track_ms` p95 was `282.9 ms` (`max = 496.4 ms`) on Cam 1 and `277.2 ms` (`max = 527.8 ms`) on Cam 2.
- **Root Cause (`labmap.py:220-269`)**:
  - Whenever a new track had `t.lab_no is None` and `looks[t.id] is None` during its first `LOOK_WAIT_S` (`1.5 s` = 9 frames), `need` was non-empty on **every frame**, causing `assign()` to lock and rewrite the 85-entry `lab_people_LAB_01.json` file 6 times/second even though `work(d)` skipped `t` at line 268 (`if no is None and lk is None and now - self.born[t.id] < LOOK_WAIT_S: continue`)! The other camera then blocked up to `50 * 10 ms = 500 ms` waiting for `.lock`.
- **Fix Implemented (`tools/security_vision/labmap.py:220-232`)**:
  - Filter `ready_need` before calling `self.reg.update(work)`: if no unnumbered track is ready to be numbered (`lk is not None` or `age >= LOOK_WAIT_S` or confirmed `label`) and `not merged_away` and `now - self.last_write < WRITE_EVERY_S`, return immediately (`0 ms`).

---

## 4. Simulated Multi-Scenario & Disappearance Analysis (`SIMULATED`)

In `scenario_bench.py` (`17 scenarios`), all 17 scenarios achieved **`false_names = 0`, `name_switches = 0`, `false_merges = 0`**.
- **Why Scenarios `07c` (25 s dead zone), `07d` (25 s dead zone + look-alike), and `11` (3 min leave & return) report `id_switches = 1, fragments = 1`**:
  - `scenario_bench.py:333` scores `out[p].id` — the camera-local `Tracker` bounding-box `Track.id`, which deliberately expires after `MAX_MISS_S = 10.0 s` so an un-detected bounding box never coasts blindly across the room for 25–180 seconds.
  - When the person re-emerges after 25 s or 180 s, `Tracker` creates a new bounding-box `Track.id` (`fragments = 1`), and `Labeler` / `LabNumbers` immediately restores their **confirmed identity (`named_share = 0.972–0.975`, `name_switches = 0`, `false_names = 0`) and global `lab_no`**. Extending raw bounding-box coasting beyond 10 s would risk latching onto a passerby (`07d`); keeping `Tracker` expiry at 10 s while re-linking via `LabNumbers` + `Labeler` is the provably safe architecture.
