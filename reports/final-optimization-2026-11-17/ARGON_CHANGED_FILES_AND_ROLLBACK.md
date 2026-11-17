# ARGON_CHANGED_FILES_AND_ROLLBACK.md

- **Isolated Worktree**: `C:\Projects\smart-lab-argon`
- **Branch**: `opt/argon-systems-vision-2026-11-17`
- **Base Commit**: `c68adb0` (`Progress checkpoint: GIU lab day 17 Nov`)
- **Main Worktree (`C:\Projects\smart-lab-portal`)**: **0 tracked files modified by Argon** (left completely untouched for Claude Code Max).

---

## 1. Complete List of Modified Files (`28 files changed, 351 insertions(+), 57 deletions(-)`)

| File Path | Lines (`+/-`) | Subsystem | Purpose of Change |
|---|---:|---|---|
| `tools/security_vision/crosscam.py` | `+25 / -2` | Vision / Cross-Camera | Veto cross-pairing confirmed different identities when both are present; allow same-confirmed-identity pairing up to `GATE_WIDE_M`; exclude conflicting pairs from `self.links`. |
| `tools/security_vision/labmap.py` | `+25 / -15` | Vision / Global Numbering | Prevent merging `lab_no` across conflicting labels; reuse existing `lab_no` for confirmed identities across breaks/restarts; combine `work` and `names_by_number` into a single `reg.update()` call. |
| `tools/security_vision/activity.py` | `+73 / -8` | Vision / Posture & Pose | Add `is_bottom_clipped()` and 8-joint `pose_visibility()` (`OBSERVED`/`OCCLUDED`/`OUT_OF_FRAME`); classify bottom-cropped boxes as `"upper body in view"` instead of `"lying down"`. |
| `tools/security_vision/vision.py` | `+1 / -1` | Vision / Desk Naming | Keep `t.source == "desk"` in `Labeler.assign()` when `t.label in self.face_named` (fixes 1,191-line `NAMED_BY_DESK` flood). |
| `tools/security_vision/security_vision.py` | `+9 / -1` | Vision / Logging | Throttle identical `CROSSCAM_CONFLICT` persistence in `identity_log` to 1 per 30 s. |
| `tools/security_vision/test_crosscam.py` | `+35 / -0` | Vision Tests | Add `test_ur5e_zone_two_confirmed_people_never_cross_pair_or_conflict`. |
| `tools/security_vision/test_labmap.py` | `+26 / -0` | Vision Tests | Add `test_conflicting_labels_never_merge_lab_numbers` and `test_confirmed_person_reuses_lab_number_immediately_after_restart`. |
| `tools/security_vision/test_activity.py` | `+18 / -0` | Vision Tests | Add `test_bottom_clipped_partial_box_reports_upper_body_and_explicit_joint_visibility`. |
| `tools/security_vision/test_posture_and_review.py` | `+22 / -0` | Vision Tests | Add `test_desk_named_face_occupant_is_not_wiped_every_pass`. |
| `tools/knowledge/gpu_gate.py` | `+1 / -1` | AI / GPU Gate | Recognise `stream.state == "STREAMING"` alongside `"LIVE"`. |
| `tools/knowledge/test_gpu_gate.py` | `+6 / -0` | AI / GPU Gate Tests | Verify `"STREAMING"` state with `0.0 fps` triggers `"live"` (`CPU` mode). |
| `tools/knowledge/kb.py` | `+1 / -1` | Knowledge Service | Align default model from `qwen2.5:3b` to `qwen2.5:1.5b`. |
| `tools/knowledge/config.example.json` | `+1 / -1` | Knowledge Service | Align default model from `qwen2.5:3b` to `qwen2.5:1.5b`. |
| `tools/knowledge/serve.py` | `+2 / -0` | Knowledge Service | Add unauthenticated `GET /health` endpoint (`200 OK`). |
| `scripts/ollama_models.bat` | `+1 / -1` | AI Startup Script | Default `M1=qwen2.5:1.5b` so missing `.env` never pulls a 2 GB `3b` model. |
| `scripts/status.ps1` | `+2 / -1` | Terminal Status | Use `-ErrorAction SilentlyContinue` on `Get-Counter` so transient process exits do not break counter display. |
| `tools/ops/watchdog.py` | `+2 / -2` | Ops Watchdog | Check `/health` on `knowledge service` (`5199`) and `voice service` (`5320`). |
| `launch.bat` | `+5 / -2` | Terminal Launcher | Check port `:5101` (`netstat`) before spawning Security Camera 2. |
| `tools/relay/relay.py` | `+7 / -0` | PC Relay | Fall back to `0.0.0.0` when `--listen` IP cannot be bound (`WinError 10049`). |
| `tools/relay/test_relay.py` | `+13 / -0` | PC Relay Tests | Add `test_serve_falls_back_to_all_interfaces_when_specific_ip_is_unavailable`. |
| `tools/pc_agent/make_kit.py` | `+29 / -9` | USB Kit Builder | Support `--no-bundle` manifest refresh in worktrees while preserving untracked runtime hashes. |
| `lab_usb_kit/Install-CurrentUser.ps1` | `+11 / -1` | USB Kit Installer | Accept LF-normalized SHA-256 hashes for text files to prevent Git CRLF false failures. |
| `lab_usb_kit/Check-CurrentUser.ps1` | `+10 / -1` | USB Kit Health Check | Accept LF-normalized SHA-256 hashes for text files. |
| `lab_usb_kit/Uninstall-CurrentUser.ps1` | `+6 / -1` | USB Kit Uninstaller | Also remove legacy `SmartLab watchdog` scheduled task and desktop `.url` shortcut. |
| `lab_usb_kit/MANIFEST.json` | `+9 / -9` | USB Kit Manifest | Refreshed SHA-256 hashes (`859 files, secret scan clean`). |
| `firmware/SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino` | `+4 / -1` | ESP32 Firmware | Add 5 s retry backoff (`lastFailMs`) on failed `sendMass()` HTTP POST. |
| `firmware/ESP32CAM_Vision_FAST/ESP32CAM_Vision_FAST.ino` | `+11 / -3` | ESP32-CAM Firmware | Always start HTTP server/tasks and reconnect Wi-Fi every 10 s in `loop()`. |
| `firmware/SmartLab_Reusable_Bin_Modular/src/WiFiManager.cpp` | `+1 / -0` | ESP32 Firmware | Re-assert `WiFi.setSleep(false)` after `WiFi.begin()` on reconnect. |

---

## 2. How to Merge Argon's Branch into Main Worktree (After Claude Completes)

Because Argon touched **zero** files in `frontend/**` or `backend/app/**`, merging `opt/argon-systems-vision-2026-11-17` into `C:\Projects\smart-lab-portal` is a clean fast-forward / 3-way merge:
```powershell
Set-Location C:\Projects\smart-lab-portal
git merge opt/argon-systems-vision-2026-11-17
```

---

## 3. Exact Rollback Commands

- **To revert the entire Argon optimization pass**:
  ```powershell
  Set-Location C:\Projects\smart-lab-portal
  git worktree remove C:\Projects\smart-lab-argon --force
  git branch -D opt/argon-systems-vision-2026-11-17
  ```
- **To revert a single file after merging**:
  ```powershell
  git checkout c68adb0 -- <path/to/file>
  ```
