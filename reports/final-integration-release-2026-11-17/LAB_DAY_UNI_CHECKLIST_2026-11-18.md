# Uni lab day checklist (2026-11-18): cameras, floor point, lab PCs, UR5e

**The 4 ESP32 nodes stay at home. That is fine for today.** Everything below works without them.
What it means at the lab:
- **Door:** cannot be used or tested. The Master is one of the four, so there is no RFID / QR / fingerprint / face entry today.
- **Portal:** shows MASTER_LAB01, ENV_LAB01, BIN_NODE_1 and REUSE_BIN_1 as **offline**. That is expected. n8n "node offline" notifications for them are expected too; ignore them today.
- **Assistant:** door-state questions will answer "too old to say" (correct behaviour).

The laptop code is the integrated release: the main checkout fast-forwarded to it on 18 Nov. Running portal: backend
279c625, frontend df3407f.

## 1. Start (laptop on the Smart_Lab cable + GIU network)
1. Free RAM first: close Chrome tabs and VS Code. Aim for more than 2.5 GB free.
2. Run `launch.bat` (repo root). Camera 2 starts only once (port 5101 check).
3. Check:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\lab_preflight.ps1
   ```
   - http://localhost:8000/api/health -> version.id starts with 279c625
   - The portal Security page shows both cameras live

## 2. Camera 1 floor point near the UR5e (Argon: 0.50 m error at UR5e_front)
Goal: one more two-camera pair near **x = 1.4, y = 3.2** (room metres, same corner as before). Only when that floor
spot is clear.
1. Stand there, **whole body visible on BOTH cameras** (feet in the picture), and stay still for about 20 s. Then run (in tools\security_vision):
   ```powershell
   py pair_capture.py "Ali standing at UR5e front x1.4 y3.2"
   ```
2. Tell me the folder it printed. I will run `pair_check.py <folder> <cam1 x,y> <cam2 x,y>` and then a **dry-run** `floor_refit.py pairs.json`. It prints the before / after error on the tape marks.
3. Only if the UR5e_front error drops and the tape marks stay at or below 0.10 m: `floor_refit.py pairs.json --save`. It backs up both floor files first. Then restart both camera windows.
   - Optional, better: repeat 1-2 at one or two more clear spots on the window / UR5e side.

## 3. Live two-camera tracking run (first live evidence for the thesis)
For each step, **tell me the clock time when it starts and ends**. I will read the outcome from the cameras' identity
logs and the portal (no video or face images are exported).

| # | What you do | What should happen |
|---|---|---|
| A | One person stands where both cameras see them | one lab number ("Person N" / the name) on both |
| B | Walk from camera 1's area to camera 2's area | the same number / name carries over |
| C | Two named people (e.g. Ali + Nour) sit / stand at the UR5e table, about 0.5 m apart, 2 min | names never swap or merge |
| D | Leave both views for about 25 s, come back | same number / name back (simulation had 1 switch) |
| E | Leave for about 3 min, come back | same as D (simulation had 1 switch) |
| F | Sit close to camera 2 so the legs are cut off by the picture | "upper body in view", never "lying down" |
| G | Restart camera 2's window while someone stays in view | no jump in "Person N"; number comes back |
| H | Hemaly at her desk (if she is there) | "Eng. Hemaly?" hint only on her, never on someone else |

## 4. Lab PCs and the relay (GIU firewall)
1. On the Engineer PC (S2PC136): the relay window runs (lab_usb_kit relay).
2. On a student PC (PC_01 = S2PC121):
   ```powershell
   Test-NetConnection 10.30.11.136 -Port 8000
   ```
   - **True:** the agent can reach the portal. Check that the PC shows online in the portal.
   - **False** (as on 17 Nov): the Windows Defender firewall on S2PC136 still blocks inbound. Ask GIU IT to allow TCP 8000 and 443 inbound from the lab subnet only. Do not change the firewall without IT.
3. Hemaly's PC: check it shows online and "signed in" in the portal PC list (the last-seen fix is live).

## 5. UR5e (read only) and FANUC
1. `tools\robot_monitor\start_ur5e_monitor.bat` (robot.env was set on 17 Nov). The UR5e twin should move with the real arm. Robot control stays OFF; never press anything that moves the robot from the portal.
2. Optional: `start_fanuc_monitor.bat`.
3. Tell me if the twin lags or shows stale data; I will measure the telemetry age from the records.

## 6. AI with cameras running (GPU sharing)
Ask the portal assistant one LLM question while both cameras run. Check that camera 2's analyses/s on the Security page
does not drop (the GPU gate gives cameras priority). Instant questions (alarms, stock, activity) never use the GPU.

## 7. Before leaving
```powershell
powershell -ExecutionPolicy Bypass -File scripts\lab_snapshot.ps1
```
That saves a snapshot of service states. Leave the camera windows running until I have read the logs, or tell me when
you close them.

## Later at home (with the ESP nodes)
- Flash the ESP32-CAM with the core 3.2.1 image (installed and built 18 Nov; procedure in ESP_FIRMWARE_AUDIT_EACH_NODE.md).
- Flash BIN_NODE_1 / REUSE_BIN_1 with the backoff fixes.
- Consumables and ESP-CAM improvements: we decide then.
