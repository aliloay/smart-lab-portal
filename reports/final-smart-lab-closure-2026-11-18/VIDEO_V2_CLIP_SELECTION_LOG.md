# Showcase V2: clip selection log

Times are V2 segment starts (0.4 s crossfades). Source times are in seconds of the source file or recording.

| # | V2 start | Chapter / scene | Source (range) | Why | Edits / privacy |
|---|---|---|---|---|---|
| 0 | 0:00.0 | opener | `FACILITY_INTELLIGENCE_47S.mp4` 0.0–3.4 | the cinematic "What if every system worked together?" | – |
| 1 | 0:03.0 | title card | generated (V1) | identity | background = blurred 1/10-resolution lab photo |
| 2 | 0:09.6 | 01 Sign-in & welcome | `rec_login` 0.6–10.8 | real sign-in with typed username + masked password | demo copy, demo account `demo.staff`; never the owner's credentials |
| 3 | 0:19.4 | welcome screen | `rec_login` 11.0–19.0 | the actual welcome screen after sign-in | – |
| 4 | 0:27.0 | Dive in | `rec_login` 19.6–25.5, 28.5–36.0, 40.5–46.0, 53.5–58.5, 61.5–65.5 @1.5× | the welcome story (labs → hub → twins → door decision → lab) | skipped the dashboard of the demo copy (demo data) |
| 5 | 0:45.2 | 02 Live system | `project-footage/iot_dash.png`, `equipment_environment.png`, `equipment_consumables.png`, `equipment_reusables.png` | real portal on 19 Oct with nodes online | labelled "Recorded 19 Oct 2026"; shown as dated cards, not as one combined "all online" screen |
| 6 | 0:56.7 | command center | v2 tour 146.5–151.5 | the 18 Nov wall view | V1 |
| 7 | 1:01.3 | devices | v2 tour 164.0–171.6 | heartbeats, honest offline | V1 |
| 8 | 1:08.5 | 03 Hardware engineering | `tools/cad/release_2026-10-25/1..4*.jpg`, `door_enclosure/out_final_2026-10-24_cam/DoorEnclosure_Assembly.png` | CAD of every enclosure, the ESP32-CAM door version | white CAD sheets placed as cards on the dark background |
| 9 | 1:20.4 | renders | `v4/node_studio_0`, `fn_E_long` 0.4–3.0, `fn_C_long` 0.3–2.7, `fn_R_long` 0.3–2.8 | clean studio renders (no home background) | – |
| 10 | 1:29.1 | prototypes | `node_master.mp4` 0–4.4, AR take 73.2–77.6 (no boxes), `binlid.mp4` 0–5.4 | the real hardware | the home desk background is pushed back: clip framed on its own blurred, darkened copy + vignette; heads blurred |
| 11 | 1:42.9 | 04 AI security cameras | v2 tour 35.4–44.3 | both cameras live | segment-wide head blur |
| 12 | 1:51.5 | camera 1 | v2 tour 36.6–44.3 (tile zoom) | V1 | head blur |
| 13 | 1:58.8 | camera 2 | v2 tour 35.4–42.6 (tile zoom) | V1 | head blur |
| 14 | 2:05.6 | tracking | `hero/hero_in.mp4` 0.3–10.8 (7 Oct recording) | people moving, boxes, lab numbers, desk/robot labels | names already masked and faces blurred in the source; V2 adds a segment-wide head blur (17 areas) |
| 15–20 | 2:15.7 | 05 Lab computers | v2 tour 67.4–74.6, 81.2–85.5, 94–100, 105.8–112, photos, 113.5–124.4 | V1 scenes | screen-wall user names blurred. **Every v2-tour frame:**<br>• "Signed in: \<account\>" on PC cards is found by template matching and the account blurred<br>• "(\<account\>)" after each exam-mode report line is blurred<br>These leaks were in V1, found by the parallel closure session, and are fixed in the build script, so a re-render stays clean |
| 21 | 2:54.1 | 06 Robots & twins | `Digital Twin_Ur5e .mp4` 2.0–9.4, crop 260,95–1660,1010 | twin with "LIVE · physical robot", 47 samples/s | browser bar (bookmarks, mail tab) cropped out |
| 22 | 3:01.1 | real UR5e | `Ur5e robot.mov` 0–10.85 | real robot + twin | V1 |
| 23 | 3:11.6 | PREVIEW interaction | `rec_live` 9.5–19.0, 20.0–30.0 (panel crop), 42.0–49.5 (full view) @1.35× | mouse orbit, zoom, joint bars, grab, full view | banner "PREVIEW · simulation only, nothing sent to the robot"; robots were off |
| 24 | 3:31.2 | 07 Augmented reality | AR take 8.0–15.5, 17.5–29.5 @1.45× | clean UR5e recognition + marker → LIVE | status bar cropped (phone number); see AR review |
| 25 | 3:44.2 | AR nodes | AR take 46.0–50.0, 53.5–60.5, 91.0–98.0, 103.0–107.6 @1.5× | FANUC + three nodes + master node, correct boxes only | wrong detections cut (AR review) |
| 26 | 3:58.9 | 08 Automation (n8n) | generated from 23 JSON files | workflow catalogue | "configuration, not a live run" |
| 27–28 | 4:10.2 | workflows 15, 23 | generated from `15-low-stock.json`, `23-emergency.json` | trigger → checks → actions, backend calls | "definition … not executed" |
| 29 | 4:20.8 | 09 Knowledge vault | `rec_obsidian` 1.0–4.5, 6.5–10.8 | real Obsidian notes | project vault only, Restricted Mode; the personal vault was never opened |
| 30–31 | 4:28.2 | graph view | `rec_obsidian` 15.2–23.5, `rec_obsidian2` 26.0–29.5 | real Obsidian graph | session-history folder filtered out of the graph |
| 32 | 4:39.2 | knowledge graph | generated from `SmartLabKnowledge/data/graph.json` | relationships by subsystem | 306 files, 781 links (mentions, imports, API calls) |
| 33 | 4:50.8 | retrieval pipeline | generated | docs → vault → embeddings → retrieval → local AI | – |
| 34 | 5:02.2 | 10 Local AI assistant | v2 tour 187–193, 208.5–213.8 | lab data answer (robots) | the earlier "who is in the lab" answer, still visible above the robots answer (names, clothing, desks), is blurred (src 865,212–1528,362); the piece ends before the panel scrolls; the "Which lab PCs are online" answer (accounts) is not used |
| 35 | 5:13.9 | Ask the project | `rec_ask` 4.5–13.5, 19.9–27.5 | project answer with sources + guard refusal | live portal 19 Nov |
| 36 | 5:30.1 | 11 One integrated system | generated | integration diagram | – |
| 37 | 5:40.9 | closing shot | `FACILITY_INTELLIGENCE_47S.mp4` 40.5–43.4 | "Modular. Lightweight. Locally operated." | – |
| 38 | 5:43.4 | outro card | generated (V1) + V1 "end" narration | – | – |

## Considered and not used
- the demo copy's dashboard (demo data);
- the 19 Nov analytics page (everything offline at home, plus TEST cards; the latter are now hidden in the code);
- the Remotion "TRIGGER → AUTOMATION" and Obsidian renders from the 47 s film (replaced by real data);
- the Operations Center screenshot ("AI assistant not set up", out of date);
- `two_cameras_portal.jpg` (covered by V1 camera footage);
- the 1-second QR clip;
- raw SECCAM recordings (faces);
- October camera/entry tests (faces).
