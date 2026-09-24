"""
Human wording for machine codes, for text the backend itself writes
(notification bodies). The audit trail always keeps the code; people get the
sentence. Kept in step with denialText() in the frontend.
"""
from typing import Optional

_DENIAL = {
    "TOKEN_UNKNOWN": "The scanned code is not a credential this system issued.",
    "TOKEN_REVOKED": "This credential was replaced or revoked.",
    "BOOKING_NOT_CONFIRMED": "The booking behind this code is not confirmed.",
    "BOOKING_CANCELLED": "The booking was cancelled.",
    "BOOKING_NOT_STARTED": "The booking window has not opened yet.",
    "BOOKING_EXPIRED": "The booking window has closed.",
    "WRONG_LAB": "This credential belongs to a different laboratory.",
    "USER_INACTIVE": "The account is not active.",
    "UNKNOWN_CREDENTIAL": "The card or tag is not registered.",
    "NO_ACTIVE_BOOKING": "No active booking for this laboratory.",
    "IDENTITY_MISMATCH": "The biometric did not match the identity from step 1.",
    "BIOMETRIC_TIMEOUT": "No fingerprint or face was presented in time.",
    "BIOMETRIC_FAILED": "The biometric check failed.",
    "DEVICE_UNKNOWN": "The reader reported an unrecognised laboratory.",
    "BACKEND_UNAVAILABLE": "The portal could not be reached, so entry was refused.",
}


def denial_sentence(reason: Optional[str]) -> Optional[str]:
    if not reason:
        return None
    return _DENIAL.get(reason, reason.replace("_", " ").capitalize() + ".")
