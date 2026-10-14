# Two security cameras - MC210 (camera 1) + MC200 1080p (camera 2)

Status: **SOFTWARE READY - camera 2 hardware not yet connected or verified.**

## Design (reuses the existing architecture)
* One service process per camera (`start_security_vision.bat [env file]`): own RTSP reader, latest-frame
  buffer (no backlog), detector, tracker, identities, zones, port. A camera that fails or disconnects
  cannot block the other (separate processes; measured below).
* Camera 1: `camera.env` (unchanged; port 5100 by default). Camera 2: `camera2.env` (copy of
  `camera2.env.example`): `DEVICE=SECCAM_LAB02`, `PORT=5101`, `SOURCE=` from the Mercusys app.
  All `camera*.env` files are git-ignored (fixed today - camera2.env was NOT ignored before).
* The backend reaches each camera at the port it reports (`component_state.port`); the portal's
  "All cameras" tab lists each security camera with its own online / source / fps status.
  Credentials stay in the env files and the process environment - never on the command line, in logs
  (`_safe` / `masked`) or in API responses.
* Per-camera files: `anchors/<DEVICE>*.npz` (looks, home, view), `recordings/identity_log_<DEVICE>.jsonl`.
* `launch.bat` starts camera 2 only when `camera2.env` exists; `stop_all.bat` closes both.

## Identity across cameras - limitation (honest)
Each camera names people **independently** with its own evidence (door entry, face, look, desk guess).
There is **no cross-camera merging**: track 3 on camera 1 and track 3 on camera 2 are unrelated, and the same
person may be named by one camera and Unknown on the other. Merging needs calibrated shared floor
coordinates (both views mapped to the room plan) plus appearance agreement - possible after camera 2 is
mounted and calibrated; not built, so nothing is ever merged by guess.

## Measured (simulated, 2026-10-14) - NOT hardware proof
| | camera 1 live alone | camera 1 + simulated camera 2 (recording, 2nd process) |
|---|---|---|
| analysis passes/s | 7.0 | 6.74 (cam 2: 6.95) |
| pass p50 / p95 | 85 / 106 ms | 102 / 143 ms (cam 2: 106 / 139) |
| GPU / VRAM | 36 % / 289 MB | 69 % / 578 MB |
Dead camera 2 (`rtsp://127.0.0.1:9/...`): service stays up, `camera:false fps:0`, retries every 3 s,
threads stable (62 -> 59), `open_failures` counted; camera 1 unaffected (7 fps, 0 errors).

## Hardware checklist (after the MC200 arrives)
1. Mount it diagonally opposite camera 1 (above Hemaly's drawer), 2.2-2.5 m, tilted down; power it.
2. Mercusys app: add the camera to the **Smart_Lab** Wi-Fi; turn OFF pan, auto-tracking, privacy mode.
3. App -> camera -> Advanced -> **Camera Account**: create user + password (keep them private).
4. Find its real IP (app device info or router client list). On the laptop:
   `ping -n 4 -S 192.168.1.200 <IP>` and `Test-NetConnection <IP> -Port 554` (TcpTestSucceeded True).
   Ask Claude to check the address is not already used before making it fixed in the router.
5. Copy `tools\security_vision\camera2.env.example` to `camera2.env`; put
   `rtsp://USER:PASSWORD@<IP>:554/stream2` after `set SOURCE=` (URL codes for @ : in the password).
6. Double-click `tools\security_vision\start_security_vision.bat camera2.env` - window title
   "Smart Lab - Security camera SECCAM_LAB02"; expect `[detector] YOLO26 on directml-gpu1`,
   `[vision] re-id on directml-gpu1`, `[camera] streaming from rtsp://***@<IP>...`.
7. Portal -> Security camera -> All cameras: both live; draw camera 2's boxes (PCs, door) on its own picture.
8. `curl http://127.0.0.1:5101/health` and `:5100/health`: both `camera:true`, fps ~7.
9. Tests: empty room; one person; several; someone visible in both views; crossing between views;
   unplug camera 2's power 30 s (camera 1 keeps working, camera 2 shows offline, then recovers).
10. Ask Claude to read both `/metrics` (fps, pass p95, frame age, GPU) - compare with the table above.
