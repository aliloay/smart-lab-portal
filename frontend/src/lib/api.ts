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

export interface User {
  id: number
  email: string
  full_name: string
  role: Role
  is_active: boolean
  auth_subject: string | null
  student_id: string | null
  department: string | null
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

export interface LabStatus {
  lab: Lab
  occupied: boolean
  current_booking_id: number | null
  current_users: string[]
  door_closed: boolean | null
  controller_online: boolean | null
  camera_online: boolean | null
  next_booking_at: string | null
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

  /** When the person ACTUALLY entered, as opposed to when they booked. */
  first_entry_at?: string | null
  last_entry_at?: string | null
  entry_count: number
  /** Minutes late (positive) or early (negative); null if never used. */
  entry_delay_minutes?: number | null

  lab_name?: string | null
  lab_code?: string | null
  lab_category?: string | null
  user_name?: string | null
  user_email?: string | null
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
}

export interface Device {
  id: number
  device_uid: string
  name: string
  device_type: string
  lab_id: number
  ip_address: string | null
  firmware_version: string | null
  last_seen_at: string | null
  is_online: boolean
  door_closed: boolean | null
}

export interface Asset {
  id: number
  asset_tag: string
  name: string
  category: string
  lab_id: number
  status: string
  notes: string
}

export interface Alert {
  id: number
  lab_id: number | null
  severity: string
  title: string
  detail: string
  is_resolved: boolean
  created_at: string
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
}

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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`/api${path}`, { ...init, headers })

  if (res.status === 401) {
    setToken(null)
    // Full reload so every component drops its stale state at once.
    if (!location.pathname.startsWith('/login')) location.href = '/login'
    throw new ApiError(401, 'Session expired')
  }

  if (!res.ok) {
    let message = res.statusText
    let code: string | undefined
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (body.detail?.message) {
        message = body.detail.message
        code = body.detail.code
      }
    } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, message, code)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; role: Role; user_id: number; full_name: string }>(
      '/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  me: () => request<User>('/auth/me'),

  labs: () => request<Lab[]>('/labs'),
  lab: (id: number) => request<LabStatus>(`/labs/${id}`),
  labActivity: (id: number, limit = 80) =>
    request<AccessEvent[]>(`/labs/${id}/activity?limit=${limit}`),
  labSensors: (id: number) => request<unknown[]>(`/labs/${id}/sensors`),

  bookings: () => request<Booking[]>('/bookings'),
  booking: (id: number) => request<Booking>(`/bookings/${id}`),
  createBooking: (b: { lab_id: number; start_time: string; end_time: string; reason: string }) =>
    request<Booking>('/bookings', { method: 'POST', body: JSON.stringify(b) }),
  cancelBooking: (id: number) =>
    request<Booking>(`/bookings/${id}/cancel`, { method: 'POST' }),
  confirmBooking: (id: number) =>
    request<Booking>(`/bookings/${id}/confirm`, { method: 'POST' }),
  qr: (id: number) => request<QrPayload>(`/bookings/${id}/qr`),

  events: (q: Record<string, string | number | undefined> = {}) => {
    const p = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => {
      if (v !== undefined && v !== '') p.set(k, String(v))
    })
    return request<AccessEvent[]>(`/access-events?${p.toString()}`)
  },

  summary: () => request<Summary>('/summary'),
  users: () => request<User[]>('/users'),
  devices: () => request<Device[]>('/devices'),
  assets: (labId?: number) =>
    request<Asset[]>(`/assets${labId ? `?lab_id=${labId}` : ''}`),
  checkoutAsset: (id: number) =>
    request<Asset>(`/assets/${id}/checkout`, { method: 'POST' }),
  returnAsset: (id: number) =>
    request<Asset>(`/assets/${id}/return`, { method: 'POST' }),
  alerts: () => request<Alert[]>('/alerts'),
  exportEventsUrl: (labId?: number) =>
    `/api/access-events/export${labId ? `?lab_id=${labId}` : ''}`,

  accessReport: (days = 7) =>
    request<{ lab: string; day: string; event: string; count: number }[]>(
      `/reports/access?days=${days}`),
  health: () => request<{ status: string; database: boolean }>('/health'),
}
