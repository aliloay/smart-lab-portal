"""
Smart Lab Portal API.

Boot order matters: the configuration check runs before anything binds, so a
production deployment cannot start with the development secret key.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import (access, admin, analytics, auth, automation,
                            bookings, issues, labs, notifications, system)
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.schema_check import check_schema, is_alembic_managed
from app.db.session import Base, SessionLocal, engine, get_db
from app.models import Role, User
from app.services import integration
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
    openapi_url=f"{settings.API_V1}/openapi.json",
    docs_url=f"{settings.API_V1}/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, labs.router, bookings.router, access.router,
          admin.router, issues.router, notifications.router, system.router,
          automation.router, analytics.router):
    app.include_router(r, prefix=settings.API_V1)


@app.get(f"{settings.API_V1}/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    """Unauthenticated liveness probe for Docker. Reveals nothing sensitive."""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "time": datetime.now(timezone.utc).isoformat(),
    }


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
