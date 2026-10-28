# Smart Lab - status report (2026-10-28, night)

Live portal: version **9ef06ec** (health OK). Nothing pushed to GitHub. Database backed up before every deploy.
Labels: **live** = deployed and checked on the running portal; **tested** = automated tests; **owner test** = still
needs the phone / the lab.

## 1. Backend speed and stability (live)
| | Before | After |
|---|---|---|
| Concurrent signed-in users, stable | 50 | **75** (two runs, 0-1 errors in ~1,850 requests) |
| Requests per second | ~31 | **47-57** |
| Database pool time-outs under load | many | **0** |
| 100 users | - | 2.3-2.7 s page p95 (CPU-bound, one process) |
Cause found with a CPU profile: worker threads (40) = database connections (40) - circular wait. Fix: 120 threads.
Full backend suite **713 passed**, 0 failed, 2 skipped. Frontend type check + build clean.

## 2. Portal speed (live, measured in real Chrome)
- Scrolling: frame p95 33 -> 16.8 ms; worst stall 233 -> 67 ms; no JavaScript freezes while scrolling.
- Sidebar pages: p95 to content 1.65 -> 0.25 s; worst 4.7 -> 0.5 s; worst control 5.2 -> 0.45 s (48 pages, 3 roles).
- Welcome page: frames > 50 ms 14 -> 10, worst 267 -> 183 ms (3D scenes kept once built).
- AI model down: correct "not running" message in 1-3 s (was 6.8 s "try a shorter question"); status 2.5 -> 0.01 s.

## 3. AI assistant (live)
- 52-question benchmark: **86.5 %** (unchanged), 34/52 answered instantly (median 0.03 s).
- Instant answers: who is where, empty labs, compare with last week/month, today's summary, low stock, recent activity,
  today's bookings, open issues (+ critical count), lab info, "how to improve / what is wrong with <device>".
- Books and cancels labs with a Confirm button (nothing changes without the tap). Proactive suggestions, answer
  feedback, citation dates, read-only MCP server (8/8).

## 4. Phone camera (live; owner test pending for the last fixes)
- Face naming worked in the owner's test; spoken answers work (voice kept warm).
- Fixed tonight: a person selected on the front camera no longer blocks the QR after switching cameras; the camera
  button says "Switch to front/back camera"; Tell me more + mic float on the picture.
- QR markers: 11 owner pictures with the real QR (incl. security camera 2); the reusable bin's sticker decodes
  (SLAB:D:REUSE_BIN_1); PDF download prints the pictures.

## 5. Recognising the reusable bin WITHOUT the QR (live, hint only)
- 27 owner photos as references (no people). Leave-one-out: 22/27 recognised, **0 wrong**.
- Runs by itself every 3 s while no QR is in view (the timer bug that stopped it is fixed); the message fades after
  5 s (it had stayed over the owner's face); a **dashed frame** is now drawn around the matched part.
- Owner test: 1 check, correct (81 matching points). Works close up; across the room it says "not recognised"
  (0 false bins on 4 non-bin pictures). A higher-detail setting was tried and **rejected** (3/4 false bins).
- A YOLO trained on the 27 close-ups was **not deployed**: it also "found" the bin in pictures with no bin (0.8-0.98) -
  no negative photos in training.

## 6. Visual AI plan (owner's revised plan - started)
- Written as the working spec: docs/VISUAL_AI_PLAN.md (12 frozen classes, box rules, data rules, comparison,
  deployment benchmarks, identity / speech / privacy rules, thesis table with measured numbers only).
- Tooling ready and smoke-tested end to end: tools/vision_train/prepare.py (video -> frames per session, session-based
  70/15/15 split, negatives kept) and compare.py (YOLO11n vs YOLO26n, same data and settings, per-class P/R/mAP50/
  mAP50-95, confusion matrix, false detections on negative images, CPU ms median/p95). YOLO26n available (8.4.191).
- **Blocked on data**: per class 100-300 images from separate sessions + 150+ lab photos/videos with none of the
  classes. No model will reach the portal before it passes the no-object test.

## 7. Owner actions
1. Phone (lab Wi-Fi, reload the page): bin without QR close up -> dashed frame + message within ~3 s; turn to your
   face -> message gone within ~5 s; switch cameras -> answers follow what is in view.
2. Collect the round-one photos/videos (section 6) - short slow videos per object and per room area, no people
   except consenting volunteers for "person".
3. At the lab: launch.bat with both cameras on -> 10-minute two-camera test and camera-service restart test.
4. Change the seed passwords; UR5e commissioning (read-only monitoring stays as is).
