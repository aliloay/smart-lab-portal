/**
 * The navigation as data, composed per ROLE (a student reserves and reports, staff run the lab, an administrator
 * oversees the platform). The server enforces the real permissions either way.
 *
 * Three ways to reach a page (2026-11-24): the sidebar (navFor), tabs shared by pages that belong together (tabsFor:
 * Live Monitoring, Analytics & health) and a button on the page it belongs to (the header bell, "Screens").
 * pagesFor() lists all of them for Ctrl+K. No address was removed (tests/nav.test.ts).
 */
import {
  Activity, Bot, Boxes, Building2, CalendarPlus, CalendarRange, Cast, Cctv, Cpu, FileText, FlaskConical, Gauge, HeartPulse,
  LayoutDashboard, LineChart, LucideIcon, Megaphone, Radar, ScanLine, Settings, ShieldCheck, Siren, TriangleAlert, UserRound,
  Users, Wrench,
} from 'lucide-react'

export type BadgeKey = 'issues' | 'alerts' | 'pending' | 'unread'
export interface NavEntry {
  to: string; label: string; icon: LucideIcon; badge?: BadgeKey; end?: boolean
  /** Other addresses that belong to this entry (its tabs, its details): they highlight it too. */
  also?: string[]
}
export interface NavGroup {
  id: string; title: string; items: NavEntry[]
  /** No heading to click: always shown. */
  pinned?: boolean
  /** Closed until the person opens it (their choice is remembered). */
  closed?: boolean
}
export interface PageTab { to: string; label: string; icon: LucideIcon; admin?: boolean }
export interface PageSet { id: 'live' | 'insight'; title: string; tabs: PageTab[] }

const i = (to: string, label: string, icon: LucideIcon, extra: Partial<NavEntry> = {}): NavEntry => ({ to, label, icon, ...extra })

const LIVE: PageSet = { id: 'live', title: 'Live Monitoring', tabs: [
  { to: '/command', label: 'IoT & sensors', icon: Radar }, { to: '/admin/security', label: 'Security cameras', icon: Cctv }] }
const INSIGHT: PageSet = { id: 'insight', title: 'Analytics & health', tabs: [
  { to: '/admin/health', label: 'Health Center', icon: HeartPulse }, { to: '/admin/sensors', label: 'Sensors', icon: LineChart },
  { to: '/admin/system', label: 'System', icon: Activity }, { to: '/admin/reliability', label: 'Reliability', icon: ShieldCheck },
  { to: '/admin/reports', label: 'Reports', icon: FileText, admin: true }] }
const operator = (role?: string) => role === 'ADMIN' || role === 'LAB_STAFF'

/** The tab strip of the page at `path`, or null. */
export function tabsFor(role: string | undefined, path: string): PageSet | null {
  if (!operator(role)) return null
  const s = [LIVE, INSIGHT].find(x => x.tabs.some(t => t.to === path))
  return s ? { ...s, tabs: s.tabs.filter(t => !t.admin || role === 'ADMIN') } : null
}

const STUDENT: NavGroup[] = [
  { id: 'lab', title: 'Laboratory', pinned: true, items: [
    i('/', 'Dashboard', LayoutDashboard, { end: true }), i('/labs', 'Laboratories', Building2),
    i('/book', 'New booking', CalendarPlus), i('/bookings', 'My bookings', CalendarRange), i('/share', 'Shared screen', Cast)] },
  { id: 'support', title: 'Support', pinned: true, items: [
    i('/robots', 'Robots', Bot), i('/issues', 'My reports', Wrench), i('/profile', 'Profile', UserRound)] },
]

function operators(admin: boolean): NavGroup[] {
  return [
    { id: 'overview', title: 'Overview', pinned: true, items: [i('/', admin ? 'System overview' : 'Lab overview', Gauge, { end: true })] },
    // second and open at the start, so that safety stays above the fold on a laptop screen
    { id: 'safety', title: 'Access & safety', items: [
      i('/admin/access', admin ? 'Access & audit' : 'Access monitor', ShieldCheck),
      i('/admin/alerts', 'Alerts', TriangleAlert, { badge: 'alerts' }), i('/admin/incidents', 'Incidents', Siren),
      ...(admin ? [i('/admin/emergency', 'Emergency', Megaphone)] : [])] },
    { id: 'live', title: 'Live operations', items: [
      i('/command', LIVE.title, Radar, { also: ['/admin/security'] }), i('/admin/operations', 'Operations Center', Activity)] },
    { id: 'equipment', title: 'Lab equipment', items: [
      i('/admin/equipment', 'Equipment, robots & PCs', Boxes, { also: ['/robots', '/equipment'] }),
      i('/admin/devices', 'System devices', Cpu), i('/issues', 'Maintenance', Wrench, { badge: 'issues' })] },
    { id: 'lab', title: 'Lab management', items: [
      i('/labs', 'Laboratories', Building2),
      i('/admin/bookings', admin ? 'Bookings' : 'Reservations', CalendarRange, { badge: 'pending', also: ['/bookings', '/book'] })] },
    { id: 'intelligence', title: 'Intelligence', closed: true, items: [
      i('/admin/health', INSIGHT.title, HeartPulse, { also: INSIGHT.tabs.filter(t => admin || !t.admin).map(t => t.to).slice(1) }),
      i('/scan', 'AR scanner', ScanLine, { also: ['/phone-setup'] }), i('/admin/experiments', 'Experiments', FlaskConical)] },
    { id: 'admin', title: 'Administration', closed: true, items: [
      i('/admin/users', admin ? 'Users & roles' : 'Users', Users),
      ...(admin ? [i('/admin/settings', 'Settings', Settings)] : [])] },
  ]
}
const STAFF = operators(false)
const ADMIN = operators(true)

export function navFor(role: string | undefined): NavGroup[] {
  return role === 'ADMIN' ? ADMIN : role === 'LAB_STAFF' ? STAFF : STUDENT
}

/** The full-screen displays, opened in their own window from Live Monitoring ("Screens"). */
export const SCREENS = [
  { to: '/monitor', label: 'Live monitor' }, { to: '/wall', label: 'Wall display' }, { to: '/exhibit', label: 'Exhibition screen' }]

/** Every page this role can open, for Ctrl+K: the menu, the tabs, and pages that have no menu entry. */
export function pagesFor(role: string | undefined): { to: string; label: string; section: string }[] {
  const out = navFor(role).flatMap(g => g.items.map(x => ({ to: x.to, label: x.label, section: g.title })))
  const add = (to: string, label: string, section: string) => { if (!out.some(p => p.to === to)) out.push({ to, label, section }) }
  if (operator(role)) {
    for (const s of [LIVE, INSIGHT]) for (const t of s.tabs) if (!t.admin || role === 'ADMIN') add(t.to, t.label, s.title)
    const eq = (tab: string, label: string) => add(`/admin/equipment?tab=${tab}`, label, 'Lab equipment')
    eq('noncons', 'Robots & PCs')
    eq('share', 'Screen sharing')
    eq('environment', 'Physical environment')
    eq('consumables', 'Consumables')
    eq('reusables', 'Reusables')
    eq('register', 'Equipment register')
    add('/robots', 'Robots', 'Lab equipment')
    add('/book', 'New booking', 'Lab management')
    add('/scan/markers', 'AR markers', 'AR scanner')
    add('/phone-setup', 'Phone setup', 'AR scanner')
    add('/demo', 'Simulation', 'Administration')
    for (const s of SCREENS) add(s.to, s.label, 'Screens')
  }
  add('/notifications', 'Notifications', 'Header')
  add('/issues/new', 'Report an issue', 'Header')
  add('/profile', 'Profile', 'Header')
  return out
}

/** True when the page belongs to this entry (the dashboard only on its own address). */
export function isHere(entry: NavEntry, path: string): boolean {
  if (entry.end) return path === entry.to
  return [entry.to, ...(entry.also ?? [])].some(p => path === p || path.startsWith(p + '/'))
}
