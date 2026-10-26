"""
Smart Lab Portal API.

Boot order matters: the configuration check runs before anything binds, so a
production deployment cannot start with the development secret key.
"""
import asyncio
import threading
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core import errors
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import (access, admin, ai, analytics, auth, automation,
                            bookings, commands, emergency, enrollment, equipment,
                            experiments, face_submissions, inventory, issues, knowledge, labs, monitor, robots, workcell,
                            incidents, notifications, reliability, reports_center, reusable, scan, search, security, system, uiperf, voice)
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.schema_check import check_schema, is_alembic_managed
from app.db.session import Base, SessionLocal, engine, get_db
from app.models import Role, User
from app.services import integration
from app.services import provenance  # noqa: F401  (stamps new rows' provenance)
from app.ws.manager import Client, manager

log = logging.getLogger("smartlab")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.ENVIRONMENT == "production":
        if settings.SECRET_KEY == "dev-only-change-me":
            raise RuntimeError("SECRET_KEY must be set in production")
        if settings.DEVICE_API_KEY == "dev-device-key-change-me":
            raise RuntimeError("DEVICE_API_KEY must be set in production")
    # A migrated database must be up to date - create_all on an old schema
    # would add new tables but not new columns, then break the migration.
    # Only an unmanaged database (tests, throwaway quickstart) gets create_all.
    if is_alembic_managed(engine):
        check_schema(engine)
    else:
        Base.metadata.create_all(engine)
    # Sync endpoints run in worker threads; the live stream publishes through
    # this loop from there.
    manager.bind_loop(asyncio.get_running_loop())
    # Optional n8n push. Starts only when AUTOMATION_WEBHOOK_BASE is set, and
    # its failures stay in its own thread - see app/services/integration.py.
    integration.dispatcher = integration.Dispatcher(SessionLocal)
    integration.dispatcher.start()
    # A robot STOP that was never recovered stays latched across this restart (2026-10-18).
    try:
        from app.api.routes.robots import restore_stop_latches
        with SessionLocal() as db:
            latched = restore_stop_latches(db)
        if latched:
            print(f"[robots] STOP still latched after restart for robot id(s) {latched} - admin recovery needed")
    except Exception as e:                          # never block start-up; the robots stay in dry run anyway
        print(f"[robots] could not restore STOP latches: {e.__class__.__name__}: {e}")
    # Optional local AI: load the model now so the first question is quick.
    from app.services import ai
    threading.Thread(target=ai.warm_up, name="ollama-warm-up", daemon=True).start()
    # Service health checks run in the background; requests read the cache (never wait on a probe).
    import os
    if os.environ.get("DEVICE_PROBES", "1") != "0":
        from app.services import health_monitor
        health_monitor.start()
    log.info("Smart Lab Portal started (%s)", settings.ENVIRONMENT)
    yield
    integration.dispatcher.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.1.0",
    description=(
        "Smart Laboratory Management Portal.\n\n"
        "Booking, time-bound QR credentials, laboratory maintenance, and the "
        "audit trail for the physical two-factor access-control system. The "
        "backend authorizes and records; the ESP32 master is the only thing "
        "that opens a door."
    ),
    # The API map is useful in development; off unless EXPOSE_API_DOCS is set
    # (it lists every endpoint to anyone who asks).
    openapi_url=f"{settings.API_V1}/openapi.json" if settings.EXPOSE_API_DOCS else None,
    docs_url=f"{settings.API_V1}/docs" if settings.EXPOSE_API_DOCS else None,
    redoc_url=None,
    lifespan=lifespan,
)
errors.install(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
# Request timing per route (app/services/perfmon.py): pure ASGI, bounded in memory, no DB writes.
from app.services.perfmon import TimingMiddleware  # noqa: E402
app.add_middleware(TimingMiddleware)

for r in (auth.router, labs.router, bookings.router, access.router,
          admin.router, issues.router, notifications.router, system.router,
          automation.router, analytics.router, ai.router, enrollment.router,
          monitor.router, commands.router, face_submissions.router,
          inventory.router, reusable.router, equipment.router, security.router,
          emergency.router, experiments.router, robots.router, knowledge.router, workcell.router, reliability.router, search.router,
          reports_center.router, incidents.router, uiperf.router, scan.router, voice.router):
    app.include_router(r, prefix=settings.API_V1)


@app.get(f"{settings.API_V1}/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    """Unauthenticated liveness probe for Docker. Reveals nothing sensitive."""
    db_time = None
    try:
        # the database's own clock (clock check, tools/evidence/clock_check.py) - doubles as SELECT 1
        db_time = float(db.execute(text("SELECT extract(epoch from clock_timestamp())")).scalar())
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "time": datetime.now(timezone.utc).isoformat(),
        "db_time": db_time,
        "version": _build_info(),
    }


_BUILD: Optional[dict] = None


def _build_info() -> dict:
    """The deployed version (tools/deploy/deploy.py stamps app/build_info.json)."""
    global _BUILD
    if _BUILD is None:
        import json
        import os
        try:
            with open(os.path.join(os.path.dirname(__file__), "build_info.json"), encoding="utf-8") as f:
                _BUILD = json.load(f)
        except (OSError, ValueError):
            _BUILD = {"id": "unstamped", "note": "deployed without tools/deploy/deploy.py"}
    return _BUILD


@app.websocket("/ws/activity")
async def ws_activity(ws: WebSocket, token: Optional[str] = Query(None),
                      lab_id: Optional[int] = Query(None)):
    """
    Live activity and notification stream.

    Authenticated with the same JWT as the REST API, passed as a query
    parameter because browsers cannot set headers on a WebSocket. Staff
    receive every access event; a student receives only their own, plus their
    notifications. Read-only by design: the socket pushes events and accepts
    nothing that changes state.
    """
    payload = decode_access_token(token) if token else None
    user = None
    if payload and "sub" in payload:
        with SessionLocal() as db:
            user = db.get(User, int(payload["sub"]))
            if user is not None and not user.is_active:
                user = None
            if user is not None:
                client = Client(user_id=user.id,
                                is_staff=user.role in (Role.ADMIN, Role.LAB_STAFF),
                                lab_filter=lab_id)
    if user is None:
        await ws.close(code=4401)
        return

    await manager.connect(ws, client)
    try:
        while True:
            await ws.receive_text()   # keepalive; content ignored
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
