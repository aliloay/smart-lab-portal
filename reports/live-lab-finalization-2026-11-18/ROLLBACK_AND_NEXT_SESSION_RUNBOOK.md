# ROLLBACK_AND_NEXT_SESSION_RUNBOOK.md

- **Isolated Worktree**: `C:\Projects\smart-lab-argon`
- **Branch**: `opt/gemini-live-lab-finalization-2026-11-18`
- **Base Commit**: `610279e` (`fix/pre-lab-hardening`)

---

## 1. Merging Gemini's 18 Nov Live-Lab Fixes into Main (`C:\Projects\smart-lab-portal`)

Once Claude Code Max finishes its current work in `C:\Projects\smart-lab-portal`, merge `opt/gemini-live-lab-finalization-2026-11-18` (zero overlapping files with `frontend/**` or `backend/app/**`):

```powershell
Set-Location C:\Projects\smart-lab-portal
git merge opt/gemini-live-lab-finalization-2026-11-18
```

Then restart only the 4 affected host Python processes (`security_camera`, `security_camera2`, `ur5e_monitor`, `fanuc_monitor`) so the live services pick up the `labmap.py`, `activity.py`, `identity.py`, and `robot_collector.py` fixes:

```powershell
# Restart only cameras & robot collectors cleanly
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
  Where-Object { $_.CommandLine -match 'security_vision\.py|robot_collector\.py' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

.\launch.bat
```

And to stamp the running Docker images (`backend` and `frontend`) with `BUILD_COMMIT` and `BUILD_TIME`:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\deploy\build_images.ps1
docker compose up -d --no-deps backend frontend
curl.exe -s http://127.0.0.1:8000/api/health
```

---

## 2. Exact Rollback Procedure

- **To roll back all 18 Nov Gemini changes before merging**:
  ```powershell
  Set-Location C:\Projects\smart-lab-argon
  git checkout opt/argon-systems-vision-2026-11-17
  git branch -D opt/gemini-live-lab-finalization-2026-11-18
  ```
- **To roll back in `C:\Projects\smart-lab-portal` after merging**:
  ```powershell
  Set-Location C:\Projects\smart-lab-portal
  git reset --hard 610279e
  ```
- **To roll back Docker images (`backend` / `frontend`)**:
  ```powershell
  docker tag smart-lab-portal-backend:pre-confirm-other-20261118 smart-lab-portal-backend:latest
  docker tag smart-lab-portal-frontend:pre-confirm-other-20261118 smart-lab-portal-frontend:latest
  docker compose up -d --no-deps backend frontend
  ```

---

## 3. Next Lab / Home Session Checklist

1. **At Home (ESP32 Nodes)**:
   - Connect each board one at a time via USB, verify COM port in Device Manager, and flash:
     - `BIN_NODE_1` (`firmware/SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino`)
     - `REUSE_BIN_1` (`firmware/SmartLab_Reusable_Bin_Modular/SmartLab_Reusable_Bin_Modular.ino`)
     - `CAM_LAB01` (`firmware/ESP32CAM_Vision_FAST/ESP32CAM_Vision_FAST.ino` using `D:\SmartLabData\arduino_core321`)
2. **At GIU Lab (Robots & Remaining PCs)**:
   - Resolve `192.168.1.100` IP overlap between `PC_ENG` USB-Ethernet adapter and `FANUC_01` (`set FANUC_IP=192.168.1.101` or `PC_ENG` USB-NIC `= 192.168.1.210`).
   - Power on `UR5E_01` (`192.168.1.102`) and `FANUC_01` (`192.168.1.101`) and verify live joint telemetry.
   - Sign in on `PC_GIULAB20-PC8`, `PC11`, `PC12`, and `PC13` and run `Install-CurrentUser.ps1 -Role Lab` from the v1.1 USB kit.
3. **Host Laptop Pre-Demo**:
   - Configure `%USERPROFILE%\.wslconfig` (`memory=4GB`) and run `scripts\status.ps1` to confirm `free RAM >= 2,000 MB` and `paging == 0 pages/s`.
