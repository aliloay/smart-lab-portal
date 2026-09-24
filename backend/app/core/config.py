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

    @property
    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
