# Smart Lab: complete project status report (2026-10-27, ~01:00 Cairo)

This is a report only; nothing was implemented for it. It is checked against:
* the repository (branch `offline-router-door-photos`, HEAD `cf81823`, plus uncommitted work listed in section 16);
* test output from 2026-10-26/27;
* the live portal's `/api/health`;
* the processes running on the laptop.

Where this report and older checkpoints disagree, this report wins.

**Conditions.** All work happened off-site. The laptop was cabled to the Smart_Lab router at 2026-10-27 ~00:10, but
only the router (192.168.1.1) answered. The UR5e (.102), FANUC (.100), door ESP32/CAM (.150), nodes and cameras did
not answer: they were **unavailable, not shown to be faulty**. All camera, robot, phone and voice results are
therefore from recordings, fake devices, mocks or synthetic speech, and are labelled that way.

Status words: PASS = verified · PARTIAL · FAIL · BLOCKED · NOT TESTED · NOT STARTED · N/A.

---

## 1. Executive summary

* **Software:** large and mostly tested. Backend **626 passed / 0 failed** at commit 53a35d0 (2026-10-26). Native
  suites pass: cameras 291, robot monitor 42, knowledge 49, UR control 20, voice 6, OPC UA 3, PC agent 14, LAN
  presence 5. Frontend `tsc` + build OK. Browser e2e: phone scan, people boxes, voice, screen-share stop and
  navigation all pass, with fake devices.
* **Live deployment is stale.** The live portal runs **`c74ee3b`, built 2026-10-21**. None of the work since then is
  deployed (cameras v2, scan, voice, UR5e local control, booking race fix, OPC UA, ...).
* **Security P0:** the live `admin@giu-uni.de` and `ramy@giu-uni.de` accounts still accept the passwords printed in
  the public README. This was checked read-only on 2026-10-26.
* **Local AI benchmark: in progress.** Research was done and 13 models were downloaded. Measured so far:
  * the baseline, end to end and raw;
  * GPU, partial-GPU and 6-thread variants;
  * one ultra-small model (Gemma 3 270M).

  The full sweep is running and **no winner has been chosen or integrated**. A deterministic tool router and
  local-only enforcement are implemented and **not committed**.
* **Offline operation:** **NOT TESTED** with the internet disconnected. The code was audited and found no
  operational cloud calls.
* **Physical validation:** none of today's hardware-facing features has run on hardware. That covers the UR5e
  Local-mode control, auto-Home, the stop relay, the phone camera on a real phone, a real microphone and the new
  camera defaults on live cameras.

**Verdict: READY FOR CONTROLLED LAB TESTING** of the software on the bench and the isolated copy. **Not ready for
demonstration** until P0-1 (passwords), P0-2 (deploy) and a lab session with the devices powered are done.

## 2. How the assessment was derived

Each requirement from the 2026-10-26/27 prompts is rated in the master table, 73 rows in all. "PASS" needs a current
test or measurement in this repository. Simulated or offline tests are rated PASS (software) and listed separately
in section 12 as physical tests still owed.

Rough count:
* PASS: 41 (all software or offline)
* PARTIAL: 15
* BLOCKED: 9
* NOT TESTED: 4
* NOT STARTED: 4

This is **not** a completion percentage of the thesis: 0 of the 9 physical-validation items are done.

## 3. Master status table

| # | Workstream / requirement | Status | Evidence | Missing / next | SW or physical |
|---|---|---|---|---|---|
| 1.1 | Portal navigation speed | PASS | nav_timing 40 warm visits p50 119 / p90 229 ms; role matrix warm median admin 145 / staff 140 / student 100 ms (2026-10-26) | `/admin/access` 1.1 s in one trial | SW |
| 1.2 | Hidden-tab polling, camera frames paused | PASS | Monitor 0.77 -> 0.2 req/s (e2e/hidden_tab_polling.mjs) | | SW |
| 1.3 | Evaluation tab, Lab Health tab, Headcount card, Excel button | PASS | screenshots; tests/test_health_headcount.py (6) | | SW |
| 1.4 | nginx: HTTP/2, gzip, immutable caching | PASS | live tls.conf `http2 on`, gzip verified | | SW |
| 2.1 | Backend regression suite | PASS (at 53a35d0) | 626 passed, 14 min | rerun after the uncommitted AI changes; a run was in progress at report time and had not finished | SW |
| 2.2 | Booking race (double booking) | PASS | tests/test_booking_race.py; negative control failed without the lock | not deployed | SW |
| 2.3 | Sign-in burst (Argon2 hash slots) | PASS | 20 at once p50 1.58 -> 0.94 s; /monitor during it 317 -> 156 ms | not deployed | SW |
| 2.4 | /equipment N+1 | PASS | test caps queries <= 20 for 6 devices | | SW |
| 2.5 | Workers / Redis decision | PASS (decision) | 1 worker kept: robot latches, WS hub and throttles are in process memory | | SW |
| 2.6 | Authorization (admin/staff/student) | PASS | authz sweep in the suite; new routes tested for 403 | | SW |
| 3.1 | Detector selection (YOLO26s 544x960) | PASS (offline) | docs/CV_BENCHMARK_2026-10-26.md: recall 0.898 -> 0.923 on 363 reviewed people | | offline |
| 3.2 | Tracking / partial body / continuity | PASS (offline) | HOTA 0.732 -> 0.779, IDF1 0.831 -> 0.874, ID switches 14 -> 12 (3 clips) | live check | offline |
| 3.3 | Two-camera throughput | PASS (recordings) | 9.4 / 9.9 analyses/s (load_simlab, 2026-10-26) | live cameras still on OLD defaults until restarted | offline |
| 3.4 | Cross-camera handoff / Re-ID | PARTIAL | desk pairing + look-led pairing (10-21), not re-verified | live test | physical |
| 3.5 | Camera FPS under AI load | **PARTIAL - risk** | AI on CPU drops cameras from ~9.4 to a median 6.3-9.0, minimum 0.6-5.5 (benchmarks 10-26/27, with other load) | pick a model / policy that keeps the cameras | SW |
| 4.1 | Phone scan: markers -> live card | PASS (fake camera) | scan_lab.mjs PASS: 227-244 ms warm, 5/5 Stop releases the camera | real phone | physical |
| 4.2 | Phone scan: people boxes | PASS (recorded footage) | scan_people.mjs: 7.4 fps, rtt p95 95 ms | real phone | physical |
| 4.3 | Phone: detect robots / PCs / node boxes by appearance | NOT STARTED | only people are detected; equipment identity comes from QR markers only | owner's photos of the boxes -> reference matching (requested 10-26) | SW + photos |
| 4.4 | QR fallback per box | PASS (software) | /scan/markers prints SLAB:D/B/A markers | print + stick on the boxes | physical |
| 4.5 | Snapshot -> send to AI | NOT STARTED | owner chose "context only" then allowed a vision model | design + build | SW |
| 4.6 | Phone HTTPS / trusted CA | PASS (software) | /phone-setup, CA cert served, private key out of nginx | trust steps on a real phone | physical |
| 5.1 | Voice STT (faster-whisper base.en, CPU) | PASS (synthetic speech) | 1.28 s/question, WER 5.7 % (Piper voice, 5 questions) | real voices / accents | physical |
| 5.2 | Voice TTS (Piper) + push-to-talk + cancel | PASS (fake mic) | voice_talk.mjs 3/3; mic released; first audio 4.3-5.3 s | | SW |
| 5.3 | Voice -> same tools / permissions | PASS | routes/voice.py -> /ai/ask; tests/test_voice.py (5) | | SW |
| 5.4 | Voice with cameras running | PASS (1 camera) | 10.0 analyses/s during 21 transcriptions | two live cameras | physical |
| 6.1 | Lab AI instant database answers | PASS | 32/52 eval questions answered in p50 0.08-0.32 s with no LLM; 10/10 instant correct (e2e 10-27) | | SW |
| 6.2 | Lab AI tool routing | PASS (uncommitted) | keyword router: tools 13/13 end to end (was 0/8); tests/test_ai_router.py (5) | commit | SW |
| 6.3 | Lab AI model answers - speed | **PARTIAL** | e2e model path p50 25 s, routed p50 47 s on the CPU with 2 cameras (10-27 00:21); about 4-9 s when the prompt cache hits | finish the model sweep; deploy the winner | SW |
| 6.4 | Lab AI accuracy | PARTIAL | e2e overall 86.5 %: snapshot 16/23, tools 13/13, unknown 6/6, instant 10/10 | snapshot answers from the small model | SW |
| 6.5 | Project knowledge agent | PASS (measured) | agent.py --bench: right source 10/12, facts 10/12, lookup 165 ms, CPU answer median 14 s | | SW |
| 6.6 | Citations in lab answers | PARTIAL | answers name the tool used ("tools_used"); no per-number citation | | SW |
| 7.x | Local model / engine search | see section 7 | | | |
| 8.1 | No cloud AI (local-only enforcement) | PASS (code, uncommitted) | `AI_LOCAL_ONLY` default true; provider test; live has no Anthropic key | commit + deploy | SW |
| 8.2 | Offline operation, internet disconnected | NOT TESTED | the egress audit found only doc links / XML namespaces | owner test (section 8) | physical |
| 9.1 | ESP32 door, NFC, fingerprint, LCD | PASS (earlier sessions) / not re-tested | door validated in earlier sessions (memory/checkpoint) | not touched (firmware rule) | physical |
| 9.2 | Environment node (DHT22, PIR, MQ-2, flame) | PARTIAL | quality flags in the portal; node offline in the copy data | live readings | physical |
| 9.3 | Consumables bin (load cell) / reusable bin (NFC) | PARTIAL | instant answer lists bins; calibration status per bin | live | physical |
| 9.4 | IoT buffering / store-and-forward | PARTIAL | RAM queue (32 events) + retry; no flash store | decide whether needed | SW + firmware |
| 9.5 | Enclosures (4 CAD designs) | PASS (owner-tested coupons) | untracked/uncommitted CAD folders preserved, untouched | owner commits when ready | physical |
| 10.1 | PC monitoring, bulk controls | PASS (tests) | pc_agent 14, equipment tests | lab PCs not exercised today | physical |
| 10.2 | Screen share Stop | PASS | 192-275 ms, 3/3 | | SW |
| 10.3 | UR5e monitoring (read-only) | PASS (earlier live) | LIVE_VERIFIED 2026-10-15 (RTDE 48 Hz) | | physical done earlier |
| 10.4 | UR5e Home/Stop in Local mode | BLOCKED | agent dry run, 20 tests; needs pendant program + host .200 + supervised session | commissioning | physical |
| 10.5 | UR5e auto-Home (idle -> 20 s countdown -> Home) | BLOCKED (SW PASS) | 6 agent tests; twin countdown + Cancel | commissioning; off by default | physical |
| 10.6 | Portal STOP via relay (safeguard input) | BLOCKED (SW PASS) | firmware compiled 71 %; backend tests (6) | parts + wiring approval; bench test | physical |
| 10.7 | FANUC Home/Stop | NOT STARTED (by plan) | adapter UNAVAILABLE; interface not configured on the controller | after the UR5e works | physical |
| 10.8 | Launcher starts every service | PARTIAL (uncommitted) | launch.bat now also starts voice, OPC UA, UR agent (if UR_AGENT_KEY); dry run of the new blocks inconclusive (tasklist /v slow) | run the full launch once; robot.env lacks UR_AGENT_KEY | SW |
| 11.1 | Security alerts / incidents / emergency | PASS (tests) | existing suites | | SW |
| 11.2 | Advisory emergency headcount | PASS | door record vs largest single camera count; tests | | SW |
| 12.1 | Backups + restore drill | PASS (existing) | auto dump 2026-10-25; restore_drill.py | | SW |
| 12.2 | Data retention (camera recordings) | PARTIAL | 1.3 GB recordings, no retention; snapshots purged after 30 days | owner decision ("never delete data") | policy |
| 13.1 | Reports: CSV / Excel / Print-PDF | PASS | xlsx tests; Excel 27 s under the benchmark load (a re-time while idle is still pending) | re-time idle | SW |
| 13.2 | AAS V3 export | PASS | /equipment/aas.json test | import into BaSyx | SW |
| 13.3 | OPC UA server | PASS | 3 + 2 tests; 408 live variables read by a client | UaExpert check; production .env key | SW |
| 13.4 | Knowledge vault / Obsidian / n8n | PASS (existing) | knowledge 49 tests; n8n untouched (rule) | | SW |
| 13.5 | Evaluation section | PASS | /reliability/evaluation | update with the model results | SW |
| 14.1 | HTTPS / LAN access | PASS | local CA, TLS 443 | phone trust | physical |
| 14.2 | Secrets in git | PASS with one risk | no tracked .env / keys; **untracked `firmware/tools/ali.jpg.jpg`, `ali2.jpg` (people photos?) are NOT git-ignored** | add to .gitignore | SW |
| 14.3 | Published default passwords | **FAIL (live)** | admin + staff still accept the README passwords; the briefing warns | owner changes them | owner |
| 14.4 | Deployment of the 10-21..10-27 work | **NOT DONE** | live = c74ee3b | deploy with the owner's credentials | owner |
| 15.1 | Identity-fusion study (E) | NOT STARTED | | | SW |
| 15.2 | Visual safety triage (L) | NOT STARTED | | | SW |
| 15.3 | Whole-lab time slider (I) | PARTIAL | robot movement replay exists | | SW |
| 15.4 | Wallet .pkpass (N) | BLOCKED | needs an Apple Developer certificate | | external |
| 15.5 | Hardware pilots (K) | N/A now | owner: no new hardware until the end | proposals only | |

## 4. Completed and verified (software), with evidence
Commits on 2026-10-26/27, not pushed:
* `9409a09`: cameras / tracking / UR5e local agent / screen share.
* `3a68d82`: Scan the lab.
* `b2d6ae5`: UR5e auto-Home + stop relay.
* `2a0b760`: voice.
* `a1470ed`: booking race, /equipment, sign-in, hidden tabs, Excel, health score, headcount, AAS.
* `53a35d0`: Evaluation tab, password warning.
* `5be385b`: audit document.
* `cf81823`: OPC UA.

Full evidence for each is in `docs/FINAL_IMPLEMENTATION_AUDIT_2026-10-26.md` and the READMEs named in the table.

## 5. Partially completed
* AI answer speed (3.5, 6.3).
* AI accuracy on snapshot questions (6.4).
* Launcher completeness (10.8).
* Cross-camera Re-ID (3.4).
* IoT buffering (9.4).
* Retention (12.2).
* Time slider (15.3).
* Citations (6.6).
* Environment / bin nodes (9.2, 9.3).

## 6. Failed, blocked, not started, untested
* **FAIL:** 14.3, default passwords live.
* **BLOCKED:** 10.4-10.6 (lab session / approval), 15.4 (Apple), 4.1/4.2/4.6/5.1 on real devices.
* **NOT STARTED:** 4.3 appearance recognition of boxes/robots/PCs, 4.5 snapshot-to-AI, 15.1, 15.2, 10.7 FANUC.
* **NOT TESTED:** 8.2 offline with the internet disconnected; 2.1 the rerun after the uncommitted AI changes; 10.8
  the full launcher run; Excel/briefing timing while idle.

## 7. Local AI model research and benchmark status (exact)

| Stage | State |
|---|---|
| **Researched** | Yes (web, 2026-10-26). Ollama library checked for **qwen3.5** (0.8b / 2b / 4b, vision+tools), **gemma4** (e2b 4.3 GB+ / e4b), **granite4** (350m-h, 1b-h, micro-h, 3b), **LiquidAI lfm2.5** (1.2b-instruct, 2.6b, thinking), **functiongemma** 270m, **gemma3** (270m, 1b). Literature found: BitNet b1.58 2B4T (needs a bitnet.cpp build; VS Build Tools 2026 present, clang/cmake not), OpenVINO GenAI (Intel CPU; not tried). Engine finding: Ollama 0.40 runs **llama.cpp's llama-server** itself, so LM Studio / Jan / GPT4All / KoboldCpp are wrappers of the same engine, not independent engines. MobileLLM, OpenELM, MiniCPM5, OLMo 2, Falcon3 3B and others: **not researched in detail**. |
| **Downloaded** | 13 models: qwen2.5:1.5b + qwen2.5:3b (existing), functiongemma:270m, gemma3:270m, gemma3:1b, qwen3:0.6b, qwen3:1.7b, qwen3.5:0.8b, smollm2:135m, smollm2:360m, LiquidAI/lfm2.5-1.2b-instruct, llama3.2:1b, llama3.2:3b. Queued and downloading: qwen3.5:2b, granite4 350m-h/1b-h/micro-h, smollm2:1.7b, falcon3:1b, phi4-mini, lfm2.5-2.6b, moondream, gemma4:e2b. The llama.cpp standalone download was stopped (internet ~80 KB/s at the time). |
| **Benchmarked** | Harness `tools/llm_bench/` (bench.py raw, e2e_ask.py through the real backend, router_bench.py, sweep.sh; **52-question** eval_lab.json), both camera services sampled. Measured (Ollama, Q4 defaults, 2 cameras from recordings): see the table below. **router_bench not yet run. Sweep in progress** (at smollm2:360m at report time; CPU contended by a parallel test run, so these numbers will be re-measured clean). |
| **Integrated** | Not yet: no model change. **Integrated but uncommitted:** keyword tool router, bounded answers (220 tokens), guide only for how-to questions, time line moved last + volatile snapshot lines last (prompt-cache reuse), one 4K context for both assistants, AI_LOCAL_ONLY. |
| **Verified offline** | No. |

Measured so far, baseline **qwen2.5:1.5b** (raw = bench.py on the frozen prompt, 34 non-instant questions; both cameras running):

| Config | TTFT p50 | Total p50 / p95 | Gen tok/s | Accuracy (snap / tools / unknown) | Cameras median (min) |
|---|---|---|---|---|---|
| CPU, 4 threads (baseline) | 1.36 s | 3.54 / 65.8 s | 6.9 | 20/22, 0/8, 4/4 | 9.4 / 9.0 (5.5 / 5.9) |
| CPU, 6 threads | 1.17 s | 3.85 / 71.7 s | 6.0 | 18/22, 0/8, 4/4 | 8.1 / 8.3 (5.5 / 5.9) - worse |
| GPU, all layers | 0.27 s | 0.96 / 10.5 s | 23.1 | 19/22, 1/8, 4/4 | **6.4 / 6.8 (4.6 / 5.4) - rejected** |
| GPU, 8 layers | 1.28 s | 3.26 / 24.6 s | 8.5 | 19/22, 0/8, 4/4 | 8.5 / 8.4 (5.7 / 4.1) |
| gemma3:270m CPU | 0.91 s | 2.47 / 12.0 s | 9.4 | **4/23, 0/13, 0/6 - rejected** | 7.1 / 6.7 (contended) |

End to end through the backend (52 questions, 2026-10-27 00:21): all p50 0.92 s / p95 50.5 s; instant p50 0.32 s
(32 questions); model p50 25.5 s; routed p50 47 s; accuracy 86.5 % (baseline before the router: 70.6 %). Cameras median
6.55 / 6.3, minimum 0.6 / 0.8 (CPU 100 %, with parallel downloads and a test run). Cause found: prompt reading on the
CPU at 14-24 tokens/s, the prompt cache broken by a per-minute time line. Fixed (uncommitted), but not yet
re-measured end to end.

## 8. Local-only / offline readiness

| Part | Local? | Tested offline? |
|---|---|---|
| LLM (Ollama), embeddings (nomic-embed-text) | yes | no |
| Cloud AI | blocked by AI_LOCAL_ONLY (uncommitted); live has no key | - |
| Knowledge retrieval (serve.py 127.0.0.1:5199) | yes | no |
| STT / TTS | yes; Whisper now loads with `local_files_only` (uncommitted) | no |
| Camera inference (DirectML ONNX) | yes | used offline at home with recordings |
| Backend / DB / WebSockets / nginx | yes (Docker); launch.bat skips the image rebuild without internet | earlier sessions ran on the Smart_Lab router (no gateway) - not re-verified today |
| Phone over the LAN | local CA | no real phone |
| IoT / PC / robot monitoring | LAN only | earlier lab sessions |
| Reports (CSV / Excel / print) | stdlib / browser | no |
| Frontend external requests | code scan: none (fonts local) | no |

**Offline test still to do (owner, 10 minutes):** keep the Smart_Lab cable, switch Wi-Fi off, then exercise in turn:
sign-in, Monitor, Ask the lab, Project knowledge, Talk, Scan, Excel export, and the OPC UA client.

## 9-10. Portal, backend, cameras, phone, voice, IoT, robots
Covered in rows 1.x-10.x. Running services right now:
* camera services 5102 / 5103 (recordings, isolated copy);
* knowledge 5199;
* voice 5320;
* OPC UA 4840 (pointing at the copy);
* face server 5000.

The UR agent (5310) is not running.

## 11. Testing, reliability, security, performance
* **Tests:** backend 626 (53a35d0); native 430; frontend tsc / build; e2e listed above.
* **Not re-run since the uncommitted AI changes:** the full backend suite. The AI subset (28) passed before the last
  two prompt edits. The AI-subset rerun after them ended under heavy CPU load (20-min limit) with **no result
  printed**, so the status is **NOT TESTED**; rerun it while idle.
* **Security:** P0 passwords; risk of untracked photos; CA key fixed; booking race fixed (not deployed).
* **Performance:** section 4 of the audit document.

## 12. Hardware and physical validation checklist (none done 2026-10-26/27)
1. Restart both camera services, then a live check of the new detector and tracker (people seated, walking, both
   cameras).
2. Real phone (Android + iPhone): trust the CA, scan printed markers, people boxes, Stop.
3. Real microphone: lab members' accents, background noise.
4. UR5e commissioning:
   * `portal_200` installation and `portal_control.urp`;
   * agent dry run, then live with a hand on the E-stop;
   * Home, Stop, then auto-Home.
5. Stop relay:
   * bench test with a multimeter;
   * wiring to SI0/SI1 after the cell owner approves;
   * safeguard-stop test.
6. Offline test (section 8).
7. Environment node / bins / door live readings after deploy.
8. OPC UA in UaExpert from another PC (LAN mode).
9. FANUC interface selection (later).

## 13. Prioritized backlog

| ID | Task | Deliverable / acceptance | Needs | Blocks |
|---|---|---|---|---|
| **P0-1** | Change admin + staff passwords | the briefing no longer shows the security item | owner, 2 min | demo |
| **P0-2** | Deploy | `/api/health` version = the latest commit; deploy.py smoke tests pass | owner credentials (SMARTLAB_EMAIL/PASSWORD), VOICE_KEY / OPCUA_KEY / UR_AGENT_KEY in .env | everything "not live" |
| **P0-3** | Git-ignore the people photos in `firmware/tools/` | `git check-ignore` true | none | accidental publication |
| **P1-1** | Finish the model sweep + router_bench, choose the winner, re-run e2e with both cameras, commit the AI changes + full backend suite | report `docs/LOCAL_AI_BENCHMARK_2026-10-27.md`; model answers faster than the baseline with accuracy >= the baseline; cameras median >= 9 | CPU time (~2 h) | demo speed |
| P1-2 | Lab session: items 1, 2, 3, 6 of section 12 | recorded results | lab, devices on | thesis evaluation |
| P1-3 | UR5e commissioning (section 12, item 4) | Home / Stop / auto-Home observed, feedback logged | operator + lab | robot demo |
| P1-4 | Full launch.bat run (all windows) | every service listening; screenshot | lab or home | |
| P2-1 | Phone: detect robots / PCs / node boxes by appearance | owner's photos -> reference set; suggestion labelled "unconfirmed, scan QR" | owner photos | |
| P2-2 | Snapshot -> AI (instant check + model) | button on Scan; answer < 2 s for the instant check | P1-1 (model) | |
| P2-3 | Stop relay bench + wiring | section 12, item 5 | approval, parts | |
| P2-4 | Retention policy for recordings | owner decision written down | owner | |
| P3 | FANUC Home/Stop, identity-fusion study, safety triage, time slider, BitNet / OpenVINO trial, .pkpass, flash store-and-forward | | | |

Duplicates and obsolete items:
* The "fastest model" requests of 10-26 and 10-27 are one task (P1-1).
* The "voice", "phone camera" and "OPC UA" requests are done in software; only the physical tests remain.
* The openpyxl install for Excel is no longer needed (stdlib writer).

## 14. Critical risks / blockers
1. **Published passwords live** (P0-1).
2. **Nothing since 10-21 is deployed** (P0-2).
3. **The local AI starves the cameras on the CPU** (median down to ~6.5/s under load). The model choice must keep
   the cameras (P1-1).
4. All hardware validation needs a lab session with the devices on (currently off).
5. Uncommitted AI work (router, local-only, prompt cache) must be committed only after its tests pass.

## 15. Next five actions, in order
1. Owner: change the admin and staff passwords (Users & roles).
2. Finish P1-1: the sweep, router_bench, winner, e2e with 2 cameras, full backend suite, commit.
3. Git-ignore `firmware/tools/*.jpg`. Set VOICE_KEY / OPCUA_KEY / UR_AGENT_KEY in `.env` / robot.env. Deploy with the
   owner's credentials.
4. Offline test (section 8) on the Smart_Lab cable with Wi-Fi off.
5. Lab session: restart the cameras; real phone + markers; real voice; UR5e commissioning step 1 (dry run with the
   pendant program).

## 16. Git and repository
* Branch `offline-router-door-photos`, HEAD `cf81823`. **Not pushed.** Live = `c74ee3b`.
* **Uncommitted (mine, AI work in progress):** `backend/app/core/config.py`, `backend/app/services/ai.py`,
  `backend/app/services/agent.py`, `backend/tests/test_ai_local.py`, `tools/voice/voice_service.py`, `launch.bat`,
  `stop_all.bat`, plus new `backend/tests/test_ai_router.py` and `tools/llm_bench/`.
* **Uncommitted (owner's, untouched):** `.env.example`, `frontend/e2e/command_center.mjs`, 54 modified CAD files,
  untracked CAD release folders, reports and figures.
* **Risky untracked:** `firmware/tools/ali.jpg.jpg`, `firmware/tools/ali2.jpg`. These are probably photos of a
  person and are not git-ignored.
* Secrets: none tracked (`.env`, camera / robot / voice / opcua env files, secrets.h are git-ignored).

## 17. Readiness verdict
**READY FOR CONTROLLED LAB TESTING.** The software is implemented and tested with recordings, fakes and mocks. It is
**not ready for demonstration** until:
* the published passwords are changed;
* the current build is deployed;
* the local AI configuration is chosen without starving the cameras;
* one lab session confirms cameras, phone, voice and offline operation on real devices.
