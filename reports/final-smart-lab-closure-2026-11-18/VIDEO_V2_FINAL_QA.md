# Showcase V2: final QA (19 Nov 2026)

## File
`SMART_RESEARCH_LAB_FINAL_SHOWCASE_V2.mp4`:
- **Duration:** 5:49.1 (10,474 frames), 1920×1080, 30 fps, H.264 (CRF 19), 109 MB.
- **Audio:** AAC stereo 48 kHz.
- **Subtitles:** `SMART_RESEARCH_LAB_FINAL_SHOWCASE_V2.srt`, all 39 narration lines + the AI question.

V1 (`SMART_RESEARCH_LAB_FINAL_SHOWCASE.mp4`) was not touched by this work. The parallel closure session separately post-blurred account names in it; its original is kept at `D:\SmartLabData\showcase_2026-11-19\build\SHOWCASE_v1_before_name_blur_20261119.mp4`.

## How it was checked
1. Stills of every new segment at full resolution, before the render.
2. The exported file watched as 174 frames, one every 2 s, at 384 px (contact sheets `D:\SmartLabData\showcase_2026-11-19\contact\v2final_0..2.jpg`).
3. Full-resolution checks of every privacy-sensitive window.
4. `ffmpeg blackdetect` (no black ≥ 0.5 s) and `volumedetect` (mean −15.7 dB, peak −0.2 dB; V1 was −15.5 / −0.4).

## Checklist
| Check | Result |
|---|---|
| No good V1 scene removed by accident | PASS. Kept: title, cameras (3), PCs (6), real PC photos, maintenance, real UR5e, command, devices, AI robots answer, outro. Replaced on purpose: the plain sign-in page, the offline robots page, node photos, bins/access. Each is listed in VIDEO_V2_CHANGELOG.md |
| No wrong or lagging AR boxes | PASS. Only the frames marked "used" in VIDEO_V2_AR_QUALITY_REVIEW.md; V1's wrong "door controller 93 %" is gone |
| n8n shown honestly | PASS. "configuration, not a live run" and "definition … not executed" on screen; count from the files (23) |
| Obsidian and its graph actually shown | PASS. Real Obsidian (project vault only, Restricted Mode): notes, graph view, zoom; plus the rendered link graph from the vault's data |
| Welcome screen + login journey | PASS. Typed username, masked password, sign-in, welcome screen, Dive in; demo copy and demo account labelled |
| Mouse interaction with the offline twin | PASS. Orbit, zoom, joint bars, grab, full view; banner "PREVIEW · simulation only, nothing sent to the robot"; robots were off |
| Hardware design / renders / prototypes | PASS. CAD (incl. ESP32-CAM door enclosure), renders, real master node, reusable-bin lid |
| 3D-printing footage | NOT AVAILABLE. None exists in the project folders (documented, not faked) |
| Camera tracking with privacy | PASS. 7 Oct clip with names masked; faces pixelated (segment-wide union of person detections) |
| Historical live states labelled with dates | PASS. "Recorded 19 Oct 2026 · nodes online", "Recorded 14 Oct 2026 · live telemetry", "Recorded 7 Oct 2026", "Recorded 17 Nov 2026 · phone AR", "Recorded at GIU · 18 Nov 2026", "Live portal · 19 Nov 2026"; no combined "all online" screen |
| Subtitles match the footage | PASS. Burned captions per segment (own captions on all new segments; the v2 tour's own captions on reused tour segments) + .srt |
| Audio balanced | PASS. Same score and sound effects as V1; music ducked under the voice |
| No blank or loading screens | PASS after one fix. The screen-wall hold showed the dark "Waiting for PC-08" frame for ~2 s (2:27); fixed in the script (piece ends at 85.4 s) and patched into the export by re-rendering that window only |
| No freezes, black gaps, broken transitions | PASS. blackdetect clean; the frame count matches the timeline |
| **Privacy: account names** | PASS. "Signed in: \<account\>" on PC cards (template-matched) and "(\<account\>)" after exam reports are blurred in every tour frame; the "Which PCs are online" answer is not used |
| **Privacy: third-person names** | PASS. The earlier "who is in the lab" answer above the robots answer is blurred; the 7 Oct clip has names masked |
| Privacy: faces / phone number / credentials | PASS. Faces pixelated (cameras, tracking clip, photos, AR); the AR status bar with a phone number is cropped; the demo account only; no owner credentials; the browser bar with bookmarks/mail is cropped from the twin clip |
| Privacy: camera-software name labels | NOTE. Labels drawn by the camera software (e.g. the owner's name, "Masters/Eng. Hemaly?") remain in the V1 camera shots reused in V2, as in V1. Faces are hidden. Blurring them too is one setting in `montage_v2.py` if wanted |

## Known limits (honest)
- **The welcome/login segment is on the demo copy.** It is the same frontend code, but the demo database is used so that no real account is typed. It is labelled on screen.
- **The "live system" views are dated recordings** (19 Oct, 14 Oct, 18 Nov), not the current state. At home on 19 Nov the nodes and robots were offline.
- **The n8n canvases are drawn from the workflow JSON.** They are not screenshots of the n8n editor, which was deliberately not started.
- **The knowledge-graph animation is rendered from the vault's link data.** The real Obsidian graph view is shown right before it.
