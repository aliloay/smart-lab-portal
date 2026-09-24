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
