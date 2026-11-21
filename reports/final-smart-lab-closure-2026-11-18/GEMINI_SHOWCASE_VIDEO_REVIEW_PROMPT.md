# GEMINI: SMART LAB SHOWCASE VIDEO, FULL REVIEW (what to fix, what to add)

You are starting a fresh chat with no memory of earlier sessions. Read and watch before you judge.
This is a **read-only review**: do not re-render, re-encode, move, rename or overwrite anything.
Write your output only to the new folder named in section 7.

## 1. What this is
- **Project:** BSc thesis (German International University, GIU), "Smart Research Lab".
  - One local system for a robotics lab: FastAPI portal + React frontend + Postgres (Docker);
  - two AI security cameras; 5 ESP32 boards (master door, environment, consumables bin, reusable bin, ESP32-CAM);
  - UR5e and FANUC digital twins (read-only); lab-PC agents (screen wall, share, message, maintenance);
  - local AI assistant (Ollama + knowledge vault, Obsidian); n8n automations; phone AR; offline voice (Piper).
  - Everything runs on one Dell G3 laptop (now 32 GB RAM, GTX 1650), local network only.
- **The video:** a narrated showcase for the thesis defense and exhibition.
  - Audience: the examiners (Dr. Ramy and the committee), visitors at the exhibition, and LinkedIn/GitHub viewers.

## 2. The video files
Folder: `C:\Projects\smart-lab-portal\reports\final-smart-lab-closure-2026-11-18\`

| File | What |
|---|---|
| `SMART_RESEARCH_LAB_FINAL_SHOWCASE_V2.mp4` | **The current video**: 5:49, 1920×1080, 30 fps, H.264 + AAC, 104 MB |
| `SMART_RESEARCH_LAB_FINAL_SHOWCASE_V2_720p_share.mp4` | Same cut, 720p, 28 MB (for sharing) |
| `SMART_RESEARCH_LAB_FINAL_SHOWCASE_V2.srt` | Subtitles of V2 (39 narration lines + the AI question) |
| `SMART_RESEARCH_LAB_FINAL_SHOWCASE.mp4` + `.srt` | V1, 3:07, the older cut (for comparison only) |

Documentation of how V2 was made (read all of these first, same folder):
- `VIDEO_SOURCE_INVENTORY.md`: every source clip/photo, its quality, privacy problems, used or not, and why.
- `VIDEO_V2_CHANGELOG.md`: what changed from V1 to V2.
- `VIDEO_V2_CLIP_SELECTION_LOG.md` and `VIDEO_EDITING_AND_CLIP_SELECTION_LOG.md`: the cut decisions.
- `VIDEO_V2_FEATURE_COVERAGE.md`: which project features the video shows.
- `VIDEO_V2_AR_QUALITY_REVIEW.md`: which phone-AR frames were judged correct.
- `VIDEO_V2_FINAL_QA.md`: the QA checklist (black frames, loudness, privacy, labels).

## 3. Build pipeline (how it is rendered)
Folder: `D:\SmartLabData\showcase_2026-11-19\`

| Path | What |
|---|---|
| `build_v2\montage_v2.py` | **The V2 build script.** The `add(...)` lines are the edit decision list. It renders with ffmpeg, synthesises the music and sound effects in NumPy, burns the captions, and writes `timeline_v2.json` |
| `build_v2\timeline_v2.json` | Every segment with its start/end time, source and caption |
| `build_v2\gen_narr_v2.py` | Generates the V2 narration lines with Piper |
| `build_v2\kg_layout.json` | Layout of the rendered knowledge-graph segment |
| `build_v2\v2_video.mp4`, `v2_audio.wav` | Intermediate picture and sound tracks before the final mux |
| `build_v2\V2_before_kg_patch.mp4`, `V2_before_wall_patch.mp4`, `patch.mp4` | Earlier V2 states kept before two patches |
| `build_v2\still_*.jpg`, `tpl_signed_in.png` | Check stills and a template image |
| `build\montage.py`, `gen_narr.py`, `timeline.json` | The V1 build (script, narration generator, timeline) |
| `build\SHOWCASE_v1_before_name_blur_20261119.mp4` | V1 before account names were blurred |
| `build\montage_preview*.mp4/.srt/.wav` | V1 previews |
| `narr\` | V1 narration WAVs |
| `narr_v2\*.wav`, `narration.json`, `durations.json` | The 21 V2 narration lines: their text and lengths |
| `contact\*.jpg` | Contact sheets and stills used for review (V2 final: `v2final_0..2.jpg`) |
| `rec_ask`, `rec_live`, `rec_login`, `rec_obsidian`, `rec_obsidian2` | Screen recordings made on 19 Nov for V2 (AI question, live portal, login, Obsidian) |
| `obsidian_backup\` | Backup of the Obsidian settings changed during recording |

**Voice:** Piper TTS, model `C:\Projects\smart-lab-portal\tools\voice\models\en_US-lessac-medium.onnx` (offline, Python 3.12).
The voice service is `tools\voice\voice_service.py` (README in `tools\voice\README.md`).
Some V2 sections reuse the 18 Nov tour narration (19 WAVs, see the next table).

**Music and sound effects:** original, synthesised in NumPy inside the build script. No downloaded or third-party audio.

## 4. Raw source material
| Path | What |
|---|---|
| `D:\SmartLabData\lab_2026-11-18\video\v2\smart_lab_portal_tour_v2_2026-11-18.mp4` + `frames\` + narration WAVs | Narrated live portal tour at GIU, 18 Nov (main backbone of the video) |
| `D:\SmartLabData\lab_2026-11-18\video\smart_lab_portal_tour_2026-11-18.mp4` | Earlier silent tour (not used) |
| `D:\SmartLabData\lab_2026-11-17\ar_test\AR_scan_test_2026-11-17.mov` | Phone AR scan of robots and nodes |
| `D:\SmartLabData\lab_2026-11-17\recordings\SECCAM_LAB01/02_2026-11-17_*.mp4` | Raw security camera recordings (many faces, not used) |
| `D:\SmartLabData\lab_2026-11-17\node_photos\`, `fanuc_photos\` | Photos of the ESP32 nodes and the FANUC cell |
| `D:\SmartLabData\lab_2026-11-18\photos_shutdown\` | Lab PCs showing the message and the shutdown countdown |
| `D:\SmartLabData\colab\robot_pack_tmp\Ur5e robot.mov` | Real UR5e moving with the digital twin following |
| `C:\Users\dell\OneDrive\Desktop\Bsc\` | Older clips (twin screen recording, early camera tests); see the inventory for why most were rejected |
| `ONECORE_LAUNCH_VIDEO\final_v3\` (location in the inventory) | Earlier promo cuts with different branding (not used) |

## 5. What is new since the video was made (19 Nov), not in it yet
All of this works on the real hardware. Evidence is in `C:\Projects\smart-lab-portal\docs\reports\MEASUREMENTS_2026-11-21.md`
and `docs\PROGRESS_CHECKPOINT.md`.
- **Measured door speed:**
  - card → identity 5 ms; QR → portal check 161 ms; fingerprint/face match → unlock 5–8 ms; unlock → grant screen 230 ms;
  - cold start ready in 2.9 s, locked from 0.47 s;
  - router power cut: all 5 nodes back within 5.4 s of the router being ready.
- **Offline door:** card + fingerprint keep working with the laptop unreachable. Door events are kept on the master and delivered
  late at their real time ("store and forward", 6 of 6 delivered within 1 s of reconnecting).
- **Grant screen photo:** the door TFT and the tablet show the person's photo on ACCESS GRANTED; the admin picks the photo from
  face-training frames, the door camera, or an upload.
- **Consumables bin:** guided calibration on the bin's LCD, and several items per scale; booking of 0.2 g resistors measured exactly.
- **Portal:** signup approval for admins; the AI assistant answers "where is the X lab" in one line; admins edit a lab's location.
- **Honest findings:** the RFID reader freezes at the relock because the lock has no flyback diode (software guard: 8 of 10
  relocks survived; the 1N4007 diode is the real fix and is being bought). The ESP32-CAM Wi-Fi fix brought ping loss to 0 %.

## 6. What to review (give evidence with timestamps mm:ss for every point)
1. **Story and length:** does 5:49 hold attention for examiners and for exhibition visitors? What to cut, merge or reorder?
   Propose a tighter defense cut (~3 min) and a 60 s social cut, as exact segment lists from `timeline_v2.json`.
2. **Narration:** read `narr_v2\narration.json` and the `.srt` against the picture.
   - Wrong, outdated or overclaimed statements (check against section 5 and the repo).
   - Lines that are too long, robotic, or repeat each other. Mispronunciations by Piper (list the words).
   - Narration and picture out of sync.
   - Rewrite every line you would change (old text → new text, with the segment name).
3. **Subtitles:** timing, line length (≤ 42 characters per line, ≤ 2 lines), spelling, burned captions vs the `.srt` matching.
4. **Picture:** blurry, dark, loading or "connecting…" frames; cuts too fast to read; text on screen too small to read at 720p;
   inconsistent caption style; labels like "Recorded 18 Nov" missing or wrong.
5. **Audio:** music level under the narration, abrupt starts/ends, loudness (target about −16 LUFS for web).
6. **Privacy (most important):** any face, person name, Windows user name, account name, email, phone number or notification
   visible, even for one frame. Give the exact timestamp and where in the frame it is. Check the V2 file and the 720p file.
7. **Honesty:** anything shown as live that was recorded, simulated or staged, without a label saying so.
8. **Coverage gaps:** which features from section 5 (and from `VIDEO_V2_FEATURE_COVERAGE.md`) are missing.
   For each, say exactly what to record (which page or device, how long, which shot) so the owner can film it.
9. **Build script:** read `montage_v2.py`. Say what to change to apply your fixes (segment by segment), and anything fragile in it.

## 7. Output
Write to a new folder: `C:\Projects\smart-lab-portal\reports\gemini-video-review-2026-11-21\`
- `VIDEO_REVIEW.md`: findings ranked **must fix / should fix / nice to have**, each with timestamp, evidence and the fix.
- `NARRATION_REWRITE.md`: table segment | old line | new line | reason.
- `SHOT_LIST_TO_RECORD.md`: new footage to film for the section 5 features (what, where, how long).
- `CUTS.md`: the ~3 min defense cut and the 60 s social cut as segment lists.
- `PRIVACY_CHECK.md`: every frame checked for privacy, with PASS or the exact problem.

## 8. Rules
- Read-only: never modify the videos, WAVs, build scripts, raw footage or the repo. Do not run `montage_v2.py`.
- Do not upload any video, frame or photo anywhere (it contains people, even if blurred).
- Do not push to GitHub. Do not touch the running services, Docker, cameras, robots or the door.
- Label every claim: **watched** (you saw it at a timestamp), **read** (from a file), or **guess**.
- If you cannot open a file (size, codec), say so instead of guessing what is in it.
