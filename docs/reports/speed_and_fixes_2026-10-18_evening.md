# Speed and fixes - 2026-10-18 (afternoon / evening)

Measured on the live portal (http://192.168.1.200) from the laptop, same scripts before and after.
Navigation: `frontend/e2e/nav_smooth.mjs` (sidebar click -> page loaded; main-thread freeze = browser long
tasks). Raw files: `docs/reports/nav_before_20261018.json`, `nav_after_20261018.json`, `perf_final_20261018.json`.

## Portal navigation (live)
| Page | Loaded before | after | Frozen before | after | Root cause fixed |
|---|---|---|---|---|---|
| IoT Dashboard | 12.9 s | 1.7 s | 4.6 s | 0.13 s | 3D scene per 64x48 thumbnail; `/monitor` 1.9 s query |
| Operations Center | 3.9 s | 0.8 s | 0.5 s | 0.4 s | `/analytics/operations` (PC metrics drawn as environment) |
| Lab Equipment | 4.0 s | 0.6 s | 0 | 0 | |
| Bookings | 2.8 s | 0.7 s | 0.8 s | 0 | `/bookings` 117 queries -> 5 |
| Access & audit | 1.5 s | 0.7 s | 0.8 s | 0.06 s | |
| Security camera | 2.35 s | 0.34 s | 0.09 s | 0 | |
| System analytics | 1.5 s | 0.8 s | 0.96 s | 0 | |

## API (live, p50)
| Call | Before | After |
|---|---|---|
| `/monitor` (IoT Dashboard, Live monitor) | 1 939 ms | latest-reading query 1 200-1 600 -> 57-60 ms |
| `/bookings` | 753 ms | 43 ms (identical output, 23 bookings) |
| `/analytics/operations` | 1 265 ms | ~600 ms (environment chart no longer loads 12 285 PC readings) |
| Face ID status / preview (backend -> face server) | 68 / 68 ms | 54 / 49 ms (kept-alive connection: 38-51 -> 8-10 ms per hop) |

## ESP32 boards (USB on the laptop)
| Board | Before | After |
|---|---|---|
| ESP32-CAM (COM7) | restored old binary: 2.17-2.65 frames/s, 394-463 ms per frame | repository source, core 3.2.1: 2.7-2.9 frames/s, 360 ms, 0 failed |
| ESP32-CAM, 2 frames in flight (tested, not kept) | - | 2.77 frames/s but 637-662 ms per frame + failures |
| Consumables bin (COM9) | bin-0.2: creep 134.80 -> 134.14 g in ~1 h = 30 read as 28-29 | bin-0.3: creep followed, count held 30 (10 min watch); restart keeps the count |
| Reusable bin (COM8) | unchanged (reuse-mod-0.1), online | - |
Door face path (software): camera capture 0 ms, face server ~100 ms (YuNet 16 + SFace 46 + QR 27), master poll 100 ms.
Offline recognition check on stored samples: 72/74 right, 2 refused, 0 wrong person (threshold 0.363 unchanged).

## Defects fixed (all tested; portal fixes deployed f5eaeff-dirty-20261018195132)
* Incident marked resolved but its state left OPEN (9 code paths) - model-level fix + regression test.
* Robots and a camera without picture shown ONLINE / OFFLINE wrongly - now "partly working" (orange) with the reason.
* IoT Dashboard showed the lab's first camera (no picture) as "Offline" while camera 2 worked - picks the working one,
  lists each camera's state; "DEGRADED" was labelled "Offline" in red.
* Operations Center drew the laptop's PC CPU/RAM as lab environment.
* Pop-ups (Add equipment and all others) rendered off-screen under a dimmed page - now on the page body.
* Welcome page skipped after a sign-in that came from an expired session / link - now always shown, then continues.
* Checked security events now leave the list (kept; "Show checked events").
* Robots removed from the staff/admin sidebar (under Lab Equipment); robot card: Full view at the top, joint bars under
  the twin, Home + STOP only (details folded); full view: Home, STOP and joints on the right.
* Add equipment: choose the system first (environment / PC / robot / consumables existing or new bin / reusables / other).
* Face ID preview: one missed frame no longer shows "camera not reachable".

## Not done / needs the owner
* Security-camera services still run the morning code (owner chose not to restart now); the tracking/identity fixes
  (213 tests passed) go live with `launch.bat` / a service restart.
* Door master and environment node not connected - their checks are pending.
* Admin password still the published seed password.

## Late evening (all five ESP32 boards powered; live version f5eaeff-dirty-20261018232259)
Tests: backend 539 passed (full suite), vision 213, knowledge 40, robot monitor 41, PC agent 5; e2e robot_readiness
and reliability ALL PASS; npm audit 0; backend log 0 errors (2 h). Migration b7c3e1f9a204 (index) applied after the
isolated restore-and-migrate drill passed.

| Path (live) | Before | After |
|---|---|---|
| Sign-in -> welcome | 2.2 s | 0.8-1.4 s |
| Welcome -> dashboard | 8.4 s (6.1 s frozen: two hidden 3D scenes) | 2.4-2.6 s (0.5-0.9 s frozen) |
| IoT Dashboard (3 rounds, all boards live) | 12.9 s / 4.6 s frozen | 1.3 s median / 0.06 s frozen |
| First robot page in a session | 3D: 2.85 s shader stall + 1.4 s Collada parse | both removed (shader check off in prod, .glb meshes) |
| Search: first result for "UR5" | an old resolved incident | the UR5e device; results 0.47-0.6 s |
| Live assistant "robots / cameras" | said "online" for robot-less collector / picture-less camera | "partly working" + reason, 48-73 ms |
| Live assistant "temperature" | data-source overview | ENV_LAB01 readings, 0.3-0.8 s |
| Live assistant "how many resistors" | language model, 213 s, "cannot answer" | 30 pieces, 0.05-0.13 s |
| API, 1 user / 10 users + 2 viewers | 36/99 ms; 121/376 ms | 36/106 ms; 103/406 ms, 0 errors (now with all boards + camera 2 live) |

Hardware observed on the bench (physical): door - 3 grants RFID + face (distance 48-63 of 70), 2 correct
denials (another person's finger), relock ~4.5 s; master log: fingerprint flips DOWN/ok ~1.5x/min and the
master briefly loses the ESP32-CAM (the laptop reaches it in 87 ms, 0/100 failed) -> suspected power/ground
since the master moved to laptop USB; LEDs dark on grant/deny -> wiring/ground (not software).
Environment node: 26.4-26.7 C, 54.5-55.5 %, PIR motion 0/1, smoke/flame 0 (not provoked), ~11 s per metric.
Bins: consumables 30 (bin-0.3), reusable all components OK, lid closed (NFC/servo not exercised).
Fixed: component faults need 45 s (no more 10-30 s flapping alarms); environment node chosen over a bin;
bin freshness from the last reading; assistant status/environment/stock answers; search order + PC link.

## 2026-10-19 00:00-01:15 - bench check (no repository code changed)
* Deployed version unchanged: f5eaeff-dirty-20261018232259; DB at b7c3e1f9a204. Ports: COM6 door master (CP210x),
  COM7 ESP32-CAM, COM9 environment node (both CH340); bins on external power.
* Security-camera services restarted on the owner's approval (new tracking code live). Camera 2 was down ~8 min
  (00:39:40-00:48:06) because of two failed launch attempts; the launch.bat form (`cmd /k call ...bat camera2.env`)
  started it in 17 s. Camera 2 now: 14.6 frames/s in, 6.99 analysed, frame age 36/99 ms, detection 53 ms (was 77).
  Camera 1: RECONNECTING with backoff ("could not open the stream") - camera at the university.
* Door master 5-min log: fingerprint DOWN/OK 6/7 transitions (10 s self-test, AS608 over UART 16/17), 7 single
  "camera unreachable" (one /status request > 800 ms; the camera counts as down only after 10 s). RFID self-test
  every ~3.2 s as designed. No software cause found in the fingerprint path; supply/wiring of the AS608 not
  recorded in the bring-up log -> physical check. Door firmware not changed (project rule).
* ESP32-CAM: 1.48 frames/s, 685 ms gaps now (2.7-2.9 / 360 ms last night). Face server 161-176 ms on a real
  frame (unchanged). One-write upload variant tested (owner approved): 1.52 frames/s, 745-887 ms -> no gain,
  previous build restored. Extra 10 Hz status polling: no change -> not the master's polling. Ping: ESP32-CAM
  avg 178 ms (max 400) vs master/environment 9-10 ms, router 0 ms; camera RSSI -20 dBm (very close to the
  router). Suspected power (laptop USB) or receiver overload at very short range - physical check.
* 10 users + 2 viewers rerun 3x: p95 274 / 302 / 350 ms, 0 errors (406 ms last night at CPU 72 %) -> variance.
  /equipment alone 64 ms (23 queries); its tail under load is the single backend process (~20 req/s), not a defect.
* e2e reliability + robot_readiness ALL PASS after the camera restarts; /admin/security 0.4 s, IoT Dashboard 1.07 s.
* Admin still on the published seed password (sign-in with it succeeds; not printed).

## 2026-10-19 01:15-01:40 - remaining issues isolated (no repository code changed)
* ESP32-CAM split (camera's own [PERF], 3 x 10 s): capture 0 ms, upload+reply 504-600 ms, 0 failed; face server
  ~160-180 ms -> ~350-420 ms on the Wi-Fi link. Ping 32 B avg 178 ms vs 1400 B avg 164 ms: size-independent, so a
  per-packet delay, not bandwidth (JPEG size / copies / HTTP are not the cause). The camera's RSSI was -31..-34 dBm
  when fast (2.9 frames/s, 30 ms ping) and -20 dBm now (moved next to the router). Next physical check: move it
  1.5-2 m from the router (then its own 5 V >= 1 A supply) and re-measure.
* Fingerprint: the 45 s confirmation works (22 alarms in the hour before it, 7 confirmed outages 00:00-01:15,
  grouped in incident #644). The confirmed outages last ~46-80 s (several failed 10 s self-tests in a row) ->
  real loss of communication with the AS608; physical check (VCC at the sensor at rest/scan, GND common with the
  ESP32, TX/RX on GPIO16/17).
* LEDs (source): grant -> GPIO14 HIGH (green); deny -> GPIO15 HIGH (red via 220 ohm) and GPIO21 HIGH (red LED +
  buzzer via NPN). Physical check: 3.3 V on those pins during a grant/deny; LED polarity and GND.
* Environment: snapshot every 10 s by design (SNAPSHOT_INTERVAL_MS = 10000, routine gap 10.7 s); changes go at once
  (26 motion changes in 3 h, fastest 0.28 s off-cycle). Readings 5 s old.
* Consumables: 30, VALID, no transaction in 6 h. Raw weight +2.2 g after the move to external power (~22:05),
  handled by the boot check ("changed") and the portal's confirmed count; stable within 0.34 g since 23:00.

## 2026-10-19 01:30-01:50 - owner bench actions (physical)
* ESP32-CAM moved away from the router (and off laptop USB - both changed at once): 2.5 frames/s, gap p50 403 ms
  (p95 534, 0 errors, 75 frames / 30 s), ping avg 67 ms (was 1.48-1.97 frames/s, 517-685 ms, 178 ms).
* Door: grant 01:30:57 (face distance 32.8 of 70), relock 4 s; denial 01:31:17 WRONG FINGER - correct.
* Common GND added: fingerprint still DOWN twice in 120 s -> not the ground alone; hum quieter -> loose /
  high-resistance connection suspected (owner). One 120 s capture showed a burst of ~11 600 serial lines,
  then 5 normal lines / 15 s - unexplained (electrical noise on the serial line possible, not confirmed).
* Reusable bin (physical): 2 checkouts through the bin (lid opened), 1 NFC scan -> lid opened for return; staff
  return records only (no lid, by design); the scanned Breadboard 2 closed Breadboard 1's checkout (swap rule
  for identical items); "weight does not match" correct - both breadboards went in (2 x 32.7 g expected 1).
  All three breadboards AVAILABLE. Portal wording added: a staff return does not open the bin (deployed
  f5eaeff-dirty-20261019014650).

## 2026-10-19 02:00-03:40 - portal refresh and both AI assistants (deployed f5eaeff-dirty-20261019033453)
* Serial "burst" explained: all ~860 garbled bytes arrive in the first second after opening COM6 (the USB-serial
  driver's backlog); then 62 normal lines / 120 s. Laptop-side artefact, not the master.
* Refresh of the System overview: 18 API calls at once through 6 browser connections (HTTP/1.1 over http://)
  into one backend process. Fixed: /ai/status answered from cache with background refresh (was a herd of
  Ollama checks), /emergency/active one query for all labs (was 11). Slowest call 1.3-1.6 s -> 0.85-1.0 s quiet,
  ~1.2 s while an AI answer runs (before: requests up to 8.7 s during AI answers). Remaining limit: http:// allows
  6 connections - HTTPS (CA on the lab browsers) would let all calls share one connection.
* AI on the graphics card (owner approved after A/B; CLAUDE.md rule updated): qwen2.5:1.5b for both assistants,
  num_gpu not forced to 0, kept loaded 24 h. Knowledge model: CPU first word 46.5 s / total 67.9 s ->
  GPU warm 0.1 s / 3.0 s (43.5 tokens/s); camera 2 6.97-6.98 analyses/s during the test (6.35 during the CPU run).
  Live: knowledge answers 3.4 s (first word ~2 s); lab-data model answers 12.6 s (were 157-231 s, one 212 s).
  Backups: backups/gpu-ai-20261019/ (.env, knowledge config). Revert: OLLAMA_CPU_ONLY=true + llm_on_cpu true.
* Lab-data assistant: "what lab is ready now" -> instant free-labs answer (0.2 s, was 212 s); questions about the
  current state no longer go to the documents lookup (an unrelated chat-log quote) but to the model with live data.
* AI tests pinned to their own model settings (they had followed the live .env). Tests: agent/AI 40 passed,
  emergency + agent + AI 66 passed.
* Project-knowledge answer to "why do we have 2 security cameras" stays generic because the documents do not
  state the reason (docs/camera-identity/TWO_CAMERAS.md describes how, not why) - owner to add the reason.
