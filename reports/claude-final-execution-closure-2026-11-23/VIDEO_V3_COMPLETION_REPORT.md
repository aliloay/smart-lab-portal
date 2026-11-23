# Video V3 completion report - 23 Nov 2026

The video was built by the separate session "Smart Lab showcase video V3 + defense/social cuts". The build is at `D:\SmartLabData\showcase_2026-11-22\build_v3\` (`montage_v3.py`, `timeline_v3_*.json`, `narration_v3.json`, `gen_narr_v3.py`, `narr_v3/`, `logs/`, `qa/`).

**This closure session independently:**
- fact-checked the narration;
- sent two corrections, both applied;
- ran its own export QA (below).

## Exports (`reports/final-smart-lab-closure-2026-11-18/`, final versions 23 Nov 06:50-06:52)
| File | Size | Video | Audio | Duration | Loudness (integrated / true peak) |
|---|---|---|---|---|---|
| `SMART_RESEARCH_LAB_FINAL_SHOWCASE_V3.mp4` (+ `.srt`) | 132.6 MB | H.264 1920×1080 30 fps | AAC 48 kHz stereo | 6:15.0 | −16.0 LUFS / −1.4 dBFS |
| `SMART_RESEARCH_LAB_DEFENSE_CUT_V3.mp4` (+ `.srt`) | 58.2 MB | H.264 1920×1080 30 fps | AAC 48 kHz stereo | 3:19.8 | −16.0 LUFS / −1.5 dBFS |
| `SMART_RESEARCH_LAB_SOCIAL_CUT_V3.mp4` (+ `.srt`) | 25.1 MB | H.264 1920×1080 30 fps | AAC 48 kHz stereo | 0:51.9 | −15.9 LUFS / −5.1 dBFS |
| `SMART_RESEARCH_LAB_FINAL_SHOWCASE_V3_720p_share.mp4` | 50.3 MB | H.264 1280×720 30 fps | AAC 48 kHz stereo | 6:15.0 | (same mix as the master) |

The V2 master (`SMART_RESEARCH_LAB_FINAL_SHOWCASE_V2.mp4`, 19 Nov) is untouched.

## Fact corrections made on 23 Nov (narration, captions and re-render)
| Segment | Was | Now | Evidence |
|---|---|---|---|
| `n8n3a` | "Twenty-four n8n workflows…" | "Twenty-six active n8n workflows…" | live n8n via the read-only MCP: 27 workflows, 26 active |
| `cam1` | "…never from a guess." | "…A match by clothing alone stays a marked guess." | fix V-F3 in `d023e98` |

Nothing in the video says the RFID relock fault is fixed. Door figures (card 5 ms, lock < 10 ms, QR about 160 ms) come from `MEASUREMENTS_2026-11-21.md` and are labelled "Measured 21 Nov 2026, home bench".

## QA run by this session
| Check | Method | Result |
|---|---|---|
| Format | `ffprobe` on all 4 files | pass (table above) |
| Black gaps | `blackdetect d=0.5 pix_th=0.10` on master, defense and social | none found |
| Silence | `silencedetect -50 dB, 2 s` | none found |
| Clipping | `ebur128 peak=true` | true peak ≤ −1.4 dBFS: no clipping |
| Captions | `.srt` grep for the corrected lines | both present in the master; social has "26 active n8n workflows" |
| Frames | contact sheets: master every 8 s (47 frames), camera segment every 2 s, intro every 1 s, social every 3 s | all frames show content. Two dark tiles were transitions (welcome animation start, a camera cross-fade); confirmed with the denser sheets |
| Privacy | the same sheets | faces blurred or pixelated in all camera footage; recognised names covered; password masked on sign-in ("demo copy, demo account"); tiles labelled "Recorded <date>", "Demo copy" or "Preview - simulation only" |
| Claims on screen | the same sheets | n8n slide: "24 workflow definitions" heading with the small print "27 definitions in the repo; 26 active … 00 error handler inactive": consistent with the narration |

**Not done:** a frame-by-frame watch of all 11,251 master frames. The checks above are automated plus sampled contact sheets (1 frame per 1-8 s). Status: **TESTED - PASSED (automated + sampled visual review)**.
