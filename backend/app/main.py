"""
Smart Lab Portal API.

Boot order matters: the configuration check runs before anything binds, so a
production deployment cannot start with the development secret key.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.routes import access, admin, auth, bookings, labs
from app.core.config import settings
from app.db.session import Base, engine, get_db
from app.ws.manager import manager

log = logging.getLogger("smartlab")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "Smart Laboratory Management Portal.\n\n"
        "Booking, time-bound QR credentials, and the audit trail for the "
        "physical two-factor access-control system. The backend authorizes "
        "and records; the ESP32 master is the only thing that opens a door."
    ),
    openapi_url=f"{settings.API_V1}/openapi.json",
    docs_url=f"{settings.API_V1}/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, labs.router, bookings.router, access.router,
          admin.router):
    app.include_router(r, prefix=settings.API_V1)


@app.on_event("startup")
def _startup() -> None:
    if settings.ENVIRONMENT == "production":
        if settings.SECRET_KEY == "dev-only-change-me":
            raise RuntimeError("SECRET_KEY must be set in production")
        if settings.DEVICE_API_KEY == "dev-device-key-change-me":
            raise RuntimeError("DEVICE_API_KEY must be set in production")
    # Tables are managed by Alembic; create_all is a convenience for the
    # no-Docker quickstart path and is a no-op once migrations have run.
    Base.metadata.create_all(engine)
    log.info("Smart Lab Portal started (%s)", settings.ENVIRONMENT)


@app.get(f"{settings.API_V1}/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "websocket_clients": manager.count,
        "time": datetime.now(timezone.utc).isoformat(),
        "environment": settings.ENVIRONMENT,
    }


@app.websocket("/ws/activity")
async def ws_activity(ws: WebSocket, lab_id: Optional[int] = Query(None)):
    """
    Live activity stream for the admin dashboard.

    Read-only by design: the socket pushes events and accepts nothing that
    changes state. A compromised browser tab cannot inject an access event.
    """
    await manager.connect(ws, lab_id)
    try:
        while True:
            await ws.receive_text()   # keepalive; content ignored
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
