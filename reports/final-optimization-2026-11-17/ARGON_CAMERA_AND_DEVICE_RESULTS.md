# ARGON_CAMERA_AND_DEVICE_RESULTS.md

This report documents the live 17 Nov GIU Lab camera and device telemetry, root causes of all observed anomalies, and the verified results after Argon's fixes.

---

## 1. Two-Camera Vision System (`SECCAM_LAB01` & `SECCAM_LAB02`)

### 1.1 Hardware & Calibration Status (`OBSERVED` on 17 Nov + `STATICALLY INSPECTED`)
| Parameter | Camera 1 (`SECCAM_LAB01`) | Camera 2 (`SECCAM_LAB02`) |
|---|---|---|
| Hardware / Stream | TP-Link Tapo C200 (`192.168.1.106:554/stream1`, RTSP TCP) | TP-Link Tapo C200 (`192.168.1.119:554/stream1`, RTSP TCP) |
| Host Port & Bind | `127.0.0.1:5100` | `127.0.0.1:5101` |
| Stream / Analysis Rate (17 Nov Live) | `6.1 fps` stream / `5.9 fps` analysis (`82.6 ms/pass`) | `14.1 fps` stream / `6.1 fps` analysis (`73.7 ms/pass`) |
| Detector Engine | `Yolo26Detector` (`yolo26n-544x960.onnx`, DirectML GPU `31.8–33.3 ms`) | `Yolo26Detector` (`yolo26n-544x960.onnx`, DirectML GPU `33.3 ms`) |
| ReID Engine | `person_reid_youtu_2021nov.onnx` (`openvino-cpu`, `37.0–46.5 ms`) | `person_reid_youtu_2021nov.onnx` (`openvino-cpu`, `37.0 ms`) |
| Floor Calibration (`anchors/*_floor.json`) | 7 floor points (`5.6 m x 4.9 m` grid, max leave-one-out error `0.50 m` at `UR5e_front`) | 7 floor points (`5.6 m x 4.9 m` grid, max leave-one-out error `0.34 m`) |
| Cross-Camera Desk Links (`desk_map.json`) | `PC-01`, `PC-04`, `PC-08`, `PC-09`, `PC-12`, `PC-13`, `PC-16` | Linked to Camera 1 via `desk_map.json` |

### 1.2 Multi-Camera Tracking, UR5e Zone & Partial Body Fixes (`LIVE MEASURED` Replay + `SIMULATED`)
1. **UR5e Zone Cross-Camera Conflict Storm (Solved)**:
   - **Why it happened**: Near the UR5e table (`x=1.40, y=2.45`), Camera 1's homography has its highest perspective error (`0.50 m`), and seated/table-occluded bounding boxes shift projected feet by `0.7–1.3 m` (`p50 = 0.55 m`, `p95 = 1.29 m` across 873 ground-truth same-person observations on 17 Nov). When two confirmed people (`Ali` = `USER1`, `Nour` = `USER6`, `Eng. Hemaly` = `USER5`) stood or sat near the UR5e table, `CrossCam._share_live()` paired `USER6` on Camera 1 with `USER1` on Camera 2 (`0.31–0.46 m` apart) even though both `USER1` and `USER6` were already separately tracked across the views, and `self.links` passed the conflicting pair to `labmap.py`, merging their `lab_no`.
   - **Argon Fix**:
     - Veto cross-pairing two different confirmed identities in `_share_live()` when either identity is already present on another track in `mine` or `peer["tracks"]`.
     - Allow same-confirmed-identity tracks (`t.label == p["label"]`) to pair across `GATE_WIDE_M (2.0 m)` when appearance does not veto (`a <= APPEAR_VETO`).
     - Never insert label-conflicting pairs into `self.links`, and guard `labmap.py` against merging conflicting labels.
     - Throttle identical `CROSSCAM_CONFLICT` log persistence to 1 per 30 s.
   - **Measured Result on 17 Nov Data**: False cross-person links dropped from `35` (`3,069` pass logs) to **`0`**, and true same-person pairings increased from `663 -> 799` (`+20.5%`) on Camera 1 and `732 -> 873` (`+19.3%`) on Camera 2.
2. **Partial-Body Posture & Explicit Keypoint Visibility (Solved)**:
   - **Why it happened**: When a person stood/sat at Camera 2's bottom edge (`y + h >= fh - 3`), their legs were out of frame, making `h / w < 1.4` (or `< 0.8`), which `activity.posture()` misread as `"bending or crouching"` or `"lying down"`.
   - **Argon Fix**: Added `is_bottom_clipped()` and `pose_visibility()` to `activity.py`. Bottom-clipped boxes now report `"upper body in view"` (or `"upper body in view, moving"`), and `pose_visibility` explicitly classifies `head`, `shoulders`, `torso`, `elbows`, `wrists`, `hips`, `knees`, and `ankles` into `OBSERVED`, `OCCLUDED`, `PREDICTED`, or `OUT_OF_FRAME` (with `xy=None` for non-observed joints).
3. **Desk Naming Stability for Face-Recognised Occupants (Solved)**:
   - **Why it happened**: `vision.py:1124` wiped `t.source == "desk"` on every pass when `t.label` was in `self.face_named` (but not `inside` door sessions), causing `home_desk()` to re-assign and log `NAMED_BY_DESK` 6 times/second (`1,191` times on 17 Nov).
   - **Argon Fix**: Included `"desk"` alongside `"look"` in `vision.py:1124` (`t.source in ("look", "desk") and t.label in self.face_named`), reducing `NAMED_BY_DESK` logs from `1,191` to `1` per seating episode.

---

## 2. ESP-CAM, ESP32 Nodes, Robots & PC Agents

| Device / Subsystem | 17 Nov Lab Observation | Argon Audit & Action Taken |
|---|---|---|
| `MASTER_LAB01` (`192.168.1.109`) | Online (`13 ms` RTT, `0%` packet loss); keypad + NFC + fingerprint door access verified | **Untouched** per safety rules (`SmartLab_Master_Portal.ino` never modified). |
| `CAM_DOOR_01` (`192.168.1.150`) & `face_server` (`:5000`) | `face_server` UP on host (`100%` match in `face_benchmark.py`); `ESP32CAM_Vision_FAST.ino` stopped retrying if boot Wi-Fi took >20 s or dropped later | Fixed `ESP32CAM_Vision_FAST.ino` in worktree so HTTP server and `analyzeTask` always start and `loop()` reconnects Wi-Fi every 10 s with `WiFi.setSleep(false)`. |
| `ENV_LAB01` (`192.168.1.105`) | Online (`14 ms` RTT, `0%` packet loss); Core 0 `netTask` decouples HTTP from sensor sampling | Audited clean (`3.1.1-env-core0net`). |
| `BIN_NODE_1` (`192.168.1.190`, Consumables Bin) | Online (`29.99 g` live reading); Wi-Fi sleep disabled on 17 Nov, but failed HTTP POSTs had zero backoff in `loop()` | Fixed `SmartLab_Consumable_Bin.ino` in worktree: added `5,000 ms` retry backoff (`lastFailMs`) on failed `sendMass()` so network drops never stall 10 Hz HX711 sampling. |
| `REUSE_BIN_1` (`192.168.1.116`, Reusable Bin) | Online (`3.4-portal`); `WiFi.setSleep(false)` set in `begin()` but not re-applied after `WiFi.begin()` in `update()` | Fixed `WiFiManager.cpp` in worktree to re-assert `WiFi.setSleep(false)` on every Wi-Fi reconnect. |
| `UR5E_01` (`.102`) & `FANUC_01` (`.101`) | Both online and streaming live joint angles (`4–5 Hz`) to portal & digital twin | Audited `tools/robot_monitor/robot_collector.py` and `backend/app/services/robot_fusion.py`: strictly read-only (`TCP 30003` receive-only for UR5e, `GET` for FANUC). `27 passed` in `pytest tools/robot_monitor`. |
| `PC_ENG` (`S2PC136`) & `PC_01..PC_16` | `PC_ENG` online (`192.168.1.210`), screen sharing verified (`58 KB` JPEG, `HTTP 200`); `relay.py` failed to start during lab install; `PC_01` blocked by Windows Firewall on `S2PC136:8000` | Fixed `relay.py` (automatic fallback to `0.0.0.0` when `--listen` IP is unavailable), fixed `Install-CurrentUser.ps1` / `Check-CurrentUser.ps1` CRLF hash check, updated `Uninstall-CurrentUser.ps1`, and rebuilt `lab_usb_kit/MANIFEST.json`. |
