# Camera latency: what is measured, how, and the results so far

## Stages (tools/security_vision/latency.py, served at `/metrics`)

| Stage | Measured as |
|---|---|
| Capture | frames per second received from the camera stream, the gaps between them, time in `read()` (network + decode) |
| Analysis | the frame's age when analysis starts, detector ms, tracking + naming ms, box checks ms, the whole pass ms, frames skipped by the latest-frame policy |
| Render | pictures drawn per second, the frame's age when drawn, JPEG encode ms |
| Serve | the frame's age when sent (`X-Frame-Age-Ms`). The portal adds `X-Proxy-Ms` for its own step. |
| Not measurable in software | camera sensor → encoder → network (glass-to-laptop). Measure it with a millisecond stopwatch in view (docs/MONDAY_LAB_2026-10-12.md §4). |

**Latest-frame policy:** the reader thread keeps one frame only. Analysis and
drawing always take the newest frame; older ones are dropped and counted. No
queue can build up.

## Measured 2026-10-08 16:39, at home, without the camera (NOT the live lab)

- Source: a lab recording (`SECCAM_LAB01_2026-10-07_15-06-14.mp4`) read by the same capture code at about 13 fps.
- Laptop: 12 cores; YOLOX-S at 416 px on the CPU; `--det-fps 3`.
- Duration: 45 s; 144 analyses, 300 drawn pictures.

| Quantity | p50 | p95 | max |
|---|---|---|---|
| read() / decode | 7.1 ms | 13.4 ms | 32.7 ms |
| frame age when analysis starts | 43 ms | 76 ms | 142 ms |
| detector | 191 ms | 211 ms | 256 ms |
| tracking + naming | 0.1 ms | 100.3 ms | 226.7 ms |
| whole analysis pass | 194 ms | 411 ms | 743 ms |
| frame age when drawn | 42 ms | 77 ms | 149 ms |
| JPEG encode (plain + annotated) | 19.8 ms | 29.2 ms | 32.7 ms |
| frame age when served (20 requests) | 128 ms | - | 166 ms |

- Rates: input 12.8 fps (limited by the file), analysis 3.0/s (the configured
  cap), drawing 14.9/s.
- 500 frames were skipped by the latest-frame policy (expected: the camera
  sends more than 3 frames a second).

**Browser** (2026-10-08, admin, same laptop):
- page switches (`e2e/nav_timing.mjs`): median 80 ms over 36 switches, max 459 ms (the charts page);
- 3D robot pages until the twin is drawn: about 1.9 s (`e2e/command_center.mjs`).

**Still to measure in the lab (NOT MEASURED yet):**
- glass-to-laptop delay (stopwatch method);
- the real stream's frame rate and gaps;
- browser → portal → camera program round trip on the lab PCs.
