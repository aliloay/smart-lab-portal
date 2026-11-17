# ARGON_FINDINGS_ROOT_CAUSES.md

Every finding below is classified by priority (`P0` / `P1` / `P2` / `P3`), evidence class (`LIVE MEASURED`, `OBSERVED`, `STATICALLY INSPECTED`, `SIMULATED`), exact `file:line`, root cause, and status (`FIXED BY ARGON`, `DOCUMENTED FOR CLAUDE`, or `EXTERNAL / HARDWARE`).

---

## Finding 1 (`P1` — Vision / Cross-Camera Fusion): 3,069 `CROSSCAM_CONFLICT` Storm & False `lab_no` Merges in UR5e Zone
- **Evidence Class**: `LIVE MEASURED` (from 17 Nov `identity_log_SECCAM_LAB01.jsonl` [1,545 conflicts], `identity_log_SECCAM_LAB02.jsonl` [1,524 conflicts], and `crosscam_obs_*.jsonl` [13,154 rows]) + `STATICALLY INSPECTED`
- **Where**:
  - `tools/security_vision/crosscam.py:336-378`, `478-492`
  - `tools/security_vision/labmap.py:168-207`
  - `tools/security_vision/security_vision.py:661-663`
- **What Happened**:
  - The 17 Nov lab report noted 489 conflicts in the UR5e zone during the afternoon run; across the full 17 Nov log files there were **3,069 `CROSSCAM_CONFLICT` records** (`1,545` on Camera 1 + `1,524` on Camera 2) across 7 episodes (`USER6 vs USER1` = 2,533; `USER6 vs USER5` = 445; `USER1 vs USER5` = 91).
- **Three Compounding Root Causes**:
  1. **Missing Confirmed-Identity Veto & Narrow Same-Label Gate in `CrossCam._share_live()` (`crosscam.py:337-349`)**:
     - When building the Hungarian assignment matrix `score[i][j]`, `_share_live()` scored floor distance `d` and appearance distance `ad[i][j]` without checking whether `mine[i].label` and `theirs[j]["label"]` already carried **different confirmed identities** while both identities were present in the views (`my_confirmed` / `their_confirmed`).
     - In Episode 6 (`15:17:59–15:22:05`, 1,288 conflicts in 4 minutes), `USER6` (Nour) sat at the UR5e table on Camera 1 while on Camera 2 she was at the bottom edge (`floor=None`, filtered out of `theirs` at line 317). Her seated bounding box bottom on Camera 1 projected onto the floor `0.31 m` from `USER1` (Ali) standing on Camera 2 (`0.31 m <= GATE_M = 0.7 m`), so `assign_max` paired Camera 1's `USER6` with Camera 2's `USER1` on every pass — even though `USER1` was already a separate track on Camera 1 and `USER6` was already a separate track in Camera 2's `peer["tracks"]`!
     - Furthermore, when both `USER6` tracks had floor coordinates near the UR5e table, perspective distortion / table occlusion shifted their projected feet `0.7–1.3 m` apart (`> GATE_M = 0.7 m`, measured `p50 = 0.55 m`, `p95 = 1.29 m` across 873 ground-truth same-person pairs), so `(USER6, USER6)` scored `None` while `(USER6, USER1)` at `0.46 m` won the pairing.
  2. **Pollution of `self.links` Before Conflict Check -> `labmap.py` Merged Confirmed Different People (`crosscam.py:353`, `labmap.py:168`)**:
     - `crosscam.py:353` populated `self.links` for **all** `pairs` with `streak >= STABLE_PASSES` **before** line 361 checked `if t.label and p.get("label") and t.label != p["label"]:`.
     - `labmap.py:168` (`LabNumbers.assign()`) then merged `t.lab_no = theirs` for any link in `links` without checking if `t.label != p.get("label")`. Thus, while `crosscam` claimed `"nothing changed"` for `.label`, `labmap` silently merged Ali's and Nour's global `Person N` numbers!
  3. **Unthrottled 6 Hz Conflict Persistence (`security_vision.py:661-663`)**:
     - Every analysis pass (`~6 fps`) appended `CROSSCAM_CONFLICT` to `identity_log` and flushed it to `identity_log_*.jsonl`.
- **Status**: **FIXED BY ARGON** (`crosscam.py`, `labmap.py`, `security_vision.py`).

---

## Finding 2 (`P1` — Vision / Activity & Pose): Bottom-Cropped Partial Bodies Misclassified as `"lying down"` or `"bending"`
- **Evidence Class**: `OBSERVED` (17 Nov live lab report) + `STATICALLY INSPECTED` + `SIMULATED` (verified in unit tests)
- **Where**: `tools/security_vision/activity.py:52-68`, `95-122`
- **Root Cause**:
  - `activity.posture(box, vel)` computed `r = h / w` without checking if the person's bounding box was clipped by the bottom edge of the camera frame (`y + h >= fh - EDGE_PX`, where `EDGE_PX = 3`).
  - When a person stood or sat at the bottom edge of Camera 2 (legs/feet out of frame), the visible upper-body box had `r = h / w` between `0.65` and `1.35`, causing `posture()` to report `"lying down"` (`r < 0.8`) or `"bending or crouching"` (`0.8 <= r < 1.4`).
  - Additionally, the pipeline lacked explicit per-body-part visibility states (`OBSERVED`, `OCCLUDED`, `PREDICTED`, `OUT_OF_FRAME`) for `head`, `shoulders`, `torso`, `elbows`, `wrists`, `hips`, `knees`, and `ankles`.
- **Status**: **FIXED BY ARGON** (`activity.py`).

---

## Finding 3 (`P1` — Vision / Desk Naming): 1,191 `NAMED_BY_DESK` Log Flood & Per-Frame Label Wipe
- **Evidence Class**: `LIVE MEASURED` (`identity_log_SECCAM_LAB01.jsonl` has 1,191 `NAMED_BY_DESK` lines on 17 Nov) + `STATICALLY INSPECTED`
- **Where**: `tools/security_vision/vision.py:1123-1126`
- **Root Cause**:
  - In `Labeler.assign()` (`vision.py:1123`), any track whose `t.label` was not in `inside` (door sessions) had its label wiped at the start of every frame unless `t.source in ("face", "peer", "operator")` or `(t.source == "look" and t.label in self.face_named)`.
  - Notice `t.source == "desk"` was omitted from the `self.face_named` exception!
  - When `USER5` (Eng. Hemaly) was in `self.face_named` (recognised by face on camera, without a door badge swipe in `inside`) and sat at his desk (`PC-04`), `home_desk()` (`vision.py:1539`) named his track with `t.source = "desk"` and logged `NAMED_BY_DESK`. On the **very next frame** (`0.16 s` later), `Labeler.assign()` line 1123 wiped `t.label = None` because `t.source == "desk"`, and 15 lines later `home_desk()` named him again and logged `NAMED_BY_DESK` again — repeating 6 times per second (1,191 times)!
- **Status**: **FIXED BY ARGON** (`vision.py:1124`).

---

## Finding 4 (`P1` — Vision / Global Numbering): `labmap.py` Double Lock/Disk Write & Confirmed-Identity Number Inflation (`Person 230`)
- **Evidence Class**: `LIVE MEASURED` (`lab_people_LAB_01.json` reached `next: 205` / `Person 230` on 17 Nov) + `STATICALLY INSPECTED`
- **Where**: `tools/security_vision/labmap.py:217-272`
- **Root Causes**:
  1. `LabNumbers.assign()` called `self.reg.update(work)` and immediately `self.reg.update(names_by_number)` (`labmap.py:270-271`), acquiring the `.lock` file, reading JSON, writing `.tmp`, and calling `os.replace()` **twice** on every update.
  2. When a track in `need` (`t.lab_no is None`) already carried a confirmed identity (`t.label` with `t.source in KEEP_NAME_SOURCES`), `work(d)` did not check whether `people` already had an entry with `who.auth_subject == t.label`. If the camera service restarted or a track broke within `PRESENT_S` (`3.0 s`), `busy` blocked `_returning()` and allocated a brand-new `d["next"]` number even though the confirmed identity was already in the register.
- **Status**: **FIXED BY ARGON** (`labmap.py`).

---

## Finding 5 (`P1` — AI / GPU Gate): Camera `"STREAMING"` vs `"LIVE"` State Mismatch in `gpu_gate.py`
- **Evidence Class**: `STATICALLY INSPECTED` + `SIMULATED` (unit test verified)
- **Where**: `tools/knowledge/gpu_gate.py:70` vs `tools/security_vision/security_vision.py:102`
- **Root Cause**:
  - `gpu_gate.py:70` checked `live = (m.get("stream") or {}).get("state") == "LIVE" or fps > LIVE_FPS`.
  - However, `security_vision.py` `Camera.status()` sets `stream.state` to `"CONNECTING"`, `"STREAMING"`, `"RECONNECTING"`, `"STALE"`, or `"OFFLINE"` — it **never** emits `"LIVE"`. Whenever `fps` briefly dipped or was `0.0` during initial warmup while `stream.state == "STREAMING"`, `gpu_gate.py` misclassified the camera as `"idle"`.
- **Status**: **FIXED BY ARGON** (`tools/knowledge/gpu_gate.py:70`).

---

## Finding 6 (`P1` — Knowledge / Ollama Config Drift): Default `qwen2.5:3b` Missing from Host Ollama
- **Evidence Class**: `LIVE MEASURED` (`ollama list` shows only `qwen2.5:1.5b` and `nomic-embed-text:latest`) + `STATICALLY INSPECTED`
- **Where**: `tools/knowledge/kb.py:172`, `tools/knowledge/config.example.json:6`, `scripts/ollama_models.bat:11`
- **Root Cause**:
  - `qwen2.5:3b` was removed on 27 Oct to save RAM/disk, and production standardized on `qwen2.5:1.5b`. While `serve.py` overrode `cfg["model"] = cfg.get("agent_model", "qwen2.5:1.5b")`, `kb.py`, `config.example.json`, and `scripts/ollama_models.bat` still defaulted to `qwen2.5:3b`.
- **Status**: **FIXED BY ARGON** (`kb.py`, `config.example.json`, `scripts/ollama_models.bat`).

---

## Finding 7 (`P1` — PC USB Kit & Relay): Engineer PC (`S2PC136`) Relay Startup Failure & CRLF Manifest Hash Rejections
- **Evidence Class**: `LIVE MEASURED` (7 SHA-256 mismatches in `lab_usb_kit/MANIFEST.json`) + `STATICALLY INSPECTED`
- **Where**:
  - `D:\SmartLabData\kit_backup_2026-11-17\INSTALL_SMARTLAB_v17nov.ps1:59`
  - `tools/relay/relay.py:108-116`
  - `lab_usb_kit/Install-CurrentUser.ps1:31-36`, `lab_usb_kit/Check-CurrentUser.ps1:14-16`, `lab_usb_kit/Uninstall-CurrentUser.ps1:9-10`
- **Root Causes**:
  1. In the ad-hoc `INSTALL_SMARTLAB_v17nov.ps1` script used on 17 Nov, line 59 had `"-E -s $dst\relay\relay.py ..."` inside double quotes, where PowerShell expanded `\r` twice as **carriage return (`0x0D`)**, passing an invalid path to `python.exe`.
  2. In `tools/relay/relay.py:112`, if `--listen 10.30.11.136` was passed (from `site.json` when `$env:COMPUTERNAME -eq 'S2PC136'`) and `10.30.11.136` was not yet bound on the adapter (`WinError 10049`), `serve()` skipped all ports and exited with `nothing to relay` instead of falling back to `0.0.0.0` (which is already protected by `--allow` subnet ACLs).
  3. In `lab_usb_kit/MANIFEST.json`, 7 text files (`Install-CurrentUser.ps1`, `Check-CurrentUser.ps1`, `Uninstall-CurrentUser.ps1`, `Start-Agent.ps1`, `Stop-Agent.ps1`, and 2 `.md` guides) had LF hashes in `MANIFEST.json` but CRLF bytes on disk after Git checkout, causing `Install-CurrentUser.ps1` to abort with `"The kit is damaged - copy it again"`.
  4. `Uninstall-CurrentUser.ps1` did not remove the legacy `SmartLab watchdog` scheduled task or desktop `Smart Lab Portal.url` shortcut.
- **Status**: **FIXED BY ARGON** (`relay.py`, `Install-CurrentUser.ps1`, `Check-CurrentUser.ps1`, `Uninstall-CurrentUser.ps1`, `make_kit.py`, `MANIFEST.json`).

---

## Finding 8 (`P2` — ESP32 Firmware): Consumables Bin Retry Storm on HTTP Failure & ESP32-CAM Wi-Fi Drop Recovery
- **Evidence Class**: `STATICALLY INSPECTED`
- **Where**:
  - `firmware/SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino:442-451`, `562-565`
  - `firmware/ESP32CAM_Vision_FAST/ESP32CAM_Vision_FAST.ino:585-618`
  - `firmware/SmartLab_Reusable_Bin_Modular/src/WiFiManager.cpp:32-38`
- **Root Causes**:
  1. In `SmartLab_Consumable_Bin.ino`, `lastSentMs` was only updated when `netOk` (`code == 200`) succeeded. When `post()` failed, `millis() - lastSentMs > KEEPALIVE_MS` (`1000 ms`) remained true on the very next `loop()` iteration, causing `sendMass()` to hammer blocking HTTP POSTs back-to-back with zero backoff and starve 10 Hz HX711 scale sampling.
  2. In `ESP32CAM_Vision_FAST.ino`, if Wi-Fi took >20 s at boot, `setup()` returned early without starting the HTTP server or `analyzeTask`, and `loop()` had no Wi-Fi reconnect logic if the router restarted.
  3. In `WiFiManager.cpp` (`SmartLab_Reusable_Bin_Modular`), `WiFi.setSleep(false)` was called in `begin()` but not re-asserted after `WiFi.disconnect(); WiFi.begin(...)` in `update()`.
- **Status**: **FIXED BY ARGON** (in firmware source files; not flashed to physical boards per safety rules).

---

## Finding 9 (`P2` — Terminal & Watchdog Observability): `status.ps1` Counter Failure, Camera 2 Port Check & Watchdog Health Paths
- **Evidence Class**: `LIVE MEASURED` (`status.ps1` printed `load: counters unavailable` during baseline) + `STATICALLY INSPECTED`
- **Where**: `scripts/status.ps1:51`, `tools/ops/watchdog.py:38-39`, `tools/knowledge/serve.py:102`, `launch.bat:69`
- **Root Causes**:
  1. `scripts/status.ps1:51` used `Get-Counter -ErrorAction Stop` with `\Process(*)\% Processor Time`; on Windows 11, if any short-lived process exits during the 1-second sample window, `Get-Counter` writes a non-terminating counter error that `-ErrorAction Stop` turns into a full exception, hiding CPU, paging, disk latency, and GPU load.
  2. `tools/ops/watchdog.py` only checked raw TCP port open (`path=None`) for `knowledge service` (`5199`) and `voice service` (`5320`).
  3. `launch.bat` checked port `:5100` via `netstat` for Camera 1, but only checked `camera2.env` in `wmic`/command-line output for Camera 2 (missing a port `:5101` check).
- **Status**: **FIXED BY ARGON** (`status.ps1`, `watchdog.py`, `serve.py`, `launch.bat`).
