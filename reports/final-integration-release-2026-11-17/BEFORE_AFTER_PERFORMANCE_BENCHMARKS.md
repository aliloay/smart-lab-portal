# Before / after performance benchmarks

Method: 20 requests per endpoint from inside the backend container, first request discarded, staff/admin JWT minted
in-process (never printed). Raw data: `performance_metrics.json`.

**Caveat:** the BEFORE run (00:15) had the backend test suite running at the same time in another container. The
AFTER run (09:55) did not. The cleanest comparison is therefore summary vs full rows **in the same AFTER run**.

## Incidents (the request the portal polls every 20 s)
| Request | Run | p50 | p95 | Raw bytes | Gzip on the wire |
|---|---|---|---|---|---|
| /incidents?state=ACTIVE (old page request, full rows) | BEFORE (old images, under load) | 32.4 ms | 42.4 ms | 134,813 | - |
| /incidents?state=ACTIVE (full rows) | AFTER (release) | 23.4 ms | 26.7 ms | 134,418 | 11,685 |
| **/incidents?state=ACTIVE&view=summary (new page request)** | AFTER (release) | **20.0 ms** | **20.7 ms** | **81,353** | **6,961** |
| /incidents (all states) | BEFORE | 56.3 ms | 77.8 ms (p99 2,541) | 268,670 | - |
| /incidents (all states) | AFTER | 36.4 ms | 38.2 ms (p99 38.8) | 263,740 | - |

- Same-run effect of summary rows: **-39 % raw bytes, -40 % bytes on the wire, -15 % p50**.
- The faster full-row figures AFTER partly come from no concurrent test load, and partly from SQL-side state filtering (fewer rows built).
- Class: LIVE LOCAL SOFTWARE.

## Other endpoints (AFTER, release images, for the record)
alerts?limit=50 10.4 / 11.4 ms (63,878 B) · devices 16.0 / 20.3 ms · bookings 11.0 / 22.0 ms · summary 5.6 / 6.7 ms ·
security/cameras 4.0 / 4.2 ms · system/services 11.7 / 14.9 ms · health 3.4 / 5.7 ms (p50 / p95).

## Frontend
- First-load motion chunk 26.32 kB gzip (Claude's LazyMotion change, from 38.5 kB; verified in the release build).
- Entry index 81.3 kB gzip.
- Robot models / charts / three.js stay route-split.

## Realtime
- Single viewer: median 26 ms / p95 35 ms.
- Under 10-client load (113 req/s): median 261 ms / p95 359 ms, 0 problems.
- See PORTAL_BACKEND_DATABASE_REALTIME_AUDIT.md.

## Camera / labmap (from Argon, HISTORICAL REPLAY, not re-measured live)
- Register write 11.8 -> 8.6 ms.
- 17 Nov replay: 35 false cross-camera links -> 0.
- Same-person pairings: camera 1 663 -> 799, camera 2 732 -> 873.

## AI
See AI_RAG_VOICE_ASSISTANT_LATENCY_AUDIT.md.
