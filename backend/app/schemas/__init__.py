"""Pydantic request/response models."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (AccessResult, AlertSeverity, AssetStatus,
                              AuthMethod, BookingStatus, DeviceType, EventType,
                              Role)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth ------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    user_id: int
    full_name: str


class UserOut(ORM):
    id: int
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    auth_subject: Optional[str] = None
    student_id: Optional[str] = None
    department: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: Role = Role.STUDENT
    auth_subject: Optional[str] = None
    student_id: Optional[str] = None
    department: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    auth_subject: Optional[str] = None
    department: Optional[str] = None


# --- labs ------------------------------------------------------------------
class LabOut(ORM):
    id: int
    code: str
    name: str
    description: str
    location: str
    capacity: int
    category: str = "General"
    has_controller: bool = False
    exclusive_booking: bool
    require_booking_for_rfid: bool
    is_active: bool


class LabCreate(BaseModel):
    code: str
    name: str
    description: str = ""
    location: str = ""
    capacity: int = 1
    category: str = "General"
    has_controller: bool = False
    exclusive_booking: bool = True
    require_booking_for_rfid: bool = False


class LabStatus(BaseModel):
    lab: LabOut
    occupied: bool
    current_booking_id: Optional[int] = None
    current_users: list[str] = []
    # None everywhere means "no data reported", never a fabricated value.
    door_closed: Optional[bool] = None
    controller_online: Optional[bool] = None
    camera_online: Optional[bool] = None
    next_booking_at: Optional[datetime] = None


# --- bookings --------------------------------------------------------------
class BookingCreate(BaseModel):
    lab_id: int
    start_time: datetime
    end_time: datetime
    reason: str = ""


class BookingOut(ORM):
    id: int
    user_id: int
    lab_id: int
    start_time: datetime
    end_time: datetime
    reason: str
    status: BookingStatus
    created_at: datetime

    # Actual use, not just the reservation.
    first_entry_at: Optional[datetime] = None
    last_entry_at: Optional[datetime] = None
    entry_count: int = 0

    lab_name: Optional[str] = None
    lab_code: Optional[str] = None
    lab_category: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    # Minutes between the booked start and the real first entry. Positive is
    # late, negative is early, None means they never came.
    entry_delay_minutes: Optional[int] = None
    # An occupancy session for this booking that has not been closed yet.
    currently_inside: bool = False


class SessionOut(ORM):
    """
    One occupancy span - when somebody was actually inside the room.

    Distinct from a booking: a booking is an intention, a session is evidence.
    """
    id: int
    lab_id: int
    user_id: int
    booking_id: Optional[int]
    entry_method: AuthMethod
    started_at: datetime
    ended_at: Optional[datetime]
    user_name: Optional[str] = None
    lab_code: Optional[str] = None
    duration_minutes: Optional[int] = None


class QrOut(BaseModel):
    booking_id: int
    token: str
    qr_png_base64: str
    valid_from: datetime
    valid_until: datetime
    status: BookingStatus
    lab_code: str
    lab_name: str
    is_currently_valid: bool


# --- access (device-facing) ------------------------------------------------
class ValidateQrRequest(BaseModel):
    lab_id: str = Field(description="Lab CODE, e.g. LAB_02")
    qr_token: str
    device_uid: Optional[str] = None


class ValidateRfidRequest(BaseModel):
    lab_id: str
    uid_hex: str
    device_uid: Optional[str] = None


class ValidateResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    user_id: Optional[int] = None
    auth_subject: Optional[str] = None
    display_name: Optional[str] = None
    booking_id: Optional[int] = None
    lab_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class DeviceEventRequest(BaseModel):
    lab_id: str
    device_uid: Optional[str] = None
    event_type: EventType
    auth_subject: Optional[str] = None
    booking_id: Optional[int] = None
    method: Optional[AuthMethod] = None
    result: Optional[AccessResult] = None
    reason: Optional[str] = None
    message: str = ""
    metadata: Optional[dict[str, Any]] = None


class HeartbeatRequest(BaseModel):
    device_uid: str
    lab_id: str
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None
    door_closed: Optional[bool] = None


# --- events ----------------------------------------------------------------
class EventOut(ORM):
    id: int
    event_type: EventType
    lab_id: Optional[int]
    user_id: Optional[int]
    booking_id: Optional[int]
    device_id: Optional[int]
    method: Optional[AuthMethod]
    result: Optional[AccessResult]
    reason: Optional[str]
    message: str
    created_at: datetime
    user_name: Optional[str] = None
    lab_code: Optional[str] = None


# --- devices / assets / alerts ---------------------------------------------
class DeviceOut(ORM):
    id: int
    device_uid: str
    name: str
    device_type: DeviceType
    lab_id: int
    ip_address: Optional[str]
    firmware_version: Optional[str]
    last_seen_at: Optional[datetime]
    is_online: bool
    door_closed: Optional[bool]


class DeviceCreate(BaseModel):
    device_uid: str
    name: str
    device_type: DeviceType
    lab_id: int
    ip_address: Optional[str] = None


class AssetOut(ORM):
    id: int
    asset_tag: str
    name: str
    category: str
    lab_id: int
    status: AssetStatus
    notes: str


class AssetCreate(BaseModel):
    asset_tag: str
    name: str
    category: str = ""
    lab_id: int
    notes: str = ""


class AlertOut(ORM):
    id: int
    lab_id: Optional[int]
    severity: AlertSeverity
    title: str
    detail: str
    is_resolved: bool
    created_at: datetime


class SensorReadingOut(ORM):
    id: int
    lab_id: int
    metric: str
    value: float
    unit: str
    recorded_at: datetime


class AdminSummary(BaseModel):
    total_labs: int
    occupied_labs: int
    active_bookings: int
    upcoming_bookings: int
    granted_today: int
    denied_today: int
    devices_online: int
    devices_total: int
    open_alerts: int
