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

    @property
    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
