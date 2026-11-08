# Smart Lab - lab day test checklist (2026-11-04)

Tick each line; write the measured value, not "ok". Hardware results only from real observations.
Never click robot motion, door open or emergency controls during these tests.

## A. Laptop (before anything else)
- [ ] On the charger. Status window: free RAM ______ MB (want > 2,000)
- [ ] Ethernet = 192.168.1.200, no gateway; Wi-Fi = phone hotspot (address ______)
- [ ] `scripts\lab_preflight.ps1`: ___ FAIL / ___ WARN (paste the FAIL lines here)
- [ ] Firewall rule present (run allow_firewall.bat as admin once if FAIL)
- [ ] Robots reached over the cable = PASS (if WARN with 192.168.1.x Wi-Fi: fix_lab_routing.ps1 -Apply)

## B. Devices (preflight "Devices" rows)
- [ ] Router .1  - [ ] FANUC .100  - [ ] UR5e .102 (tcp 30004)  - [ ] ESP32-CAM .150  - [ ] Master .151
- [ ] Env node .152  - [ ] Cameras .155 / .156 (tcp 554)

## C. Portal on the laptop and a phone
- [ ] https://192.168.1.200 loads on a phone on the lab Wi-Fi; login works
- [ ] Overview / Equipment / IoT pages open in < 3 s (time: ____ s)
- [ ] Security: camera 1 and 2 live, fps ____ / ____ (Status window: GPU ____ MB)
- [ ] Assistant: ask one question while both cameras run -> answer in ____ s, camera fps during it ____ / ____
- [ ] Phone Scan: bin, switch, router named correctly; phone not hot after 2 min

## D. Engineer PC (needs the lab engineer / GIU IT) - docs/SMART_LAB_PC_DEPLOYMENT_GUIDE.md
- [ ] hostname ______ GIU IP ______ ; USB-Ethernet 192.168.1.210, `ping 192.168.1.200` OK
- [ ] relay.py running, "portal reachable - OK"
- [ ] PC_ENG online in Equipment with screen preview

## E. One approved GIU lab PC
- [ ] hostname ______ IP ______ ; Test-NetConnection ENG_IP 8000 / 443 OK
- [ ] pc_agent running -> PC_xx online + preview (refresh ~1.2 s)
- [ ] Focus view (fast refresh)
- [ ] Request screen share -> share page opens on https://ENG_IP -> admin sees it
- [ ] Admin broadcast -> viewer window on the PC
- [ ] Exam mode ON -> PC shows exam state within ____ s -> OFF -> back to normal
- [ ] Ctrl+C the agent -> PC goes offline in the portal; restart it -> online again (reconnection)
- [ ] Unplug/replug the engineer PC's USB-Ethernet for 10 s -> agent recovers by itself (time ____ s)

## F. Data to capture for the detector (Gemini list)
- [ ] TP-Link switch in place with cables + LEDs (2 videos, 10-15 s)
- [ ] Huawei router with cables (1 video + 10 photos)
- [ ] Mounted cameras 1.5-4 m (10-15 photos)
- [ ] Door + mounted enclosures (10-15 photos)
- [ ] Wide scenes with 2-5 objects (15-20 photos)

## G. End
- [ ] `scripts\lab_preflight.ps1` once more; copy logs\preflight-*.txt to the thesis folder
- [ ] Ctrl+C launch.bat; Ctrl+C relay + agents on the GIU PCs; delete their temp folders
