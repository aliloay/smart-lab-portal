# Thesis readiness and claimable results

Use the evidence class exactly as written. A result without a class is not claimable.

## Claimable now (measured in this integration, 18 Nov 2026)
| Claim | Number | Class |
|---|---|---|
| Backend regression suite | 826 passed, 3 skipped, 0 failed (6 min, isolated in-memory DB) | UNIT TEST |
| Camera / identity suite | 363 passed, 22 skipped, 0 failed | UNIT TEST |
| All other tool suites | 228 passed (knowledge 49, robot monitor 42, UR5e control 20, OPC UA 3, relay 6, PC agent 40, LAN presence 6, ops 28, voice 6, face server 14, door entry 4, benchmarks 6) | UNIT TEST |
| Role-separated portal navigation (student / staff / admin) | 98 checks, 0 problems | LIVE LOCAL SOFTWARE (isolated copy) |
| End-to-end workflows (booking -> QR, issue with photo, phone width) | 30 / 30 | LIVE LOCAL SOFTWARE (isolated copy) |
| Realtime push to painted card, single viewer | median 26 ms, p95 35 ms (n=30) | LIVE LOCAL SOFTWARE, synthetic device reports |
| Same, under 10 concurrent clients (113 req/s) | median 261 ms, p95 359 ms, 0 errors, 0 missed / duplicate pushes | LIVE LOCAL SOFTWARE |
| Incidents list payload (portal request) | 134.4 -> 81.4 kB raw, 11.7 -> 7.0 kB on the wire, p50 23.4 -> 20.0 ms | LIVE LOCAL SOFTWARE |
| Database query plans | key queries 1.3-4 ms; one 84 ms scan every 10 min | LIVE LOCAL SOFTWARE (EXPLAIN ANALYZE) |
| Local LLM (qwen2.5:1.5b) on a GTX 1650 | first token 0.19 s, full answer 0.33 s, 76 tok/s; CPU 0.66 s / 25 tok/s | LIVE LOCAL SOFTWARE |
| LLM answer quality, 11-case golden set | 0.68 mean, 5/11 fully correct, 1 forbidden statement | LIVE LOCAL SOFTWARE |
| Assistant facts answered from records (alarms, access, activity, stock, door state, node capabilities) | 34-71 ms, no model | LIVE LOCAL SOFTWARE |
| Firmware: 7 ESP32 projects compile | 7 / 7 (compile only) | STATIC INSPECTION |
| No physical action reachable from AI / MCP | MCP 9 tools read-only; unlock_door refused | LIVE LOCAL SOFTWARE |

## Claimable only with the label shown (from earlier work, not re-run here)
- **Cross-camera identity:** 17 Nov replay, 24,499 camera observations; false links 35 -> 0; same-person pairings 663 -> 799 (cam 1), 732 -> 873 (cam 2). HISTORICAL REPLAY.
- **Tracking continuity:** 17/17 simulated scenarios pass, with 1 ID switch and 1 fragment after a 25 s dead zone, and 1 of each after 3 min. SIMULATED.
- **AR detector v8:** 17 Nov photos 34/35, camera 283/290. Owner's measurement in commit 4e58b52.

## NOT claimable yet (say "not measured" in the thesis)
- Live two-camera tracking accuracy and ID continuity: no labelled live run.
- Device-sample-to-portal latency on real nodes: needs the lab.
- Student PCs online through the relay: GIU firewall.
- Firmware fixes on the boards: not flashed.
- Door / tablet / TFT behaviour after this release: door firmware unchanged; not re-tested physically.
- Real-account (owner password) click-through: blocked by design.
- "Perfect" anything: there is no ground truth for it.

## Wording guidance
Say **"compiled"**, not "deployed", for firmware. Say **"in an isolated software test with synthetic device reports"**
for realtime numbers. Say **"historical replay"** for the 17 Nov camera figures. Name the evidence class in each
results table.
