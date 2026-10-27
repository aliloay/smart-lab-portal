# Smart Lab - AI agent, speed and markers report (2026-10-27, evening)

Labels: **tested offline** = automated tests on the isolated copy (`smartlab_test` / `smartlab_perf_test`);
**live-verified** = measured on the running portal; **not tested** = still needs the owner / a real phone.

## 1. Local model benchmark (finished; model kept: qwen2.5:1.5b)
End-to-end, 52 questions, through the portal's own route (instant answers -> tool router -> local model), CPU, cameras
not streaming (tested offline):

| Model | Accuracy | Median | p95 | Model-path median |
|---|---|---|---|---|
| **qwen2.5:1.5b (kept)** | **86.5 %** | 0.66 s | 24 s | 2.2 s |
| qwen3:1.7b | 80.8 % | 0.10 s | 21 s | 2.1 s |
| qwen2.5:3b | 88.5 % | 0.14 s | 46 s | 3.9 s (measured during a build) |

Raw screening of 11 more models: all below 62 %. 15 unused models removed (~15 GB); kept qwen2.5:1.5b + nomic-embed-text.

## 2. Agent upgrades (tested offline)
- **Instant answers** (database, no model): added compare-with-previous-period, today's summary vs yesterday, low stock,
  recent activity (door, alerts, robots, 24 h), today's bookings, who is where / empty labs. Existing: reports, occupancy,
  environment, stock, robots / PCs / cameras status, open alerts, open maintenance, offline devices, system health, bookings.
  Lab-vs-lab questions are excluded from "compare". 52-question routing: one change (the compare question became instant).
- **Phone assistant**: "what is wrong?" now gives a verdict from the target's record (stale / offline telemetry, safety
  mode, simulation, open alerts on that device, low or uncalibrated stock) or says what was checked; "tell me more",
  joints, stock, people (ticket-bound face match) and follow-ups unchanged.
- **Proactive suggestions** (`/api/insights/proactive`, also in "any suggestions?"): CONFIRMED (offline devices, low stock,
  recurring problems) vs POSSIBLE (sensor value with robust z >= 4 against its own 7 days; door entries x3 or zero vs the
  week before), each with evidence and timestamps, de-duplicated, recomputed only when the data fingerprint changes and
  at most once a minute. No root causes are invented.
- **Tool gateway** (`services/tool_gateway.py`, `/api/ai/tools`): 9 read-only tools with typed, bounded schemas; strict
  validation for API/MCP, clamping for the portal's own model; staff only; own DB session with an 8 s timeout; every
  call audited (`LAB_TOOL_CALL`). Door / relay / robot motion are not tools and are refused by name.
- **MCP server** (`tools/mcp_server/server.py`, official SDK `mcp` 2.3.0 in a git-ignored venv, owner consent 2026-10-27):
  stdio only, read-only annotations, thin front to the gateway; the portal does not depend on it.
  `test_mcp_e2e.py`: 8/8 PASS (list 42 ms, call 43 ms; out-of-range and `unlock_door` refused).
- **Knowledge**: citations carry the source file's last-change date; the same passage copied into several files is cited
  once. **Feedback**: optional thumbs up/down on answers (`/api/ai/feedback`), stored in the audit log; staff review
  groups down-votes by route with emails / ids / user labels removed. Nothing is trained automatically.

### Regression (tested offline, after the upgrade)
52 questions, qwen2.5:1.5b: **86.5 %** (snapshot 16/23, tools 13/13, unknown 6/6, instant 10/10) - baseline kept.
Instant path: median 0.04 s; all database answers <= 0.13 s; the slowest instant item is the document lookup (0.30 s,
knowledge service). Model path: median 1.9 s, p95 30 s. Errors 0.

## 3. Portal speed (measured in real Chrome with the GPU, isolated copy)
Cause found: every card, the top bar, the sidebar and lab chips used a live `backdrop-filter` blur, and the page
background was `background-attachment: fixed` - painting work on every scroll frame (no JavaScript long tasks).
Charts were built mid-scroll when they came near the screen (55-63 ms long tasks).

| Fast wheel scrolling, 6 heavy pages | Before | After |
|---|---|---|
| frame p95 | 33.4 ms | **16.8 ms** (60 fps) |
| worst frame | 233 ms | 67 ms |
| long tasks while scrolling | 2 | **0** |

Welcome -> Skip -> dashboard drawn: 0.28-0.47 s. Sidebar pages: 0.08-0.35 s to content (first /admin/system 0.68 s).
Robots & PCs tab: 0 frames over 50 ms idle with live data and while scrolling. Reliability briefing (3.5 s per call)
cached 30 s.

## 4. Markers
`SmartLab_10_Scannable_QR_Images.zip` - the owner's 10 object pictures with the real QR (portal encoder, ECC H) in each
white panel (door: sticker below the handle), upscaled 6x with the QR drawn at full resolution. jsQR 80/80 (sizes,
blur, rotation, dim, JPEG 40), OpenCV 48/50 (both misses at 337 px thumbnail size). Payloads from the live registry:
6 pack payloads verified; CONS_BIN_01 / SEC_NODE_01 do not exist and were replaced by BIN_NODE_1 / SECCAM_LAB01;
added REUSE_BIN_1 and PC_01. Markers page default "Illustrated"; other assets fall back to the pack artwork.
Manifest: `docs/markers_2026-10-27/manifest.json`.

## 5. Not done / needs the owner
- **Not tested on a real phone**: markers scan, face naming speed, spoken answers on the iPhone (fixed: the voice status is
  now read on every device and the browser voice is primed in the tap).
- Phone people boxes over 5G took 3.3 s per round trip; on the laptop the detector answers in 0.06-0.2 s - use the lab Wi-Fi.
- Both-camera sustained acceptance run (camera stalls > 2 s) was not run tonight - cameras were offline for most of it.
- Robot commissioning, password change, offline (Wi-Fi off) test: owner items, unchanged.
