---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/models/__init__.py"
source_hash: "3e53a09ed66d1134f91bee40353d05fb19ecca6d0b7aae7be66d9c2688b69f5d"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/models/__init__.py` - edit the original in the repository, not this note.

Systems: [[Backend and data]]

```py
from app.models.enums import (AccessResult, AlertSeverity, AssetStatus,
                              AuthMethod, BookingStatus, DenialReason,
                              DeviceType, EventType, IssueCategory,
                              IssueEventType, IssuePhotoStage, IssueSeverity,
                              IssueStatus, Role, SessionEndReason)
from app.models.tables import (AccessAttempt, AccessEvent, AccessSession, Alert, IncidentNote,
                               Asset, AssetTransaction, AuditLog, Booking, BookingItem, PersonalQrCredential,
                               Device, DeviceCommand, FaceSubmission,
                               IntegrationEvent, InventoryBin,
                               InventoryMeasurement, InventoryTransaction, Issue,
                               EquipmentSession, PolicyViolation, RobotEvent, RobotHomeCalibration, WorkcellSetup,
                               SecurityEvent, SecurityZone,
                               LabEmergency, SystemSetting,
                               IssueComment, IssueHistory,
                               IssuePhoto, Lab, LabDevice, Notification,
                               QrToken, RfidCredential, RoleRow, SensorReading,
                               User, utcnow, Experiment, ExperimentTrial, PROVENANCES)

__all__ = [
    "AccessResult", "AlertSeverity", "AssetStatus", "AuthMethod",
    "BookingStatus", "DenialReason", "DeviceType", "EventType", "Role",
    "IssueCategory", "IssueEventType", "IssuePhotoStage", "IssueSeverity",
    "IssueStatus", "SessionEndReason",
    "AccessAttempt", "AccessEvent", "AccessSession", "Alert", "IncidentNote", "Asset",
    "AssetTransaction", "AuditLog", "Booking", "BookingItem", "PersonalQrCredential", "Device", "DeviceCommand",
    "FaceSubmission", "InventoryBin", "InventoryMeasurement",
    "InventoryTransaction", "EquipmentSession", "PolicyViolation",
    "SecurityEvent", "SecurityZone", "LabEmergency", "SystemSetting", "RobotEvent", "RobotHomeCalibration", "WorkcellSetup",
    "IntegrationEvent", "Experiment", "ExperimentTrial", "PROVENANCES",
    "Issue",
    "IssueComment", "IssueHistory", "IssuePhoto", "Lab", "LabDevice",
    "Notification", "QrToken", "RfidCredential", "RoleRow", "SensorReading",
    "User", "utcnow",
]

```
