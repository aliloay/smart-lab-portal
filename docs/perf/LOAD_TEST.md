# Full-system load test (simulated, isolated)

Repeatable and non-destructive. Nothing touches the live portal, the `smartlab` database, a robot or a
physical camera. All load is **SIMULATED** (sim robots, recorded video, a fake environment node).

## 1. Isolated backend on its own database

```
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" smartlab_loadtest_test'     # once
docker compose run -d --name smartlab-loadtest-backend --no-deps -p 127.0.0.1:8100:8000 backend \
  sh -c 'export DATABASE_URL="${DATABASE_URL%/*}/smartlab_loadtest_test"; case "$DATABASE_URL" in *_test) ;; *) echo REFUSING; exit 1;; esac; alembic upgrade head && python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000'
```

The `case` line refuses to start on any database whose name does not end in `_test`.
`seed.py` creates the demo accounts (public in the repo, test database only).

## 2. Load + measurements

```
set E2E_EMAIL=admin@giu-uni.de & set E2E_PASSWORD=...        (seeded demo account)
py tools/perf/load_simlab.py 120                              # robots, 2 cameras, env node, API latency, CPU/GPU
node tools/perf/ws_clients.mjs http://127.0.0.1:8100 3 90     # WebSocket message rates (run alongside)
```

`load_simlab.py` refuses port 8000. The test cameras use ports 5102/5103 and `--face-server ""` (the
live face server is not called). Their dashboard poll rates are **higher** than the real portal's
(e.g. `/monitor` every 2.5 s, the portal uses 10 s): a worst case.

## 3. Browser under load

```
cd frontend && npx vite build
set VITE_API_TARGET=http://127.0.0.1:8100 && npx vite preview --port 5174 --strictPort
node e2e/perf_portal.mjs http://127.0.0.1:5174 25
node e2e/profile_page.mjs http://127.0.0.1:5174 /command 20
```

Headless Chrome has no GPU: three.js runs in software WebGL, so long tasks on `/command` are inflated.

## 4. Clean up

Stop the preview server and the camera copies, then `docker rm -f smartlab-loadtest-backend`.
The `smartlab_loadtest_test` database may stay; the production database is never dropped.

## Results 2026-10-14 (laptop, live camera 1 also running)

| Measure | Before | After the Command Center fix |
|---|---|---|
| `/command` browser requests/s | 13.5 | 9.4 |
| `/api/monitor` from `/command` | 0.8/s | 0.4/s |
| robot events from `/command` | 1.5/s | 0.7/s |
| API errors under load | 0 | 0 |

Server side, worst-case polling: every endpoint p95 < 260 ms except `/monitor` (p95 0.25-1.0 s while a
browser was also open). `/monitor` costs ~22 ms idle (15 queries) and ~51 ms under load out of process:
host CPU contention from two cameras (system CPU ~69%), not slow queries. Two simulated cameras each
analysed 6.5-6.7 fps on the GPU (pass p95 170-282 ms), GPU ~65%. WebSocket: 9.7 msgs/s, 2.2 KB/s per client.
