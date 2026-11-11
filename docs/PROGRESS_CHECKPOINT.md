# Progress checkpoint - Smart Lab master completion mission

## RESUME HERE - 2026-11-11 ~01:00 (closure mission in progress; NOTHING committed, NOTHING pushed)
Branch `qa/browser-and-camera-docs` on fdfd1fe, working tree dirty on purpose. Recovery: branch
`backup/before-closure-2026-11-11`, DB dump + diffs in `C:\Users\dell\smart-lab-backups\closure-2026-11-11\`.
Owner ran launch.bat at 21:05 on 10 Nov: the live backend image was built from the tree as it was THEN (door-route
scope, PC enrolment closed, scan rate limit are live; everything later is not).
Sources: 25 Argon files in Downloads + the two "Master Unified Engineering Execution Blueprint" files (identical,
SHA-256 6957fbfe...). The Argon patch was NOT applied; its findings were checked against the code one by one.

Done, tested offline (labels: tested offline unless said otherwise):
- SEC-01 door reports: `/api/access/validate-qr|validate-rfid|events|grant|deny` took any device key. Now a
  device's own key speaks only for itself and only door devices (master / camera / face server) may report
  (`access.py::_door_scope`); shared key unchanged. tests/test_device_keys.py (2 new).
- SEC-02 `/api/equipment/state`: an own-key device cannot report as another kind (PC key as ROBOT). test_pc_keys.py.
- SEC-03 `PC_ENROLL_OPEN` default false AND passed through docker-compose (before, .env could not close it);
  start-up warnings for open enrolment / open sign-up. OWNER: put `PC_ENROLL_OPEN=true` in .env while installing PCs.
- SEC-04 live-updates socket: one-time 30 s ticket (`POST /api/auth/ws-ticket`, core/ws_ticket.py, lib/live.tsx)
  instead of the sign-in token in the URL; nginx access log without query strings. test_portal.py (1 new).
- SEC-05 `/api/scan/appearance`: 6 frames / 2 s per user (core/throttle.py RateLimit; one backend process).
- CI failure on main (test_qr_pipeline, random token read at 2 of 7 distances): `issue_token()` now also checks the
  token through the door-camera model (`qr.door_reads_at_distance`, 6 of 7 distances); measured locally 392/400
  random tokens at 7/7, 7 at 6/7, 1 at 5/7 before the fix. 3 tests added.
- README: hardware caption row fixed (Master was missing), AR image added (a composed overlay, said so).
- Cameras: local commit 68b7157 (look handoff) brought into the tree; cross-camera elimination now needs a
  measured, agreeing look (no name from the head count alone); LOOK GUESS: a person named before comes back from the
  stored look as a marked guess "Name ? (look)" - also after a service restart (face names are restored as
  candidates), never confirmed without the face, never shared, never learnt from (vision.py, identity.py,
  crosscam.py, test_look_guess.py 9 tests). Camera suite 320 passed; scenario bench 14 scenarios, 0 false names.
  NOT lab-verified; camera services still run the OLD code until restarted (owner).
- Storage: Docker build cache + dangling images removed (about 21 GB inside Docker's disk file; the file itself
  only shrinks when Docker Desktop compacts / moves it).

UPDATE 2026-11-11 13:50: full report docs/reports/SMART_LAB_CLOSURE_AND_PERFORMANCE_REPORT_2026-11-11.md (read it
first). Added since: portal last-answer-first (api.peek), 2-3 s read caches + ClearOnWrite, AI streaming endpoints,
AR max_instances, tools/ops/watchdog.py (monitor only), camera --cv-threads 2 + idle render 1/s, knowledge warm-up
opt-in. Training data moved to D:\SmartLabData (junction). Backend 757 passed / 1 intermittent, targeted 121 passed,
camera 320 passed.

Open (in order, superseded by the report's section 7): full backend suite result; partial-body look (measurement on recordings running); portal
stale-while-revalidate cache; hot GET caching + housekeeping out of GETs + indexes (measure first); AI streaming
endpoint; AR box smoothing; watchdog (monitor-only); docs + final reports; owner decisions: push, deploy, camera
service restart, moving Docker's disk file to D:.

## RESUME HERE - 2026-11-03 00:10 (lab-wide 12-class detector LIVE, not committed)
- Colab lab_2026-11-02_1731 (Drive zip unpacked in tools/vision_train/results/lab_2026-11-02_1731/drive): best r1_n
  (YOLO11n) -> backend/data/models/lab_detector.onnx (byte-identical to r1_n/weights/best.onnx). Colab test split
  (conf 0.5, IoU>=0.5): bin 15/15, consumables 22/22, environment 34/35, master 26/26, switch 12/29, router 18/18,
  UR5e 7/7, UR5e pendant 2/2, FANUC 2/6, FANUC pendant 3/3, PC 3/4, door 4/4; mAP50 0.947, mAP50-95 0.839.
  Local check with the backend parser (class found, no IoU): no-object photos with a hit 1/200; CPU 2 threads median 77 ms.
- Live-verified after deploy: health 200, extras [lab_detector, all_detector], a UR5e test photo -> SLAB:D:UR5E_01 0.896.
- Code: detect_all skips the one-class bin model when the lab model answers the bin, keeps one hit per code;
  /scan/appearance returns `detections` (all hits); Scan.tsx draws every detection with label + %.
  Tests: test_bin_detector 14 passed; full backend 730 passed, 2 skipped; tsc 0 errors.
- launch.bat: 13 helper services start hidden via scripts/bg.ps1 (logs/<service>.log); backup backups/launch.bat.2026-11-02.bak.
  Helper tested; a full launch.bat run is NOT yet tested.
- Open: r1_s has switch 25/29 (later switch upgrade); one box per class (two PCs = one box); responsive/perf audit
  needs E2E_ADMIN_PW / E2E_PW; Gemini review request 2026-11-02-225500 pending.

## RESUME HERE - 2026-10-30 ~00:15 (bin round 5 scored - round 4 stays; switch round 1 training)
- Bin round 5 (round-4 weights + 33 owner-video frames, 30 epochs, data/bin_r5): scored with eval_bin.py on the same
  15 unseen bins + 429 no-bin pictures. conf 0.3-0.4: 15/15 found but 2/429 wrongly called a bin (top no-bin 0.58);
  deployed round 4: 14/15, 0/429 (top no-bin 0.19) and still 14/15 at 0.6 where round 5 falls to 9/15. Round 5 is NOT
  better - round 4 stays deployed (backend/data/models/bin_detector.onnx, conf 0.4). Log: data/eval_r4_vs_r5.log.
- Switch round 1 (data/switch_r1: 150 boxes + 657 no-switch frames in train, 16 val, 29 test; YOLO11n 40 epochs, CPU):
  RUNNING since 23:29 (epoch 8/40 at 00:05, ~4:40/epoch, ETA ~02:45). Windows Update is paused until 2026-11-05, so no
  reboot should kill it. Mid-run checkpoint (epoch 7) through the new tools/vision_train/eval_switch.py (29 held-out
  switch photos + 461 no-switch pictures): 7/29 found, 20/461 false at 0.3 - not usable yet; the round may need more
  boxed switch photos (only 150 positives).
- finish_switch.cmd (detached) waits for sw_done.txt, then scores the final weights with eval_switch.py and exports
  best.onnx: data/switch_r1/switch_eval.log, marker switch_eval_done.txt. Nothing is deployed from it.
- Router drop (Drive, 2026-10-30 00:20): SmartLab_router.zip 211 MB = 113 iPhone HEIC + 1 MOV, a white Vodafone home
  router on a table / carpet / floor. The switch zip in the folder is the one already used; the bin photos are the same
  615 MB zip already used - no new bin images. New tools: prepare_photos.py (HEIC/EXIF-safe + 2 fps video frames ->
  data/router_set, 211 images, 98 of them video frames) and make_object_round.py (YOLO-World boxes + shooting-order
  split + negatives + contact sheets). YOLO-World found the router in 121 of 211 at conf 0.08/960; the misses are
  edge-on, tiny/far and blurred frames. conf 0.05/1280 found 120 with visibly oversized boxes and 0.03/1280 146 with
  sloppy boxes, so 0.08/960 was kept. data/router_r1: 91 boxed + 237 lab no-object frames in train, 12 val, 18 test;
  the held-out no-object sets (lab_neg_test 221, coco_val/negtest 200) were kept OUT of training.
- (DROPPED 00:50 - superseded by the ALL-IN-ONE round below; the script was removed, data/router_r1 is a source of
  data/all_r1) router-only round: run_router.cmd waited for switch_eval_done.txt, trained YOLO11n 40 epochs (rt11) on
  data/router_r1, scored it with eval_object.py and exported best.onnx.
- ALL-IN-ONE round (owner, 2026-10-30 00:45: "train all ... so that it detects all at any time, anywhereee"): ONE
  3-class detector - reusable_bin / network_switch / network_router - from build_all.py -> data/all_r1. Train 995
  images (390 boxes + 607 no-object frames), val 113 (33 + 80), test 483 (62 boxes + 421 held-out no-object photos;
  per class 15 bin / 29 switch / 18 router). Sources bin_r5 + switch_r1 + router_r1; a photo that appears in two sources
  keeps both boxes (matched by file hash). Leak check: 0 overlap between train no-object photos and the held-out test
  ones. This replaces the per-object models: switch/router confusion cannot happen inside one model.
- run_all.cmd (detached, waits for switch_eval_done.txt = one CPU job at a time) trains YOLO11n (all11) then YOLO26n
  (all26), 30 epochs each, then eval_all.py per class + ONNX export: data/all_r1/all11{,_eval}.log, all26{,_eval}.log,
  markers all11_done.txt / all26_done.txt. eval_all.py re-ran the deployed bin round-5 weights on this test split:
  15/15 bins, 1/421 false at 0.3-0.4 - same as eval_bin.py, so the combined test set is comparable.
- The router-only round (run_router.cmd) was dropped when the all-in-one round replaced it; data/router_r1 is now a
  source of data/all_r1.
- Bin drop re-check (2026-10-30 01:30, Drive link shared publicly): Resuables_Bin.zip (626 MB) is a RE-UPLOAD - 117 of
  its 119 files are byte-identical to the zip used in rounds 1-5; only ReusableBin_Video.MOV (already mined for round 5)
  and the report PDF are new. It contains NO new bin photos. The one thing never used before is IMG_6882.MOV inside it:
  37 s, 2160x3840, 2158 frames - the real LAB bin station (grey bin with the 3D-printed lid, the black control box, the
  cable nest, the phone showing the portal, the printed markers), a scene the models have never seen. Mined with
  prepare_photos.py (74 frames at 2 fps -> data/bin_v2_set), auto-boxed with make_object_round.py -> data/bin_v2: 59 of
  74 frames got a box. Those boxes are inconsistent (sometimes the control box, sometimes the bin), so data/bin_v2 is a
  TRAIN-ONLY source of data/all_r1 (build_all.py 'forced split'): bin train boxes 149 -> 208, test unchanged at 15/29/18
  so the deployed round-4/5 comparison stays comparable. The 15 undetected frames were left out (they do contain the bin - as
  negatives they would teach the opposite). NEXT quality step for the bin: hand-box this lab video (station = bin +
  control box, as make_dataset.py does) so the lab scene can also appear in the scored test split.
- Lab frames as NEGATIVES (2026-10-30 02:00): 202 frames pulled with ffmpeg keyframe seeks (one per 45 s) from the four
  long Oct-12 camera recordings in tools/security_vision/recordings -> data/lab3_raw (own lab view: UR5e cell, FANUC,
  PCs, staff). The auto-labels there were JUNK and were deleted: YOLO-World drew "reusable bin" (113 frames) and
  "router" (63) boxes on the GREEN BLOCKS in the UR5e cell, and found 0 switches (the switch is out of that view). They
  are used as no-object pictures only (build_all.py), train negatives 607 -> 809.
  data/all_r1 FINAL for this round: train 1256 (390 boxes: 208 bin / 150 switch / 91 router + 809 no-object frames),
  val 113, test 483 (15 bin / 29 switch / 18 router + 421 held-out no-object photos).
- PORTAL, multi-class support (2026-10-30 02:10): app/services/bin_detector.py gained detect_all / _infer_multi /
  _parse_multi (rows = 4 + highest listed class index + 1, so a spec exposing classes 1-2 of a 3-class file still reads
  the file's real 7 rows) and data/models/detectors.json lists all_detector.onnx with ONLY network_switch (class 1) and
  network_router (class 2) - the bin stays on the deployed round-4 model. tests/test_bin_detector.py 8 passed
  (run with --noconftest; the full suite needs the Docker backend). The row-count guard was checked against an 80-class
  export (84 rows): it reports nothing instead of misreading - the real 7-row check happens on the all11 export.
  DEPLOY when all11 wins: copy data/all_r1/runs/detect/runs/all11/weights/best.onnx -> backend/data/models/
  all_detector.onnx, then docker compose build backend + up -d --no-deps backend; test PUT a switch/router photo through
  POST /api/scan/appearance (phone: Scan the lab).
- Earlier Colab switch trial (data/colab_switch/network_switch_2026-10-29_1845) was unusable: 220 photos but only 5
  boxed, 0 test objects, 176/200 no-switch photos scored >= 0.3. The notebook needs boxed labels in the zip.

## RESUME HERE - 2026-10-29 ~17:10 (round 4 done - best model deployed)
- Six models compared (eval_bin.py, 15 unseen bins + 429 no-bin): WINNER round-4 YOLO11n (+237 lab-camera negatives):
  14/15 found, 0/429 false at 0.3-0.6 (top no-bin 0.19). Deployed at conf 0.4 (commit 7fe4e9d); live container
  14/15, 0/44, 86 ms. Round-4 YOLO26n early-stopped (1-8/15) - rejected. Report PDF:
  docs/reports/SmartLab_Project_Report_2026-10-29.pdf (untracked). Windows Update paused until 2026-11-05.
- NEXT: owner phone test; outdoor bin photos; round-one lab photo sessions (Colab notebook ready).

## RESUME HERE - 2026-10-29 ~14:30 (bin detector live, round 4 training)
- Windows Update restarted the laptop at 08:37 and 13:54 (event 1074) - training died, Docker + lab services were down
  until 14:15; restarted with launch.bat (face 5000, cameras 5100/5101, voice 5320, knowledge 5199, Ollama).
- LIVE: reusable-bin detector behind /scan/appearance (only when the photo matcher says UNKNOWN):
  backend/data/models/bin_detector.onnx = round-3 YOLO26n, ONNX Runtime CPU 2 threads, conf 0.6. Unseen scenes 14/15,
  no-bin 5/429 (lab frames 0/221, COCO 5/200, patches 0/8); live container 14/15, 130 ms warm. Commits a962057, 7075d8e.
- Matcher 421 -> 333 ms (4 cores), warm-up at startup; phone-local YOLO26s in ONNX Runtime Web rejected (2.7-13.4 s/frame
  simulated vs ~37 ms server).
- Data (git-ignored): tools/vision_train/data - owner_set (113 photos), bin_r2/r3/r4, coco_val/negtest, lab_neg(_test).
- RUNNING: tools/vision_train/run_r4.cmd (detached): YOLO11n resume -> YOLO26n, writes data/bin_r4/r4_done.txt.
  NEXT: eval_bin.py + eval_deployed.py on all 6 (r2/r3/r4 x 11n/26n), deploy the best, retest live.
- Weak spot: only indoor home photos - outdoor (street, car, roof, pool) untested; owner to shoot ~30-40 outdoor.
- Owner photo list for round one (13 + controllers, network devices, optional PLC); Colab notebook ready
  (tools/vision_train/colab_train_bin.ipynb). n8n: cloud instance gone, local MCP needs owner token.

## RESUME HERE - 2026-10-27 ~20:00 (agent upgrades + speed + owner's QR pictures)
Full write-up: docs/AGENT_SPEED_REPORT_2026-10-27.md. Model kept qwen2.5:1.5b (e2e 86.5 %, unchanged after the
upgrade: 13/13, 6/6, 10/10); 15 unused models removed. New: instant compare / daily / low stock / recent activity /
today's bookings / who is where; phone "what is wrong?" verdict; proactive suggestions (/api/insights/proactive);
read-only tool gateway (/api/ai/tools) + MCP server (tools/mcp_server, official SDK in .venv, e2e 8/8); citation dates
+ copy de-dup; answer feedback. Scroll: frame p95 33 -> 16.8 ms (no backdrop blur, fixed background layer, charts built
on idle). Markers: owner's 10 pictures + real QR, jsQR 80/80. NEXT: owner real-phone test (markers, face, iPhone voice),
both-camera sustained run, time-slider UI, offline test.

## RESUME HERE - 2026-10-27 ~14:10 (live camera + markers deployed)
Deployed, live (health 200, version bc843aa): commits 3634647, 6c6dc25, a70512f, b929c62, 1848fe3, bc843aa.
- Live Smart Lab camera (/scan): pinned live chips per marker/person, tap to select, live panel (UR5e six joint bars +
  velocity/TCP/modes LIVE/STALE/OFFLINE, bins, reusables, environment, door, PC); person tracker (names only from a
  track's own face crop, never transferred: e2e/tracker_check.mjs 8/8); /scan/ask target-aware answers (voice +
  typed; backend tests/test_live_target.py); equipment boxes from the camera service /detect (code changed in
  tools/security_vision - NEEDS a camera-service restart to take effect). e2e/live_camera.mjs PASS (fake devices).
- Voice STT tiny.en (tools/voice/voice.env + default): same transcripts on 5 recorded questions, RTF 0.51 -> 0.23;
  tell-me-more stop->answer 0.8 s (fake mic, warm).
- Markers: asset-shaped QR (backend/app/services/marker_shapes.py, fallback plain QR); OpenCV 220/220, jsQR 218/220
  (frontend/e2e/qr_decode_jsqr.mjs over scratch renders). Print = the sheet itself (CSP blocks in-page PDF viewer).
- Floor plan: owner numbering, TA's desk PC-16, UR5e middle, table from the left wall; Back-to-portal + Esc on /wall
  and /monitor.
NEXT: (1) start lab services (launch.bat) after the laptop restart; (2) AI model sweep / router bench (P1);
(3) offline test checklist; (4) remaining backlog. Owner: real-phone tests, camera-service restart, passwords.

## RESUME HERE - 2026-10-27 ~02:00 (continuation mission, in progress)
Done this session (UNCOMMITTED until the full backend suite passes):
- Launcher: one process/port snapshot instead of 8x `tasklist /v` (10-60 s each); rebuild only when code changed
  (`.last_build_fingerprint`, `launch.bat rebuild` forces); helpers at below-normal priority; fixed PC-agent/UR-agent
  window check clash; voice / OPC UA / UR agent started. Dry run OK. (A dry run wrote a false fingerprint - deleted.)
- smartlab.local: announcer (tools/mdns/announce.py) was not running after the reboot - started; resolves + HTTPS 200.
- P0 photos: firmware/tools/ali.jpg.jpg + ali2.jpg git-ignored (portrait photo), kept on disk.
- P0 passwords: seed.py uses SEED_*_PASSWORD or random (never printed); README / DEMO.md / How_To_Run_System.md no
  longer list passwords; backend/set_password.py (hidden prompt, policy, audit) + tests/test_set_password.py (2 pass).
  LIVE accounts still on the published passwords - OWNER: change them (Users & roles).
- Deploy: tools/deploy/deploy_now.ps1 (hidden password prompt -> deploy.py --full-tests). OWNER runs it. A token-mint
  shortcut was refused by the permission system (credential access) and removed.
- IoT Dashboard floor plan: camera 2 drawn diagonally opposite camera 1; per-camera people counts (never summed);
  PC state from either camera (LabFloor.tsx, CommandCenter.tsx).
- Screen share "Waiting for the first frame": frame loop no longer blocks on video.play(); hint when the shared
  window gives no picture (screenShare.ts, ScreenShare.tsx).
- Scan + voice: mic on the Scan page; the asset card in view travels as context (Scan.tsx ScanVoice, cardContext);
  e2e/scan_voice.mjs written - NOT yet passed (copy backend slow during the suite).
- Robot twins: 3D starts by itself after the page settles (UR5e 0.9 s, FANUC 2.2 s) or on click / slider; the still
  picture stays on top until the meshes are drawn (RobotTwin onReady) - no blank flash.
- AI (from 10-26/27, uncommitted): keyword tool router, bounded answers, guide only for how-to, time line + volatile
  snapshot lines last (prompt cache), 4K ctx, AI_LOCAL_ONLY, Whisper local_files_only.
NEXT: full backend suite result -> commit (review files) -> e2e scan_voice + robots smoothness -> owner deploy ->
model sweep (clean CPU, one job at a time) -> docs/LOCAL_AI_BENCHMARK -> remaining backlog.

> 2026-10-27 ~01:00 status: docs/SMART_LAB_COMPLETE_STATUS_REPORT_2026-10-27.md (report only). Live still c74ee3b; HEAD cf81823 + uncommitted AI router / local-only / prompt-cache work; local model sweep in progress; offline test not done.

## Checkpoint 2026-10-26 evening - FINAL AUDIT (docs/FINAL_IMPLEMENTATION_AUDIT_2026-10-26.md) - committed, NOT pushed, NOT deployed
Verdict: READY WITH DOCUMENTED LIMITATIONS. Owner actions first: (1) change the admin + staff passwords - the live portal
still accepts the ones printed in the README (read-only check; the briefing now flags it); (2) deploy (live = c74ee3b of
10-21; needs SMARTLAB_EMAIL/PASSWORD for the smoke tests; add VOICE_KEY + UR_AGENT_KEY to .env); (3) restart both camera
services in the lab; (4) UR5e commissioning + stop-relay bench test (docs/ROBOT_CONTROL.md, firmware/SmartLab_Robot_Stop).
Commits today after 3a68d82: b2d6ae5 (UR5e auto-Home + stop relay), 2a0b760 (voice), a1470ed (booking race fix, /equipment,
sign-in burst, hidden tabs, Excel, health score, headcount, AAS), 53a35d0 (Evaluation tab, default-password warning).

## Checkpoint 2026-10-26 (home, cameras + robots OFFLINE - recordings / mocks only) - committed, NOT pushed, NOT deployed
| Done | Evidence |
|---|---|
| Camera detector + tracker chosen on OUR footage: YOLO26s 544x960 + low-confidence stage 0.15 + new-track 0.60 + part boxes + zoom model 416 | docs/CV_BENCHMARK_2026-10-26.md: 363 reviewed people (recall 0.898 -> 0.923), 3 reviewed clips (HOTA 0.732 -> 0.779, IDF1 0.831 -> 0.874, ID switches 14 -> 12, missed -24 %), two cameras 7.8/8.9 -> 9.4/9.9 analyses/s, pass p95 134-156 -> 115-129 ms; 30 detector configs + 9 published trackers compared |
| Camera tests | tools/security_vision 288 passed (+7 test_tracking_2026_10_26.py) |
| UR5e Home + software STOP with the robot in LOCAL mode (design per UR docs: Dashboard load/play/stop are Remote-only; Local = pendant-started External Control program) | tools/ur5e_control (agent, 14 tests), backend ur_agent.py + test_robot_control_local.py (6); twin shows Local/Remote + who drives the arm; DRY RUN, nothing ever sent; docs/ROBOT_CONTROL.md 2026-10-26 |
| Screen share: Stop pressed in another tab releases the presenting tab's capture via the share_state push (uploads held: before = never released, after 368-853 ms, 3/3) | frontend/e2e/share_stop_release.mjs |
| /reliability/briefing 433 -> 54 ms (alembic head read once per process); page-load burst 770 -> 510 ms | isolated copy backend (smartlab_perf_test) |
| Backend 590 passed; frontend tsc + build OK | this session |

**Open (owner / lab):** live camera check of the new defaults (restart both camera services); UR5e commissioning steps 1-6
(docs/ROBOT_CONTROL.md, needs the lab + operator + host IP .200 in the External Control program); AI on the CPU pushes the
system to 98 % and slows both cameras to ~7/s (next: AI threads / scheduling).

### Persistent checklist (missions of 2026-10-26; update as items close)
- [x] CV benchmark + tracking + two-camera speed (above)   - [x] UR5e Local-mode Home/Stop software (dry run)
- [x] Phone camera "Scan the lab" (docs/SCAN_THE_LAB.md; fake-camera browser tests pass; real phone + printed markers still to verify)
- [x] Voice in the assistant (tools/voice/README.md; 2a0b760)   - [x] UR5e automatic Home + hardware stop relay (b2d6ae5, dry run / not wired)
- [~] A security: HTTPS/secrets PASS; seed passwords still live (owner); recording retention (owner)   - [x] B Evaluation tab   - [~] C IoT (quality flags exist; no flash buffering)
- [x] D performance (hidden-tab polling, /equipment, sign-in burst, booking race lock, 1 worker/no Redis decided, nginx verified)
- [ ] E identity fusion study   - [~] F AI agents (knowledge bench 10/12; Qwen vs Gemma not run)   - [x] G Excel (stdlib) + Print/PDF
- [x] H Lab Health Score (+ existing anomalies/inventory)   - [~] I robot replay only   - [~] J AAS export (no OPC UA)   - [~] headcount done; triage/.pkpass not built
- [ ] FANUC Home/Stop (after UR5e works physically)   - [ ] K hardware pilots: LAST, proposals only (owner: no new hardware now)

## Checkpoint 2026-10-21 ~15:40 (lab) - cameras re-boxed by real PC numbers - committed, NOT pushed
| Done | Evidence |
|---|---|
| PTZ power-on guard: no view anchor / box re-alignment for 180 s after a stream (re)connects (camera 2's boxes had been moved to the post-sweep view) | test_view_startup.py; both services restarted 14:27, boxes in place on live frames (bf0264e) |
| Owner re-drew all boxes by the real lab numbers: camera 1 PC-01,02,04-15 + UR5e, Fanuc, door, Security_Camera_2; camera 2 PC-05..13, PC-16 + UR5e, Fanuc, Security_Camera_1. Robot boxes no motion alert. PC-03 not boxed yet | DB zones 5 / 12; smallest box 0.5 % (2a7e934, deployed) |
| Two-camera PC links (same number on both cameras): PC-05..PC-13 (9 PCs), owner-verified | tools/security_vision/anchors/desk_map.json (local, git-ignored); deskmap.validate = no problems. The same-desk identity rule that would use it is still OFF |
| Snapshots for the thesis: both live views, plain views, side by side, one crop per box, contact sheets, boxes.json, portal screenshots | tools/security_vision/anchors/box_snapshots/2026-10-21_1539/ (local only: shows people - blur faces before any figure is published) |
| Earlier 10 min activity correlation for the PC links rejected (busy room: common motion matched nearly every pair) | not used |

## Checkpoint 2026-10-21 ~18:45 (lab, closing) - committed, NOT pushed; cameras/face server were closed at the end
| Done | Evidence |
|---|---|
| Same-desk pairing (desk_map.json, PC-05..13) in crosscam; desk guesses "Eng. Hemaly? (desk)" (PC-04/PC-01) and "TA? (desk)" (PC-16) shown only | test_crosscam_desk.py, test_desk_hints.py; live: Hemaly's guess at PC-04 |
| Look leads close pairings: veto > 0.65, clear match <= 0.40 with 0.20 margin pairs up to 2 m and may cross while touching (measured from 396 obs: same 0.31, different 0.79); tie-break | test_crosscam_look_leads.py (replays 18:37: floor put Nour where Ali sat); 275 camera tests (02cb119) - NOT yet seen live (cameras closed right after) |
| Door TEST watcher needs agreement (same name 2x / 5 s, no other in 10 s): one face read USER5, USER1, USER3 in 25 s and named Ali "USER3 by door" | test_door_test_entry.py (72bedff); wrong USER3/USER5 test entries closed with TEST exits |
| Analysis 10/s (live 9.1 / 8.6, GTX 70-76 %); live view ~15 pictures/s; boxes < 8 px learn; PC in use held only by a seated person; Robots & PCs smooth (18k -> 5.5k elements) | d6cf0ef, 5d76dfa, b3dc744, f2b2884 |
| Floor maps refit with 3 clean two-camera pairs (UR5e side); backups *_floor.20261021-1823.bak.json | gaps 0.37-0.52 -> 0.27-0.44 m; tape marks <= 0.11 m |

Open (next lab visit):
* Seat areas per PC: sitting at PC-07 shows PC-08 (and PC-11 -> PC-12) on BOTH cameras - the body covers the next monitor box. Owner sits at each PC 5 s; record seat boxes; use them for in-use + desk pairing.
* Look re-acquire after a track break while moving (name kept only on hand-back at the same place within 20 s).
* UR5e "Moving - by teach pendant" while another person moves it (owner: the pendant moves one joint at a time, or all only going home) - check tools/robot_monitor/control_source.py.
* Verify the look-led pairing live (Ali seated next to Nour at the UR5e table).
* UR5e area floor still ~0.3-0.5 m apart between cameras; far corner beyond calibration (tile-counted marks there).
* DONE 2026-10-22 (42c198f, deployed; camera + robot monitor code active at their next start):
  - Robots & PCs, both robots live (simulated at real rates, visible Chrome): 51/48 fps, 11+3 janky, 2 freezes
    (worst 350 ms) -> 60/60 fps, 0 janky, 0 freezes (static 3D parts memoized).
  - PC in use: recorded SEATS (py tools/security_vision/seat_capture.py PC-07 while sitting there; no restart)
    decide over monitor boxes; PC power from the LAN (config "pc_on") prefers the PC that is on. Lab PCs on the
    university network show power unknown - the seats are the fix for them. PC tiles: "Seated · PC off" / "Off".
  - UR5e Local mode: External Control program = computer, other program = started on the pendant, one joint =
    jogging, several joints = Move/Home or another way (tests 42).
  - NOT built: name back "by look anywhere" - conflicts with the owner's 2026-10-12 rule (a lost name comes back
    only to a person whose own face matched it, never by clothes); needs the owner's explicit decision.
  - Next lab visit: run seat_capture.py at each PC both cameras see; then the walk-in test; check UR5e labels.
* (was IN PROGRESS) Robots & PCs with BOTH robots live reproduced offline (e2e/robots_pcs_smooth.mjs
  LIVE_ROBOT=2 HEADFUL=1): 2 freezes > 200 ms, worst 350 ms, 11 janky frames / 12 s; profile = R3F re-diffing the whole
  scene on every joint update. RobotTwin.tsx now memoizes the static parts (frame, FANUC cell, obstacles, lights,
  controls) - tsc OK; NEXT: re-measure with the same script, then deploy. Also planned: PC status = LAN on/off + camera
  (a PC that is off cannot be in use; prefer the PC that is on when a body covers two monitor boxes); UR5e Local-mode
  label (a running program / several joints at once is not "teach pendant jogging").

## Checkpoint 2026-10-21 ~04:45 (home, Smart_Lab router on LAN3 with the owner's old HP laptop = PC-01) - committed, NOT pushed, deployed
| Done | Evidence |
|---|---|
| Lab PCs on/off over the LAN by MAC with nothing installed (tools/lan_presence: ping from 192.168.1.200 + Windows neighbour table; MACs learned from the agents) | live: PC-01 ON via ping (4 ms); cable/shutdown transitions in presence_log.jsonl and the audit log |
| PC agent on Windows 7 (Python 3.8 fix, offline USB installer, invisible via scheduled task every minute + single instance, kill alert, portal opens at sign-in, MAC report) | PC-01 reports agent 0.9 live; agent tests 14 |
| Admin who signs in = master (agent HMAC proof on 127.0.0.1:47123; Docker hides client IPs) | live: MASTER_CLAIMED pc=PC_ADMIN_LAPTOP 00:22:34Z; tests/test_master_signin.py |
| Screen sharing: Stop ends it from any tab; 410 "ended" + share_state push; presenter-gone auto end (90 s); viewer cache bypass | live E2E 5 rounds: stop -> viewer cleared 52-144 ms; under load 24-337 ms, late frames 409 |
| Live pushes pc_state / share_state (WS) | ws_clients: +0.2 msg/s per client |
| Students share their PC screen after admin approval (everyone / staff only), Exam lockdown (kiosk Chrome --app, closes other windows, reports), Maintenance full-screen cover, coloured notice cards, 60 s restart/shut-down countdown + /f | backend tests/test_share_requests_exam.py; agent test_exam_lockdown.py; cards and cover rendered (screenshots) |
| Robots & PCs: picture-first robot views (no WebGL context until live / pointed at), wheel scrolls the page (Ctrl+wheel zooms) | robots shown 2.9-3.3 s -> 0.53-0.60 s; longest task 0.88-1.6 s -> 0.11-0.16 s; wheel over twin scrolled 720 px |
| Old Chrome support (structuredClone fallback) | e2e/old_browser_compat.test.mjs |
| Load (isolated, simulated, docs/perf/runs_2026-10-21): robots + 2 cameras + env + 11 PCs + share + 11 viewers + WS | 0 errors; /monitor p95 364 ms (10-14: 0.25-1.0 s); cameras 6.6-6.8 fps, pass p95 120-133 ms; RSS flat |
| Door box: 0.3 mm fit rule (Neptune 4), STL zip, renders | commit 66fa726 |
| Tests: backend 581 passed; agent 14; lan_presence 5; robot_monitor 41; knowledge 49; frontend tsc + build + node tests | this session |

**Physical / pending:** on PC-01 install the 04:26 update and verify: invisible start, portal at sign-in, Restart countdown,
Maintenance cover, Exam lockdown closing real programs, student share; PC-01 clock is 2010 (CMOS battery);
print the FitCoupon before the box; camera walk tests; usernames.

## Checkpoint 2026-10-20 ~21:30 (home, cameras OFFLINE) - committed, NOT pushed, nothing deployed
| Done | Evidence |
|---|---|
| Role matrix (`e2e/role_matrix_perf.mjs`, 1 trial, live portal): admin 19 / staff 16 / student 8 sidebar routes, 0 refused, 0 console errors; cold content 0.29-0.90 s, warm 52-267 ms; search 1.2-6.2 ms, right first hit for lab1/robot/fanuk/door/oscilloscope | scratchpad role_matrix.json; only failures = camera frame.jpg 503 (cameras off) |
| RBAC spot check: student GET /api/users -> 403 | live |
| Door box deepened 90 -> 110 mm (owner: more room for wires): wire gap 25 -> 45 mm; front-panel envelopes z +20; washers + 5 mm spacers added to BOM | interference.txt NO INTERFERENCES (17 bodies); check_stl 4/4 OK; body 170 x 210 x 110, 370 cm3 |
| Release ZIP refreshed (old kept as *_pre-snapfix.zip); STL-only ZIP DoorEnclosure_PrintReady_STL_2026-10-20.zip | tools/cad/door_enclosure/ |
| Tests: backend 565 passed; camera 253; robot_monitor 41; knowledge 49; tsc + vite build; search_rank 9/9 | this session |

**Blocked / physical:** print + measure the FitCoupon (inserts 3.9/4.0/4.2, pilots, LED, buzzer, glands, FP opening,
NFC read through 1.5 skin); buy 1 x M16x1.5 + 3 x PG7 glands; drawings PDF still from 90 mm (HTML regenerated);
camera walk tests; assign usernames.

## Checkpoint 2026-10-20 ~16:30 (laptop at home, cameras OFFLINE - no stream) - committed, NOT pushed
Live deploy unchanged since `f5eaeff-dirty-20261020021246` (FANUC front facing, UR5e home start, Face-ID photo
self-service, GPU gate code inactive by default). Nothing deployed this round (CAD + docs only).

| Done | Evidence |
|---|---|
| Door enclosure fit-test release: researched dimensions (4 researchers; report `reports/Door enclosure component dimensions.md`), new panel mounts (TFT on its 4 holes, PN532 islands + 1.5 skin, R307 cradle + tie, buzzer cradle), fit coupon 180 x 150, centred text, STEP export, 14 component envelopes | `tools/cad/door_enclosure/out/interference.txt` = NO INTERFERENCES (17 bodies); `check_stl.py`: 4/4 closed + manifold; drawings PDF; `docs/hardware/DOOR_ENCLOSURE.md` |
| Speaker / PAM8403 removed from the wiring record (owner) | `docs/hardware/DOOR_MASTER_WIRING.md` |
| Tests: backend 554 passed; camera 253; robot_monitor 41; knowledge 49; pc_agent 5; tsc + vite build | this session |

**Blocked / owner:** print the FitCoupon first and check the parts (DOOR_ENCLOSURE.md section 7); the 3-run
sidebar benchmark needs E2E_PASSWORD in the environment (not passed on the command line); camera walk test at
the lab (TWO_CAMERAS.md steps), PC letter -> number map, Hemaly at the door; ESPs are unpowered on purpose.


## Checkpoint 2026-10-20 ~01:00 (laptop at home, OFF the lab network) - nothing committed, nothing pushed
Deployed: `f5eaeff-dirty-20261020004125` (/api/health). Cameras restarted with the new identity code (healthy,
reconnecting - no stream off the lab network). Report: `docs/reports/SmartLab_Engineering_Dossier_2026-10-20.pdf`.

| Done | Evidence |
|---|---|
| Desk rule only continues evidence (fixes the USER1/USER5 conflict: 4 wrong-name episodes 2026-10-19) | test_desk_evidence_2026_10_19.py (fails on old code); 248 -> 253 camera tests pass |
| Coasting tracks keep names (seated flicker, NAME_ON_TWO_PEOPLE x24); hand-back from last-seen time, along the walking path | same tests + test_walk_handback.py |
| Carried-over (peer / desk) names give way to this camera's agreeing face matches (19:05 Ali/Nour case) | test_face_overrides_carried_name.py (fails on old code) |
| FANUC cell after the owner's photos: glass, doors, FANUC sticker, yellow side panels, controller, pendant, parts plate; "FANUC Robot ER-4iA" on the arm; robot right of the plate | screenshots; Front view = real front |
| Meshes compacted, same triangles: UR5e+Robotiq 10.4 -> 1.9 MB, FANUC 1.26 -> 0.26 MB (the 2026-10-19 "12.5 MB -> 75 KB" counted only index files) | scripts/compact_glb.mjs, stl_to_glb.mjs; before/after renders identical |
| Robots & PCs tab: cold 2.0 -> 1.5 s, repeat 0.78 -> 0.29 s; System tab 1.20 -> 0.27 s; Reliability 0.96 -> 0.08 s | e2e/robots_tab_perf.mjs, e2e/nav_timing.mjs |
| Bug fixed: evacuation alarm / emergency message missing on /welcome, /monitor, /wall, /report | e2e/emergency_message.mjs now passes |
| Bug fixed: a write followed by a reload within 1 s showed stale data (photo upload) | e2e/workflows.mjs 30/30 |
| Bug fixed (own regression, deployed 23:36, fixed 00:01): Welcome finale crashed (Kinova .STL through the glTF loader) | e2e/welcome.mjs 27/27 |
| Tests: backend 542 passed; camera 253; robot_monitor 41; knowledge 40; pc_agent 5; tsc + vite build; e2e on the isolated seeded copy all pass except navigation's 2 camera-503 messages (cameras stopped there); live: robot_readiness, monitor_security, reliability, welcome (admin/staff) pass | logs in the session scratchpad |
| Load (isolated, simulated): 0 errors, API p95 < 220 ms (summary 1 sample 525 ms), 2 sim cameras 6.5/6.9 fps, RSS flat | tools/perf/load_simlab.py |

**Next / owner:** walk tests at the lab (TWO_CAMERAS.md 2026-10-20 steps); a 2-person session for appearance data;
PC letter -> number map; Hemaly at the door (USER5 template IS loaded); why no ESP node reported since 04:00
2026-10-19 (power / Wi-Fi / portal address); door wiring values to measure (docs/hardware/DOOR_MASTER_WIRING.md);
**change the admin password** (it equals the public demo seed password in the repo); AI answers 51 s on CPU (owner's
GPU-for-cameras choice).


Latest checkpoint: 2026-10-14 ~16:30 (local, at the lab). Branch `offline-router-door-photos`. Nothing pushed.
Resume = read this file, `git status`, `git log --oneline -6`, then continue at "Next".

## Done (with evidence)
| Item | Evidence |
|---|---|
| UR5e collector: frozen RTDE data never shown live; NaN rejected (422, was 500); rtde_check.py | d4e5685; 22 robot tests; new tests fail on old code |
| Camera: strict DirectML detector, engines in /metrics + portal chip | d4e5685; camera tests |
| Camera re-ID fell to CPU at a busy start-up (seen live 03:00) -> re-measure before fallback, logged | d1aaa17; regression test fails on old code, passes now; 103 camera tests |
| Camera password: not on the command line any more (env), masked in logs | d1aaa17; test_masking.py; **live-checked 07:40: no process shows the camera address** |
| Visual foundation (intro, /welcome, manifest, photo folder) | 5b47851; browser checks on dev and **live** |
| n8n 01/03/05/07: owner versions recovered byte-exact, then option (b) repo = live (owner delegated) | docs/N8N_RECOVERY_2026-10-14.md; backups/n8n-recovery-20261014/ |
| Portal deployed (owner approved) | /api/health ok; DB dump backups/smartlab_before_deploy_20261014-0158.dump |
| Agent warm-up (2 h keep-alive) | portal: first word 9.1 s (was 14.3 s), done 12.2 s |
| Native knowledge graph (graph.py), used by investigate | 418 nodes / 2,186 edges, 2 s build; 4 graph tests; 40 knowledge tests; re-ID question now reads vision.py |
| Test DB isolation: advisory lock, concurrent runs wait instead of deadlocking | two parallel runs: second waited, both 11 passed |
| Claude Code toolkit audit | docs/knowledge-platform/CLAUDE_CODE_TOOLKIT_AUDIT.md (measured baseline: ~506 k tokens re-read per request) |

## 07:33 laptop reboot - recovered
`launch.bat` restarted everything: portal health ok, n8n 26 workflows / 0 drift, knowledge service up, Ollama
models on CPU (0 VRAM). Camera service started with the new code: **detector directml-gpu1 (24 ms), re-ID
directml-gpu1 (12 ms/crop)** - the busy-start-up fix verified live (the camera itself is at the lab: camera false).

## Running / pending
* Full backend suite: 436 passed (434 + the 2 AI-local tests after pinning OLLAMA_CPU_ONLY in conftest).
* Knowledge service runs in its own window "Smart Lab - Knowledge" (current code, restarted 07:13).

## At the lab 2026-10-14 (all recorded in docs/LAB_TEST_2026-10-15.md)
* UR5e LIVE_VERIFIED (192.168.1.102, RTDE 48 Hz, J1-J6 mapping, stale 2.0 s on cable pull, auto-recovery).
* Camera LIVE: GPU detector + re-ID; driver-crash root cause fixed (shared GPU session + GPU lock);
  analysis 7 passes/s (pass p50 85 ms, p95 106 ms); zoom finds people seated behind others.
* Identity: door naming via TEST entries (`tools/door_test_entry.py --watch-face`, window
  "Smart Lab - Door test entries"); home desk USER5 -> PC-09/PC-10; face outranks look; hand-back while
  touching. Decisions persisted in tools/security_vision/recordings/identity_log.jsonl (git-ignored).
* Scripts: stop_all.bat / restart_all.bat.

## Evening 2026-10-14 (deployed 19:14, owner approved)
* Commits 72c247d (tracking/elimination/desk guess/monitor query) and 82a76b5 (FANUC live twin, two cameras).
* Backend + frontend rebuilt and restarted (DB dump backups/smartlab_before_deploy_20261014-1912.dump);
  /monitor live 97 -> 59 ms. Camera service restarted with the new tracker (camera powered off at lab close:
  it reconnects by itself).
* FANUC ER-4iA LIVE_VERIFIED read-only at 192.168.1.100 (twin moved with the pendant; ~3 samples/s).
  To confirm: J2/J3 coupling by pose; DIAG-009 controller battery to replace.
* Camera 2 (MC200) arrives tomorrow: docs/camera-identity/TWO_CAMERAS.md.

## Waiting for the owner / hardware
* At the lab: start the camera window (loads re-ID fix + masking) -> check `re-id on directml-gpu1`.
* UR5e: **LIVE_VERIFIED** - telemetry 48 Hz, J1-J6 mapping/direction, stale in 2.0 s on cable pull, auto-recovery (docs/LAB_TEST_2026-10-15.md). Next: camera.
* Photos -> frontend/public/lab + labVisuals.ts.
* Optional (owner): CodeBurn `npx` run, Ponytail lite trial; TikTok effect needs a screen recording. All work committed (c4390ae), nothing pushed.

## 2026-10-14 night - performance mission (uncommitted, awaiting approval)
- Load test: tools/perf/load_simlab.py + ws_clients.mjs, guide docs/perf/LOAD_TEST.md (isolated DB smartlab_loadtest_test, port 8100; container removed after the run).
- Fixed: Command Center reloaded all 8 endpoints on every live status message -> safety msgs 400 ms as before, status msgs at most every 3 s (13.5 -> 9.4 req/s, /monitor 0.8 -> 0.4/s). tsc + build OK; NOT deployed.
- No backend/DB bottleneck: /monitor 22 ms idle; under load the time is host CPU contention from cameras.
- Report: docs/reports/SmartLab_Status_Report_2026-10-14.pdf. Suites: robot 32, camera 148 passed.
- Next mission: ESP32-CAM face enrollment / door recognition speed (flash of the ESP32-CAM authorised by the owner).

## 2026-10-14 late - ESP32-CAM face speed mission (uncommitted, awaiting approval)
- Automatic enrolment: face server POST/GET/DELETE /enroll/auto (device key) saves steady, sharp, new-looking frames from the door camera's /analyze stream; refuses a face that is clearly another enrolled person. Portal: /users/{id}/face/auto; preview from the face server's frame (camera /snapshot only as fallback). /enroll: 1 YuNet pass instead of 3.
- Door decision logic, threshold 0.363, master/RFID/fingerprint untouched. Face server must be RESTARTED (approval) for this to go live.
- Firmware: /enroll upload setNoDelay + timing (source only). Core 3.3.12 builds break the camera (frame buffer malloc failed, PSRAM free) -> board restored from backups/face-speed-20261014/esp32cam_flash_before.bin; camera boots OK. Needs the earlier 3.3.x core (install = approval).
- Laptop Ethernet to Smart_Lab was unplugged: no live camera<->laptop test yet.

## 2026-10-16 - ALIoT upgrade, round 1 (deployed, uncommitted)
- System analytics: `GET /api/analytics/system?days=` + `/analytics/kpis` (backend/app/services/system_analytics.py) - daily series for door, environment, safety sensors, robots (SIM labelled), consumables weight, inventory tx, camera events, PC hours, n8n deliveries, alerts; freshness live/stale/offline/never per source; KPI catalogue. Page /admin/system (frontend/src/pages/SystemAnalytics.tsx), sidebar "System analytics".
- AI agent: staff intent "system" answers data-source health + 7-day totals from system_analytics (no LLM), link to /admin/system.
- Demo /demo: 12 scenarios in 5 groups (door, smoke, evacuation, robot, bin, n8n, vault, AI) - still client-only, nothing recorded.
- Lab page door scene (components/visual.tsx DoorSchematic): red door opens only when reported open; lights = real device state.
- nginx: /api/knowledge/ 600 s, unbuffered (fixes "network error" on long investigations).
- Tests: backend 461 passed; new tests/test_system_analytics.py (4). DB dump before deploy: smart-lab-backups/smartlab-before-system-analytics-*.dump.
- Next: Reports Centre (CSV/PDF per subsystem), cross-system incident timeline, inventory discrepancy view, PC telemetry adapter (IT approval pending).

## 2026-10-17 - readiness round (performance, AI speed, UR5e master controls, PC actions, lab images)

Deployed and checked on http://192.168.1.200 (backend + frontend rebuilt; db/n8n/cameras untouched).
- Lab images: Power (LAB_08), Design (LAB_09), Fashion (LAB_11) card + hero + gallery; Power gallery has no SCADA item.
- Performance root causes: (1) `/system/status` probed the internet inline (2 x 1 s timeouts, holding a DB
  connection) -> background thread; (2) face-server / ESP32-CAM probes inline every 15 s (1.0 s spikes on
  `/devices`, `/labs/{id}`) -> background refresh; (3) DB pool 5+10 for ~20 parallel dashboard requests -> 20+20;
  (4) duplicate identical GETs (summary x2, system/status x3) -> shared in-flight GETs in `lib/api.ts`.
  Measured: login->app 3.6 s -> 0.95 s; `/api/devices` 40 sequential calls all 18-45 ms (was 1.0 s spikes);
  sidebar navigation route 80-130 ms, data 140-200 ms median. Scripts: `frontend/e2e/perf_routes.mjs`, `perf_nav.mjs`;
  results `docs/reports/perf_before.json`, `perf_after.json`.
- AI: project/technical questions answered from the knowledge index ("lookup", cited passages, no model):
  ~100-110 s -> 0.12-0.45 s. Lab-data questions already instant (30-100 ms). KB rebuild is incremental (208/7449 chunks).
- UR5e master controls (DRY RUN - nothing sent): verified Home pose [-15.00, -126.00, 117.03, -80.00, 91.00, 95.27] deg,
  Home via URScript movej in live mode only, state from joint feedback, global STOP (any staff, latch, priority),
  admin recovery, E-stop disclaimer. FANUC separate (UNAVAILABLE). docs/ROBOT_CONTROL.md has the lab checklist.
- PC actions: open/close approved app, lock, log off / restart / shut down (admin, confirmed, 60 s warning),
  QUEUED/EXECUTING/COMPLETED/FAILED/EXPIRED from the agent's own result; audited. No PC enrolled yet.
- Tests: backend 466 + new (robot control 29, equipment 13) pass; tools: robot 37, knowledge 40, vision 163; tsc + vite build OK.
- Open: physical validation at the lab (UR5e cable/IP + commissioning, FANUC interface, MC210 camera 1 at uni,
  PC agent install on lab PCs). ROBOT_CONTROL stays dry_run until the owner signs off.

## 2026-10-17 (afternoon) - 8 upgrades round (all deployed on http://192.168.1.200)

- System health: background probes (`app/services/health_monitor.py`, parallel, every 10 s) - /system/services and
  new /system/health never wait on a probe; ONLINE/DEGRADED/STALE/OFFLINE/UNKNOWN/SIMULATION, last OK, failing since,
  guidance; robot collector without joints = DEGRADED. Page: System analytics (top).
- PCs: viewer picks monitor (agent enumerates monitors) + quality/fps; view start/end audited; sharing to selected PCs;
  browser sharing = picker -> local preview -> Go live. Agent 0.5. No remote keyboard/mouse (documented: RDP shadow).
- Incidents: migration a9d4e7c1b305 (additive: alerts.state/ack/owner/resolution + incident_notes), applied after a
  verified dump + restore drill (smartlab_restore_drill: counts match, upgrade/downgrade/upgrade OK). Page /admin/incidents.
- Anomalies: rules + sensor-fault + robust 7-day baseline on ENV_LAB01 (no ML - documented). Found: flame detector active
  in 17% of readings over its history. /analytics/anomalies cached 60 s.
- Reports Centre (Reports page): 7 exports (CSV / print-PDF, source + warnings), cross-system timeline (co-occurrence =
  timing only), inventory discrepancies, equipment lifecycle (overdue / maintenance / faults).
- Security: authorization sweep test over all 258 API routes (anonymous refused); login throttle already existed.
- Evidence: `py -I tools/evidence/run_evidence.py` -> docs/reports/evidence_<ts>.md/json (classes REAL_HARDWARE /
  LIVE_SYSTEM / OFFLINE / SIMULATION). Latest: 32 pass, 12 fail (devices off/away), 9 n/a, 2 simulation.
- AI: project questions 0.13-0.45 s cited lookup; full answers stream sources at 0.1-1.3 s, first word 8-17 s (CPU model).
- Tests: backend 492 passed; tools 37/40/163; tsc + vite OK.

## 2026-10-17 (evening) - continuation round
- PC agent 0.6: Pillow-free capture (Windows GDI + OpenCV, already installed), DPI-aware monitors, 1 s poll.
  Live-verified with this laptop as the admin/master PC (PC_ADMIN_LAPTOP, id 13): preview first frame 1.7 s, 2.2 fps,
  monitor 1/2/all, wall, close stops frames, agent restart -> frames again in 1.3 s, browser share to a selected PC,
  master-PC share (first frame 0.5 s), Stop ends both; audit rows present. `start_pc_agent.bat` + agent.env(.example).
  Fix: "View all screens" now shown when the only PC is the master PC.
- Anomalies: fixed Row.t bug in sensor series (timestamps were rows); flame finding now states activations and the
  longest run. Flame history: 642/678 active readings in one 3 h block on 2026-10-09 16-19 h - check physically.
- Incidents page: "group similar" + provenance labels (display only; nothing resolved).
- AI: knowledge agent k 4 -> 3 (bench 13 q: facts 9/12 -> 10/12, median first word 8.5 -> 4.4 s, total 12.9 -> 7.5 s);
  answer cache in serve.py (same question + same index version -> instant). Eval set +2 questions (UR5e Home, STOP).
- Backend: backup status read cached by file mtime; refresh_liveness throttled 3 s (LIVENESS_THROTTLE_S; tests 0).
- Evidence: 35 pass, 12 fail (all hardware off/away), 7 n/a, 2 simulation. Lab steps: docs/LAB_READINESS_2026-10-18.md.

## 2026-10-17 (night) - camera-wide incidents, split live view, robot controls in Equipment, fleet card fix
See docs/LAB_READINESS_2026-10-18.md "Update 2026-10-17 night" and docs/INCIDENT_REVIEW_2026-10-17.md.

## 2026-10-18 - reliability, identity, robots readiness, AI vs cameras (deployed; uncommitted)
Start here next time: docs/OPERATIONS.md (runbook), docs/LAB_GO_NOGO_2026-10-18.md (physical tests),
docs/BACKLOG.md (open items), docs/SECURITY_FINDINGS_2026-10-18.md.
* Robots: UR5e Home = pendant program `home.urp` (load + play, completion from joint feedback); readiness
  checklist; STOP latch survives backend restarts (audit log); FANUC identity + 220 installed options from the
  controller's own SUMMARY.DG (DEMO list empty), motion BLOCKED; 10-step plans in docs/ROBOT_CONTROL.md.
* Cameras (tested offline + live test instance; take effect when the camera services restart): reconnect
  backoff + FFmpeg timeouts + stream states; real CPU / private memory / GPU in /metrics; above-normal priority;
  identity: door entries need "at the door when first seen, alone", posture changes keep the track, staged
  association, crossing re-deals flagged for review, cross-camera states bug fixed. Simulated bench
  (tools/security_vision/scenario_bench.py): 180 runs, 0 false-name frames, 0 name switches.
* Incidents: grouping by fingerprint (occurrences, last seen, reopen), MITIGATED state, escalation on repeats,
  alert quality; migration d5e8b2c4f917 (additive) applied after an isolated restore + migrate drill.
  Fixed: resolved camera alert broke the next camera event (HTTP 500); stale offline incidents; camera "no
  picture" incident.
* Reliability centre (/admin/reliability): briefing, dependency graph + what-if (simulation), drift vs
  backend/app/config_baseline.json, request performance + objectives, alert quality, backups + restore drill,
  action policy; incident investigation (ranked explanations, correlation not proof); global search (Ctrl+K);
  sidebar regrouped (no page removed; Robots + Reliability added).
* AI: status questions answered from the records (44-142 ms instead of ~50 s); LLM 4 threads, one answer at a
  time (camera analysis held 6.6-6.9 fps during an answer vs 4.6 avg / 1.7 min before); knowledge embed
  keep-alive 2 h.
* Tools: tools/evidence/clock_check.py, restore_drill.py, run_evidence.py (extended), tools/deploy/deploy.py
  (version stamp, smoke tests, automatic rollback).
* Evidence run 2026-10-18 11:22 UTC: PASS 41, FAIL 13 (all physical devices not connected here), NOT_AVAILABLE
  7, SIMULATION 3, PHYSICAL_VALIDATION_REQUIRED 4, BLOCKED 1 (docs/reports/evidence_20261018_112213.md).

### 2026-10-18 14:50 - final deploy + engineering dossier
* Backend suite 529 passed / 0 failed (18 min, smartlab_test).
* Deployed with `tools/deploy/deploy.py`: version `f5eaeff-dirty-20261018144505`, quick tests, schema at head, 7 smoke checks, no rollback.
* Post-deploy load: single user p50 31 / p95 80 ms; 10 users + 2 live viewers p50 65 / p95 271 ms, frames p50 44 / p95 91 ms, 0 errors (`docs/reports/perf_final_20261018.json`).
* Dossier: `docs/reports/SmartLab_Engineering_Dossier_2026-10-18.pdf` (14 pages) from `docs/reports/dossier/*.html` + `evidence_index.json`; renderer `frontend/e2e/dossier_pdf.mjs`.
* Still open (owner / lab): admin password, camera-service restart (new code), clock sync, physical tests (LAB_GO_NOGO), ESP32 offline queue, commit.

### 2026-10-18 evening - ESP32-CAM rebuilt from source (kept), bin-0.3 on the consumables bin
* ESP32-CAM (COM7) now runs the repository source built with **esp32 core 3.2.1** (board `esp32:esp32:esp32cam`,
  installed in an isolated arduino-cli data dir; the main 3.3.12 install is untouched). Measured: 2.7-2.9 frames/s,
  upload+reply 360 ms, 0 failed (old binary: 2.17-2.65 frames/s, 394-463 ms). 2 frames in flight tested: 2.77 frames/s
  but 637-662 ms round trip + failures -> 1 kept. Backups: `backups/esp32cam-20261018/` (before + kept image).
* Consumables bin (COM9) runs **bin-0.3** (loaded-creep following, restart keeps the count, correct hx711 flag);
  backup `backups/bin-flash-20261018/`. Count re-anchored to the owner's 30 (audited).

### 2026-10-18 late evening - full system on the bench
* Live f5eaeff-dirty-20261018232259 (migration b7c3e1f9a204 index). Backend 539, vision 213, e2e ALL PASS.
* All five ESP32 boards reporting; door Face ID path verified physically (3 grants, 2 correct denials).
* Open: master fingerprint/LED/camera-poll flapping on laptop USB power (check common ground / power from the
  5 V buck); security-camera services to restart for the new tracking code (owner: tomorrow); camera 1 + robots
  at the university. Report: docs/reports/speed_and_fixes_2026-10-18_evening.md.

## 2026-11-07 master finalization (not committed, not deployed)
Thesis and manuscript: `thesis_overleaf/FINAL_SUBMISSION/FINAL_RELEASE_2026-11-07_v2`. Backend 753 passed, 2 skipped. New: `pc_account_keys` migration f1a7c3d9e250 (needs `tools/deploy/deploy.py --allow-migration` with SMARTLAB_PASSWORD); PC kit 1.1 with Install/Check/Uninstall-CurrentUser, Start/Stop-Agent, DPAPI keys, tray icon, site.json; scripts syntax-checked only (execution policy off on this laptop). Door fault open, firmware unchanged. Containers db, backend, frontend, backup left running.
