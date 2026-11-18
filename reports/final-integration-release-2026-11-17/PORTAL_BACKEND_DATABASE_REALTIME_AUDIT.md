# Portal, backend, database and realtime audit

## Fixed in this release
| Issue | Root cause | Fix | Evidence |
|---|---|---|---|
| /api/health reported a 28 Oct build (1be41ab) or "unstamped" | a git-ignored app/build_info.json was copied into hand-built images; worktree builds had none; `docker compose build` builds nothing (Compose v5) | stamp from build args (ENV SMARTLAB_BUILD_*); file excluded via .dockerignore; deploy.py uses `docker build`; tools/deploy/build_images.ps1; web app serves /version.json | LIVE: health + /version.json = df3407f-20261118094636; 4 tests |
| Incidents list polled every 20 s was heavy | every row in the 30-day window was built in Python before state/lab filtering | state/lab filtered in SQL (same meaning as state()); only page rows built; view=summary; keyset cursor (limit, before, next_cursor; URL-safe); portal "Load older" | 4 new tests; LIVE numbers below |
| Claude's cap-after-filter fix (5314195) | - | integrated and kept (total / truncated) | test_state_filter_is_applied_before_the_row_cap |

## Database (PostgreSQL 16; EXPLAIN (ANALYZE, BUFFERS), LIVE, read-only)
| Query | Plan | Time |
|---|---|---|
| incidents 30-day window (380 rows) | seq scan + sort, 47 buffer hits | 1.4 ms |
| incidents ACTIVE (195 rows) | bitmap scan on ix_alerts_is_resolved | 1.3 ms |
| newest reading per lab/metric (environment.py) | index scan (recorded_at, or the composite index for a silent metric) | 2-4 ms |
| automation.sensor_evaluation latest per (lab, metric) | parallel seq scan of 166,862 rows | **84 ms**, every 10 min (n8n 08): P3, not changed |
Table sizes: sensor_readings 166,862 rows / 44 MB; robot_events 25,972; audit_logs 18,919; notifications 6,525;
alerts 765. Conclusion: the database is not the bottleneck. The endpoint cost was Python row building and JSON, which
the incidents change removes. Data retention: nothing was deleted or truncated.

## Realtime (WebSocket push -> painted card; isolated copy, release images, headless Chrome)
| Condition | n | median | p95 | max | problems |
|---|---|---|---|---|---|
| single viewer | 30 | 26 ms | 35 ms | 47 ms | 0 |
| plus 10 concurrent staff clients, 113 req/s, 0 errors | 30 | 261 ms | 359 ms | 383 ms | 0 |
"problems = 0" means: every accepted report pushed exactly once, the page never reloaded, a rejected report (401)
pushed nothing, and a stale node showed "Bin offline". Class: LIVE LOCAL SOFTWARE (isolated, SYNTHETIC device
reports), not device-sample-to-portal (that needs the lab). 113 req/s is far above a real lab's load and shows the
saturation of a single uvicorn process; it is not a defect at lab scale.

## Role-based portal (isolated copy, seeded accounts with random per-run passwords)
- navigation.mjs: **98 checks, 0 problems**: student, lab staff and admin menus, direct links, reloads, back/forward, expired session -> sign-in.
- workflows.mjs: **30 passed, 0 problems**: booking -> QR, staff booking, issue with photo, phone width.
- Real-account click-through: BLOCKED (real passwords are not available to agents and are not requested).

## Remaining (not changed, with reason)
- **Alerts payload** (~1.3 KB/alert, 63.9 KB for 50, p50 10.4 ms): P3. Gzip on the wire is already about 10x; no user-visible delay.
- **Sensor-evaluation scan** (84 ms / 10 min): P3. A real fix needs an index on (lab_id, metric, id) and a migration; not worth it at current size.
- **robotModels chunk** 689 kB (178 kB gzip): already lazy-loaded on robot pages only.
- **Single uvicorn worker**: fine at lab load. Adding workers would need the in-process caches and rate limits reviewed first.
