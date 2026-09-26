"""
The complete relational schema.

Three rules run through all of it:

  1. Every lab-scoped row carries lab_id. Traceability is the point of the
     system, and an event you cannot attribute to a laboratory is useless.
  2. No biometric material is stored here. Fingerprint templates live in the
     AS608 sensor's own flash; face images live in the face server's dataset
     directory. This database stores identity references and outcomes only.
  3. Every timestamp is timezone-aware (TIMESTAMPTZ). Booking windows are
     compared in UTC; a naive timestamp would make 'is the booking active'
     depend on server locale, which is exactly the kind of bug that silently
     grants access at the wrong hour.
"""
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Enum, Float,
                        ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import (AccessResult, AlertSeverity, AssetStatus,
                              AuthMethod, BookingStatus, DenialReason,
                              DeviceType, EventType, IssueCategory,
                              IssueEventType, IssuePhotoStage, IssueSeverity,
                              IssueStatus, Role, SessionEndReason)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum(e, name):
    return Enum(e, name=name, native_enum=False, validate_strings=True,
                length=48)


TS = DateTime(timezone=True)


# ===========================================================================
# Identity
# ===========================================================================
class RoleRow(Base):
    """
    Roles as data as well as an enum on users. The enum enforces the value at
    write time; this table gives the admin UI something to describe.
    """
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role, "role_enum"),
                                       default=Role.STUDENT, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # The bridge to the embedded system. The face server's labels and the
    # master firmware's authorizedUsers[] both use these strings, so this is
    # what lets a biometric result be checked against a portal identity.
    # Nullable: a user may exist in the portal before being enrolled.
    auth_subject: Mapped[str | None] = mapped_column(String(32), unique=True,
                                                     index=True, nullable=True)

    student_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")
    rfid_credentials: Mapped[list["RfidCredential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")


class RfidCredential(Base):
    """
    The physical card/tag. Stores the UID only - an MFRC522 UID is not secret
    and is trivially cloneable, which is precisely why it is only ever the
    FIRST factor.
    """
    __tablename__ = "rfid_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid_hex: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    issued_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)

    user: Mapped[User] = relationship(back_populates="rfid_credentials")


# ===========================================================================
# Facility
# ===========================================================================
class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Human/firmware-facing identifier, e.g. LAB_02. This is what the ESP32
    # sends, so it must be stable and unique.
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(128), default="")
    capacity: Mapped[int] = mapped_column(Integer, default=1)

    # Grouping for the UI. A lab is still booked as a ROOM - the category is
    # presentation only, because a door belongs to a room and not to a degree
    # programme.
    category: Mapped[str] = mapped_column(String(64), default="General")

    # Whether this laboratory actually has access-control hardware installed.
    # False is the honest state for every lab except the one with the physical
    # door controller, and the UI says so rather than implying a lock exists.
    has_controller: Mapped[bool] = mapped_column(Boolean, default=False)

    # When false, several bookings may overlap in this lab.
    exclusive_booking: Mapped[bool] = mapped_column(Boolean, default=True)
    # When true, RFID access also requires an active booking. Default false so
    # the existing local RFID + biometric behaviour is preserved untouched.
    require_booking_for_rfid: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    devices: Mapped[list["Device"]] = relationship(back_populates="lab")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="lab")


class Device(Base):
    """Every physical device belongs to exactly one laboratory."""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    device_type: Mapped[DeviceType] = mapped_column(
        _enum(DeviceType, "device_type_enum"))
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(TS, nullable=True,
                                                          index=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    # Latest reported door state, or NULL when the device has never reported.
    # NULL means "no data", never a fabricated default.
    door_closed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Per-component health as the device itself reported it in its last
    # heartbeat, e.g. {"rfid": true, "fingerprint": true, "relay_locked": true}.
    # NULL until firmware sends it; the UI then labels reader states as
    # inferred from the heartbeat rather than presenting them as measured.
    component_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    lab: Mapped[Lab] = relationship(back_populates="devices")


class LabDevice(Base):
    """
    Association table. Device.lab_id is the owning lab; this allows a device
    to additionally serve other labs (a shared corridor camera, say) without
    losing the single owning relationship.
    """
    __tablename__ = "lab_devices"
    __table_args__ = (UniqueConstraint("lab_id", "device_id",
                                       name="uq_lab_device"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"),
                                        index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(64), default="primary")


# ===========================================================================
# Bookings and credentials
# ===========================================================================
class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_booking_window"),
        Index("ix_booking_lab_window", "lab_id", "start_time", "end_time"),
        # "my bookings", newest first - the most frequent student query
        Index("ix_booking_user_start", "user_id", "start_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(TS, index=True)
    end_time: Mapped[datetime] = mapped_column(TS, index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[BookingStatus] = mapped_column(
        _enum(BookingStatus, "booking_status_enum"),
        default=BookingStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)

    # ACTUAL use, as opposed to booked intent.
    #
    # A booking says 14:00-16:00; the person may walk in at 14:16 and never
    # come back. Storing the real first entry alongside the reservation is
    # what turns this from a calendar into a record of what happened - and it
    # is the difference between "the room was booked" and "the room was used".
    first_entry_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    last_entry_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    entry_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="bookings")
    lab: Mapped[Lab] = relationship(back_populates="bookings")
    qr_tokens: Mapped[list["QrToken"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan")


class QrToken(Base):
    """
    A booking's door credential.

    The token is opaque: it carries no user, lab or time information of its
    own. Everything that decides validity is looked up here, server-side, at
    the moment of the scan. That is what makes a photographed QR useless
    outside its window - there is nothing in the image to replay.
    """
    __tablename__ = "qr_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), index=True)
    valid_from: Mapped[datetime] = mapped_column(TS, index=True)
    valid_until: Mapped[datetime] = mapped_column(TS, index=True)
    issued_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)

    booking: Mapped[Booking] = relationship(back_populates="qr_tokens")


# ===========================================================================
# Access
# ===========================================================================
class AccessAttempt(Base):
    """
    One row per credential presentation, successful or not. Separate from
    access_events so the security view stays readable: attempts are the
    security record, events are the full narrative timeline.
    """
    __tablename__ = "access_attempts"
    __table_args__ = (Index("ix_attempt_lab_time", "lab_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable ONLY so that an attempt against an unrecognised lab code is
    # still recorded. A device presenting an unknown lab is exactly the event
    # you least want to drop on the floor.
    lab_id: Mapped[int | None] = mapped_column(ForeignKey("labs.id"),
                                               nullable=True, index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"),
                                                  nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"),
                                                nullable=True, index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"),
                                                   nullable=True, index=True)
    method: Mapped[AuthMethod] = mapped_column(_enum(AuthMethod, "auth_method_enum"))
    result: Mapped[AccessResult] = mapped_column(
        _enum(AccessResult, "access_result_enum"), index=True)
    denial_reason: Mapped[DenialReason | None] = mapped_column(
        _enum(DenialReason, "denial_reason_enum"), nullable=True, index=True)
    # Never the raw credential: a truncated reference for forensics.
    credential_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class AccessEvent(Base):
    """The complete event timeline. Every lab-related event references a lab."""
    __tablename__ = "access_events"
    __table_args__ = (Index("ix_event_lab_time", "lab_id", "created_at"),
                      Index("ix_event_type_time", "event_type", "created_at"),
                      # a person's own timeline (student dashboard, traces)
                      Index("ix_event_user_time", "user_id", "created_at"))

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[EventType] = mapped_column(
        _enum(EventType, "event_type_enum"), index=True)
    lab_id: Mapped[int | None] = mapped_column(ForeignKey("labs.id"),
                                               nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"),
                                                nullable=True, index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"),
                                                   nullable=True, index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"),
                                                  nullable=True, index=True)
    method: Mapped[AuthMethod | None] = mapped_column(
        _enum(AuthMethod, "auth_method_enum2"), nullable=True)
    result: Mapped[AccessResult | None] = mapped_column(
        _enum(AccessResult, "access_result_enum2"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(String(255), default="")
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class AccessSession(Base):
    """
    An occupancy span, opened when access is granted.

    The door cycle (opened, closed behind the person) is recorded on the
    session but does NOT end it: the door closing a few seconds after entry is
    not the person leaving. The session ends when an exit is actually
    reported, or - because the current door has no exit reader - when the
    booking window closes, and end_reason says which. An exit time is only
    ever presented as an exit when end_reason is EXIT_RECORDED.
    """
    __tablename__ = "access_sessions"
    # "who is inside this lab now" = open sessions per lab
    __table_args__ = (Index("ix_session_lab_open", "lab_id", "ended_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"),
                                                   nullable=True, index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"),
                                                  nullable=True)
    entry_method: Mapped[AuthMethod] = mapped_column(
        _enum(AuthMethod, "auth_method_enum3"))
    # The biometric that completed step 2, when the device reported it.
    second_factor: Mapped[AuthMethod | None] = mapped_column(
        _enum(AuthMethod, "auth_method_enum4"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    door_opened_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    door_closed_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(TS, nullable=True, index=True)
    end_reason: Mapped[SessionEndReason | None] = mapped_column(
        _enum(SessionEndReason, "session_end_reason_enum"), nullable=True)


# ===========================================================================
# Assets
# ===========================================================================
class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_tag: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64), default="")
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), index=True)
    status: Mapped[AssetStatus] = mapped_column(
        _enum(AssetStatus, "asset_status_enum"),
        default=AssetStatus.AVAILABLE, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    # Lifecycle. All optional: an item may never have been inspected, and
    # a missing value is shown as "not recorded", never guessed.
    serial_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Who has it right now. Set on checkout, cleared on return.
    holder_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    last_inspected_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    next_maintenance_at: Mapped[datetime | None] = mapped_column(
        TS, nullable=True, index=True)


class AssetTransaction(Base):
    __tablename__ = "asset_transactions"
    __table_args__ = (Index("ix_asset_tx_asset_time", "asset_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"),
                                          index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), index=True)
    # CHECKOUT / RETURN / INSPECTION / STATUS_<new status>
    action: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    note: Mapped[str] = mapped_column(String(255), default="")


# ===========================================================================
# Environment and operations
# ===========================================================================
class SensorReading(Base):
    """
    Structure only. Nothing writes here until a real sensor node exists; the
    lab page must render 'No data available' rather than invent values.
    """
    __tablename__ = "sensor_readings"
    __table_args__ = (Index("ix_sensor_lab_metric_time",
                            "lab_id", "metric", "recorded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"),
                                                  nullable=True)
    metric: Mapped[str] = mapped_column(String(48), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="")
    recorded_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_alerts_dedupe_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_id: Mapped[int | None] = mapped_column(ForeignKey("labs.id"),
                                               nullable=True, index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"),
                                                  nullable=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        _enum(AlertSeverity, "alert_severity_enum"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    detail: Mapped[str] = mapped_column(Text, default="")
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    # Set by automation (n8n) so a retried call cannot raise the same alert
    # twice. NULL for alerts the portal raises itself.
    dedupe_key: Mapped[str | None] = mapped_column(String(160), nullable=True)


class AuditLog(Base):
    """Who did what, in the portal. Distinct from physical access events."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"),
                                                      nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


# ===========================================================================
# Maintenance: issue reports
# ===========================================================================
class Issue(Base):
    """
    A problem reported in a laboratory - broken equipment, a missing tool, a
    reader that stopped detecting cards.

    Always attributable to a laboratory and a reporter. The asset, device and
    access event links are optional and are validated to belong to that same
    laboratory, so an issue can never claim a relationship that is not real.
    """
    __tablename__ = "issues"
    __table_args__ = (
        Index("ix_issue_status_severity", "status", "severity"),
        Index("ix_issue_lab_status", "lab_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Human-readable, e.g. ISS-2026-000142. Derived from the row id at insert,
    # so it is unique without a second sequence to keep in step.
    ticket_number: Mapped[str | None] = mapped_column(String(32), unique=True,
                                                      index=True, nullable=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), index=True)
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    access_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("access_events.id", ondelete="SET NULL"), nullable=True)

    category: Mapped[IssueCategory] = mapped_column(
        _enum(IssueCategory, "issue_category_enum"), index=True)
    severity: Mapped[IssueSeverity] = mapped_column(
        _enum(IssueSeverity, "issue_severity_enum"), index=True)
    status: Mapped[IssueStatus] = mapped_column(
        _enum(IssueStatus, "issue_status_enum"), default=IssueStatus.OPEN,
        index=True)

    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(Text)
    additional_comments: Mapped[str] = mapped_column(Text, default="")

    assigned_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True)
    resolution_notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow,
                                                 onupdate=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)

    photos: Mapped[list["IssuePhoto"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan",
        order_by="IssuePhoto.created_at")
    comments: Mapped[list["IssueComment"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan",
        order_by="IssueComment.created_at")
    history: Mapped[list["IssueHistory"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan",
        order_by="IssueHistory.created_at")


class IssuePhoto(Base):
    """
    Metadata only. The image bytes live in object storage (the local
    filesystem for now) under storage_key; a database row stays small and the
    storage backend can change without touching this table.
    """
    __tablename__ = "issue_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    stage: Mapped[IssuePhotoStage] = mapped_column(
        _enum(IssuePhotoStage, "issue_photo_stage_enum"),
        default=IssuePhotoStage.REPORT)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    thumb_key: Mapped[str] = mapped_column(String(255), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), default="")
    content_type: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    issue: Mapped[Issue] = relationship(back_populates="photos")


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    # Staff working notes. Never returned to a student.
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    issue: Mapped[Issue] = relationship(back_populates="comments")


class IssueHistory(Base):
    """
    The issue's audit trail and timeline in one: every change is a row with
    who, when, old and new status. Nothing about an issue changes without
    one of these being written in the same transaction.
    """
    __tablename__ = "issue_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"),
                                                 nullable=True)
    event_type: Mapped[IssueEventType] = mapped_column(
        _enum(IssueEventType, "issue_event_type_enum"), index=True)
    old_status: Mapped[IssueStatus | None] = mapped_column(
        _enum(IssueStatus, "issue_status_enum2"), nullable=True)
    new_status: Mapped[IssueStatus | None] = mapped_column(
        _enum(IssueStatus, "issue_status_enum3"), nullable=True)
    message: Mapped[str] = mapped_column(String(500), default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Mirrors IssueComment.is_internal for history rows about internal notes.
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)

    issue: Mapped[Issue] = relationship(back_populates="history")


# ===========================================================================
# In-portal notifications
# ===========================================================================
class Notification(Base):
    """
    A message for one person, raised by something that actually happened -
    a booking confirmed, an issue acknowledged, a device going silent. There
    is no email or SMS provider; the portal is the delivery channel.
    """
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notification_user_unread", "user_id", "is_read", "created_at"),
        # One notification per person per automation key: a retried n8n run
        # (or a reminder raised by both n8n and the lazy path) lands once.
        UniqueConstraint("user_id", "dedupe_key", name="uq_notification_dedupe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(500), default="")
    # A portal route, e.g. /issues/12 - never an external URL.
    link: Mapped[str | None] = mapped_column(String(160), nullable=True)
    issue_id: Mapped[int | None] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=True, index=True)
    booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(160), nullable=True)


class IntegrationEvent(Base):
    """
    Transactional outbox for external automation (n8n).

    A row is staged in the same transaction as the change it describes, so an
    event exists if and only if the change committed. A background dispatcher
    pushes selected types to n8n; every row is also readable from the pull
    feed. event_id is the idempotency key consumers de-duplicate on - a push
    that is retried after a timeout carries the same id.

    This is an integration record, not the audit trail: access_events stays
    the authoritative log, and pruning this table loses nothing.
    """
    __tablename__ = "integration_events"
    __table_args__ = (
        Index("ix_integration_due", "delivery_status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    occurred_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    lab_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True,
                                                       index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # PENDING -> DELIVERED | FAILED (gave up) ; SKIPPED = not a pushed type
    delivery_status: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
