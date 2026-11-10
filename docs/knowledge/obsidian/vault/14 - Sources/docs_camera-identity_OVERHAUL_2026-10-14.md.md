---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/camera-identity/OVERHAUL_2026-10-14.md"
source_hash: "378463b2760850d6fadd6a217fa7489c1875f958fa84533359b4f53765b35f35"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/camera-identity/OVERHAUL_2026-10-14.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[tools_security_vision_bench_tracking.py]] - mentioned by docs

# Detection / identity / portal-performance overhaul - 2026-10-14 evening

Checkpoint: branch `snapshot/before-detection-identity-overhaul-20261014` (HEAD 842776e) +
`backups/uncommitted-before-overhaul-20261014.patch` (git-ignored). Nothing below is committed,
deployed, or restarted - each needs the owner's approval (rules of 2026-10-14 evening).

## Verified root causes and fixes (working tree)
| Issue | Evidence | Fix | Tests |
|---|---|---|---|
| Wall screen / IoT dashboard slow; other API calls slowed while it was open | profile: `/monitor` 88 ms, of which `environment.latest_many` 53 ms; EXPLAIN: DISTINCT ON sorted all 21,892 readings (72 ms) every call, growing daily | newest reading per (lab, metric) via LATERAL + existing index: **72 ms -> 2.1 ms** (query), latest_many **92 -> 11.6 ms** on live data, same readings | +1 backend test; env+monitor 24 passed |
| Tracks broke for seated people (names handed over constantly) | live log: NAME_LOST every 6-10 s for USER5; tracker dropped tracks after 2 s missing | still, confirmed tracks survive 6 s; after a gap a box rejoins only if its look is not clearly different (0.65 = the naming veto) | 4 new + 1 deliberately updated tracker test |
| Misleading NAME_LOST log entries | labeler sees only tracks seen in the last 0.6 s | a track back under its own id is removed from "lost" | suite |
| Stale entries could name a stranger by elimination | test entries never get exits; USER2 open 2.2 h, never seen | elimination only for names entered/seen within 30 min | 2 tests |

## Measured (offline replay of real 2026-10-12 footage, same detections, CPU detector; proxies - no labels)
| Segment | people/frame | tracks started | fragmentations (one person -> 2 tracks) | median track life |
|---|---|---|---|---|
| 16:37-16:40 | 1.14 | 20 -> 11 | 10 -> 2 | 7.5 -> 12.3 s |
| 17:17-17:20 | 3.49 | 25 -> 15 | 12 -> 4 | 16.9 -> 52.3 s |
Tool: `tools/security_vision/bench_tracking.py` (caches boxes only, never images).

## Live baseline (one browser, read-only, `frontend/e2e/perf_portal.mjs`)
| Page | req/s | long tasks / 30 s | heap | /api/health while open |
|---|---|---|---|---|
| Security camera | 12.1 (frames 4.4/s, fetch p50 20 ms, proxy 7 ms) | 0 | 13 -> 9 MB | 9-37 ms |
| IoT dashboard | 9.7 | 7 (max 155 ms, page load: three.js twin) | 10 -> 52 MB | 61-264 ms |
| Overview | 3.4 | 0 | | 8-49 ms |
Steady state IoT dashboard: main thread busy 7 % (CPU profile). Camera analysis live: 7.0 passes/s, pass p50 85 ms / p95 106 ms, frame age p50 32-36 ms, GPU 36 %.

## Open decision (conflict between instructions)
The evening mission says "never assign a profile solely because of the usual desk"; earlier the owner asked for
Hemaly to be named at his desk. Current rule: desk names only after the door/face placed him in the lab, only one
seated person at desk scale, yielding to any newer door entry. Proposed: show desk names as TENTATIVE ("Eng. Hemaly?")
until face/door confirms. Owner to choose.

## Not done / needs hardware or approval
Cross-camera association (needs camera 2 + calibration); live re-measure of fragmentation (needs camera restart);
labelled precision/recall (no ground truth exists); IoT dashboard 3D load cost (design choice).

