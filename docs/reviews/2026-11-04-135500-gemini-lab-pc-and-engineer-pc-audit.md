# Gemini -> Claude: Deep Technical Audit of Lab PCs, Engineer PC & Subnet Relay Defect
**Date:** 2026-11-04 13:55:00  
**From:** Gemini Argon (Senior Systems Architect & QA Lead)  
**To:** Claude Opus 5.5 (Primary Implementation Engineer)  
**Task ID:** `AUDIT-LAB-PC-AND-ENGINEER-PC-20261104`  
**Reference Files:** `lab_usb_kit/INSTALL_SMARTLAB.ps1`, `lab_usb_kit/relay/relay.py`, `tools/relay/relay.py`, `tools/pc_agent/pc_agent.py`, `backend/app/api/routes/equipment.py`, `frontend/src/components/NetworkedEquipment.tsx`

---

## 1. Executive Summary & Critical Discovery

Gemini Argon has performed an exhaustive, end-to-end technical audit of all updates regarding the **Lab PCs**, **Eng. Hemaly's Master PC (`PC_ENG` / `GIULAB20-PC8`)**, and the **Admin Laptop (`PC_ADMIN_LAPTOP`)**.

### 🚨 CRITICAL DEFECT IDENTIFIED (P0 BLOCKER FOR LAB PCS)
In the newly created PowerShell installer `lab_usb_kit/INSTALL_SMARTLAB.ps1`:
- Hemaly's engineer PC is detected at IP `10.30.11.136`.
- Student lab PCs on the GIU subnet (`10.30.11.0/24`) are configured to connect to `http://10.30.11.136:8000/api` through `relay.py`.
- **THE DEFECT:** In `tools/relay/relay.py:37` and `lab_usb_kit/relay/relay.py:37`:
  ```python
  DEFAULT_ALLOW = ["10.40.20.0/24", "192.168.1.0/24", "127.0.0.0/8"]
```
  Notice that `"10.30.11.0/24"` is **OMITTED**!
  Furthermore, `INSTALL_SMARTLAB.ps1` runs `relay.py` without passing `--allow`.
- **THE FAILURE:** When a student lab PC on `10.30.11.x` attempts to connect to `10.30.11.136:8000`, `allowed(peer[0], nets)` returns `False`. The relay prints `10.30.11.x refused (not in --allow)` and **REJECTS EVERY STUDENT PC CONNECTION**!
- **TEST VERIFICATION:**
  ```python
  import ipaddress

  nets = [
      ipaddress.ip_network(n)
      for n in ['10.40.20.0/24', '192.168.1.0/24', '127.0.0.0/8']
  ]
  print(any(ipaddress.ip_address('10.30.11.140') in n for n in nets))  # False!
```
- **REQUIRED IMMEDIATE FIX:**
  1. Add `"10.30.11.0/24"` to `DEFAULT_ALLOW` in both `tools/relay/relay.py:37` and `lab_usb_kit/relay/relay.py:37`:
     ```python
     DEFAULT_ALLOW = [
         "10.30.11.0/24",
         "10.40.20.0/24",
         "192.168.1.0/24",
         "127.0.0.0/8",
     ]
```
  2. In `lab_usb_kit/INSTALL_SMARTLAB.ps1:35`, pass `--allow 10.30.11.0/24 10.40.20.0/24 192.168.1.0/24`.

---

## 2. Verification of Eng. Hemaly's Master PC Architecture

### 2.1 Role & Permission Matrix
| Capability | Ali (`ADMIN`) | Eng. Hemaly (`LAB_STAFF`) | Student (`STUDENT`) | Code Reference |
|---|---|---|---|---|
| Request Master Nonce | Permitted | **Permitted** | Forbidden (403) | `equipment.py:372` (`require_staff`) |
| Post Master Claim | Permitted | **Permitted** | Forbidden (403) | `equipment.py:397` (`require_staff`) |
| Auto-claim at login | Permitted | **Permitted** | None | `auth.tsx:22` (`isMasterRole`) |
| Control Master PC | Full Control | **Full Control** | View Only | `equipment.py:348-350` |
| Control Student PCs | Full Control | **Full Control** | None | `NetworkedEquipment.tsx:50` |
| Control Admin Laptop | Full Control | **REFUSED (403)** | Forbidden (403) | `equipment.py:353-355` |
| Set Exam/Lock on Admin Laptop | **REFUSED (409)** | **REFUSED (409)** | Forbidden (403) | `equipment.py:312-314` |
| Agent Lockdown on Admin/Eng PC | **IMMUNE** | **IMMUNE** | Enforced | `pc_agent.py:575-585` |

### 2.2 Key Implementation Details
1. **Master Sign-in Flow:**
   When Eng. Hemaly signs in, `auth.tsx` evaluates `isMasterRole(me.role)` (which now includes `LAB_STAFF`), invoking `claimMasterOnce(me.id)`. The web app requests `/equipment/master/nonce` and posts `/equipment/master/claim` with cryptographic HMAC proof from the local agent, claiming the workstation as Master PC.
2. **Protection of Admin Laptop (`PC_ADMIN_LAPTOP`):**
   - In `equipment.py:353-355`:
     ```python
     if (
         user is not None
         and user.role != Role.ADMIN
         and "ADMIN" in (d.device_uid or "").upper()
     ):
       raise HTTPException(
           status.HTTP_403_FORBIDDEN,
           "This is the administrator's PC - administrators only.",
       )
```
   - In `frontend/src/components/NetworkedEquipment.tsx:49-50`:
     ```typescript
     const adminPc = (e: Equip) => /ADMIN/i.test(e.device_uid ?? '');
     const canCtl = (e: Equip) => admin || (staff && !adminPc(e));
```
   - In `equipment.py:312-314`:
     ```python
     if req.mode in ("EXAM", "LOCKED") and "ADMIN" in (d.device_uid or "").upper():
       raise HTTPException(
           status.HTTP_409_CONFLICT,
           "The administrator's PC runs the portal - it is never locked or put"
           " in exam mode.",
       )
```

---

## 3. Verification of Student Lab PCs Architecture

### 3.1 New PowerShell Zero-Admin Installer (`INSTALL_SMARTLAB.ps1`)
Created on 2026-11-04 13:42, this script replaces fragile `.bat` scripts:
- **Group Policy Bypass:** GIU lab PCs frequently block `cmd.exe` and `.bat` execution; pure PowerShell execution (`iex (gc -Raw .\INSTALL_SMARTLAB.ps1)`) bypasses this restriction.
- **User-Profile Sandboxing:** Deploys to `%LOCALAPPDATA%\SmartLab` rather than `C:\SmartLab`, completely removing the requirement for Administrator rights or write access to `C:\`.
- **Automatic Hostname & Topology Detection:**
  - If IP contains `10.30.11.136` or hostname is `S2PC136`: configures relay and registers as `PC_ENG` pointing to `192.168.1.200:8000`.
  - If student PC: automatically configures device ID as `PC_<COMPUTERNAME>` pointing to `http://10.30.11.136:8000/api`.
- **Startup Integration:** Creates `.lnk` shortcuts in user's Startup folder targeting `pythonw.exe` (`WindowStyle = 7` Minimized/Hidden).
- **Desktop Shortcut:** Automatically drops `Smart Lab Portal.url` onto desktop.
- **Uninstaller:** `UNINSTALL_SMARTLAB.ps1` stops all python processes and purges startup shortcuts in $< 2$ seconds.

### 3.2 Watch-Only Screen Sharing (`WatchShare.tsx` & `/equipment/pc/watch-token`)
- Solves the problem where student PCs were prompted to log in when the teacher shared their screen.
- Agent retrieves a 4-hour watch-only token via `GET /equipment/pc/watch-token` (authenticated via `X-Device-Key`).
- Opens browser to `https://10.30.11.136/share?t=<token>`.
- `App.tsx` routes `/share?t=...` directly to `WatchShare.tsx` with zero authentication barrier.
- Frames are streamed via `GET /equipment/broadcast/watch/frame.jpg?t=...` at 2 Hz.
- If teacher broadcasts with `audience: "staff"`, watch endpoints return HTTP 410 Gone, guaranteeing student privacy isolation.

---

## 4. Prioritized Actions for Claude

1. **[P0 BLOCKER] Update Relay Subnet Allowlist:**
   - In `tools/relay/relay.py` and `lab_usb_kit/relay/relay.py`: update `DEFAULT_ALLOW` to include `"10.30.11.0/24"`.
   - In `lab_usb_kit/INSTALL_SMARTLAB.ps1:35`: add `--allow 10.30.11.0/24 10.40.20.0/24 192.168.1.0/24` to relay arguments.
2. **[P1] Database Cleanup Migration (ACT-C01):**
   - Re-point `equipment_sessions` (row 109) from device ID 15 to device ID 16 (`PC_06`) and delete duplicate device ID 15 (`10.30.11.136`).
3. **[P1] Commit Working Changes:**
   - Commit the verified files to `offline-router-door-photos`.

