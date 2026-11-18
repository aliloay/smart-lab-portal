# Video source inventory (19 Nov 2026)

Every candidate clip and photo was opened and reviewed, with contact sheets made at fixed intervals in
`D:\SmartLabData\showcase_2026-11-19\contact\`. Originals were opened read-only and nothing was moved, re-encoded or overwritten.
The montage writes only to `D:\SmartLabData\showcase_2026-11-19\build\` and to this folder.

| # | Source | Length / size | What it shows | Quality | Privacy check | Used? |
|---|---|---|---|---|---|---|
| 1 | `D:\SmartLabData\lab_2026-11-18\video\v2\smart_lab_portal_tour_v2_2026-11-18.mp4` + `frames\` (9,452 timestamped JPEGs) + 19 narration WAVs | 230.5 s, 1600×900 | Narrated live portal tour at GIU on 18 Nov: welcome, sign-in, cameras (tiles + both enlarged), lab PCs, screen wall, screen share, message all, maintenance, robots, command center, bins, devices, access, AI assistant | Sharp. Some dark loading frames (security page start, black camera-enlarge start, "connecting…" tiles, a "Waiting for PC-08" screen, the AI page loading) | Login field shows the admin account name; the screen wall shows Windows user names under each tile; camera views show people; the "Who is in the lab" answer lists people | **Yes**, main backbone (loading frames, login and the people answer cut; heads and user names blurred) |
| 2 | `D:\SmartLabData\lab_2026-11-18\video\smart_lab_portal_tour_2026-11-18.mp4` (v1) | ~1:50, 1600×900 | Earlier silent tour, same pages | Superseded by v2 (no narration, fewer sections) | Same issues as v2 | No: v2 covers it better |
| 3 | `D:\SmartLabData\lab_2026-11-17\ar_test\AR_scan_test_2026-11-17.mov` | 125 s, 384×848 portrait, 60 fps | Phone AR: UR5e 52 %, UR5e marker → LIVE, FANUC 89 %, FANUC marker → LIVE, master door node close-up, door controller 93 %, consumables bin 80 %, "appearance only, not confirmed" | Good. A floor shot at ~60–70 s; motion blur at ~31 s | **Phone number** in a WhatsApp notification (~21 s) and a social notification (~31 s), both in the top status area; a person's back (~31 s); a **face** at ~110 s to the end | **Yes**: 9–18, 19.5–27.5, 41–55, 72–76, 80–90, 100–106.5 s; status and notification area cropped away (rows 0–116 px); ends before the face |
| 4 | `D:\SmartLabData\colab\robot_pack_tmp\Ur5e robot.mov` | 10.9 s, 576×1024 portrait | Real UR5e moving, with the portal digital twin following on the laptop | Best real-robot shot | No people | **Yes**, whole clip |
| 5 | `C:\Users\dell\OneDrive\Desktop\Bsc\Digital Twin_Ur5e .mp4` | 61.5 s, 1920×1020 | Screen recording of the twin page moving | Good, but the browser bar and bookmarks are visible | Bookmarks bar = personal browser content | No: clip 4 shows the same with the real robot |
| 6 | `C:\Users\dell\OneDrive\Desktop\Bsc\Camera_lab_testt.mp4` | 7 Oct | First annotated camera test | Older pipeline | Close-up **face** | No |
| 7 | `nourramy entery test.mp4` | Oct | Door entry test | n/a | A named third person's face | No |
| 8 | `C:\Users\dell\OneDrive\Desktop\Bsc\Recording 2026-10-19 144725.mp4` | Oct | Old security page | Older UI | Faces in tiles | No: v2 has the current UI |
| 9 | `ONECORE_LAUNCH_VIDEO\final_v3\ONECORE_V3_30S.mp4`, `FACILITY_INTELLIGENCE_47S.mp4`, `SmartLab_overview_47s_github.mp4` | 30–47 s | Earlier promo cuts ("Disconnected systems" intro) | Polished, but other branding and an older UI | Faces blurred | No: different name and look; this montage keeps one consistent style |
| 10 | Raw `SECCAM` recordings 17 Nov | ~12 min | Unannotated camera streams | Raw | Many faces | No |
| 11 | `D:\SmartLabData\lab_2026-11-18\photos_shutdown\pc_shutdown_1..5.jpg` | 2576×1450 | Lab PC row showing the message and the shutdown countdown on real PCs | Good | Small far-away people (1, 2) | **Yes**: 1 (heads blurred) and 3 (countdown close-up) |
| 12 | `D:\SmartLabData\lab_2026-11-17\node_photos\nodes_01..11.jpg` | 1450×2576 portrait | The 4 ESP32 nodes in their 3D-printed enclosures | 05–09 sharp | Legs and a hand in 01–04; people in the background of 10–11 | **Yes**: 06 and 10 (heads blurred) |
| 13 | `D:\SmartLabData\lab_2026-11-18\screen_wall_1/2.png` | screenshots | Screen wall | Same content as v2 | User names visible | No: v2 wall used with names blurred |
| 14 | `D:\SmartLabData\lab_2026-11-17\fanuc_photos\fanuc_01..15.jpg` | photos | FANUC cell | Good | n/a | No: the AR clip shows the FANUC live and recognised |

## Narration and sound
- v2 narration: Piper `en_US-lessac-medium` WAVs recorded on 18 Nov, reused unchanged for the v2 sections.
- New lines, generated locally with the same Piper voice (`tools/voice/models`, Python 3.12, offline) into
  `D:\SmartLabData\showcase_2026-11-19\narr\`: `photo_msg`, `ur5e`, `ar1`, `ar2`, `nodes`.
- Music and sound effects are original, synthesised in NumPy inside the build script: an A-minor / F / C / G pad, a soft
  arpeggio, bass and hats, whooshes at cuts and chimes at chapter cards. No downloaded or third-party audio was used.
