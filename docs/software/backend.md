# Backend

FastAPI 0.143 on Python 3.11 (`backend/Dockerfile`, `python:3.11-slim`), SQLAlchemy 2.0, Alembic 1.14, PostgreSQL 16 (psycopg 3), served by uvicorn on port 8000 behind nginx.

| Area | Location |
|---|---|
| App entry, middleware, WebSocket `/ws/activity` | [`backend/app/main.py`](../../backend/app/main.py) |
| Routes (33 modules, 329 operations) | [`backend/app/api/routes/`](../../backend/app/api/routes/) · reference: [api-reference.md](api-reference.md) · spec: [openapi.json](openapi.json) |
| Auth and role dependencies, device keys | [`backend/app/api/deps.py`](../../backend/app/api/deps.py), [`backend/app/core/security.py`](../../backend/app/core/security.py) |
| Settings (all from environment / `.env`) | [`backend/app/core/config.py`](../../backend/app/core/config.py) |
| Models (42 tables) | [`backend/app/models/tables.py`](../../backend/app/models/tables.py) · [database-schema.md](database-schema.md) |
| Migrations (applied by the API at start) | [`backend/alembic/versions/`](../../backend/alembic/versions/) |
| Services: access, sessions, devices, security, robots, automation, AI, reports, scan, notifications, storage | [`backend/app/services/`](../../backend/app/services/) |
| Tests (753 passed, 2 skipped on 9 Nov 2026, against `smartlab_test`) | [`backend/tests/`](../../backend/tests/) |

Run the tests (they never touch the live database: `conftest.py` forces `smartlab_test`):

```powershell
docker compose run --rm --no-deps -T -v "${PWD}\backend:/app" backend python -m pytest -q -p no:cacheprovider
```

Design rules visible in the code: devices only report (HTTP with a per-device key); the backend decides rules and alerts; there is no endpoint that commands a robot controller; health reports only what the database and live sockets show (a device that never reported is not shown as healthy).
