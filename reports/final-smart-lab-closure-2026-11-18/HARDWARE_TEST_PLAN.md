# Hardware test plan - what only the owner can do (19 Nov 2026)

Nothing on this list was tested in software only. Each step needs the real device and the owner present.
The detailed step-by-step version is Gemini's
`C:\Projects\smart-lab-argon\reports\gemini-full-inspection-2026-11-19\HARDWARE_TEST_PLAN_FOR_OWNER.md` (checked by
Claude: the addresses and firmware names below match the live database on 19 Nov). This page is the short order to work in,
plus what to write down so the result can go into the thesis.

## Rules for every step
- One verified step at a time. Write down the real measured number, or "not measured". Never a guessed value.
- The door opens **only** through the Master ESP32's normal scan flow, with the owner at the door. No test opens it any other way.
- Robots: read-only. Move them only from the teach pendant, by a trained operator. The portal never sends a command.
- Back up each board's flash with esptool before uploading. Build the **ESP32-CAM with esp32 core 3.2.1**
  (`D:\SmartLabData\arduino_core321`); 3.3.x builds fail at boot with "Camera init failed".
- No photos of people in the evidence folder.

## A. At home: the four ESP32 nodes and the entry camera (Smart_Lab router)
| # | Device (portal id, address) | Do | Write down | Pass when |
|---|---|---|---|---|
| A1 | Consumables bin `BIN_NODE_1` .153 | Flash the 17-18 Nov firmware; tare; known mass x10 | each reading (g), the mass used | portal card updates within a few seconds; spread recorded |
| A2 | Reusable bin `REUSE_BIN_1` .154 | Flash; reed open/closed; servo lid cycle; NFC borrow + return | reed level for open/closed, servo angles that work | borrow and return show in the portal |
| A3 | Environment node `ENV_LAB01` .152 | Check the 4 `VERIFY` constants in `env_config.h` with a multimeter (PIR, flame, MQ polarity) | each measured level | a real trigger raises the portal alert, nothing else does |
| A4 | Entry camera `CAM_LAB01` .150 | Build with core 3.2.1, flash, open `/status` | boot log line, fps idle | card shows ONLINE "checked by the portal" |
| A5 | Door `MASTER_LAB01` .151 | 20 normal entries (card or QR, then fingerprint or face) | time from scan to click for each | 20 times recorded; portal shows each ACCESS event |
| A6 | All nodes | USB meter per node, idle and active; one power cut of router + nodes | mA idle/active; seconds until each is back in the portal | numbers recorded |
| A7 | Face server (laptop, port 5000) | Start it, then stop it | - | since 19 Nov the card is ONLINE only while `/health` answers `{"status":"ok"}`; stopping it turns the card off within ~15 s |

## B. At GIU (LAB_01)
| # | Item | Do | Pass when |
|---|---|---|---|
| B1 | **IP clash first** | Give Hemaly's PC (S2PC136) a fixed Smart_Lab address outside the robot range (e.g. .210, no gateway) or move the router's DHCP pool above .110 and reserve .100 / .102 | no PC holds .100 or .102 |
| B2 | UR5e (.102) and FANUC (.100) | Power on; operator jogs from the pendant | portal twins go ONLINE and follow; after power-off they show offline/stale, never "online idle" |
| B3 | PC-10 (hostname GIULAB20-PC13) | Re-run `INSTALL_SMARTLAB.bat` | card shows pc-agent-1.0 |
| B4 | PC-11 sticker | Read the sticker on hostname GIULAB20-PC14 | matches "PC-11", else Rename on its card |
| B5 | Screen share | Present from the master PC, then switch it off without pressing stop | share ends by itself within ~90 s; a new share never shows the old PC's picture |
| B6 | Phone AR | Install `/smartlab-ca.crt` on the demo phone; 10 scans per marker | no HTTPS warning; result per marker recorded (the 17 Nov 52/89/93/80 % figures were appearance hints, not a ground-truth test) |
| B7 | Assistant with both cameras running | Ask the 6 benchmark questions (AI_PERFORMANCE_BEFORE_AFTER.md) | times recorded with "cameras live, GPU" in the conditions |
| B8 | 30-minute offline run | Unplug the internet; `py tools/offline/offline_check.py` | all local functions keep working for 30 min |

## Thesis numbers this produces (Gemini B-11)
Door scan-to-unlock time (A5), cold start `launch.bat` to `/api/health` 200 (time it once), power-cut recovery (A6),
per-node power draw (A6), offline run (B8). A priced bill of materials comes from the receipts, not from a test.
