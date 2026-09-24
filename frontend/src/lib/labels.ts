/**
 * Human wording for machine codes, in one place.
 *
 * The audit trail keeps the codes; people read these. Centralised so a denial
 * reads the same - and is the same colour - on every screen.
 */
import type {
  AuthMethod, IssueCategory, IssueSeverity, IssueStatus, SessionEndReason,
} from './api'

export type Tone = 'ok' | 'warn' | 'bad' | 'info' | 'idle' | 'violet'

const EVENT_LABEL: Record<string, string> = {
  BOOKING_CREATED: 'Booking requested', BOOKING_CONFIRMED: 'Booking confirmed',
  BOOKING_CANCELLED: 'Booking cancelled', QR_GENERATED: 'Credential issued',
  QR_SCAN: 'QR scanned', QR_VALIDATED: 'QR valid', QR_REJECTED: 'QR rejected',
  RFID_SCAN: 'Card scanned', RFID_ACCEPTED: 'Card accepted',
  RFID_REJECTED: 'Card rejected', FINGERPRINT_ATTEMPT: 'Fingerprint presented',
  FINGERPRINT_ACCEPTED: 'Fingerprint matched',
  FINGERPRINT_REJECTED: 'Fingerprint rejected', FACE_ATTEMPT: 'Face presented',
  FACE_ACCEPTED: 'Face matched', FACE_REJECTED: 'Face rejected',
  IDENTITY_MISMATCH: 'Identity mismatch', ACCESS_GRANTED: 'Access granted',
  ACCESS_DENIED: 'Access denied', DOOR_OPENED: 'Door opened',
  DOOR_CLOSED: 'Door closed', EXIT_RECORDED: 'Exit recorded',
  DEVICE_ONLINE: 'Device online', DEVICE_OFFLINE: 'Device offline',
  ALARM: 'Alarm', ASSET_CHECKOUT: 'Equipment checked out',
  ASSET_RETURN: 'Equipment returned',
}

export const eventLabel = (t: string) =>
  EVENT_LABEL[t] ?? t.replace(/_/g, ' ').toLowerCase()
    .replace(/^\w/, c => c.toUpperCase())

export function eventTone(t: string): Tone {
  if (t === 'ACCESS_GRANTED' || t.endsWith('ACCEPTED') || t === 'QR_VALIDATED'
      || t === 'BOOKING_CONFIRMED' || t === 'DEVICE_ONLINE') return 'ok'
  if (t === 'ACCESS_DENIED' || t.endsWith('REJECTED')
      || t === 'IDENTITY_MISMATCH' || t === 'ALARM') return 'bad'
  if (t === 'DEVICE_OFFLINE' || t === 'BOOKING_CANCELLED') return 'warn'
  if (t.startsWith('DOOR') || t === 'EXIT_RECORDED') return 'violet'
  if (t.startsWith('BOOKING') || t.startsWith('QR') || t.startsWith('ASSET')
      || t.endsWith('ATTEMPT') || t.endsWith('SCAN')) return 'info'
  return 'idle'
}

/** Events that belong to the physical door, as opposed to the portal. */
export const DOOR_EVENTS = new Set([
  'QR_SCAN', 'QR_VALIDATED', 'QR_REJECTED', 'RFID_SCAN', 'RFID_ACCEPTED',
  'RFID_REJECTED', 'FINGERPRINT_ATTEMPT', 'FINGERPRINT_ACCEPTED',
  'FINGERPRINT_REJECTED', 'FACE_ATTEMPT', 'FACE_ACCEPTED', 'FACE_REJECTED',
  'IDENTITY_MISMATCH', 'ACCESS_GRANTED', 'ACCESS_DENIED', 'DOOR_OPENED',
  'DOOR_CLOSED', 'EXIT_RECORDED',
])

const DENIAL: Record<string, string> = {
  TOKEN_UNKNOWN: 'The scanned code is not a credential this system issued.',
  TOKEN_REVOKED: 'This credential was replaced or revoked.',
  BOOKING_NOT_CONFIRMED: 'The booking behind this code is not confirmed.',
  BOOKING_CANCELLED: 'The booking was cancelled.',
  BOOKING_NOT_STARTED: 'The booking window has not opened yet.',
  BOOKING_EXPIRED: 'The booking window has closed.',
  WRONG_LAB: 'This credential belongs to a different laboratory.',
  USER_INACTIVE: 'The account is not active.',
  UNKNOWN_CREDENTIAL: 'The card or tag is not registered.',
  NO_ACTIVE_BOOKING: 'No active booking for this laboratory.',
  IDENTITY_MISMATCH: 'The biometric did not match the identity from step 1.',
  BIOMETRIC_TIMEOUT: 'No fingerprint or face was presented in time.',
  BIOMETRIC_FAILED: 'The biometric check failed.',
  DEVICE_UNKNOWN: 'The reader reported an unrecognised laboratory.',
  BACKEND_UNAVAILABLE: 'The portal could not be reached, so entry was refused.',
}

const DENIAL_SHORT: Record<string, string> = {
  TOKEN_UNKNOWN: 'Unknown QR', TOKEN_REVOKED: 'Revoked QR',
  BOOKING_NOT_CONFIRMED: 'Not confirmed', BOOKING_CANCELLED: 'Cancelled booking',
  BOOKING_NOT_STARTED: 'Too early', BOOKING_EXPIRED: 'Expired QR',
  WRONG_LAB: 'Wrong lab', USER_INACTIVE: 'Inactive user',
  UNKNOWN_CREDENTIAL: 'Unknown RFID', NO_ACTIVE_BOOKING: 'No booking',
  IDENTITY_MISMATCH: 'Identity mismatch', BIOMETRIC_TIMEOUT: 'Biometric timeout',
  BIOMETRIC_FAILED: 'Biometric failed', DEVICE_UNKNOWN: 'Unknown device',
  BACKEND_UNAVAILABLE: 'Portal unreachable',
}

export function denialText(reason?: string | null): string | null {
  if (!reason) return null
  return DENIAL[reason] ?? reason.replace(/_/g, ' ').toLowerCase()
}
export const denialShort = (reason?: string | null) =>
  reason ? DENIAL_SHORT[reason] ?? reason.replace(/_/g, ' ').toLowerCase() : null

export const DENIAL_CODES = Object.keys(DENIAL_SHORT)

export const methodLabel = (m?: string | null) =>
  ({ RFID: 'RFID card', QR: 'QR code', FINGERPRINT: 'Fingerprint', FACE: 'Face',
     PORTAL: 'Portal' } as Record<string, string>)[m ?? ''] ?? (m || '—')

export function endReasonText(r: SessionEndReason | null | undefined): string {
  switch (r) {
    case 'EXIT_RECORDED': return 'Exit recorded'
    case 'BOOKING_ENDED': return 'No exit recorded · counted until the booking ended'
    case 'DOOR_NOT_OPENED': return 'Unlocked, but the door was never opened'
    case 'SUPERSEDED': return 'Superseded by a later entry'
    case 'NO_EXIT_TIMEOUT': return 'No exit recorded · stopped counting after the maximum window'
    default: return 'Inside - no exit recorded yet'
  }
}

// --- bookings ----------------------------------------------------------------
export function bookingTone(s: string): Tone {
  if (s === 'CONFIRMED') return 'ok'
  if (s === 'CANCELLED' || s === 'REJECTED') return 'bad'
  if (s === 'PENDING') return 'warn'
  return 'idle'
}

// --- assets ------------------------------------------------------------------
export function assetTone(s: string): Tone {
  if (s === 'AVAILABLE') return 'ok'
  if (s === 'MAINTENANCE') return 'warn'
  if (s === 'RETIRED') return 'bad'
  if (s === 'CHECKED_OUT') return 'info'
  return 'idle'
}
export const assetStatusLabel = (s: string) =>
  ({ AVAILABLE: 'Available', CHECKED_OUT: 'Checked out',
     MAINTENANCE: 'Maintenance', RETIRED: 'Retired' } as Record<string, string>)[s] ?? s

// --- issues ------------------------------------------------------------------
export const ISSUE_CATEGORIES: { value: IssueCategory; label: string; hint: string }[] = [
  { value: 'DAMAGED', label: 'Damaged', hint: 'Broken, cracked or physically harmed' },
  { value: 'MISSING', label: 'Missing', hint: 'Not where it should be' },
  { value: 'MALFUNCTION', label: 'Malfunction', hint: 'Present but not working properly' },
  { value: 'MAINTENANCE', label: 'Needs maintenance', hint: 'Calibration, cleaning, servicing' },
  { value: 'SAFETY', label: 'Safety concern', hint: 'A risk to people or property' },
  { value: 'SOFTWARE', label: 'Software', hint: 'Licences, updates, crashes' },
  { value: 'NETWORK', label: 'Network', hint: 'Wi-Fi, Ethernet, connectivity' },
  { value: 'ACCESS_CONTROL', label: 'Access control', hint: 'RFID, fingerprint, camera, lock' },
  { value: 'OTHER', label: 'Other', hint: 'Anything else in the laboratory' },
]
export const categoryLabel = (c: string) =>
  ISSUE_CATEGORIES.find(x => x.value === c)?.label ?? c

export const SEVERITIES: { value: IssueSeverity; label: string; hint: string }[] = [
  { value: 'LOW', label: 'Low', hint: 'Inconvenient, work can continue' },
  { value: 'MEDIUM', label: 'Medium', hint: 'Affects work, a workaround exists' },
  { value: 'HIGH', label: 'High', hint: 'Blocks work on this equipment' },
  { value: 'CRITICAL', label: 'Critical', hint: 'Safety risk or the lab cannot be used' },
]

export function severityTone(s: IssueSeverity | string): Tone {
  return s === 'CRITICAL' ? 'bad' : s === 'HIGH' ? 'warn'
    : s === 'MEDIUM' ? 'info' : 'idle'
}

export const STATUS_LABEL: Record<IssueStatus, string> = {
  OPEN: 'Open', ACKNOWLEDGED: 'Acknowledged', IN_PROGRESS: 'In progress',
  WAITING_FOR_PARTS: 'Waiting for parts', RESOLVED: 'Resolved', CLOSED: 'Closed',
  REJECTED: 'Rejected',
}

export function issueStatusTone(s: IssueStatus | string): Tone {
  switch (s) {
    case 'OPEN': return 'warn'
    case 'ACKNOWLEDGED': return 'info'
    case 'IN_PROGRESS': return 'violet'
    case 'WAITING_FOR_PARTS': return 'warn'
    case 'RESOLVED': return 'ok'
    case 'REJECTED': return 'bad'
    default: return 'idle'
  }
}

export const ACTIVE_ISSUE: IssueStatus[] =
  ['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'WAITING_FOR_PARTS']

export const isBiometric = (m?: AuthMethod | string | null) =>
  m === 'FACE' || m === 'FINGERPRINT'
