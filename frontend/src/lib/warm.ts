/**
 * The first reads each page makes, PER ROLE (recorded 2026-10-20 in a real browser as admin, lab staff
 * and student), started on sidebar hover / focus / touch so the data is usually there when the click
 * lands (lib/api.ts warmGets: shared, max 5 s old, dropped by any write).
 *
 * Per role on purpose: a page can show different things to different roles (Issues = the staff
 * maintenance queue, or a student's own reports). Warming one role's reads for another would ask for
 * data that role may not see - the server refuses (403), but it is wasted work and noise.
 * Paths must match the pages' own request paths exactly, or the warm-up is simply not used.
 */
import type { Role } from './api'
import { warmGets } from './api'

const STAFF_PAGES: Record<string, string[]> = {
  '/admin/alerts': ['/alerts?open_only=false'],
  '/notifications': ['/notifications/inbox?tab=all&offset=0&limit=50'],
  '/admin/devices': ['/devices'],
  '/admin/users': ['/face-submissions', '/users'],
  '/admin/access': ['/labs', '/users', '/access-events?limit=400'],
  '/admin/bookings': ['/bookings'],
  '/admin/incidents': ['/incidents?state=ACTIVE'],
  '/admin/operations': ['/analytics/trends?weeks=5', '/analytics/operations?days=30', '/labs'],
  '/admin/system': ['/system/health', '/analytics/anomalies', '/analytics/system?days=30'],
  '/admin/reliability': ['/reliability/briefing'],
  '/admin/equipment': ['/labs/environment/all', '/labs/1/environment'],
  '/issues': ['/issues?limit=500&active=true', '/issues/summary', '/labs', '/users'],
  '/command': ['/robots', '/monitor', '/security/cameras', '/system/services', '/alerts?open_only=true',
               '/access-events?limit=40', '/security/events?limit=30', '/labs/environment/all'],
  '/admin/security': ['/labs'],
}

const WARM: Record<Role, Record<string, string[]>> = {
  ADMIN: {
    ...STAFF_PAGES,
    '/': ['/access-events?limit=30&security_only=true', '/issues/summary', '/issues?active=true&limit=50',
          '/access-events?limit=40', '/devices', '/summary', '/labs/overview', '/alerts?open_only=true',
          '/reports/access?days=7'],
    '/admin/devices': ['/devices', '/labs'],
    '/admin/reports': ['/reports-center', '/reports/overview?days=30', '/issues/summary'],
    '/admin/settings': ['/system/config'],
    '/admin/emergency': ['/emergency/status'],
  },
  LAB_STAFF: {
    ...STAFF_PAGES,
    '/': ['/issues/summary', '/issues?active=true&limit=50', '/access-events?limit=40', '/devices', '/summary',
          '/labs/overview'],
  },
  STUDENT: {
    '/': ['/analytics/me?days=90', '/ai/student/status', '/bookings', '/labs/overview', '/access-events?limit=8',
          '/issues?limit=20'],
    '/book': ['/labs'],
    '/bookings': ['/bookings'],
    '/robots': ['/robots'],
    '/issues': ['/issues?limit=200'],
    '/notifications': ['/notifications/inbox?tab=all&offset=0&limit=50'],
    '/profile': ['/bookings', '/issues?mine=true'],
  },
}

// Page code per path (registered by App): pointing at a sidebar link also downloads that page's code, so the click
// shows the page at once even before the idle prefetch reached it (2026-10-27 click-through: first /labs 4.7 s).
const CHUNKS = new Map<string, () => Promise<unknown>>()
export function registerChunks(m: Record<string, () => Promise<unknown>>) {
  for (const [k, v] of Object.entries(m)) CHUNKS.set(k, v)
}

/** Start the first reads of `path` for this role (no-op when unknown), and its page code. */
export function warmRoute(role: Role | undefined | null, path: string) {
  const key = path.split('?')[0]
  CHUNKS.get(key)?.().catch(() => {})
  const w = role ? WARM[role]?.[key] : undefined
  if (w) warmGets(w)
}
