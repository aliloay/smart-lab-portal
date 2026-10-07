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
  fingerprint_enrolled_at?: string | null
  face_enrolled_at?: string | null
}

export interface AccessSetupItem {
  key: 'identity' | 'fingerprint' | 'face'
  label: string; done: boolean; how: string
  value?: string | null; at?: string | null
}
/** One lab on the wall screen (/monitor). null = never reported. */
export interface MonitorTile {
  lab_id: number; code: string; name: string; has_door: boolean
  state: 'OK' | 'WARN' | 'ALERT'
  controller_online: boolean | null; camera_online: boolean | null
  door_closed: boolean | null; locked: boolean | null; faults: string[]
  people: { name: string | null; role: Role | null; since: string }[]
  /** Head count per role, e.g. { STUDENT: 2, LAB_STAFF: 1 }. */
  people_by_role: Partial<Record<Role, number>>
  /** Someone inside or booked right now. */
  in_use: boolean
  booking: { name: string | null; until: string } | null
  next_booking_at: string | null
  alerts: { severity: 'INFO' | 'WARNING' | 'CRITICAL'; title: string; at: string; count: number }[]
  alert_count: number
  last_event: { type: string; result: string | null; who: string | null;
                reason: string | null; at: string } | null
  environment: Partial<Record<'temperature' | 'humidity', { value: number; unit: string; at: string }>>
  /** Active hazard states: smoke, flame, water_leak, emergency. */
  hazards: string[]
  /** Environment node reporting? null = the lab has none. */
  env_online: boolean | null
  motion: boolean
  /** The lab's fixed security camera (tools/security_vision); null = none. */
  security_camera: SecurityCameraTile | null
  /** Set by an administrator from the Emergency tab; null = none. */
  emergency: EmergencyState | null
}

export interface EmergencyState {
  door_mode: 'NORMAL' | 'UNLOCKED' | 'LOCKDOWN'; door_until: string | null; door_remaining_s: number | null
  message: string; message_until: string | null; alarm: boolean; speak: boolean; version: number; active: boolean
  updated_at: string
}
/** A lab's emergency message / alarm, for every signed-in screen (GET /emergency/active). */
export interface EmergencyBroadcast {
  lab_id: number; lab_code: string; message: string; speak: boolean; alarm: boolean
  version: number; active: boolean; at: string | null
}
export interface EmergencyLab extends EmergencyState {
  lab_id: number; code: string; name: string; has_door: boolean; controller_online: boolean | null
  door_closed: boolean | null; lock_released: boolean | null; applied: boolean; updated_by: string | null
}
export interface EmergencyAction {
  door?: 'NORMAL' | 'UNLOCKED' | 'LOCKDOWN'; minutes?: number | null
  message?: string; message_minutes?: number | null; alarm?: boolean; speak?: boolean
}

export interface SecurityCameraTile {
  device_id: number; online: boolean | null; source_ok: boolean | null
  /** People the camera sees now, and how many of them it could not name. */
  people: number | null; unknown: number | null
  /** source: how the name was given; entered = false: named by face, no door entry yet (on hold). */
  named: { label: string; name: string; role: Role | null; source?: 'door' | 'face' | null; entered?: boolean
           /** door and face agree */ verified?: boolean; /** the face says this other person */ face?: string | null }[]
  /** People inside per the door. */
  inside: number
  open_events: number
}
export interface SecurityCamera extends SecurityCameraTile {
  device_uid: string; name: string; lab_id: number; lab_code: string | null
  last_seen_at: string | null; fps: number | null
  zones: { id: number; name: string; status: 'LEARNING' | 'OK' | 'IN_USE' | 'CHANGED' | 'MOTION'; score: number }[]
  /** Seen by the camera (red door leaf in the door box); null = no door box / offline. */
  door_open?: boolean | null
}
/** Where a record came from (thesis traceability); set once, never rewritten. */
export type Provenance = 'REAL_OPERATION' | 'PHYSICAL_TEST' | 'BENCH_TEST' | 'SOFTWARE_TEST'
  | 'RECOVERED_HISTORY' | 'DEMO_DATA' | 'UNKNOWN_PROVENANCE'
export interface ExperimentTrial {
  id: number; repeat_number: number; input: string; expected: string; actual: string
  measurement: number | null; unit: string | null; result: 'PASS' | 'FAIL' | 'NA' | null; notes: string
  recorded_at: string
}
export interface Experiment {
  id: number; code: string; name: string; subsystem: string; operator_id: number | null
  device_id: number | null; firmware_version: string | null; hardware_configuration: string
  environment: string; network_state: string; data_mode: Provenance; test_condition: string
  expected_result: string; actual_result: string; result: 'PASS' | 'FAIL' | 'PARTIAL' | 'INCONCLUSIVE' | null
  notes: string; status: 'PLANNED' | 'RUNNING' | 'FINISHED'; started_at: string | null; ended_at: string | null
  created_at: string
  trials?: ExperimentTrial[]; records?: Record<string, number>
}
/** The camera service's recorder (GET /security/cameras/{id}/recording). */
export interface RecordingStatus {
  recording: boolean; file: string | null; started_at: string | null; started_by: string | null
  elapsed_s: number | null; parts: number; segment_s: number; ffmpeg: boolean; free_gb: number; min_free_gb: number
}
export interface Recording {
  file: string; size_bytes: number; recording: boolean; started_at: string | null; stopped_at: string | null
  duration_s: number | null; started_by: string | null; stopped_by: string | null; stop_reason: string | null
  /** Part n of N of one recording (split into 1-hour files). */
  part?: number | null; parts?: number | null; recording_started_at?: string | null
}
export interface EquipmentSuggestion {
  kind: string; score: number; name: string; x: number; y: number; w: number; h: number
  replaces: number | null          // a saved box that is off this item: "move it here"
}
export interface SecurityZone {
  id: number; name: string; kind: 'EQUIPMENT' | 'DOOR'; asset_id: number | null; asset_tag: string | null
  x: number; y: number; w: number; h: number; alert_on_motion: boolean; ref_version: number
}
export type SecurityZoneIn = Omit<SecurityZone, 'id' | 'asset_tag' | 'ref_version'>
export interface SecurityEvent {
  id: number; device_id: number; lab_code: string | null; kind: string; title: string
  zone_name: string | null; detail: string; people_seen: number; people_inside: number
  has_snapshot: boolean; created_at: string; acknowledged_at: string | null; acknowledged_by: string | null
}

/** A request the door controller fetches and carries out (fingerprint enrollment). */
export interface DeviceCommand {
  id: number; command: string
  status: 'PENDING' | 'SENT' | 'RUNNING' | 'DONE' | 'FAILED' | 'EXPIRED' | 'CANCELLED'
  step: string | null; message: string | null; args: Record<string, unknown>
  created_at: string; expires_at: string; sent_at: string | null; completed_at: string | null
}

/** A consumable weighing bin (Robotics Lab, System 3). */
export interface InventoryBin {
  id: number; code: string; item_name: string; category: string
  lab_id: number; lab_code: string | null; device_uid: string | null
  mass_g: number | null; measured_at: string | null
  quality: 'VALID' | 'STALE' | 'MISSING' | 'DEVICE_OFFLINE'
  calibrated: boolean; tare_g: number | null; unit_mass_g: number | null
  noise_g: number | null; calibrated_at: string | null; min_change_g: number
  qty_est: number | null; qty_err: number | null; reorder_qty: number | null
  low: boolean; notes: string; is_active: boolean
}
export interface InventoryTx {
  id: number; kind: 'WITHDRAWAL' | 'REFILL' | 'COUNT'
  delta_mass_g: number | null; delta_qty_est: number | null; qty_est_after: number | null
  actual_count: number | null; attribution: string; user_name: string | null
  booking_id: number | null; note: string; recorded_at: string
}

/** A tagged item of a lab's reusable smart bin (System 4). */
export interface BinItem {
  id: number; asset_tag: string; name: string; category: string
  status: 'AVAILABLE' | 'CHECKED_OUT' | 'MAINTENANCE' | 'RETIRED'
  holder: string | null; checked_out_at: string | null; nfc_uid?: string
}

/** Face photos a person sent for review (Profile -> Face ID). */
export interface FaceSubmission {
  id: number; user_id: number; user_name: string | null; auth_subject: string | null
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN'
  photo_count: number; has_photos: boolean; created_at: string; reviewed_at: string | null
  reason: string | null; samples_saved: number | null; min_samples: number
}

/** Face enrollment status (Users & roles -> Edit user -> Face ID). */
export interface FaceStatus {
  auth_subject: string | null; face_enrolled_at: string | null
  samples: number; has_photo: boolean; face_server_online: boolean
  camera_page_url: string; target_samples: number; min_samples: number
}

export interface AccessSetup {
  complete: boolean; needed: boolean; auth_subject: string | null
  items: AccessSetupItem[]; summary: string; pending: string[]
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
  device_type: 'MASTER_CONTROLLER' | 'CAMERA' | 'FACE_SERVER' | 'SENSOR_NODE' | 'SECURITY_CAMERA'
  lab_id: number
  /** Uses its own key (Devices -> Issue key) rather than the shared one. */
  has_own_key?: boolean
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

export interface SessionTrace {
  session: Session
  user: { id: number; full_name: string; role: Role; auth_subject: string | null }
  lab: Lab
  booking: Booking | null
  summary: TraceSummary
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
  lab_location?: string | null
  open_issues: number
  serial_number?: string | null
  holder_id?: number | null
  /** Staff only. */
  holder_name?: string | null
  checked_out_at?: string | null
  last_inspected_at?: string | null
  next_maintenance_at?: string | null
  maintenance_due: boolean
  /** NFC sticker for the reusable smart bin; null = not tagged. */
  nfc_uid?: string | null
  unit_mass_g?: number | null
  /** Kept in the reusable smart bin (System 4), not fixed equipment. */
  bin_item?: boolean
}

export interface LifecycleEntry {
  at: string
  kind: 'ISSUE_REPORTED' | 'ISSUE_RESOLVED' | 'INSPECTION' | 'CHECKOUT' | 'RETURN' | 'STATUS'
  title: string
  detail: string
  actor: string | null
  issue_id: number | null
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
  lifecycle: LifecycleEntry[]
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
  /** "n8n" (automation) or "portal"; null = from before this was recorded. */
  source?: string | null
}
export type InboxTab = 'all' | 'unread' | 'n8n' | 'portal' | 'critical'
export interface Inbox {
  items: Notification[]; total: number; counts: Record<InboxTab, number>; kinds: string[]
}

export interface SystemStatus {
  status: 'HEALTHY' | 'DEGRADED'
  /** Optional uplink; null = not checked yet. Not part of 'healthy'. */
  internet?: boolean | null
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

// --- analytics (Operations Center, lab twin, my usage) ----------------------
export interface EnvSeries {
  metric: string; unit: string; min: number | null; max: number | null
  latest: number; latest_at: string
  /** Readings in the period (points is a sparkline of at most 120). */
  count?: number
  points: { t: string; v: number; lab_id: number }[]
}
/** Latest environment value per metric with its quality (System 2). */
export type EnvQuality = 'VALID' | 'STALE' | 'MISSING' | 'DEVICE_OFFLINE' | 'OUT_OF_RANGE'
/** A smoke / flame alarm still open (GET /labs/hazards/active). */
export interface ActiveHazard {
  alert_id: number; lab_id: number; lab_code: string; metric: string
  label: string; title: string; detail: string; at: string | null
}

export interface LabEnvironment {
  node: { device_uid: string; online: boolean | null; last_seen_at: string | null } | null
  metrics: Record<'temperature' | 'humidity' | 'smoke' | 'flame' | 'water_leak' | 'motion' | 'emergency',
                  { value: number | null; unit: string | null; at: string | null; quality: EnvQuality }>
  hazards: string[]
}

export interface EnvironmentBlock {
  hours: number; has_data: boolean; message: string | null; series: EnvSeries[]
}
export interface AutomationStatus {
  api_enabled: boolean; push_enabled: boolean; dispatcher_running: boolean
  push_types: string[]
  outbox: { PENDING: number; DELIVERED: number; FAILED: number; SKIPPED: number }
  last_delivered_at: string | null
  last_error: { event_type: string; error: string; at: string } | null
  recent_runs: { workflow: string; status: string; summary: string; at: string }[]
}
export interface OpsDevice {
  device_id: number; name: string; type: string; lab_code: string | null
  state: 'ONLINE' | 'OFFLINE' | 'NO_DATA'; last_seen_at: string | null
  components: Record<string, boolean> | null
  offline_events: number; offline_minutes: number | null
  outages: { from: string; to: string }[]
}
export interface Operations {
  period_days: number; lab_id: number | null; generated_at: string
  timezone: string; open_hours_per_day: number
  utilisation: { lab_id: number; lab_code: string; lab_name: string; booked_hours: number
                 available_hours: number; utilisation: number | null; bookings: number
                 used: number }[]
  booked_heatmap: number[][]
  entry_heatmap: number[][]
  funnel: { step: string; count: number }[]
  granted_by_method: { method: string; count: number }[]
  access_outcomes: { day: string; granted: number; denied: number }[]
  denial_reasons: { reason: string; count: number }[]
  security: { identity_mismatch: number; alarms: number }
  sessions: {
    started: number; open_now: number; end_reasons: Record<string, number>
    exit_recorded: number; median_minutes: number | null
    duration_buckets: { label: string; count: number }[]
    second_factor: { entry: string; second: string; count: number }[]
  }
  devices: OpsDevice[]
  maintenance: {
    open: number; overdue: number; unassigned: number
    by_severity: { severity: string; count: number }[]
    flow: { day: string; opened: number; resolved: number }[]
    median_hours_to_resolve: { severity: string; hours: number; resolved: number }[]
    sla_hours: Record<string, number>
  }
  automation: AutomationStatus
  environment: EnvironmentBlock
}
export interface LabTwin {
  lab_id: number; days: number; timezone: string; open_hours_per_day: number
  heatmap: number[][]; heatmap_unit: string
  days_strip: { day: string; booked_hours: number }[]
  has_bookings: boolean
  environment: EnvironmentBlock
}
export interface MyStats {
  period_days: number; booked_hours: number; sessions_finished: number
  attended: number; attendance_rate: number | null; upcoming: number
  cancelled: number; by_lab: { lab_code: string; count: number }[]
  weekly_hours: { week: string; hours: number }[]
}

export interface TrendWeek {
  week: string; partial: boolean; bookings: number; booked_hours: number
  finished: number; no_shows: number; late: number; entries: number
  granted: number; denied: number; no_show_rate: number | null; late_rate: number | null
}
export interface Trends {
  weeks: number; timezone: string; late_minutes: number; series: TrendWeek[]
  week_over_week: Record<string, { current: number; previous: number | null; change: number | null }>
  by_lab: { lab_code: string; finished: number; no_shows: number; late: number; attended: number
            no_show_rate: number | null; late_rate: number | null }[]
}
export interface Priority {
  issue_id: number; ticket: string; title: string; lab_code: string | null
  severity: string; category: string; status: string; assigned: boolean
  age_hours: number; sla_hours: number | null; overdue: boolean
  bookings_next_24h: number; score: number; reasons: string[]; link: string
}
/** A chart the agent answered with: data from the records; the chat draws it. */
export interface AiChartData {
  kind: 'bar' | 'pie'; title: string; x: string[]; stacked?: boolean
  series: { name: string; color: string; data: number[]; colors?: string[] }[]
}
export interface AiAnswer {
  answer: string; tools_used: string[]; model: string
  /** Answered by the agent straight from the records (no model). */
  instant?: boolean; link?: { label: string; to: string }; charts?: AiChartData[]
}
export interface ManagementReport {
  charts?: AiChartData[]
  kind: 'weekly' | 'monthly'; span: string; title: string; period_label: string; generated_at: string
  lines: string[]
  bookings: { total: number; confirmed: number; cancelled: number; rejected: number; finished: number
    attended: number; no_show: number; attendance_rate: number | null; booked_hours: number }
  access: { granted: number; denied: number; identity_mismatch: number; forced_entry: number; door_held_open: number }
  sessions: { started: number; exit_recorded: number; exit_not_recorded: number }
  maintenance: { opened: number; resolved: number; open_now: number; critical_open: number; overdue_now: number }
  devices: { offline_now: string[]; offline_events: number }
  alerts: { opened: number }
  labs: { lab_code: string; bookings: number; hours: number; attended: number }[]
  change_pct: { bookings: number | null; hours: number | null; entries: number | null }
  equipment: { device_uid: string; name: string; kind: string; lab_code: string | null; running_h: number
    idle_h: number; fault_h: number; faults: number; users: number; master_pc: boolean }[]
  insights: { kind: string; title: string; lab_code: string | null; count: number; severity: string
    recommendation: string; first?: string | null; last?: string | null
    cause?: string; steps?: string[]; done_when?: string; ongoing?: boolean; unresolved?: number }[]
  top_denials: { reason: string; count: number; meaning: string }[]
}
export interface AiStatus {
  configured: boolean; provider: 'ollama' | 'anthropic' | null; model: string | null
  student_model?: string | null; reachable: boolean; missing_models: string[]; questions_per_hour: number
}

// ---------------------------------------------------------------------------
/** PC mode staff set; LOCKED = access removed (the agent keeps the PC locked). */
export type PcMode = 'NORMAL' | 'EXAM' | 'MAINTENANCE' | 'LOCKED'

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

// While the API restarts (about 12 s: migrations, seed, start-up) the web
// server answers 502/503/504. Reads wait and try again for up to ~25 s instead
// of leaving "Bad Gateway" on the page; writes are never repeated.
const RETRY_MS = [1000, 2000, 3000, 4000, 5000, 5000, 5000]
async function fetchRetrying(url: string, init: RequestInit): Promise<Response> {
  const read = !init.method || init.method === 'GET'
  for (let i = 0; ; i++) {
    try {
      const res = await fetch(url, init)
      if (!read || i >= RETRY_MS.length || ![502, 503, 504].includes(res.status)) return res
    } catch (e) {
      if (!read || i >= RETRY_MS.length) throw e
    }
    await new Promise(r => setTimeout(r, RETRY_MS[i]))
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.body && !(init.body instanceof FormData)
      ? { 'Content-Type': 'application/json' } : {}),
    ...(init.headers as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetchRetrying(`/api${path}`, { ...init, headers })
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
  signupConfig: () => request<{ enabled: boolean; email_domains: string[]; requires_approval: boolean }>(
    '/auth/signup-config'),
  signup: (u: { email: string; full_name: string; password: string; student_id?: string; department?: string }) =>
    post<{ pending_approval: boolean; message?: string; access_token?: string }>('/auth/signup', u),

  // --- labs
  labs: () => request<Lab[]>('/labs'),
  labsOverview: () => request<LabOverview[]>('/labs/overview'),
  lab: (id: number) => request<LabStatus>(`/labs/${id}`),
  labActivity: (id: number, limit = 80) =>
    request<AccessEvent[]>(`/labs/${id}/activity?limit=${limit}`),
  labSensors: (id: number) => request<unknown[]>(`/labs/${id}/sensors`),
  labEnvironment: (id: number) => request<LabEnvironment>(`/labs/${id}/environment`),
  allEnvironments: () => request<{ lab: Pick<Lab, 'id' | 'code' | 'name'>; env: LabEnvironment }[]>('/labs/environment/all'),
  activeHazards: () => request<ActiveHazard[]>('/labs/hazards/active'),
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
  session: (id: number) => request<SessionTrace>(`/access-sessions/${id}`),
  sessionLookup: (userId: number, labId: number, at: string) =>
    request<{ session_id: number | null }>(
      `/access-sessions/lookup${qs({ user_id: userId, lab_id: labId, at })}`),
  exportEventsPath: (labId?: number) =>
    `/access-events/export${labId ? `?lab_id=${labId}` : ''}`,

  // --- operations
  summary: () => request<Summary>('/summary'),
  users: () => request<User[]>('/users'),
  createUser: (u: Partial<User> & { password: string }) =>
    post<User>('/auth/register', u),
  myAccessSetup: () => request<AccessSetup>('/auth/me/access-setup'),
  userAccessSetup: (id: number) => request<AccessSetup>(`/users/${id}/access-setup`),
  nextAuthSubject: () => request<{ auth_subject: string | null }>('/users/next-auth-subject'),
  monitor: () => request<{ generated_at: string; labs: MonitorTile[] }>('/monitor'),
  // Emergency tab (admin): the token comes from the password, for a few minutes.
  emergencySession: (password: string) =>
    post<{ token: string; expires_at: string }>('/emergency/session', { password }),
  emergencyActive: () => request<EmergencyBroadcast[]>('/emergency/active'),
  emergencyStatus: () => request<{ password_set: boolean; labs: EmergencyLab[]
    pcs: { total: number; locked: number; master: number } }>('/emergency/status'),
  emergencyAct: (token: string, labId: number, a: EmergencyAction) =>
    request<EmergencyState>(`/emergency/labs/${labId}`, { method: 'POST', body: JSON.stringify(a),
      headers: { 'X-Emergency-Token': token } }),
  emergencyNormal: (token: string, labId: number) =>
    request<EmergencyState>(`/emergency/labs/${labId}/normal`, { method: 'POST',
      headers: { 'X-Emergency-Token': token } }),
  emergencyPcs: (token: string, a: { action: 'LOCK' | 'UNLOCK' | 'MESSAGE'; text?: string; include_master?: boolean }) =>
    request<{ done: number }>('/emergency/pcs', { method: 'POST', body: JSON.stringify(a),
      headers: { 'X-Emergency-Token': token } }),
  emergencyPassword: (token: string, new_password: string) =>
    request<{ ok: boolean }>('/emergency/password', { method: 'PUT', body: JSON.stringify({ new_password }),
      headers: { 'X-Emergency-Token': token } }),
  setMasterPc: (id: number, is_master: boolean) =>
    request<{ device_id: number; is_master_pc: boolean }>(`/equipment/${id}/master`,
      { method: 'PUT', body: JSON.stringify({ is_master }) }),
  // Security camera (fixed, lab corner): frames come through the portal.
  securityCameras: () => request<SecurityCamera[]>('/security/cameras'),
  securityZones: (cam: number) => request<SecurityZone[]>(`/security/cameras/${cam}/zones`),
  addSecurityZone: (cam: number, z: SecurityZoneIn) => post<SecurityZone>(`/security/cameras/${cam}/zones`, z),
  dataMode: () => request<{ mode: Provenance; experiment_id: number | null }>('/system/data-mode'),
  setDataMode: (mode: Provenance) =>
    request<{ mode: Provenance }>('/system/data-mode', { method: 'PUT', body: JSON.stringify({ mode }) }),
  experiments: () => request<Experiment[]>('/experiments'),
  experiment: (id: number) => request<Experiment>(`/experiments/${id}`),
  createExperiment: (e: Partial<Experiment>) => post<Experiment>('/experiments', e),
  startExperiment: (id: number) => post<Experiment>(`/experiments/${id}/start`),
  stopExperiment: (id: number, body: { actual_result: string; result: string | null; notes?: string }) =>
    post<Experiment>(`/experiments/${id}/stop`, body),
  addTrial: (id: number, t: Partial<ExperimentTrial>) => post<ExperimentTrial>(`/experiments/${id}/trials`, t),
  /** Monitors / laptops the detector finds now, numbered after the saved boxes (nothing saved). */
  securitySuggestions: (cam: number) => request<EquipmentSuggestion[]>(`/security/cameras/${cam}/suggestions`),
  // Recording (administrators): the video stays on the laptop.
  recordingStatus: (cam: number) => request<RecordingStatus>(`/security/cameras/${cam}/recording`),
  recordingSwitch: (cam: number, action: 'start' | 'stop') =>
    post<{ ok: boolean; file?: string; duration_s?: number; size_bytes?: number }>(`/security/cameras/${cam}/recording/${action}`),
  datasetStatus: (cam: number) => request<{ collecting: boolean; started_by: string; saved_this_run: number
    skipped_unchanged: number; total: number; interval_s: number; max_pictures: number }>(`/security/cameras/${cam}/dataset`),
  datasetSwitch: (cam: number, action: 'start' | 'stop') =>
    post<{ ok: boolean; saved?: number }>(`/security/cameras/${cam}/dataset/${action}`),
  recordings: (cam: number) => request<{ items: Recording[]; free_gb: number }>(`/security/cameras/${cam}/recordings`),
  recordingDelete: (cam: number, file: string) =>
    post<{ ok: boolean }>(`/security/cameras/${cam}/recordings/${encodeURIComponent(file)}/delete`),
  recordingLink: (cam: number, file: string) =>
    post<{ url: string; expires_at: string }>(`/security/cameras/${cam}/recordings/${encodeURIComponent(file)}/link`),
  updateSecurityZone: (cam: number, id: number, z: SecurityZoneIn) =>
    request<SecurityZone>(`/security/cameras/${cam}/zones/${id}`, { method: 'PUT', body: JSON.stringify(z) }),
  deleteSecurityZone: (cam: number, id: number) =>
    request<void>(`/security/cameras/${cam}/zones/${id}`, { method: 'DELETE' }),
  acceptSecurityZone: (cam: number, id: number) => post<SecurityZone>(`/security/cameras/${cam}/zones/${id}/accept`),
  securityEvents: (q: { lab_id?: number; open_only?: boolean; limit?: number } = {}) =>
    request<SecurityEvent[]>(`/security/events${qs(q)}`),
  ackSecurityEvent: (id: number) => post<SecurityEvent>(`/security/events/${id}/ack`),
  inventoryBins: () => request<InventoryBin[]>('/inventory/bins'),
  equipment: () => request<{
    device_id: number; device_uid: string; kind: 'ROBOT' | 'PC'; name: string; asset_tag: string | null
    lab_code: string | null; online: boolean | null; last_seen_at: string | null
    state: 'RUNNING' | 'IDLE' | 'FAULT' | null; since: string | null; detail: Record<string, unknown>
    user_name: string | null; booking_id: number | null; mode: PcMode
    running_today_s: number; open_violations: number; is_master_pc: boolean }[]>('/equipment'),
  equipmentViolations: () => request<{ id: number; device_uid: string; kind: string; detail: string
    os_user: string | null; reviewed: boolean; created_at: string }[]>('/equipment/violations'),
  setEquipmentMode: (id: number, mode: PcMode) =>
    request<{ device_id: number; mode: string }>(`/equipment/${id}/mode`, { method: 'PUT', body: JSON.stringify({ mode }) }),
  // Admin master PC (System 1): screen view while staff watch, and messages.
  pcScreenStart: (id: number) => post<{ watching: boolean }>(`/equipment/${id}/screen/start`),
  pcScreenStop: (id: number) => post<{ watching: boolean }>(`/equipment/${id}/screen/stop`),
  pcMessage: (id: number, text: string) => post<DeviceCommand>(`/equipment/${id}/message`, { text }),
  binItems: (labId: number) =>
    request<{ bin_online: boolean; bin_device: string | null; inside: boolean; items: BinItem[] }>(
      `/reusable/items?lab_id=${labId}`),
  takeFromBin: (assetId: number) =>
    post<DeviceCommand & { message: string }>('/reusable/checkout', { asset_id: assetId }),
  setItemMass: (assetId: number, unit_mass_g: number | null) =>
    request<{ asset_id: number; unit_mass_g: number | null }>(
      `/reusable/assets/${assetId}/mass`, { method: 'PUT', body: JSON.stringify({ unit_mass_g }) }),
  lastUnknownTag: () => request<{ nfc_uid: string; device_uid: string; at: string } | null>('/reusable/last-unknown'),
  assignTag: (assetId: number, nfc_uid: string | null) =>
    request<{ asset_id: number; asset_tag: string; nfc_uid: string | null }>(
      `/reusable/assets/${assetId}/tag`, { method: 'PUT', body: JSON.stringify({ nfc_uid }) }),
  createBin: (b: { code: string; lab_id: number; item_name: string; reorder_qty?: number | null }) =>
    post<InventoryBin>('/inventory/bins', b),
  updateBin: (id: number, b: Partial<Pick<InventoryBin, 'item_name' | 'tare_g' | 'unit_mass_g' |
    'noise_g' | 'min_change_g' | 'reorder_qty' | 'notes' | 'is_active'>>) =>
    request<InventoryBin>(`/inventory/bins/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
  binHistory: (id: number, hours = 168) =>
    request<{ bin: InventoryBin; measurements: { mass_g: number; at: string }[]; transactions: InventoryTx[] }>(
      `/inventory/bins/${id}/history?hours=${hours}`),
  recordBinCount: (id: number, actual_count: number, note = '') =>
    post<{ estimate: number | null; actual_count: number; error: number | null; mass_g: number | null }>(
      `/inventory/bins/${id}/count`, { actual_count, note }),
  myFaceSubmission: () => request<FaceSubmission | null>('/auth/me/face-submission'),
  submitFacePhotos: (files: File[], onProgress?: (f: number) => void) => {
    const form = new FormData()
    files.forEach(f => form.append('files', f))
    return upload<FaceSubmission>('/auth/me/face-submission', form, onProgress)
  },
  withdrawFaceSubmission: () => post<FaceSubmission>('/auth/me/face-submission/withdraw'),
  pendingFaceSubmission: (userId: number) =>
    request<FaceSubmission | null>(`/users/${userId}/face/submission`),
  approveFaceSubmission: (id: number) => post<FaceSubmission>(`/face-submissions/${id}/approve`),
  rejectFaceSubmission: (id: number, reason: string) =>
    post<FaceSubmission>(`/face-submissions/${id}/reject`, { reason }),
  fingerprintEnroll: (id: number, force: boolean) =>
    post<DeviceCommand>(`/users/${id}/fingerprint/enroll`, { force }),
  // RFID card: the person taps it at the door; the controller stores it.
  cardEnroll: (id: number) => post<DeviceCommand>(`/users/${id}/rfid/enroll`, {}),
  cardRemove: (id: number) => post<DeviceCommand>(`/users/${id}/rfid/remove`, {}),
  userCards: (id: number) => request<{ id: number; uid_hex: string; label: string; issued_at: string }[]>(`/users/${id}/rfid`),
  // Face photos uploaded by staff: straight to the face server, nothing kept.
  faceUpload: (id: number, files: File[], onProgress?: (f: number) => void) => {
    const form = new FormData()
    files.forEach(f => form.append('files', f))
    return upload<{ sent: number; saved: number; samples: number; face_enrolled: boolean; message: string }>(
      `/users/${id}/face/upload`, form, onProgress)
  },
  deviceCommand: (id: number) => request<DeviceCommand>(`/device-commands/${id}`),
  cancelDeviceCommand: (id: number) => post<DeviceCommand>(`/device-commands/${id}/cancel`),
  faceStatus: (id: number) => request<FaceStatus>(`/users/${id}/face`),
  faceCapture: (id: number) =>
    post<{ saved: boolean; samples: number | null; message: string }>(`/users/${id}/face/capture`),
  faceFinish: (id: number) =>
    post<{ trained: boolean; samples: number; has_photo: boolean; face_enrolled_at: string }>(
      `/users/${id}/face/finish`),
  /** Admins: anyone; lab staff: students only. Takes effect at the next sign-in. */
  setUserPassword: (id: number, new_password: string) =>
    request<{ ok: boolean }>(`/users/${id}/password`, { method: 'PUT', body: JSON.stringify({ new_password }) }),
  updateUser: (id: number, u: Partial<User> & { fingerprint_enrolled?: boolean; face_enrolled?: boolean }) =>
    request<User>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(u) }),
  devices: (labId?: number) => request<Device[]>(`/devices${qs({ lab_id: labId })}`),
  issueDeviceKey: (id: number) =>
    post<{ device_uid: string; device_key: string; note: string }>(`/devices/${id}/key`),
  createDevice: (d: { device_uid: string; name: string; device_type: string; lab_id: number;
                      ip_address?: string | null }) => post<Device>('/devices', d),
  createAsset: (a: { asset_tag: string; name: string; category: string; lab_id: number;
                     notes?: string; serial_number?: string | null;
                     next_maintenance_at?: string | null; bin_item?: boolean }) => post<Asset>('/assets', a),
  assets: (labId?: number, due?: boolean) =>
    request<Asset[]>(`/assets${qs({ lab_id: labId, due: due || undefined })}`),
  asset: (id: number) => request<AssetDetail>(`/assets/${id}`),
  updateAsset: (id: number, body: { status?: string; notes?: string; name?: string;
                                    category?: string; serial_number?: string | null;
                                    next_maintenance_at?: string | null }) =>
    request<Asset>(`/assets/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  inspectAsset: (id: number, note: string, nextMaintenanceAt?: string | null) =>
    post<Asset>(`/assets/${id}/inspect`, { note, next_maintenance_at: nextMaintenanceAt || null }),
  checkoutAsset: (id: number) => post<Asset>(`/assets/${id}/checkout`),
  returnAsset: (id: number) => post<Asset>(`/assets/${id}/return`),
  alerts: (openOnly = false) => request<Alert[]>(`/alerts${qs({ open_only: openOnly })}`),
  resolveAlert: (id: number) => post<Alert>(`/alerts/${id}/resolve`),
  accessReport: (days = 7) =>
    request<{ lab: string; day: string; event: string; count: number }[]>(
      `/reports/access?days=${days}`),
  reports: (days = 30) => request<ReportsOverview>(`/reports/overview?days=${days}`),
  operations: (days = 30, labId?: number) =>
    request<Operations>(`/analytics/operations${qs({ days, lab_id: labId })}`),
  trends: (weeks = 8, labId?: number) =>
    request<Trends>(`/analytics/trends${qs({ weeks, lab_id: labId })}`),
  exportCsvPath: (kind: 'bookings' | 'sessions' | 'events' | 'weekly', days = 90) =>
    `/analytics/export.csv${qs({ kind, days })}`,
  aiStatus: () => request<AiStatus>('/ai/status'),
  studentAiStatus: () => request<AiStatus>('/ai/student/status'),
  studentAiAsk: (question: string, history: { role: 'user' | 'assistant'; content: string }[] = []) =>
    post<AiAnswer>('/ai/student/ask', { question, history }),
  aiAsk: (question: string, history: { role: 'user' | 'assistant'; content: string }[] = []) =>
    post<AiAnswer>('/ai/ask', { question, history }),
  managementReport: (period: 'weekly' | 'monthly') => request<ManagementReport>(`/ai/report?period=${period}`),
  aiSummary: (kind: 'issues' | 'weekly') => post<AiAnswer>(`/ai/summaries/${kind}`),
  priorities: (limit = 20) =>
    request<{ open_issues: number; scoring: string[]; priorities: Priority[] }>(
      `/ai/maintenance-priorities${qs({ limit })}`),
  labTwin: (id: number) => request<LabTwin>(`/analytics/labs/${id}`),
  myStats: (days = 90) => request<MyStats>(`/analytics/me?days=${days}`),

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
  inbox: (q: { tab?: InboxTab; kind?: string; q?: string; offset?: number; limit?: number }) =>
    request<Inbox>(`/notifications/inbox${qs(q)}`),

  // --- system
  systemStatus: () => request<SystemStatus>('/system/status'),
  systemConfig: () => request<SystemConfig>('/system/config'),
}
