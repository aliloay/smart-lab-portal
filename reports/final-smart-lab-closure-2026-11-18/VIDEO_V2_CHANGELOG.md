# Showcase V2: editing plan and changelog

- **V1 (unchanged):** `SMART_RESEARCH_LAB_FINAL_SHOWCASE.mp4`, 3:07, 22 segments.
- **V2:** `SMART_RESEARCH_LAB_FINAL_SHOWCASE_V2.mp4`, 5:50, 39 segments, 1920×1080, 30 fps.
- **Build:** `D:\SmartLabData\showcase_2026-11-19\build_v2\montage_v2.py`. This is the editable timeline: the `add(...)` lines are the edit decision list. It also writes `timeline_v2.json`.
- **Narration:** 21 new Piper lines (same voice as V1) in `narr_v2\`.
- **New recordings** (all in `D:\SmartLabData\showcase_2026-11-19\`):
  - `rec_login`: demo copy;
  - `rec_live`: twin PREVIEW;
  - `rec_ask`: Ask the project;
  - `rec_obsidian` and `rec_obsidian2`: the project vault.

## Plan (made from the V1 review, before editing)

| V1 time | V1 scene | Decision |
|---|---|---|
| 0:00–0:05 | title card | **keep**; add the 47 s film's cinematic opener in front and the intro narration |
| 0:05–0:13 | sign-in page (v2 tour), no typing | **replace** with the real journey: typed demo sign-in → welcome screen → Dive in |
| 0:13–0:42 | cameras tile + zoom 1 + zoom 2 | **keep** (strong); add the 7 Oct tracking clip with moving people |
| 0:42–1:13 | PCs, wall, share, message | **keep** (strong, real PCs) |
| 1:00–1:06 | real PC photos | **keep** |
| 1:06–1:24 | maintenance + robots page (offline) | keep maintenance; **replace** the offline robots page with the live 14 Oct twin + mouse interaction in PREVIEW |
| 1:24–1:35 | real UR5e + twin | **keep** |
| 1:35–2:09 | AR (two clips) | **re-cut**: V1 contained wrong detections (door controller label on the black bins at ~86–89 s, quoted as "93 %"); use only clean frames |
| 2:09–2:20 | node photos | **replace** with the full engineering sequence: CAD → renders → real prototypes |
| 2:20–2:42 | command, bins, devices, access | keep command + devices; **add** recorded live readings (19 Oct) before them; bins and access are covered by the live readings |
| 2:42–3:00 | AI (lab data) | **keep** (shortened to the robots question); add Ask the project with sources + refusal |
| – | n8n | **add** (catalog of 23 + two workflow canvases from JSON) |
| – | Obsidian / graph / retrieval | **add** (real Obsidian + rendered link graph + pipeline) |
| – | architecture | **add** an animated integration diagram before the close |
| 3:00–3:07 | outro | **keep**; add the 47 s film's "modular, lightweight, locally operated" shot before it |

## Changes made
1. **New opener:** 3.4 s from the 47 s film, then V1's title card with spoken intro.
2. **Sign-in and welcome (new):**
   - typed `demo.staff` with a masked password on the demo copy;
   - real welcome screen;
   - Dive in sections at 1.5×.
3. **Live system (new):**
   - four dated portal views from 19 Oct when the nodes were online;
   - V1's command center and devices (18 Nov).
4. **Hardware engineering (new):**
   - five CAD sheets, including the door enclosure with the ESP32-CAM;
   - four node renders;
   - real master node, AR-take close-up and reusable-bin lid.
5. **Cameras:**
   - V1's three camera scenes kept;
   - new 10 s tracking clip, faces blurred again segment-wide on top of the original blur.
6. **Lab PCs:** V1 scenes kept unchanged.
7. **Robots:**
   - live twin 14 Oct (browser bar with bookmarks/mail cropped);
   - V1's real UR5e clip;
   - new 20 s PREVIEW interaction (orbit, Ctrl+wheel zoom, joint bars, grab, full view), with the banner "PREVIEW · simulation only, nothing sent to the robot".
8. **AR:** re-cut from clean frames only (see VIDEO_V2_AR_QUALITY_REVIEW.md); side labels corrected (V1's "door controller 93 %" was a wrong detection).
9. **Automation (new):** catalog of the 23 workflow definitions; canvases of workflows 15 and 23 drawn from their JSON. Marked "configuration, not a live run".
10. **Knowledge (new):** real Obsidian (project vault only), graph view, rendered link graph group by group, and the retrieval pipeline. It states that Obsidian is the source, not the AI.
11. **AI:** V1 robots question kept; new live "Ask the project" answer with sources, and the guard refusing "Open the lab door".
12. **Integration diagram (new)**, then the 47 s film's closing shot, then V1's outro.
13. **Kept from V1:** colours, typography, caption style, chapter pills (now 11), badges, progress line, synthesised score, whooshes and chimes.

## Removed from V1
- the robots page with offline twins: replaced by live and PREVIEW twin footage;
- the AR frames with wrong detections;
- the 18 Nov AI "Which lab PCs are online?" answer: shortened for pace (the robots question stays);
- bins (current offline) and access pages: replaced by the 19 Oct live readings; access is still covered in V1.
