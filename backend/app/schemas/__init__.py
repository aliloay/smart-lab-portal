"""Pydantic request/response models."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import (AccessResult, AlertSeverity, AssetStatus,
                              AuthMethod, BookingStatus, DeviceType, EventType,
                              IssueCategory, IssueEventType, IssuePhotoStage,
                              IssueSeverity, IssueStatus, Role,
                              SessionEndReason)


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
    created_at: Optional[datetime] = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8)
    role: Role = Role.STUDENT
    auth_subject: Optional[str] = Field(default=None, max_length=32)
    student_id: Optional[str] = None
    department: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    auth_subject: Optional[str] = Field(default=None, max_length=32)
    department: Optional[str] = None
    student_id: Optional[str] = None


class UserBrief(BaseModel):
    id: int
    full_name: str
    role: Role
    auth_subject: Optional[str] = None


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


class BookingSlot(BaseModel):
    """A reserved interval. Identity only for staff or for the booking's owner."""
    booking_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    is_mine: bool = False
    user_name: Optional[str] = None


class LabOverview(BaseModel):
    """One row per lab for the catalogue: everything a card shows, one query."""
    lab: LabOut
    occupied: bool
    occupants: int
    available_now: bool
    controller_online: Optional[bool] = None
    door_closed: Optional[bool] = None
    next_booking_at: Optional[datetime] = None
    bookings_today: int = 0
    open_issues: int = 0
    high_priority_issues: int = 0


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
    component_state: Optional[dict[str, Any]] = None
    lab_code: Optional[str] = None
    # ONLINE / OFFLINE / NO_DATA - NO_DATA means it has never reported.
    state: str = "NO_DATA"
    seconds_since_seen: Optional[int] = None


class LabIssueBrief(BaseModel):
    """What anyone may see about a lab's open problems: no reporter, no text."""
    id: int
    ticket_number: Optional[str]
    title: str
    category: IssueCategory
    severity: IssueSeverity
    status: IssueStatus
    asset_name: Optional[str] = None
    created_at: datetime
    is_mine: bool = False


class LabStatus(BaseModel):
    lab: LabOut
    occupied: bool
    occupants: int = 0
    current_booking_id: Optional[int] = None
    # Names only for staff; everyone else sees a count.
    current_users: list[str] = []
    # None everywhere means "no data reported", never a fabricated value.
    door_closed: Optional[bool] = None
    controller_online: Optional[bool] = None
    camera_online: Optional[bool] = None
    next_booking_at: Optional[datetime] = None
    current_booking: Optional[BookingSlot] = None
    upcoming: list[BookingSlot] = []
    devices: list[DeviceOut] = []
    open_issues: int = 0
    high_priority_issues: int = 0
    recent_issues: list[LabIssueBrief] = []


# --- bookings --------------------------------------------------------------
class BookingCreate(BaseModel):
    lab_id: int
    start_time: datetime
    end_time: datetime
    reason: str = Field(default="", max_length=500)
    # Staff only: book on behalf of someone else.
    user_id: Optional[int] = None


class BookingOut(ORM):
    id: int
    user_id: int
    lab_id: int
    start_time: datetime
    end_time: datetime
    reason: str
    status: BookingStatus
    created_at: datetime
    cancelled_at: Optional[datetime] = None

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
    # Only set when an exit was actually observed.
    last_exit_at: Optional[datetime] = None
    time_inside_minutes: Optional[int] = None
    # Whether a live (unrevoked) credential exists.
    qr_active: bool = False


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
    second_factor: Optional[AuthMethod] = None
    started_at: datetime
    door_opened_at: Optional[datetime] = None
    door_closed_at: Optional[datetime] = None
    ended_at: Optional[datetime]
    end_reason: Optional[SessionEndReason] = None
    user_name: Optional[str] = None
    lab_code: Optional[str] = None
    # Only when an exit was observed; never derived from the door closing.
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


class TokenInfo(BaseModel):
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    revoked_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    use_count: int = 0
    # ISSUED (not yet valid) / VALID / EXPIRED / REVOKED
    state: str


class TraceSummary(BaseModel):
    """The one-screen answer to 'what happened with this booking at the door'."""
    first_factor: Optional[AuthMethod] = None
    first_factor_identity: Optional[str] = None
    qr_result: Optional[str] = None
    second_factor: Optional[AuthMethod] = None
    second_factor_identity: Optional[str] = None
    result: Optional[str] = None          # GRANTED / DENIED / None (no attempt)
    denial_reason: Optional[str] = None
    entry_at: Optional[datetime] = None
    door_opened_at: Optional[datetime] = None
    door_closed_at: Optional[datetime] = None
    exit_at: Optional[datetime] = None
    exit_recorded: bool = False
    session_end_reason: Optional[SessionEndReason] = None
    duration_minutes: Optional[int] = None
    attempts: int = 0
    denials: int = 0


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
    device_name: Optional[str] = None


class SessionTrace(BaseModel):
    """One occupancy session, traced: who, where, both factors, the door."""
    session: SessionOut
    user: "UserBrief"
    lab: LabOut
    booking: Optional[BookingOut] = None
    summary: TraceSummary
    events: list[EventOut] = []


class BookingTrace(BaseModel):
    booking: BookingOut
    user: UserBrief
    lab: LabOut
    token: Optional[TokenInfo] = None
    summary: TraceSummary
    sessions: list[SessionOut] = []
    events: list[EventOut] = []


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
    # Used only when the device is auto-registered by its first heartbeat.
    device_type: Optional[DeviceType] = None
    # Per-component health: {"rfid", "fingerprint", "camera", "relay_locked"}.
    # A false rfid/fingerprint/camera raises an alert (services/devices.py).
    components: Optional[dict[str, Any]] = None


# --- devices / assets / alerts ---------------------------------------------
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
    lab_code: Optional[str] = None
    lab_name: Optional[str] = None
    lab_location: Optional[str] = None
    open_issues: int = 0
    # lifecycle
    serial_number: Optional[str] = None
    holder_id: Optional[int] = None
    holder_name: Optional[str] = None       # staff only
    checked_out_at: Optional[datetime] = None
    last_inspected_at: Optional[datetime] = None
    next_maintenance_at: Optional[datetime] = None
    maintenance_due: bool = False           # next_maintenance_at has passed


class AssetCreate(BaseModel):
    asset_tag: str
    name: str
    category: str = ""
    lab_id: int
    notes: str = ""
    serial_number: Optional[str] = Field(default=None, max_length=64)
    next_maintenance_at: Optional[datetime] = None


class AssetUpdate(BaseModel):
    status: Optional[AssetStatus] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    category: Optional[str] = Field(default=None, max_length=64)
    serial_number: Optional[str] = Field(default=None, max_length=64)
    next_maintenance_at: Optional[datetime] = None


class AssetInspect(BaseModel):
    """A recorded inspection: when, what was found, when the next is due."""
    note: str = Field(default="", max_length=255)
    next_maintenance_at: Optional[datetime] = None


class AssetTransactionOut(ORM):
    id: int
    action: str
    note: str
    created_at: datetime
    user_name: Optional[str] = None


class AssetMaintenanceRow(BaseModel):
    """One line of an equipment's maintenance history. No reporter identity."""
    id: int
    ticket_number: Optional[str]
    title: str
    category: IssueCategory
    severity: IssueSeverity
    status: IssueStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    technician: Optional[str] = None
    resolution_notes: str = ""
    is_mine: bool = False


class LifecycleEntry(BaseModel):
    """One line of an item's life: reported, fixed, inspected, lent, moved."""
    at: datetime
    kind: str       # ISSUE_REPORTED / ISSUE_RESOLVED / INSPECTION / CHECKOUT /
                    # RETURN / STATUS
    title: str
    detail: str = ""
    actor: Optional[str] = None     # staff only
    issue_id: Optional[int] = None


class AssetDetail(BaseModel):
    asset: "AssetOut"
    lab: "LabOut"
    transactions: list[AssetTransactionOut] = []
    maintenance: list[AssetMaintenanceRow] = []
    lifecycle: list[LifecycleEntry] = []


class AlertOut(ORM):
    id: int
    lab_id: Optional[int]
    device_id: Optional[int] = None
    severity: AlertSeverity
    title: str
    detail: str
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None
    lab_code: Optional[str] = None


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
    # Additions for the role dashboards. Every one is a count of real rows.
    labs_with_hardware: int = 0
    active_users: int = 0
    bookings_today: int = 0
    pending_bookings: int = 0
    people_inside: int = 0
    security_events_today: int = 0
    assets_total: int = 0
    assets_in_maintenance: int = 0
    assets_checked_out: int = 0
    open_issues: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    unassigned_issues: int = 0
    overdue_issues: int = 0


# --- issues ----------------------------------------------------------------
def _clean(v: str) -> str:
    return (v or "").strip()


class IssueCreate(BaseModel):
    lab_id: int
    asset_id: Optional[int] = None
    device_id: Optional[int] = None
    access_event_id: Optional[int] = None
    category: IssueCategory
    severity: IssueSeverity
    title: str = Field(max_length=140)
    description: str = Field(max_length=4000)
    additional_comments: str = Field(default="", max_length=2000)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 5:
            raise ValueError("Title must be at least 5 characters.")
        return v

    @field_validator("description")
    @classmethod
    def _description(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 10:
            raise ValueError("Describe the problem in at least 10 characters.")
        return v

    @field_validator("additional_comments")
    @classmethod
    def _comments(cls, v: str) -> str:
        return _clean(v)


class IssueUpdate(BaseModel):
    """Staff edits. Status changes go through the status endpoint."""
    severity: Optional[IssueSeverity] = None
    category: Optional[IssueCategory] = None
    asset_id: Optional[int] = None
    device_id: Optional[int] = None
    title: Optional[str] = Field(default=None, max_length=140)
    resolution_notes: Optional[str] = Field(default=None, max_length=4000)


class IssueAssign(BaseModel):
    assignee_id: Optional[int] = None   # None unassigns


class IssueStatusChange(BaseModel):
    status: IssueStatus
    note: str = Field(default="", max_length=2000)


class NoteBody(BaseModel):
    note: str = Field(default="", max_length=2000)


class IssueResolve(BaseModel):
    resolution_notes: str = Field(max_length=4000)

    @field_validator("resolution_notes")
    @classmethod
    def _notes(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 5:
            raise ValueError("Describe what was done to resolve the issue.")
        return v


class CommentCreate(BaseModel):
    body: str = Field(max_length=2000)
    is_internal: bool = False

    @field_validator("body")
    @classmethod
    def _body(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("A comment cannot be empty.")
        return v


class IssuePhotoOut(ORM):
    id: int
    stage: IssuePhotoStage
    original_filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    created_at: datetime
    uploaded_by_name: Optional[str] = None


class IssueCommentOut(ORM):
    id: int
    body: str
    is_internal: bool
    created_at: datetime
    author_id: int
    author_name: Optional[str] = None
    author_role: Optional[Role] = None


class IssueHistoryOut(ORM):
    id: int
    event_type: IssueEventType
    old_status: Optional[IssueStatus] = None
    new_status: Optional[IssueStatus] = None
    message: str
    created_at: datetime
    actor_name: Optional[str] = None
    actor_role: Optional[Role] = None


class IssueOut(ORM):
    id: int
    ticket_number: Optional[str]
    lab_id: int
    asset_id: Optional[int] = None
    device_id: Optional[int] = None
    access_event_id: Optional[int] = None
    category: IssueCategory
    severity: IssueSeverity
    status: IssueStatus
    title: str
    description: str
    additional_comments: str = ""
    resolution_notes: str = ""
    reporter_id: int
    assigned_to_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    lab_code: Optional[str] = None
    lab_name: Optional[str] = None
    asset_tag: Optional[str] = None
    asset_name: Optional[str] = None
    device_name: Optional[str] = None
    reporter_name: Optional[str] = None
    assignee_name: Optional[str] = None
    photo_count: int = 0
    is_overdue: bool = False


class IssueDetail(IssueOut):
    photos: list[IssuePhotoOut] = []
    comments: list[IssueCommentOut] = []
    history: list[IssueHistoryOut] = []
    # What the caller may do, computed from the same rules the server
    # enforces - so the UI never offers an action the API would refuse.
    can_manage: bool = False
    can_close: bool = False
    can_comment: bool = False
    can_add_photos: bool = False
    allowed_statuses: list[IssueStatus] = []


class CountRow(BaseModel):
    key: str
    label: str
    count: int


class TrendPoint(BaseModel):
    day: str
    created: int
    resolved: int


class IssueSummary(BaseModel):
    open: int
    critical: int
    high: int
    in_progress: int
    waiting_for_parts: int
    unassigned: int
    overdue: int
    resolved_this_month: int
    total: int
    avg_resolution_hours: Optional[float] = None
    by_lab: list[CountRow] = []
    by_category: list[CountRow] = []
    by_asset: list[CountRow] = []
    by_status: list[CountRow] = []
    trend: list[TrendPoint] = []
    sla_hours: dict[str, int] = {}


# --- notifications ---------------------------------------------------------
class NotificationOut(ORM):
    id: int
    kind: str
    severity: str
    title: str
    body: str
    link: Optional[str] = None
    issue_id: Optional[int] = None
    booking_id: Optional[int] = None
    is_read: bool
    created_at: datetime


# --- system ----------------------------------------------------------------
class SystemStatus(BaseModel):
    status: str                # HEALTHY / DEGRADED
    api: bool = True
    database: bool
    websocket_clients: int
    devices_online: int
    devices_total: int
    devices_reporting: int     # have ever sent a heartbeat
    controllers_online: int
    controllers_total: int
    last_heartbeat_at: Optional[datetime] = None
    time: datetime


class SystemConfig(BaseModel):
    environment: str
    booking_auto_approve: bool
    max_booking_hours: int
    booking_grace_minutes: int
    booking_reminder_minutes: int
    qr_token_bytes: int
    access_token_expire_minutes: int
    device_stale_seconds: int
    max_upload_mb: int
    max_photos_per_issue: int
    image_max_dimension: int
    issue_sla_hours: dict[str, int]
    storage_backend: str
