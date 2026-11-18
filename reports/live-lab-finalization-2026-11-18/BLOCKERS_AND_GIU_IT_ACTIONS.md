# BLOCKERS_AND_GIU_IT_ACTIONS.md

Machine-readable blocker list is saved in `reports/live-lab-finalization-2026-11-18/raw/blockers.csv` and `D:\SmartLabData\live-lab-finalization-2026-11-18\raw\blockers.csv`.

---

## 1. Resolved Previous Blockers (Verified Closed on 18 Nov at GIU)

| Previous Blocker (17 Nov) | 18 Nov Live Status at GIU | Evidence |
|---|---|---|
| **Student PCs (`10.40.20.x`) blocked from reaching `S2PC136` Relay (`10.30.11.136:8000`)** | **RESOLVED (`LIVE_PHYSICAL`)** | 6 Student Lab PCs (`PC_GIULAB20-PC4`, `PC13`, `PC14`, `PC17`, `PC18`, `PC19`) on `10.40.20.0/24` and `PC_ENG` (`S2PC136`) are actively reporting live to the portal through the `S2PC136` relay right now (`last_seen_at` within `1.5–13.0 s`). |
| **Camera 1 (`SECCAM_LAB01`) `UR5e_front` Floor Residual (`0.50 m`)** | **RESOLVED (`LIVE_PHYSICAL`)** | 8 new two-camera standing pairs were captured and refit on 18 Nov (`commit 6606ed5`). Camera 1 LOO max error dropped from `0.500 m` to **`0.419 m`** (`median = 0.197 m`), and spots within the `0.70 m` gate improved from `1/8` to **`7/8`**. |
| **3,069 `CROSSCAM_CONFLICT` & 1,191 `NAMED_BY_DESK` Log Flood** | **RESOLVED (`LIVE_PHYSICAL`)** | Live 18 Nov camera logs show only `12` total conflicts (`-99.61%`) and `0` `NAMED_BY_DESK` flood (`-100.0%`). |

---

## 2. Remaining Hardware, Network & Operational Items (`BLK-01` .. `BLK-04`)

| ID | Priority | Item | Root Cause | Exact Action Required |
|---|---|---|---|---|
| **`BLK-01`** | `P2` | **Physical Robots (`UR5E_01` & `FANUC_01`) Powered Off + IP Overlap on `192.168.1.100`** | During today's audit window, the UR5e (`192.168.1.102:30003`) was powered off/unplugged, and `192.168.1.100` (configured as `--robot 192.168.1.100` for `FANUC_01`) was occupied by `PC_ENG`'s USB-Ethernet adapter (`00-e0-4c-18-65-60`). | 1. Change `PC_ENG`'s Smart Lab USB-Ethernet static IP from `192.168.1.100` to `192.168.1.210` (as documented in `site.json` / `relay.py`), OR set the FANUC controller IP to `192.168.1.101` and update `FANUC_IP=192.168.1.101` in `tools/robot_monitor/robot.env`.<br>2. Power on both robot controllers to verify live joint angles on the 3D digital twin. |
| **`BLK-02`** | `P2` | **Remaining Student Lab PCs (`PC8`, `PC11`, `PC12`) & `PC13` Agent Version `0.9`** | `PC_GIULAB20-PC8`, `PC11`, and `PC12` were powered off or had no signed-in user session during the audit window; `PC_GIULAB20-PC13` is online (`10.40.20.13`) but still running `pc-agent-0.9` (missing `clock_offset_s`). | Sign in to `PC8`, `PC11`, `PC12` (and `PC13`) and run `.\Install-CurrentUser.ps1 -Role Lab` from the updated `lab_usb_kit` v1.1 USB stick. |
| **`BLK-03`** | `P2` | **Physical ESP32 Nodes (`BIN_NODE_1`, `REUSE_BIN_1`, `CAM_LAB01`) Not Yet Flashed with 17–18 Nov Source Fixes** | The 4 ESP32 breadboard/bin nodes were intentionally left at home per `LAB_DAY_UNI_CHECKLIST_2026-11-18.md`. All 7 firmware sketches compile cleanly (`7/7`). | At home (with owner confirmation and board/COM verification), flash:<br>- `BIN_NODE_1`: `SmartLab_Consumable_Bin.ino` (5 s HTTP retry backoff + `WiFi.setSleep(false)`)<br>- `REUSE_BIN_1`: `SmartLab_Reusable_Bin_Modular` (reconnect `WiFi.setSleep(false)`)<br>- `CAM_LAB01`: `ESP32CAM_Vision_FAST.ino` (`esp32@3.2.1`, adaptive 1 fps idle + 10 s Wi-Fi reconnect). |
| **`BLK-04`** | `P1` | **Host Laptop Free RAM (`1.4 GB` free / `811 pages/s`) Under Concurrent WSL2 + Dual AI CLI Load** | Running 5 Docker containers (`vmmemWSL` ~3.2 GB) + 2 DirectML camera processes (`~1.25 GB` RSS) + Ollama + Voice + Chrome + 2 AI coding CLIs on a 16 GB laptop leaves `1.1–1.4 GB` free RAM. | Create `%USERPROFILE%\.wslconfig` with `memory=4GB` and close coding CLIs before 30-minute live thesis demonstrations. |
