/**
 * The sidebar as data: six groups, composed per ROLE (a student reserves and reports, staff run the lab, an
 * administrator oversees the platform). The server enforces the real permissions either way.
 * Every address that was in the old menu is still here (tests/nav.test.ts).
 */
import {
  Activity, Bell, Bot, Boxes, Building2, CalendarPlus, CalendarRange, Cast, Cctv, Cpu, Gauge, HeartPulse,
  LayoutDashboard, LineChart, LucideIcon, MonitorPlay, Presentation, Radar, Settings, ShieldCheck, Siren, TriangleAlert,
  UserRound, Users, Wrench,
} from 'lucide-react'

export type BadgeKey = 'issues' | 'alerts' | 'pending' | 'unread'
export interface NavEntry {
  to: string; label: string; icon: LucideIcon; badge?: BadgeKey; end?: boolean
  /** Opens in its own window (wall screen, exhibition), not in the portal frame. */
  window?: boolean
}
export interface NavGroup {
  id: string; title: string; items: NavEntry[]
  /** Never collapsible: safety has to stay one click away. */
  pinned?: boolean
  /** Closed until the person opens it (their choice is remembered). */
  closed?: boolean
}

const i = (to: string, label: string, icon: LucideIcon, extra: Partial<NavEntry> = {}): NavEntry => ({ to, label, icon, ...extra })

const STUDENT: NavGroup[] = [
  { id: 'lab', title: 'Laboratory', pinned: true, items: [
    i('/', 'Dashboard', LayoutDashboard, { end: true }), i('/labs', 'Laboratories', Building2),
    i('/book', 'New booking', CalendarPlus), i('/bookings', 'My bookings', CalendarRange), i('/share', 'Share screen', Cast)] },
  { id: 'support', title: 'Support', pinned: true, items: [
    i('/robots', 'Robots', Bot), i('/issues', 'My reports', Wrench),
    i('/notifications', 'Notifications', Bell, { badge: 'unread' }), i('/profile', 'Profile', UserRound)] },
]

function operators(admin: boolean): NavGroup[] {
  return [
    { id: 'overview', title: 'Overview', pinned: true, items: [
      i('/', admin ? 'System overview' : 'Operations', Gauge, { end: true }),
      i('/notifications', 'Notifications', Bell, { badge: 'unread' })] },
    // second, so that it stays above the fold on a laptop screen
    { id: 'safety', title: 'Access & safety', pinned: true, items: [
      i('/admin/access', admin ? 'Access & audit' : 'Access monitor', ShieldCheck),
      i('/admin/alerts', 'Alerts', TriangleAlert, { badge: 'alerts' }), i('/admin/incidents', 'Incidents', Siren),
      ...(admin ? [i('/admin/emergency', 'Emergency', Siren)] : [])] },
    { id: 'live', title: 'Live operations', items: [
      i('/command', 'IoT Dashboard', Radar), i('/admin/security', 'Security camera', Cctv),
      i('/admin/operations', 'Operations Center', Activity), i('/monitor', 'Live monitor', MonitorPlay, { window: true }),
      i('/share', 'Share screen', Cast)] },
    { id: 'lab', title: 'Lab management', items: [
      i('/labs', 'Laboratories', Building2),
      i('/admin/bookings', admin ? 'Bookings' : 'Reservations', CalendarRange, { badge: 'pending' }),
      i('/admin/equipment', 'Lab Equipment', Boxes), i('/admin/devices', 'System Devices', Cpu),
      i('/issues', 'Maintenance', Wrench, { badge: 'issues' })] },
    { id: 'intelligence', title: 'Intelligence', closed: true, items: [
      i('/admin/health', 'Health Center', HeartPulse), i('/admin/sensors', 'Sensor analytics', LineChart),
      i('/admin/system', 'System analytics', Activity), i('/admin/reliability', 'Reliability', ShieldCheck),
      ...(admin ? [i('/admin/reports', 'Reports', LineChart)] : [])] },
    { id: 'admin', title: 'Automation & admin', closed: true, items: [
      i('/admin/users', admin ? 'Users & roles' : 'Users', Users),
      ...(admin ? [i('/admin/settings', 'Settings', Settings)] : []),
      i('/exhibit', 'Exhibition screen', Presentation, { window: true })] },
  ]
}
const STAFF = operators(false)
const ADMIN = operators(true)

export function navFor(role: string | undefined): NavGroup[] {
  return role === 'ADMIN' ? ADMIN : role === 'LAB_STAFF' ? STAFF : STUDENT
}

/** True when the page belongs to this entry (the dashboard only on its own address). */
export function isHere(entry: NavEntry, path: string): boolean {
  return entry.end ? path === entry.to : path === entry.to || path.startsWith(entry.to + '/')
}
