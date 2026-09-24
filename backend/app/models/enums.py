"""
Enumerations shared across the schema.

Stored as VARCHAR with a CHECK constraint (native_enum=False) rather than as
PostgreSQL ENUM types: adding a value to a native enum needs its own migration
and locks the type, which is painful for an event catalogue that will grow.
"""
import enum


class Role(str, enum.Enum):
    STUDENT = "STUDENT"
    LAB_STAFF = "LAB_STAFF"
    ADMIN = "ADMIN"


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"        # awaiting administrator approval
    CONFIRMED = "CONFIRMED"    # active credential can be issued
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class AuthMethod(str, enum.Enum):
    RFID = "RFID"
    QR = "QR"
    FINGERPRINT = "FINGERPRINT"
    FACE = "FACE"
    PORTAL = "PORTAL"


class AccessResult(str, enum.Enum):
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    PENDING = "PENDING"


class DenialReason(str, enum.Enum):
    """
    Explicit denial reasons. Every rejection path names one of these, so the
    audit log answers 'why' rather than just 'no'.
    """
    TOKEN_UNKNOWN = "TOKEN_UNKNOWN"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    BOOKING_NOT_CONFIRMED = "BOOKING_NOT_CONFIRMED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_NOT_STARTED = "BOOKING_NOT_STARTED"
    BOOKING_EXPIRED = "BOOKING_EXPIRED"
    WRONG_LAB = "WRONG_LAB"
    USER_INACTIVE = "USER_INACTIVE"
    UNKNOWN_CREDENTIAL = "UNKNOWN_CREDENTIAL"
    NO_ACTIVE_BOOKING = "NO_ACTIVE_BOOKING"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    BIOMETRIC_TIMEOUT = "BIOMETRIC_TIMEOUT"
    BIOMETRIC_FAILED = "BIOMETRIC_FAILED"
    DEVICE_UNKNOWN = "DEVICE_UNKNOWN"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"


class EventType(str, enum.Enum):
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    QR_GENERATED = "QR_GENERATED"
    QR_SCAN = "QR_SCAN"
    QR_VALIDATED = "QR_VALIDATED"
    QR_REJECTED = "QR_REJECTED"
    RFID_SCAN = "RFID_SCAN"
    RFID_ACCEPTED = "RFID_ACCEPTED"
    RFID_REJECTED = "RFID_REJECTED"
    FINGERPRINT_ATTEMPT = "FINGERPRINT_ATTEMPT"
    FINGERPRINT_ACCEPTED = "FINGERPRINT_ACCEPTED"
    FINGERPRINT_REJECTED = "FINGERPRINT_REJECTED"
    FACE_ATTEMPT = "FACE_ATTEMPT"
    FACE_ACCEPTED = "FACE_ACCEPTED"
    FACE_REJECTED = "FACE_REJECTED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    ACCESS_GRANTED = "ACCESS_GRANTED"
    ACCESS_DENIED = "ACCESS_DENIED"
    DOOR_OPENED = "DOOR_OPENED"
    DOOR_CLOSED = "DOOR_CLOSED"
    # The person has left. Nothing on the current door reports this - it has
    # no exit reader - but the event exists so an exit button or reader can be
    # added later without a schema change, and so a session is only ever
    # given an exit time by something that actually observed an exit.
    EXIT_RECORDED = "EXIT_RECORDED"
    DEVICE_ONLINE = "DEVICE_ONLINE"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    ALARM = "ALARM"
    ASSET_CHECKOUT = "ASSET_CHECKOUT"
    ASSET_RETURN = "ASSET_RETURN"


class DeviceType(str, enum.Enum):
    MASTER_CONTROLLER = "MASTER_CONTROLLER"
    CAMERA = "CAMERA"
    FACE_SERVER = "FACE_SERVER"
    SENSOR_NODE = "SENSOR_NODE"


class AssetStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    CHECKED_OUT = "CHECKED_OUT"
    MAINTENANCE = "MAINTENANCE"
    RETIRED = "RETIRED"


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class SessionEndReason(str, enum.Enum):
    """
    Why an occupancy session stopped counting. Only EXIT_RECORDED means an
    exit was actually observed; every other value is the system admitting it
    does not know when the person left, and the UI must say so.
    """
    EXIT_RECORDED = "EXIT_RECORDED"      # an exit event was reported
    BOOKING_ENDED = "BOOKING_ENDED"      # the booking window closed
    DOOR_NOT_OPENED = "DOOR_NOT_OPENED"  # unlocked, relocked, never opened
    SUPERSEDED = "SUPERSEDED"            # a newer entry by the same person
    # No booking window to close it and no exit observed: the session stops
    # counting towards occupancy after MAX_BOOKING_HOURS. ended_at is that
    # cut-off, NOT an exit time.
    NO_EXIT_TIMEOUT = "NO_EXIT_TIMEOUT"


# --- maintenance -------------------------------------------------------------
class IssueCategory(str, enum.Enum):
    DAMAGED = "DAMAGED"
    MISSING = "MISSING"
    MALFUNCTION = "MALFUNCTION"
    MAINTENANCE = "MAINTENANCE"
    SAFETY = "SAFETY"
    SOFTWARE = "SOFTWARE"
    NETWORK = "NETWORK"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    OTHER = "OTHER"


class IssueSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IssueStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_PARTS = "WAITING_FOR_PARTS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class IssuePhotoStage(str, enum.Enum):
    """When a photo was taken. Maintenance photos never replace report ones."""
    REPORT = "REPORT"
    BEFORE = "BEFORE"
    AFTER = "AFTER"


class IssueEventType(str, enum.Enum):
    ISSUE_CREATED = "ISSUE_CREATED"
    ISSUE_ACKNOWLEDGED = "ISSUE_ACKNOWLEDGED"
    ISSUE_ASSIGNED = "ISSUE_ASSIGNED"
    ISSUE_STATUS_CHANGED = "ISSUE_STATUS_CHANGED"
    ISSUE_SEVERITY_CHANGED = "ISSUE_SEVERITY_CHANGED"
    ISSUE_UPDATED = "ISSUE_UPDATED"
    ISSUE_COMMENT_ADDED = "ISSUE_COMMENT_ADDED"
    ISSUE_PHOTO_ADDED = "ISSUE_PHOTO_ADDED"
    ISSUE_RESOLVED = "ISSUE_RESOLVED"
    ISSUE_CLOSED = "ISSUE_CLOSED"
    ISSUE_REOPENED = "ISSUE_REOPENED"
