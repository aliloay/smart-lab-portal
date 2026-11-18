# Video editing and clip selection log: SMART_RESEARCH_LAB_FINAL_SHOWCASE.mp4

- **Output:** 1920×1080, 30 fps, H.264 (CRF 19) + AAC 192 kb/s, about 3 min 10 s.
- **Subtitles:** `SMART_RESEARCH_LAB_FINAL_SHOWCASE.srt`. Captions are also burned into the picture.
- **Build script:** `montage.py` in the session scratchpad; a copy is in `D:\SmartLabData\showcase_2026-11-19\build\montage.py`.
  - It decodes the originals read-only and writes only to `D:\SmartLabData\showcase_2026-11-19\build\` and to this folder.
- **Timeline:** `D:\SmartLabData\showcase_2026-11-19\build\timeline.json` (segment start times in the film).
- **Style:**
  - one navy/cyan look;
  - 0.4 s crossfades;
  - a numbered chapter pill at each chapter (7 chapters);
  - a "Real lab · 18 Nov" badge on real footage;
  - a thin progress line along the bottom;
  - animated title and outro cards (letter-spacing settle, underline sweep, moving grid, glow ring).

## Running order and why each clip was chosen

| # | Segment | Source (time range) | Why this cut | Edits / privacy |
|---|---|---|---|---|
| 1 | Title card | generated | Names the project at once | Background = a lab photo at 1/10 resolution, heavily blurred (nobody recognisable) |
| 2 | Welcome page | v2 1.6–9.6 s | Best-looking first page, with narration | — |
| — | *(sign-in skipped)* | v2 10–15 s | — | **Cut:** the account name is typed in the email field |
| 3 | 01 · AI security cameras | v2 35.4–44.3 s | Both camera tiles live side by side | The loading frames before 35 s were skipped; heads blurred (YOLO person boxes → head pixelated) |
| 4 | Camera 1 | v2 36.6–44.3 s, zoomed into the camera-1 tile | The enlarged view in v2 was ~40 % black (picture placed low) | Own caption, because the burned-in caption at that moment belongs to the previous line; heads blurred on the zoomed crop |
| 5 | Camera 2 | v2 35.4–42.6 s, zoomed into the camera-2 tile | The enlarged camera-2 view was ~65 % black | Same as 4 |
| 6 | 02 · Lab computers | v2 67.4–74.6 s | PC cards with signed-in user and running program | — |
| 7 | Screen wall | v2 81.2–85.5 s (last frame held) | Starts once the tiles show real screens (79.8–81 s were "connecting…") | **Windows user names under every tile blurred** |
| — | *(single screen skipped)* | v2 85.6–93.9 s | — | **Cut:** "Waiting for PC-08…" dark screen |
| 8 | Screen share | v2 94–100 s | The share panel going live to one chosen PC | — |
| 9 | Message all | v2 105.8–112 s | The broadcast action | — |
| 10 | Real lab photos | `pc_shutdown_1.jpg`, `pc_shutdown_3.jpg` | Proof on real PCs: the notice/countdown on every screen at once | Ken Burns zoom; heads of the two people in the back row pixelated; new narration |
| 11 | Maintenance | v2 113.5–117.0 + 119.6–124.4 s | The OUT OF ORDER screen on a real PC | **Cut:** the dark loading gap 117–119.6 s |
| 12 | 03 · Robots & digital twins | v2 130.1–140.6 s | Twin page; honest "controllers off → offline" | — |
| 13 | Real UR5e + twin | `Ur5e robot.mov` 0–10.85 s | The only shot of the real robot moving with its twin following | Portrait on a blurred backdrop + side labels; new narration |
| 14 | 04 · Augmented reality | AR 9–18 + 19.5–27.5 s at 1.4× | UR5e recognised (52 %), then marker → LIVE | **Top 116 px cropped** (status bar + a WhatsApp notification showing a phone number at ~21 s); speed-up keeps the pace |
| 15 | AR: FANUC + nodes | AR 41–55, 72–76, 80–90, 100–106.5 s at 1.5× | FANUC 89 % + LIVE, master node close-up, door controller 93 %, consumables bin 80 %, "appearance only, not confirmed" | Same crop; **ends at 106.5 s, before a person's face appears (~110 s)**; skipped the floor shot (60–70 s) and the blurred person (~31 s) |
| 16 | 05 · Sensor nodes | `nodes_06.jpg`, `nodes_10.jpg` | The 4 enclosures, sharp | Ken Burns; legs/people in the background of photo 10 pixelated |
| 17 | 06 · Operations | v2 146.5–151.5 s | Command center wall view | — |
| 18 | Smart bins | v2 154.5–160.8 s | Consumables by weight / NFC | — |
| 19 | Devices | v2 164.0–171.6 s | Heartbeats; offline shown honestly | — |
| 20 | Access & audit | v2 174.0–179.6 s | Audit log (device events only, no people) | — |
| 21 | 07 · Local AI assistant | v2 187–193 + 196–202 + 208.5–214.6 s | Intro, "Which lab PCs are online?", "What is the state of the robots?" | **Cut:** "Who is in the lab right now?" (202–208 s), because its answer lists people by name and clothing |
| 22 | Outro card | generated | Closing line + v2 "end" narration | — |

**How faces are blurred in the camera segments (3–5):** the cameras are fixed. The person detector (YOLO26s) runs every 0.5 s over the whole segment, on 2×2 or 3×3 upscaled tiles with a low threshold (0.15).
Every person area found anywhere in the segment is pixelated in every frame.
This was added after the first 1080p check: a person seated behind a desk in camera 2 was missed by the single-frame detector, and her face was visible. The film was re-rendered with this method.

## Clips reviewed and rejected
See VIDEO_SOURCE_INVENTORY.md: v1 tour (superseded), twin screen recording (browser bookmarks visible), October camera and entry tests (faces), raw SECCAM recordings (faces), ONECORE/FACILITY promos (other branding), FANUC photos (the AR clip shows the FANUC better).

## Audio
- **Narration:**
  - 19 Nov Piper lines: photo_msg, ur5e, ar1, ar2, nodes;
  - 18 Nov v2 lines: welcome, cameras, cam1, cam2, pcs, wall, share, message, maint, robots, command, bins, devices, access, ai, end.
  - Same voice (en_US-lessac-medium).
- **Music:** original synthesis in NumPy:
  - A-minor / F / C / G pad at 92 BPM, soft eighth-note arpeggio, sub bass, quiet hats;
  - ducked by 62 % under the voice (0.25 s envelope); faded in and out.
- **Sound effects (synthesised):** a filtered-noise whoosh at every cut, a soft three-partial chime at the title and at each chapter.
- **Level:** soft tanh limiter; mono mix duplicated to stereo.

## Privacy checklist (checked on the preview frames)
- [x] No readable face: the people in the camera tiles and photos are pixelated, and the AR face is outside the cut.
- [x] No phone number: the AR notification area is cropped away.
- [x] No credentials: the sign-in is cut, and the password was never shown.
- [x] No Windows user names. **Corrected 19 Nov (second check):** v1 of the film blurred only the screen-wall labels; lab
  Windows account names were still readable at 48–54 s (exam-mode reports, "(user)" column), 54–60 s ("Signed in:" line
  on the PC cards) and 168–175 s (the "Which lab PCs are online?" answer). These regions are now blurred (film v2).
- [x] No "who is in the lab" answer with names and clothing. **Corrected 19 Nov:** the question was cut, but its answer
  stayed on screen above the robot answer at 175–180 s ("nour ramy ... at the UR5e", "Person 12 ... Hemaly's desk").
  That block is now blurred (film v2).
- [ ] Names drawn by the camera software on its own boxes (e.g. the owner's name, "Masters/Eng. Hemaly?") stay visible in the camera views, because they are the feature being shown.
  - Faces are blurred. If the owner prefers, the label boxes can be blurred too and the film re-rendered (one setting).

## Film v2 - 19 Nov second privacy pass (Claude, final-closure worktree)
- Found by frame-by-frame checking of the exported v1 (contact sheets every 3–12 s, full-resolution crops).
- Fix: ffmpeg box blur over four fixed screen regions in the exported film (no re-render of the montage, no GPU):
  `x895 y160 125×600` at 47.9–54.0 s, `x380 y695 1220×60` at 53.6–60.2 s, `x1040 y250 820×600` at 167.8–175.6 s,
  `x1040 y250 820×175` at 175.0–180.6 s. Audio copied unchanged, so subtitles and narration timing are unchanged.
- v1 kept unchanged: `D:\SmartLabData\showcase_2026-11-19\build\SHOWCASE_v1_before_name_blur_20261119.mp4`.
  v2 also at `D:\SmartLabData\showcase_2026-11-19\build\SHOWCASE_v2_names_blurred.mp4`.
- Checks on v2: 1920×1080 h264 + AAC, 186.7 s, full decode with no errors; no black frames ≥0.5 s, no freezes ≥2 s, no silences
  ≥2 s (checked on v1, same picture timing and the same audio); loudness −12.9 LUFS integrated, true peak −0.4 dBFS (no clipping);
  blurred regions checked on frames at 49, 52.5, 57, 170, 173 and 177 s.
- Still visible on purpose (owner decision, B-26): the names the camera software draws on its own boxes in the camera views.
