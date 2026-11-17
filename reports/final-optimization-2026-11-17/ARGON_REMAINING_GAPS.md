# ARGON_REMAINING_GAPS.md

Every remaining gap below is outside software code in Argon's worktree (either requiring GIU IT administrative action, on-site physical calibration, or physical USB flashing at the lab).

---

## 1. External / GIU IT Administrative Blockers (`BLOCKED` Outside Software)

| # | Gap / Blocker | Root Cause | Required Action & Owner |
|---|---|---|---|
| 1 | **Student Lab PCs (`PC_01..PC_16`) Cannot Reach Relay on `S2PC136:8000`** | On 17 Nov, `Test-NetConnection 10.30.11.136 -Port 8000` from `PC_01` (`S2PC121`) failed because Windows Defender Firewall on `S2PC136` blocks inbound TCP `8000, 443, 80` on the university Ethernet interface (`10.30.11.136`), and adding a firewall rule requires local Administrator rights. | **GIU IT**: Approve and apply the one-line inbound firewall rule on `S2PC136`:<br>`New-NetFirewallRule -DisplayName 'SmartLab Relay' -Direction Inbound -Protocol TCP -LocalPort 8000,443,80 -RemoteAddress 10.30.11.0/24,10.40.20.0/24 -Action Allow`<br>**Lab Admin**: Re-run `Install-CurrentUser.ps1 -Role Engineer` from the updated `lab_usb_kit` on `S2PC136` so the fixed `relay.py` (with `0.0.0.0` fallback) runs automatically. |
| 2 | **Windows SmartScreen / ExecutionPolicy Prompt on Fresh Lab PCs** | University Group Policy may prompt on first run of unsigned `.ps1` scripts copied from USB. | Use `Right-click -> Run with PowerShell` per `SMART_LAB_POWERSHELL_PC_DEPLOYMENT_GUIDE.md` (never bypass university policy). |

---

## 2. On-Site Physical Hardware & Calibration Follow-Ups (`NEXT LAB VISIT`)

| # | Item | Current Status | Next-Visit Action |
|---|---|---|---|
| 1 | **Flash Updated Firmware to `BIN_NODE_1`, `REUSE_BIN_1`, and `CAM_DOOR_01`** | Source fixes are committed and verified in `firmware/SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino` (5 s HTTP retry backoff), `firmware/SmartLab_Reusable_Bin_Modular/src/WiFiManager.cpp` (reconnect `WiFi.setSleep(false)`), and `firmware/ESP32CAM_Vision_FAST/ESP32CAM_Vision_FAST.ino` (boot/loop Wi-Fi recovery). | With owner approval on-site at GIU lab, compile and flash via Arduino IDE over USB. |
| 2 | **Camera 1 (`SECCAM_LAB01`) `UR5e_front` Floor Anchor Refinement** | Argon's `crosscam.py` fix (`GATE_WIDE_M = 2.0 m` for same-confirmed-identity pairs + confirmed-identity veto) already eliminates 100% of the UR5e false conflicts in software. However, `SECCAM_LAB01_floor.json` still has a `0.50 m` leave-one-out homography residual at `UR5e_front` (`[1.40, 2.45]`). | On next lab visit, run `py tools/security_vision/floor_refit.py` with one additional clicked floor point near the UR5e pedestal base (`x=1.4, y=3.2`) when unobstructed. |
| 3 | **Host Laptop Free RAM & Disk `C:` Margin** | Host laptop has `16,213 MB` RAM (`884–1,502 MB` free when Chrome + VS Code + WSL2 + AI agents run together) and `22.0 GB` free on `C:`. | Before live thesis/lab demos, cap WSL2 at `4 GB` in `%USERPROFILE%\.wslconfig`, close coding CLIs/unused browser tabs, and keep `C:` above `20 GB` free (`docker builder prune` if needed). |
