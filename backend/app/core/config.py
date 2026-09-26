"""
Configuration. Everything sensitive comes from the environment; nothing
secret is hardcoded here. See .env.example for the full list.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Smart Lab Portal"
    API_V1: str = "/api"

    # --- database -----------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/smartlab"

    # --- security -----------------------------------------------------------
    # No default in production: start_backend refuses to run with the dev value
    # when ENVIRONMENT=production.
    SECRET_KEY: str = "dev-only-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    ENVIRONMENT: str = "development"

    # --- CORS ---------------------------------------------------------------
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- door / device integration -----------------------------------------
    # The ESP32 master authenticates to the device endpoints with this key
    # rather than a user JWT: it is a device, not a person.
    DEVICE_API_KEY: str = "dev-device-key-change-me"

    # QR tokens are opaque and random.
    #
    # 16 bytes, NOT 32, and the reason is optical rather than cryptographic.
    # Measured module counts at error-correction level Q:
    #
    #     32 bytes -> 47 chars -> QR version 5 -> 45 modules -> 5.78 px/module
    #     16 bytes -> 26 chars -> QR version 3 -> 37 modules -> 7.03 px/module
    #
    # (at a QR occupying 260px of a 640x480 frame, i.e. a phone held at a
    # normal distance from the door camera)
    #
    # 22% more pixels per module is the difference between reliable and
    # intermittent decoding through an OV2640 at jpeg_quality 12. 128 bits of
    # entropy remains overwhelming for a credential that also expires within
    # hours and is bound to one booking and one laboratory - guessing one is
    # not a threat model, photographing one is, and that is handled by the
    # time window rather than by token length.
    QR_TOKEN_BYTES: int = 16

    # Grace either side of a booking window, in minutes. A student arriving a
    # minute early should not be refused; this is a usability allowance and is
    # deliberately small and explicit rather than hidden in the comparison.
    BOOKING_GRACE_MINUTES: int = 0

    # Booking policy
    MAX_BOOKING_HOURS: int = 8
    BOOKING_AUTO_APPROVE: bool = True
    # A booking reminder is raised this many minutes before the window opens.
    BOOKING_REMINDER_MINUTES: int = 15

    # A device that has not sent a heartbeat for this long is offline.
    DEVICE_STALE_SECONDS: int = 90

    # --- issue photos ---------------------------------------------------------
    # Local filesystem storage for the first deployment. The storage service
    # hides the backend, so this can become S3/MinIO without touching issues.
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 12
    MAX_PHOTOS_PER_ISSUE: int = 12
    MAX_PHOTOS_PER_REQUEST: int = 6
    # Larger photos are scaled down to this longest side - still enough to
    # read a serial plate or a burnt trace, a fraction of a raw phone photo.
    IMAGE_MAX_DIMENSION: int = 2560
    THUMBNAIL_DIMENSION: int = 480

    # Hours before an unresolved issue counts as overdue, by severity. A
    # published service level, not a hidden constant, so a report can say
    # what "overdue" means.
    ISSUE_SLA_HOURS_CRITICAL: int = 24
    ISSUE_SLA_HOURS_HIGH: int = 72
    ISSUE_SLA_HOURS_MEDIUM: int = 168
    ISSUE_SLA_HOURS_LOW: int = 336

    # --- automation (n8n) ---------------------------------------------------
    # Everything here is optional. With these unset the portal behaves exactly
    # as before: events are still recorded in the outbox (so a consumer added
    # later can read the history), nothing is pushed, and /api/automation/*
    # answers 503. n8n is never on the door path - it cannot lock or unlock.
    #
    # Key n8n presents in X-Automation-Key when it calls /api/automation/*.
    AUTOMATION_API_KEY: str = ""
    # Base URL of the n8n webhooks, e.g. http://n8n:5678/webhook. Each pushed
    # event goes to {base}/smartlab-{event.type with . -> -}.
    AUTOMATION_WEBHOOK_BASE: str = ""
    # Sent as X-Smartlab-Token on every push; the n8n Webhook nodes check it
    # with a Header Auth credential.
    AUTOMATION_WEBHOOK_TOKEN: str = ""
    # Which event types are pushed. The rest stay in the pull feed only.
    AUTOMATION_PUSH_TYPES: str = ("booking.confirmed,access.denied,"
                                  "issue.created,device.offline,door.alarm")
    AUTOMATION_MAX_ATTEMPTS: int = 6
    # Delivered/skipped outbox rows older than this are pruned.
    AUTOMATION_RETENTION_DAYS: int = 30

    # Rule thresholds the automation API evaluates. Rules live here, in the
    # backend, so n8n never re-implements them.
    DENIAL_WINDOW_MINUTES: int = 10
    DENIAL_WARNING_COUNT: int = 3
    # Offline escalation, minutes since the last heartbeat: level 1 at the
    # stale threshold, level 2 and 3 at these.
    DEVICE_ESCALATE_L2_MINUTES: int = 15
    DEVICE_ESCALATE_L3_MINUTES: int = 60
    # Hours per day a laboratory is bookable - the denominator of the
    # utilisation percentage, stated on the chart rather than hidden.
    LAB_OPEN_HOURS_PER_DAY: int = 10
    # Hours considered "out of hours" by the anomaly rules, in this zone.
    LOCAL_TIMEZONE: str = "Africa/Cairo"
    AFTER_HOURS_START: int = 22
    AFTER_HOURS_END: int = 6
    # metric=min:max, comma separated. Empty side = unbounded.
    SENSOR_THRESHOLDS: str = ("temperature=16:30,humidity=20:70,"
                              "co2=:1000,noise=:85")

    # --- AI assistant (optional) --------------------------------------------
    # Unset = the assistant is off and every AI endpoint says so; nothing else
    # changes. The key is read here only and never sent to the browser.
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-opus-5"
    # Analytics Q&A is not a hard reasoning task; medium keeps it quick and
    # cheap. Raise to "high" if answers feel shallow.
    AI_EFFORT: str = "medium"
    AI_MAX_TOOL_ROUNDS: int = 6
    AI_QUESTIONS_PER_HOUR: int = 30

    @property
    def automation_push_types(self) -> set[str]:
        return {t.strip() for t in self.AUTOMATION_PUSH_TYPES.split(",")
                if t.strip()}

    @property
    def sensor_thresholds(self) -> dict[str, tuple[float | None, float | None]]:
        out: dict[str, tuple[float | None, float | None]] = {}
        for part in self.SENSOR_THRESHOLDS.split(","):
            if "=" not in part:
                continue
            metric, _, rng = part.partition("=")
            lo, _, hi = rng.partition(":")
            try:
                out[metric.strip()] = (float(lo) if lo.strip() else None,
                                       float(hi) if hi.strip() else None)
            except ValueError:
                continue
        return out

    @property
    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
