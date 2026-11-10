---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/SMART_LAB_FINAL_LAUNCH_GUIDE.md"
source_hash: "308bb7a74c607c181deb574e2768b24037ac1bd36448258e8dfd5e52452b2a4a"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/SMART_LAB_FINAL_LAUNCH_GUIDE.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_SMART_LAB_LAB_DAY_TEST_CHECKLIST.md]] - mentioned by docs
- [[docs_SMART_LAB_PC_DEPLOYMENT_GUIDE.md]] - mentioned by docs

# Smart Lab - final launch guide (lab day 2026-11-04)

## Before leaving home
1. Charger in the bag (on battery the i7 throttles and everything is slow).
2. Close what the lab does not need: extra VS Code windows, Chrome tabs, games/launchers.

## At the lab, in this order
1. Ethernet cable -> Huawei Smart Lab router. The adapter keeps 192.168.1.200 / 255.255.255.0, **no gateway**.
2. Wi-Fi -> your phone hotspot (internet for Claude/Docker; the portal itself runs offline).
3. Double-click `launch.bat`. It opens:
   - the Docker portal (db, backend, web) - builds only when the code changed;
   - Face server, Security camera 1 + 2, UR5e + FANUC monitors (visible windows);
   - Ollama, Knowledge, Voice, OPC UA, PC agent, LAN presence, smartlab.local (minimised, low priority);
   - **"Smart Lab - Status"**: one live table of every service (UP / STARTING / DOWN + port), the containers,
     free RAM and GPU memory. Watch this window instead of the others.
4. Wait ~1-2 minutes until Status shows everything UP (cameras load models last).
5. Run the preflight: `powershell -ExecutionPolicy Bypass -File scripts\lab_preflight.ps1`
   (PASS/WARN/FAIL for network, firewall, portal, services and every lab device; saves logs\preflight-*.txt).
6. If the Wi-Fi is ALSO a 192.168.1.x network (not the case with a phone hotspot): administrator PowerShell
   `scripts\fix_lab_routing.ps1 -Apply` (routes vanish on reboot, or `-Revert`).
7. Engineer PC and lab PCs: `docs/SMART_LAB_PC_DEPLOYMENT_GUIDE.md`.
8. Test list: `docs/SMART_LAB_LAB_DAY_TEST_CHECKLIST.md`.

## Do not click inside the visible console windows
Windows pauses a console program while text is selected in it. If a window title starts with "Select", press Esc.

## Stop everything
Ctrl+C in the launch.bat window (stops Docker), then close the service windows. Data is kept.

## Restart one service
Close its window and run `launch.bat` again - it only starts what is missing.

