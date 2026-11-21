# Executive summary: independent full audit (21 Nov 2026)

- **Auditor:** Claude (independent session). No other model's reports were read or used as evidence.
- **Inspection window:** 19:06 to 19:40 local (UTC+2), 2026-11-21.
- **Local repository:** `C:\Projects\smart-lab-portal`, branch `fix/pre-lab-hardening`, HEAD `f32d7b33f27a` (5 commits ahead of `origin`).
- **GitHub:** `origin/fix/pre-lab-hardening` = `origin/main` = `35d2a10`. The default branch is `main`. Checked at 19:06 and again at 19:24, unchanged.
- **Running images:**
  - Backend: `a0814c7-20261121185827`.
  - Frontend: `8fcef6f-20261121155020`.
  - `git diff` from those commits to HEAD is empty for `backend/` and `frontend/`, so the live code equals HEAD.

## Bottom line

The software is in a strong, well-tested state. I re-ran every test suite myself and all passed, and the deployed code equals the source. The portal is fast to load.

The project is **not** fully demonstration-verified, for one reason that is not a code defect: the cameras, robots, lab PCs and Hemaly's PC are at GIU. Everything that depends on them is either historical or untested today.

I found:

- One real backend security bug (P1).
- One firmware credential leak (P2).
- Two network address conflicts (P1).
- One AI performance regression: the assistant runs on the CPU although the gate allows the GPU (P1).
- Several retention, monitoring and documentation gaps.

I found nothing that breaks safety. Robot control is `off` in the live backend, and every adapter reports UNAVAILABLE.

## Tests I ran (TESTED – PASSED)

| Suite | Result | Command |
|---|---|---|
| Backend | **887 passed, 3 skipped**, 601 s | `powershell -ExecutionPolicy Bypass -File tools\ops\test_backend_fast.ps1` |
| Security vision | **396 passed** | `py -3.14 -m pytest -q tools/security_vision` |
| Robot monitor | **44 passed** | `py -3.12 -m pytest -q tools/robot_monitor` |
| Knowledge | **64 passed** | `py -3.12 -m pytest -q tools/knowledge` |
| Face server | **22 passed** | `py -3.14 -m pytest -q` in `firmware/face_server` |
| PC agent | **40 passed** | `py -3.14 -m pytest -q` in `tools/pc_agent` |
| Relay | **6 passed** | `py -3.14 -m pytest -q` in `tools/relay` |
| Frontend types | **tsc exit 0** | `npx tsc --noEmit -p frontend` |

I did not run `vite build`. The live image already serves a production build, which I measured directly.

## Top 10 findings

| # | Sev | Finding | Label |
|---|---|---|---|
| 1 | P1 | A recording-play JWT is accepted as an **admin Bearer token** for 10 minutes. `decode_access_token` does not check `typ` (`core/security.py:72`; issued at `routes/security.py:906`). | VERIFIED FROM CODE |
| 2 | P1 | **Overlapping subnets.** The Ethernet (Smart_Lab) and Wi-Fi (Vodafone) interfaces are both on 192.168.1.0/24, and two different routers answer at 192.168.1.1 (two MACs). Traffic reaches the right router only because of interface metrics (10 vs 35). | LIVE-VERIFIED |
| 3 | P1 | **192.168.1.100 conflict.** The FANUC collector targets .100, and Hemaly's PC reported .100 as its own address. | VERIFIED (DB + process args), NEEDS HARDWARE |
| 4 | P1 | **Both camera streams OFFLINE** since 15:50 (317 failed opens each). The IP cameras are at GIU, so no live camera metric is possible today. | LIVE-VERIFIED |
| 5 | P1 | **AI runs on the CPU although the GPU gate says "gpu".** Synthesis answers took 11.7–18.4 s (prompt evaluation 7.7 s). | TESTED (measured) |
| 6 | P2 | The ESP32-CAM `/status` endpoint is unauthenticated and returns the **last booking QR token**, which is reusable for the whole booking window. | LIVE-VERIFIED (value redacted) |
| 7 | P2 | The **consumables bin reads about 60 screws** while the owner reports it empty. The tare values disagree with each other, and the 0.2 g resistor item produces ±1 notification noise. | LIVE-VERIFIED data, NEEDS HARDWARE |
| 8 | P2 | **Backups have no retention** (6.2 GB on C:). They are unencrypted, the uploads tarball of people snapshots is never encrypted, and no restore has been tested. | VERIFIED |
| 9 | P2 | **Vault self-ingests its own repo snapshot:** 322 of 740 source notes are recursive copies. 182 unique broken wikilinks; 335 notes have no inbound link. | VERIFIED (read-only scan) |
| 10 | P2 | **n8n:** no error workflow, no HTTP timeouts, and no retries on the webhook workflows, including emergency. Daily jobs last ran on 18 Nov. | VERIFIED FROM CODE + DB |

## Answers to the 36 questions (short form; details in COMPLETE_CODE_AND_SYSTEM_AUDIT.md)

### GitHub and source control

1. **Is local source fully pushed?** No. Local is 5 commits ahead (`5b458f4`..`f32d7b3`) and 0 behind.
2. **Does GitHub have the same revision?** No. GitHub is at `35d2a10` and local is at `f32d7b3`. There are no remote-only commits, so no conflict.
3. **Uncommitted or untracked changes?** No tracked modifications. There are 8 untracked paths: old handoff and report folders, 3 showcase MP4s and a Gemini report folder.
4. **Sensitive or oversized files tracked?**
   - No `.env`, `secrets.h`, `camera.env`, `robot.env` or `config.json` files are tracked.
   - Oversized: a 37 MB ONNX model, duplicated CAD STEP files (4 copies of about 11 MB), and 422 MB of loose git objects.

### Hardware and networking

5. **Are all five ESP32s connected?** Yes on the network: 5/5 answer ping and all report heartbeats under 30 s old. Only 3 are on USB (COM6, COM7, COM8).
6. **Wi-Fi and packet loss acceptable?** Yes. 20 pings each: 0 % loss, average 8–20 ms, maximum 54 ms (ESP32-CAM). RSSI is not reported by any node, so it is UNVERIFIED.
7. **COM ports correctly mapped?**
   - COM6 is a CP210x, COM7 and COM8 are CH340. This matches the documented mapping (master, bin, CAM).
   - I did not open the ports: COM6 is held by a running serial logger. Board identity is therefore unverified.
8. **Are both networks routed correctly?** They work: Smart_Lab traffic goes out on Ethernet (metric 10) and the internet on Wi-Fi. This depends on metrics, not on the design.
9. **Router, subnet or IP conflict?** Yes, two: the same subnet and gateway IP on both networks, and 192.168.1.100 used by both FANUC and Hemaly's PC.
10. **Empty consumables bin handled accurately?**
    - The code distinguishes these states: the `hx711` flag, `calibrated`, `boot_reading: empty`, and an offline node versus a valid zero.
    - Today's data shows about 60 screws while the owner says the bin is empty. A physical check is needed.

### Cameras and AR

11. **Are both camera services running?** The processes are running and answering on 5100/5101, but neither has a camera picture (stream OFFLINE).
12. **Fast detection and fresh frames?** Not measurable today (`frame_age` is null). The design is a 6 analyses/s target with a stale guard. UNVERIFIED live.
13. **Is body-pose or keypoint tracking implemented?** No. There is no keypoint model; body parts are box-geometry PREDICTED estimates, honestly labelled in code.
14. **Are head and limb measurements trustworthy?** No. They are proportion estimates, not measurements.
15. **How fast is dead-zone recovery?**
    - Not measured live. From code: tracks persist 2 s while moving and 6 s while still; a name waits up to 60 s for handback.
    - Re-acquisition requires look distance ≤ 0.18 and a margin of 0.10.
    - Simulated benchmarks exist (`scenario_bench.py`). No real measurement.
16. **Do the two cameras need batching, stitching or shared tracking?**
    - Not stitching.
    - Shared global tracking already exists (`crosscam.py`, `labmap.py`).
    - Batched inference is the only candidate worth benchmarking. See the plan.
17. **Best measured architecture?** None has been measured on this hardware with live cameras. I recommend keeping the current architecture until the GIU benchmark.
18. **What remains for phone AR?**
    - Object boxes refresh only every 3–6 s, server-side.
    - PCs have no identity mapping without a marker.
    - No client-side box tracking between detections.
    - No measured phone latency.

### AI and knowledge

19. **Which model is loaded?** Three are resident on the CPU: `qwen3:1.7b` (knowledge), `qwen2.5:1.5b` (portal) and `nomic-embed-text`.
20. **Is the config/model mismatch fixed?** Yes for the live configuration: knowledge uses `qwen3:1.7b`, which is installed. `qwen2.5:3b` remains only in `.env.example` comments and tests. CLAUDE.md is stale.
21. **Measured short and long answer latencies?**
    - Lookup route: 99 ms.
    - Guard refusal: 20 ms.
    - Cached repeat: 0 s.
    - Synthesis: 11.7 s (one-liner), 15.7 s (RAG) and 18.4 s (multi-document), all on the CPU.
22. **Can basic WH questions use a direct fast path?** Yes. 58 draft questions are in FAQ_FAST_ANSWER_PROPOSAL.md.
23. **Does Obsidian need more source-backed material?** Little new material is needed. Mainly: remove the 322 recursive mirrors, mirror the n8n JSON, and fix the broken links.
24. **Are the graph and embeddings current?** The index was built 18:01 today (13,292 chunks). That is current except for the 2 commits made after it.
25. **Are citations and grounding reliable?**
    - Citation validation is in place (`citations_valid`), and the guard refused the password question.
    - One synthesis answer contained an invented statement.
    - Partly reliable overall.

### Portal and integration

26. **Is navigation smooth and fast?**
    - Initial transfer is about 227 KB gzip, `index.html` loads in 21 ms, and `/api/health` answers in 14 ms.
    - Routes are lazy-loaded, GETs are deduplicated, and polling is paused when the tab is hidden.
    - Authenticated page timing was not measured (I used no credentials).
27. **APIs and routes free of important regressions?** Yes on tests: 887 backend tests and tsc pass. One security bug was found by code review (F-01).
28. **Are all n8n workflows valid?**
    - Structurally yes: 26 files, no dangling connections.
    - Robustness gaps: no error workflow, timeouts or webhook retries.
    - Live active state is unverified (MCP refused).
29. **Are all 14 PCs and Hemaly's relay correct?**
    - The 14 rows are 9 GIU PCs, Hemaly's PC, the admin laptop and 3 TEST cards.
    - PC-10 still runs agent 0.9.
    - All GIU telemetry is historical (18 Nov).
    - The relay passes its tests but is not live.
30. **Are the robot twins showing current telemetry?** No. Last data was 18 Nov 16:39 UTC. The UI correctly marks this OFFLINE and stale.
31. **Are admin notification and approval reliable?**
    - Mostly. The admin is notified and approval is audited, and the backend tests pass.
    - Edge cases: a staff edit hides a pending account, and pending users see "Account is disabled" (F-17).

### Thesis readiness

32. **Which engineering features are fully verified?**
    - Portal, auth and RBAC (by tests).
    - Door event pipeline and the 5 ESP32 heartbeats (live).
    - Backups run.
    - Knowledge retrieval and guard (live).
    - Robot-control lockout (live).
    - Lazy-loaded frontend.
33. **Which are shown only by historical recordings?**
    - Camera tracking, cross-camera naming, seat/PC occupancy.
    - UR5e/FANUC live twins.
    - PC fleet, screen wall and relay.
    - AR on robots, PCs and the door at GIU.
34. **Which claims have no evidence?**
    - Real dead-zone recovery time.
    - Live ID-switch rate.
    - Phone AR latency and stability numbers.
    - ESP32 RSSI.
    - Full-body pose (not implemented).
    - Restore from backup.
35. **What requires physical attendance at GIU?**
    - Cameras.
    - Robots and the .100 conflict.
    - Hemaly's PC, the relay, PC-10 and PC-11.
    - The AR robot and PC test.
    - Assistant timing with cameras live.
36. **The 10 next actions:** see below.

## The 10 most important next steps (in order)

1. Fix F-01: check the token type and add a test. About 1 hour; deploy.
2. Unload or reload the AI models when the GPU gate flips, then re-measure. Add the FAQ and live fast path for one-line questions.
3. Physically check the consumables scale and re-tare before any "empty bin" demonstration.
4. Fit the 1N4007 flyback diode on the lock, then run 20 relock cycles (see the hardware plan).
5. At GIU: set Hemaly's PC to a static IP outside .100–.103, then verify FANUC (.100) and UR5e (.102) telemetry and both twins.
6. At GIU: run the two-camera live benchmark: frame age, FPS, ID switches, recovery after 1/3/10/30 s gaps.
7. Push the 5 local commits after review; keep the MP4s out of git.
8. Add backup retention, encrypt the uploads tarball, copy nightly to D:, and run one test restore.
9. Clean the vault source list (exclude `docs/knowledge/obsidian/**`, mirror the n8n JSON), then rebuild the index with owner approval.
10. Correct the thesis and demo wording: pose = box geometry, the AR model version is v8, the "14 PCs" composition, the AI device, and the historical versus live labels.
