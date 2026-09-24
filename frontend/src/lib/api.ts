/**
 * Typed API client.
 *
 * The token lives in memory and in sessionStorage, not localStorage:
 * sessionStorage is cleared when the tab closes, which is the right default
 * for something that controls physical access to a room.
 */

export type Role = 'STUDENT' | 'LAB_STAFF' | 'ADMIN'
export type BookingStatus =
  | 'PENDING' | 'CONFIRMED' | 'CANCELLED' | 'REJECTED' | 'COMPLETED'
export type AuthMethod = 'RFID' | 'QR' | 'FINGERPRINT' | 'FACE' | 'PORTAL'
export type SessionEndReason =
  | 'EXIT_RECORDED' | 'BOOKING_ENDED' | 'DOOR_NOT_OPENED' | 'SUPERSEDED'
  | 'NO_EXIT_TIMEOUT'
export type IssueCategory =
  | 'DAMAGED' | 'MISSING' | 'MALFUNCTION' | 'MAINTENANCE' | 'SAFETY'
  | 'SOFTWARE' | 'NETWORK' | 'ACCESS_CONTROL' | 'OTHER'
export type IssueSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type IssueStatus =
  | 'OPEN' | 'ACKNOWLEDGED' | 'IN_PROGRESS' | 'WAITING_FOR_PARTS'
  | 'RESOLVED' | 'CLOSED' | 'REJECTED'
export type PhotoStage = 'REPORT' | 'BEFORE' | 'AFTER'

export interface User {
  id: number
  email: string
  full_name: string
  role: Role
  is_active: boolean
  auth_subject: string | null
  student_id: string | null
  department: string | null
  created_at?: string | null
}

export interface Lab {
  id: number
  code: string
  name: string
  description: string
  location: string
  capacity: number
  /** Presentation grouping only — a lab is booked as a room, not a discipline. */
  category: string
  /** Whether access-control hardware is actually installed at this door. */
  has_controller: boolean
  exclusive_booking: boolean
  require_booking_for_rfid: boolean
  is_active: boolean
}

export interface BookingSlot {
  booking_id: number | null
  start_time: string
  end_time: string
  status: BookingStatus
  is_mine: boolean
  user_name: string | null
}

export interface LabOverview {
  lab: Lab
  occupied: boolean
  occupants: number
  available_now: boolean
  controller_online: boolean | null
  door_closed: boolean | null
  next_booking_at: string | null
  bookings_today: number
  open_issues: number
  high_priority_issues: number
}

export interface Device {
  id: number
  device_uid: string
  name: string
  device_type: 'MASTER_CONTROLLER' | 'CAMERA' | 'FACE_SERVER' | 'SENSOR_NODE'
  lab_id: number
  lab_code?: string | null
  ip_address: string | null
  firmware_version: string | null
  last_seen_at: string | null
  is_online: boolean
  door_closed: boolean | null
  component_state?: Record<string, unknown> | null
  /** ONLINE / OFFLINE / NO_DATA (never reported). */
  state: 'ONLINE' | 'OFFLINE' | 'NO_DATA'
  seconds_since_seen: number | null
}

export interface LabIssueBrief {
  id: number
  ticket_number: string | null
  title: string
  category: IssueCategory
  severity: IssueSeverity
  status: IssueStatus
  asset_name: string | null
  created_at: string
  is_mine: boolean
}

export interface LabStatus {
  lab: Lab
  occupied: boolean
  occupants: number
  current_booking_id: number | null
  current_users: string[]
  door_closed: boolean | null
  controller_online: boolean | null
  camera_online: boolean | null
  next_booking_at: string | null
  current_booking: BookingSlot | null
  upcoming: BookingSlot[]
  devices: Device[]
  open_issues: number
  high_priority_issues: number
  recent_issues: LabIssueBrief[]
}

export interface Booking {
  id: number
  user_id: number
  lab_id: number
  start_time: string
  end_time: string
  reason: string
  status: BookingStatus
  created_at: string
  cancelled_at?: string | null

  /** When the person ACTUALLY entered, as opposed to when they booked. */
  first_entry_at?: string | null
  last_entry_at?: string | null
  entry_count: number
  /** Minutes late (positive) or early (negative); null if never used. */
  entry_delay_minutes?: number | null
  currently_inside: boolean
  /** Only when an exit was actually observed. */
  last_exit_at?: string | null
  time_inside_minutes?: number | null
  qr_active: boolean

  lab_name?: string | null
  lab_code?: string | null
  lab_category?: string | null
  user_name?: string | null
  user_email?: string | null
}

export interface Session {
  id: number
  lab_id: number
  user_id: number
  booking_id: number | null
  entry_method: AuthMethod
  second_factor: AuthMethod | null
  started_at: string
  door_opened_at: string | null
  door_closed_at: string | null
  ended_at: string | null
  end_reason: SessionEndReason | null
  user_name?: string | null
  lab_code?: string | null
  duration_minutes: number | null
}

export interface QrPayload {
  booking_id: number
  token: string
  qr_png_base64: string
  valid_from: string
  valid_until: string
  status: BookingStatus
  lab_code: string
  lab_name: string
  is_currently_valid: boolean
}

export interface AccessEvent {
  id: number
  event_type: string
  lab_id: number | null
  user_id: number | null
  booking_id: number | null
  device_id: number | null
  method: string | null
  result: string | null
  reason: string | null
  message: string
  created_at: string
  user_name?: string | null
  lab_code?: string | null
  device_name?: string | null
}

export interface TraceSummary {
  first_factor: AuthMethod | null
  first_factor_identity: string | null
  qr_result: string | null
  second_factor: AuthMethod | null
  second_factor_identity: string | null
  result: 'GRANTED' | 'DENIED' | null
  denial_reason: string | null
  entry_at: string | null
  door_opened_at: string | null
  door_closed_at: string | null
  exit_at: string | null
  exit_recorded: boolean
  session_end_reason: SessionEndReason | null
  duration_minutes: number | null
  attempts: number
  denials: number
}

export interface BookingTrace {
  booking: Booking
  user: { id: number; full_name: string; role: Role; auth_subject: string | null }
  lab: Lab
  token: {
    issued_at: string; valid_from: string; valid_until: string
    revoked_at: string | null; last_used_at: string | null
    use_count: number; state: 'ISSUED' | 'VALID' | 'EXPIRED' | 'REVOKED'
  } | null
  summary: TraceSummary
  sessions: Session[]
  events: AccessEvent[]
}

export interface Asset {
  id: number
  asset_tag: string
  name: string
  category: string
  lab_id: number
  status: 'AVAILABLE' | 'CHECKED_OUT' | 'MAINTENANCE' | 'RETIRED'
  notes: string
  lab_code?: string | null
  lab_name?: string | null
  open_issues: number
}

export interface AssetDetail {
  asset: Asset
  lab: Lab
  transactions: { id: number; action: string; note: string; created_at: string;
                  user_name: string | null }[]
  maintenance: {
    id: number; ticket_number: string | null; title: string
    category: IssueCategory; severity: IssueSeverity; status: IssueStatus
    created_at: string; resolved_at: string | null; technician: string | null
    resolution_notes: string; is_mine: boolean
  }[]
}

export interface Alert {
  id: number
  lab_id: number | null
  device_id: number | null
  severity: 'INFO' | 'WARNING' | 'CRITICAL'
  title: string
  detail: string
  is_resolved: boolean
  created_at: string
  resolved_at: string | null
  lab_code?: string | null
}

export interface Summary {
  total_labs: number
  occupied_labs: number
  active_bookings: number
  upcoming_bookings: number
  granted_today: number
  denied_today: number
  devices_online: number
  devices_total: number
  open_alerts: number
  labs_with_hardware: number
  active_users: number
  bookings_today: number
  pending_bookings: number
  people_inside: number
  security_events_today: number
  assets_total: number
  assets_in_maintenance: number
  assets_checked_out: number
  open_issues: number
  critical_issues: number
  high_issues: number
  unassigned_issues: number
  overdue_issues: number
}

export interface IssuePhoto {
  id: number
  stage: PhotoStage
  original_filename: string
  content_type: string
  size_bytes: number
  width: number
  height: number
  created_at: string
  uploaded_by_name: string | null
}

export interface IssueComment {
  id: number
  body: string
  is_internal: boolean
  created_at: string
  author_id: number
  author_name: string | null
  author_role: Role | null
}

export interface IssueHistory {
  id: number
  event_type: string
  old_status: IssueStatus | null
  new_status: IssueStatus | null
  message: string
  created_at: string
  actor_name: string | null
  actor_role: Role | null
}

export interface Issue {
  id: number
  ticket_number: string | null
  lab_id: number
  asset_id: number | null
  device_id: number | null
  access_event_id: number | null
  category: IssueCategory
  severity: IssueSeverity
  status: IssueStatus
  title: string
  description: string
  additional_comments: string
  resolution_notes: string
  reporter_id: number
  assigned_to_id: number | null
  created_at: string
  updated_at: string
  acknowledged_at: string | null
  resolved_at: string | null
  closed_at: string | null
  lab_code: string | null
  lab_name: string | null
  asset_tag: string | null
  asset_name: string | null
  device_name: string | null
  reporter_name: string | null
  assignee_name: string | null
  photo_count: number
  is_overdue: boolean
}

export interface IssueDetail extends Issue {
  photos: IssuePhoto[]
  comments: IssueComment[]
  history: IssueHistory[]
  can_manage: boolean
  can_close: boolean
  can_comment: boolean
  can_add_photos: boolean
  allowed_statuses: IssueStatus[]
}

export interface CountRow { key: string; label: string; count: number }

export interface IssueSummary {
  open: number
  critical: number
  high: number
  in_progress: number
  waiting_for_parts: number
  unassigned: number
  overdue: number
  resolved_this_month: number
  total: number
  avg_resolution_hours: number | null
  by_lab: CountRow[]
  by_category: CountRow[]
  by_asset: CountRow[]
  by_status: CountRow[]
  trend: { day: string; created: number; resolved: number }[]
  sla_hours: Record<IssueSeverity, number>
}

export interface Notification {
  id: number
  kind: string
  severity: 'info' | 'warning' | 'critical'
  title: string
  body: string
  link: string | null
  issue_id: number | null
  booking_id: number | null
  is_read: boolean
  created_at: string
}

export interface SystemStatus {
  status: 'HEALTHY' | 'DEGRADED'
  api: boolean
  database: boolean
  websocket_clients: number
  devices_online: number
  devices_total: number
  devices_reporting: number
  controllers_online: number
  controllers_total: number
  last_heartbeat_at: string | null
  time: string
}

export interface SystemConfig {
  environment: string
  booking_auto_approve: boolean
  max_booking_hours: number
  booking_grace_minutes: number
  booking_reminder_minutes: number
  qr_token_bytes: number
  access_token_expire_minutes: number
  device_stale_seconds: number
  max_upload_mb: number
  max_photos_per_issue: number
  image_max_dimension: number
  issue_sla_hours: Record<string, number>
  storage_backend: string
}

export interface ReportsOverview {
  period_days: number
  generated_at: string
  bookings_by_lab: { label: string; name: string; count: number; hours: number; used: number }[]
  booking_volume: { day: string; count: number }[]
  booking_hours_utc: { hour: number; count: number }[]
  entry_hours_utc: { hour: number; count: number }[]
  utilisation: { bookings: number; finished: number; used: number; no_show: number;
                 used_rate: number | null }
  entry_delays: Partial<Record<'early' | 'on_time' | 'late_5_15' | 'late_15_30' | 'late_30_plus', number>>
  access_outcomes: { day: string; granted: number; denied: number }[]
  denial_reasons: { reason: string; count: number }[]
  asset_checkouts: { label: string; count: number }[]
}

// ---------------------------------------------------------------------------
const TOKEN_KEY = 'slp.token'

export function getToken(): string | null {
  try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(t: string | null) {
  try {
    if (t) sessionStorage.setItem(TOKEN_KEY, t)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch { /* private mode - the in-memory session still works */ }
}

export class ApiError extends Error {
  status: number
  code?: string
  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

function expired(): never {
  setToken(null)
  // Full reload so every component drops its stale state at once.
  if (!location.pathname.startsWith('/login')) {
    location.href = `/login?expired=1&next=${encodeURIComponent(location.pathname)}`
  }
  throw new ApiError(401, 'Session expired')
}

async function parseError(res: Response): Promise<ApiError> {
  let message = res.statusText || `Request failed (${res.status})`
  let code: string | undefined
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') message = body.detail
    else if (body.detail?.message) {
      message = body.detail.message
      code = body.detail.code
    } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      // FastAPI validation error: first human-readable message.
      message = String(body.detail[0].msg).replace(/^Value error, /, '')
      code = 'VALIDATION'
    }
  } catch { /* non-JSON error body */ }
  return new ApiError(res.status, message, code)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.body && !(init.body instanceof FormData)
      ? { 'Content-Type': 'application/json' } : {}),
    ...(init.headers as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`/api${path}`, { ...init, headers })
  if (res.status === 401 && token) expired()
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

const qs = (q: Record<string, unknown>) => {
  const p = new URLSearchParams()
  Object.entries(q).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    if (Array.isArray(v)) v.forEach(x => p.append(k, String(x)))
    else p.set(k, String(v))
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

/** Upload with progress. fetch() cannot report upload progress; XHR can. */
function upload<T>(path: string, form: FormData,
                   onProgress?: (fraction: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api${path}`)
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = e => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
    }
    xhr.onload = async () => {
      if (xhr.status === 401 && token) { try { expired() } catch (e) { reject(e) } return }
      const res = new Response(xhr.responseText, { status: xhr.status })
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText))
      else reject(await parseError(res))
    }
    xhr.onerror = () => reject(new ApiError(0, 'Network error while uploading'))
    xhr.send(form)
  })
}

/** Fetch a protected binary (photo, CSV) with the auth header. */
export async function fetchBlob(path: string): Promise<Blob> {
  const token = getToken()
  const res = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (res.status === 401 && token) expired()
  if (!res.ok) throw await parseError(res)
  return res.blob()
}

export const api = {
  login: (email: string, password: string) =>
    post<{ access_token: string; role: Role; user_id: number; full_name: string }>(
      '/auth/login', { email, password }),
  me: () => request<User>('/auth/me'),

  // --- labs
  labs: () => request<Lab[]>('/labs'),
  labsOverview: () => request<LabOverview[]>('/labs/overview'),
  lab: (id: number) => request<LabStatus>(`/labs/${id}`),
  labActivity: (id: number, limit = 80) =>
    request<AccessEvent[]>(`/labs/${id}/activity?limit=${limit}`),
  labSensors: (id: number) => request<unknown[]>(`/labs/${id}/sensors`),
  labIssues: (id: number) => request<LabIssueBrief[]>(`/labs/${id}/issues`),
  availability: (id: number, start: string, end: string) =>
    request<BookingSlot[]>(`/labs/${id}/availability${qs({ start, end })}`),

  // --- bookings
  bookings: (q: { lab_id?: number; user_id?: number; status?: string;
                  from?: string; to?: string } = {}) =>
    request<Booking[]>(`/bookings${qs(q)}`),
  booking: (id: number) => request<Booking>(`/bookings/${id}`),
  createBooking: (b: { lab_id: number; start_time: string; end_time: string;
                       reason: string; user_id?: number }) =>
    post<Booking>('/bookings', b),
  cancelBooking: (id: number) => post<Booking>(`/bookings/${id}/cancel`),
  confirmBooking: (id: number) => post<Booking>(`/bookings/${id}/confirm`),
  rejectBooking: (id: number, note = '') => post<Booking>(`/bookings/${id}/reject`, { note }),
  qr: (id: number) => request<QrPayload>(`/bookings/${id}/qr`),
  trace: (id: number) => request<BookingTrace>(`/bookings/${id}/trace`),

  // --- access
  events: (q: Record<string, string | number | boolean | string[] | undefined> = {}) =>
    request<AccessEvent[]>(`/access-events${qs(q)}`),
  sessions: (q: { lab_id?: number; open_only?: boolean; limit?: number } = {}) =>
    request<Session[]>(`/access-sessions${qs(q)}`),
  exportEventsPath: (labId?: number) =>
    `/access-events/export${labId ? `?lab_id=${labId}` : ''}`,

  // --- operations
  summary: () => request<Summary>('/summary'),
  users: () => request<User[]>('/users'),
  createUser: (u: Partial<User> & { password: string }) =>
    post<User>('/auth/register', u),
  updateUser: (id: number, u: Partial<User>) =>
    request<User>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(u) }),
  devices: (labId?: number) => request<Device[]>(`/devices${qs({ lab_id: labId })}`),
  createDevice: (d: { device_uid: string; name: string; device_type: string; lab_id: number;
                      ip_address?: string | null }) => post<Device>('/devices', d),
  createAsset: (a: { asset_tag: string; name: string; category: string; lab_id: number;
                     notes?: string }) => post<Asset>('/assets', a),
  assets: (labId?: number) => request<Asset[]>(`/assets${qs({ lab_id: labId })}`),
  asset: (id: number) => request<AssetDetail>(`/assets/${id}`),
  updateAsset: (id: number, body: { status?: string; notes?: string }) =>
    request<Asset>(`/assets/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  checkoutAsset: (id: number) => post<Asset>(`/assets/${id}/checkout`),
  returnAsset: (id: number) => post<Asset>(`/assets/${id}/return`),
  alerts: (openOnly = false) => request<Alert[]>(`/alerts${qs({ open_only: openOnly })}`),
  resolveAlert: (id: number) => post<Alert>(`/alerts/${id}/resolve`),
  accessReport: (days = 7) =>
    request<{ lab: string; day: string; event: string; count: number }[]>(
      `/reports/access?days=${days}`),
  reports: (days = 30) => request<ReportsOverview>(`/reports/overview?days=${days}`),

  // --- issues
  issues: (q: Record<string, string | number | boolean | string[] | undefined> = {}) =>
    request<Issue[]>(`/issues${qs(q)}`),
  issue: (id: number) => request<IssueDetail>(`/issues/${id}`),
  issueSummary: (labId?: number) => request<IssueSummary>(`/issues/summary${qs({ lab_id: labId })}`),
  createIssue: (b: {
    lab_id: number; asset_id?: number | null; device_id?: number | null
    access_event_id?: number | null; category: IssueCategory
    severity: IssueSeverity; title: string; description: string
    additional_comments?: string }) => post<IssueDetail>('/issues', b),
  updateIssue: (id: number, b: Partial<Pick<Issue, 'severity' | 'category' | 'title' |
    'asset_id' | 'device_id' | 'resolution_notes'>>) =>
    request<IssueDetail>(`/issues/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
  acknowledgeIssue: (id: number) => post<IssueDetail>(`/issues/${id}/acknowledge`),
  assignIssue: (id: number, assignee_id: number | null) =>
    post<IssueDetail>(`/issues/${id}/assign`, { assignee_id }),
  setIssueStatus: (id: number, status: IssueStatus, note = '') =>
    post<IssueDetail>(`/issues/${id}/status`, { status, note }),
  resolveIssue: (id: number, resolution_notes: string) =>
    post<IssueDetail>(`/issues/${id}/resolve`, { resolution_notes }),
  closeIssue: (id: number, note = '') => post<IssueDetail>(`/issues/${id}/close`, { note }),
  reopenIssue: (id: number, note = '') => post<IssueDetail>(`/issues/${id}/reopen`, { note }),
  commentIssue: (id: number, body: string, is_internal = false) =>
    post<IssueComment>(`/issues/${id}/comments`, { body, is_internal }),
  uploadIssuePhotos: (id: number, files: File[], stage: PhotoStage = 'REPORT',
                      onProgress?: (f: number) => void) => {
    const form = new FormData()
    files.forEach(f => form.append('files', f, f.name))
    form.append('stage', stage)
    return upload<IssuePhoto[]>(`/issues/${id}/photos`, form, onProgress)
  },
  issuePhotoPath: (issueId: number, photoId: number, variant: 'full' | 'thumb' = 'full',
                   download = false) =>
    `/issues/${issueId}/photos/${photoId}/file${qs({ variant, download: download || undefined })}`,

  // --- notifications
  notifications: (unreadOnly = false, limit = 50) =>
    request<Notification[]>(`/notifications${qs({ unread_only: unreadOnly || undefined, limit })}`),
  unreadCount: () => request<{ unread: number }>('/notifications/unread-count'),
  markRead: (id: number) => post<Notification>(`/notifications/${id}/read`),
  markAllRead: () => post<{ updated: number }>('/notifications/read-all'),

  // --- system
  systemStatus: () => request<SystemStatus>('/system/status'),
  systemConfig: () => request<SystemConfig>('/system/config'),
}
