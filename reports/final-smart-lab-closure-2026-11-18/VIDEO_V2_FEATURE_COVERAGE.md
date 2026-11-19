# Showcase V2: feature coverage

Evidence types:
- **LIVE-REC (current):** recorded from the running portal on 19 Nov 2026.
- **HIST-REC:** recorded earlier from the real system; the date is shown on screen.
- **DEMO:** the isolated demo copy of the portal (throwaway database, demo account).
- **SIM:** visual simulation (digital-twin PREVIEW).
- **CONFIG:** a static visualisation of configuration or data files.
- **RENDER/CAD:** design renders.
- **PHOTO:** real photos.

Times are in the V2 film (start of the segment).

| Feature | In V2? | Time | Footage | Type |
|---|---|---|---|---|
| Cinematic intro | yes | 0:00 | 47 s film intro ("What if every system worked together?") + V1 title card | RENDER |
| Welcome screen | yes | 0:19 | real welcome screen after sign-in, then Dive in through 5 sections | DEMO (same frontend code as live) |
| Login journey (type username + masked password, submit, success) | yes | 0:09 | `demo.staff` typed on the demo copy; password masked; no real credentials | DEMO |
| Dashboard / command center | yes | 0:45, 0:56 | command center 19 Oct (9/10 devices reporting) + command center at GIU 18 Nov | HIST-REC |
| Environment readings | yes | 0:45 | ENV_LAB01 online, 26.6 °C / 54 %, 19 Oct | HIST-REC |
| Consumables (weight → count) | yes | 0:45 | bin LIVE, ~30 resistors / 134.8 g, 19 Oct | HIST-REC |
| Reusable items (NFC) | yes | 0:45, 1:29 | NFC item list 19 Oct + real bin lid opening | HIST-REC + PHOTO/video |
| Devices / heartbeats | yes | 1:01 | devices page at GIU 18 Nov | HIST-REC |
| CAD design | yes | 1:08 | CAD sheets of all 4 enclosures + door enclosure with ESP32-CAM | RENDER/CAD |
| 3D renders of the nodes and PCs | yes | 1:20 | master, environment, consumables, reusable renders | RENDER |
| 3D-printing footage | **no** | – | no printing video or photo exists in the project folders (searched D:\SmartLabData, OneDrive\Desktop\Bsc, docs, tools/cad) | – |
| Physical prototypes (master node, reusable bin, ESP32-CAM in door enclosure) | yes | 1:29 | real master-node clip, AR-take close-up, real reusable bin | PHOTO/video |
| ESP32-CAM | partial | 1:08 | CAD of the door enclosure with the ESP32-CAM; no separate clip of the camera board | RENDER/CAD |
| Security cameras: two cameras, zooms | yes | 1:42 | V1 footage (18 Nov), heads blurred | HIST-REC |
| People moving + tracking + labels | yes | 2:05 | 7 Oct recording: people walking, boxes, lab numbers, desk/robot labels; names masked, faces blurred (+ V2 segment-wide head blur) | HIST-REC |
| Lab PCs (status, wall, share, message, real PCs, maintenance) | yes | 2:15 | V1 footage (18 Nov) + real PC photos | HIST-REC + PHOTO |
| UR5e twin following the real robot | yes | 2:54 | twin with "LIVE · physical robot", 47 samples/s, 14 Oct | HIST-REC |
| Real UR5e moving with twin | yes | 3:01 | phone video of the robot and laptop | HIST-REC |
| Digital-twin mouse interaction (rotate, zoom, pose joints, grab arm, full view) | yes | 3:11 | live portal, PREVIEW mode, banner "simulation only, nothing sent to the robot" | SIM (LIVE-REC) |
| AR recognition + marker → live data | yes | 3:31 | only clean frames (see VIDEO_V2_AR_QUALITY_REVIEW.md) | HIST-REC (17 Nov) |
| n8n workflow overview | yes | 3:58 | all 23 workflow definitions from `automation/n8n/json` (count verified: 23 files) | CONFIG |
| n8n canvas (trigger → checks → actions, backend calls) | yes | 4:10 | workflows 15 and 23 drawn from their JSON node positions and connections | CONFIG ("not a live run" on screen) |
| Obsidian interface + notes | yes | 4:20 | real Obsidian, project vault only (Restricted Mode), notes Project-Timeline and SecurityCam | LIVE-REC (19 Nov) |
| Obsidian graph view | yes | 4:28 | real global graph (coloured groups), zoom with note labels | LIVE-REC |
| Knowledge-graph relationships (sensors, robots, AI, modules, docs) | yes | 4:39 | rendered from the vault's link graph (306 files, 781 links), group by group | CONFIG |
| Docs → vault → embeddings → retrieval → local AI | yes | 4:50 | animated pipeline; states Obsidian is the source, not the AI | CONFIG |
| AI assistant (lab data) | yes | 5:02 | V1 footage (18 Nov) | HIST-REC |
| AI assistant (project answer with sources + refusal) | yes | 5:13 | live portal 19 Nov: relay answer with 3 sources; "Open the lab door" refused by the guard | LIVE-REC |
| Architecture / integration | yes | 5:30 | animated diagram: nodes, ESP32-CAM, cameras, robots, PCs → backend/DB → portal, n8n, AR, AI | CONFIG |
| Professional close | yes | 5:41 | 47 s film "Modular. Lightweight. Locally operated." + V1 outro card | RENDER |
| PLC monitoring | not shown | – | no PLC footage; robots are monitored through RTDE / OPC UA collectors, shown in the architecture | – |
