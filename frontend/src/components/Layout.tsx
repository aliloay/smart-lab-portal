import { ReactNode, useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity, Bell, Boxes, Building2, CalendarPlus, CalendarRange, ChevronDown, Cpu,
  Gauge, LayoutDashboard, LogOut, Menu, Settings, ShieldCheck, TriangleAlert,
  UserRound, Users, Wrench, X,
} from 'lucide-react'
import DoorStatus from './DoorStatus'
import ErrorBoundary from './ErrorBoundary'
import { InstitutionLogo, SmartLabMark, Wordmark } from './Brand'
import NotificationBell from './NotificationBell'
import SystemHealth from './SystemHealth'
import { Avatar } from './ui'
import { GridBackdrop } from './visual'
import { Summary, api } from '../lib/api'
import { isStaff, roleLabel, useAuth } from '../lib/auth'
import { useLive, useLiveMessages } from '../lib/live'

type BadgeKey = 'issues' | 'alerts' | 'pending' | 'unread'
interface Item { to: string; label: string; icon: ReactNode; badge?: BadgeKey; end?: boolean }
interface Section { title: string; items: Item[] }

/**
 * Navigation is composed per ROLE, not filtered per permission.
 *
 * A student reserves laboratories and reports problems. Staff run the
 * laboratories day to day. An administrator oversees the whole platform. An
 * administrator seeing "New booking" and "My bookings" as primary navigation
 * would be a student workflow wearing an admin's badge - so each role gets a
 * sidebar for what that person actually does. The server enforces the real
 * permissions either way.
 */
const STUDENT_NAV: Section[] = [
  { title: 'Laboratory', items: [
    { to: '/', label: 'Dashboard', icon: <LayoutDashboard size={17} />, end: true },
    { to: '/labs', label: 'Laboratories', icon: <Building2 size={17} /> },
    { to: '/book', label: 'New booking', icon: <CalendarPlus size={17} /> },
    { to: '/bookings', label: 'My bookings', icon: <CalendarRange size={17} /> },
  ]},
  { title: 'Support', items: [
    { to: '/issues', label: 'My reports', icon: <Wrench size={17} /> },
    { to: '/notifications', label: 'Notifications', icon: <Bell size={17} />, badge: 'unread' },
    { to: '/profile', label: 'Profile', icon: <UserRound size={17} /> },
  ]},
]

const STAFF_NAV: Section[] = [
  { title: 'Operations', items: [
    { to: '/', label: 'Operations', icon: <Gauge size={17} />, end: true },
    { to: '/labs', label: 'Laboratories', icon: <Building2 size={17} /> },
    { to: '/admin/bookings', label: 'Reservations', icon: <CalendarRange size={17} />, badge: 'pending' },
    { to: '/admin/access', label: 'Access monitor', icon: <ShieldCheck size={17} /> },
  ]},
  { title: 'Facility', items: [
    { to: '/issues', label: 'Maintenance', icon: <Wrench size={17} />, badge: 'issues' },
    { to: '/admin/devices', label: 'Devices', icon: <Cpu size={17} /> },
    { to: '/admin/equipment', label: 'Equipment', icon: <Boxes size={17} /> },
    { to: '/admin/alerts', label: 'Alerts', icon: <TriangleAlert size={17} />, badge: 'alerts' },
    { to: '/notifications', label: 'Notifications', icon: <Bell size={17} />, badge: 'unread' },
  ]},
]

const ADMIN_NAV: Section[] = [
  { title: 'Operations', items: [
    { to: '/', label: 'System overview', icon: <Gauge size={17} />, end: true },
    { to: '/labs', label: 'Laboratories', icon: <Building2 size={17} /> },
  ]},
  { title: 'Access & audit', items: [
    { to: '/admin/bookings', label: 'Bookings', icon: <CalendarRange size={17} />, badge: 'pending' },
    { to: '/admin/access', label: 'Access & audit', icon: <ShieldCheck size={17} /> },
    { to: '/admin/reports', label: 'Reports', icon: <Activity size={17} /> },
  ]},
  { title: 'Facility', items: [
    { to: '/issues', label: 'Maintenance', icon: <Wrench size={17} />, badge: 'issues' },
    { to: '/admin/devices', label: 'Devices', icon: <Cpu size={17} /> },
    { to: '/admin/equipment', label: 'Equipment', icon: <Boxes size={17} /> },
    { to: '/admin/alerts', label: 'Alerts', icon: <TriangleAlert size={17} />, badge: 'alerts' },
  ]},
  { title: 'Administration', items: [
    { to: '/admin/users', label: 'Users & roles', icon: <Users size={17} /> },
    { to: '/admin/settings', label: 'Settings', icon: <Settings size={17} /> },
  ]},
]

function navFor(role: string | undefined): Section[] {
  if (role === 'ADMIN') return ADMIN_NAV
  if (role === 'LAB_STAFF') return STAFF_NAV
  return STUDENT_NAV
}

function NavItem({ item, badge, onNavigate }: {
  item: Item; badge?: number; onNavigate: () => void
}) {
  return (
    <NavLink to={item.to} end={item.end} onClick={onNavigate}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 pl-3.5 pr-2.5 py-2 rounded-xl text-[13.5px]
         transition-colors ${isActive
          ? 'text-white bg-gradient-to-r from-accent-400/[0.14] to-transparent'
          : 'text-slate-300 hover:text-white hover:bg-white/[0.04]'}`}>
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span layoutId="nav-active"
              className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-accent-400
                         shadow-[0_0_8px_rgba(56,189,248,.55)]"
              transition={{ type: 'spring', stiffness: 500, damping: 40 }} />
          )}
          <span className={isActive ? 'text-accent-300'
            : 'text-slate-400 group-hover:text-slate-200'}>{item.icon}</span>
          <span className="flex-1">{item.label}</span>
          {!!badge && (
            <span className="min-w-[20px] h-5 px-1.5 rounded-md grid place-items-center
                             text-[11px] font-semibold tnum bg-ink-600 text-slate-100">
              {badge > 99 ? '99+' : badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)} aria-expanded={open}
        className="glass-control flex items-center gap-2.5 pl-1 pr-2.5">
        <Avatar name={user?.full_name} size={28} />
        <span className="hidden xl:block text-left leading-tight">
          <span className="block text-[12.5px] text-white max-w-[140px] truncate">
            {user?.full_name}</span>
          <span className="block text-[10.5px] text-slate-400">{roleLabel(user?.role)}</span>
        </span>
        <ChevronDown size={14} className="text-slate-400" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }} transition={{ duration: .14 }}
            className="absolute right-0 mt-2 w-60 card p-2 z-40">
            <div className="px-3 py-2">
              <div className="text-sm text-white truncate">{user?.full_name}</div>
              <div className="text-xs text-slate-400 truncate">{user?.email}</div>
            </div>
            <div className="divider my-1" />
            <Link to="/profile" onClick={() => setOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm
                             text-slate-200 hover:bg-ink-700/60">
              <UserRound size={15} /> Profile
            </Link>
            <button onClick={logout}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm
                               text-slate-200 hover:bg-ink-700/60">
              <LogOut size={15} /> Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const { unread } = useLive()
  const loc = useLocation()
  const staff = isStaff(user)

  // A permanent column on a desktop, an off-canvas drawer on a phone - a fixed
  // sidebar on a 390px screen would squeeze the entry QR to an unscannable
  // thumbnail.
  const [open, setOpen] = useState(false)
  useEffect(() => { setOpen(false) }, [loc.pathname])

  // Workload badges for staff, recounted from the database, refreshed live.
  const [summary, setSummary] = useState<Summary | null>(null)
  useEffect(() => {
    if (!staff) return
    const load = () => api.summary().then(setSummary).catch(() => {})
    load()
    const t = window.setInterval(load, 60000)
    return () => window.clearInterval(t)
  }, [staff])
  useLiveMessages(m => {
    if (staff && m.type === 'staff') api.summary().then(setSummary).catch(() => {})
  })

  const badges: Record<BadgeKey, number> = {
    issues: summary?.open_issues ?? 0,
    alerts: summary?.open_alerts ?? 0,
    pending: summary?.pending_bookings ?? 0,
    unread,
  }

  // Never float anything over the entry QR - it must stay fully scannable.
  const onQrPage = /^\/bookings\/\d+\/qr/.test(loc.pathname)
  const showFab = !onQrPage && !loc.pathname.startsWith('/issues/new')

  const sidebar = (
    <>
      <div className="relative mx-3 px-2 pt-5 pb-4 mb-2 border-b border-ink-600/60">
        <Link to="/" className="flex items-center gap-3 min-w-0" aria-label="Smart Lab home">
          <SmartLabMark size={38} animated />
          <Wordmark tight />
        </Link>
        {/* Pinned inside the drawer: in the brand row it overflowed the
            264px column and showed through while the drawer was closed. */}
        <button onClick={() => setOpen(false)} aria-label="Close navigation"
                className="lg:hidden absolute top-2 right-2 text-slate-400 hover:text-white p-1.5">
          <X size={18} />
        </button>
      </div>

      {/* Navigation first. The status card sits at the bottom when there is
          room, and simply follows the menu on short screens - it never takes
          space from a navigation item. */}
      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col">
        <nav className="px-3 pb-3" aria-label="Main">
          {navFor(user?.role).map((section, i) => (
            <div key={section.title}>
              <div className={`label !text-[10.5px] !text-slate-500 px-3.5 pb-1.5
                               ${i === 0 ? 'pt-2' : 'pt-5'}`}>{section.title}</div>
              <div className="space-y-0.5">
                {section.items.map(item => (
                  <NavItem key={item.to} item={item}
                           badge={item.badge ? badges[item.badge] : undefined}
                           onNavigate={() => setOpen(false)} />
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="mt-auto pt-2">
          {/* The spare space under the navigation: the door, at a glance. */}
          <DoorStatus onNavigate={() => setOpen(false)} />

          {/* Phones have no desktop top bar, so the university mark sits here. */}
          <div className="lg:hidden px-5 pb-3">
            <InstitutionLogo strong className="!h-8" textClass="!text-[10px] !tracking-[0.12em] !text-slate-200" />
          </div>
        </div>
      </div>

      <div className="p-3 border-t border-ink-600/60">
        <div className="flex items-center gap-3 px-2 py-2">
          <Avatar name={user?.full_name} size={34} />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] text-white truncate">{user?.full_name}</div>
            <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
              {roleLabel(user?.role)}
              {user?.auth_subject && (
                <span className="mono !text-[10.5px] text-accent-300">· {user.auth_subject}</span>
              )}
            </div>
          </div>
          <button onClick={logout} title="Sign out" aria-label="Sign out"
                  className="btn-quiet !p-2"><LogOut size={16} /></button>
        </div>
      </div>
    </>
  )

  return (
    <div className="min-h-screen lg:flex relative">
      <GridBackdrop className="fixed inset-0 z-0" />

      {/* phone header */}
      <header className="lg:hidden sticky top-0 z-30 flex items-center gap-3 px-4 h-14
                         bg-ink-900/80 backdrop-blur-xl border-b border-white/[0.07]">
        <button onClick={() => setOpen(v => !v)} aria-label="Open navigation"
                className="p-2 -ml-2 text-slate-300 hover:text-white">
          <Menu size={20} />
        </button>
        <Link to="/" className="flex items-center gap-2 flex-1 min-w-0">
          <SmartLabMark size={28} />
          <Wordmark compact />
        </Link>
        <SystemHealth />
        <NotificationBell />
      </header>

      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            className="lg:hidden fixed inset-0 z-40 bg-ink-950/75 backdrop-blur-sm" />
        )}
      </AnimatePresence>

      <aside className={`fixed lg:sticky top-0 lg:h-screen inset-y-0 left-0 z-50 w-[264px]
                         shrink-0 flex flex-col border-r border-white/[0.07] overflow-hidden
                         bg-ink-900/95 lg:bg-ink-900/60 backdrop-blur-xl
                         transition-transform duration-200 ease-out
                         ${open ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}>
        {sidebar}
      </aside>

      <div className="flex-1 min-w-0 relative z-10 flex flex-col">
        {/* desktop top bar */}
        {/* Left: the university. Right: system and account actions. */}
        <div className="hidden lg:flex sticky top-0 z-30 items-center gap-2.5
                        h-16 px-8 bg-ink-900/55 backdrop-blur-xl border-b border-white/[0.07]">
          <div className="mr-auto flex items-center min-w-0">
            <InstitutionLogo strong className="!h-10"
                             textClass="!text-[11px] !tracking-[0.14em] !text-slate-200 whitespace-nowrap" />
          </div>
          <Link to="/issues/new" className="glass-control inline-flex items-center gap-2 px-3 text-[13px] font-medium">
            <Wrench size={15} /> Report an issue
          </Link>
          <span className="h-6 w-px bg-ink-600/70 mx-1" aria-hidden />
          <SystemHealth />
          <NotificationBell />
          <UserMenu />
        </div>

        <main className="flex-1">
          {/* Bottom padding on phones keeps the last content clear of the
              floating Report button. */}
          <div className="max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-24 lg:py-8">
            {/*
              The page is keyed on the path and fades in with a CSS keyframe.

              Nothing gates MOUNTING on an animation. The earlier blank-page
              bug came from <AnimatePresence mode="wait">, which only mounted
              the next page after the previous page's exit animation reported
              completion; a missed callback left <main> empty until a reload.
              A CSS animation is driven by the clock alone - there is no
              completion callback to miss - so it cannot strand a page, and
              with reduced motion it finishes instantly.
            */}
            <ErrorBoundary resetKey={loc.pathname}>
              <div key={loc.pathname} className="animate-page-in">
                {children}
              </div>
            </ErrorBoundary>
          </div>
        </main>
      </div>

      {/* phone quick action - hidden where it could cover the entry QR */}
      {showFab && (
        <Link to="/issues/new" aria-label="Report an issue"
          className="lg:hidden fixed bottom-5 right-5 z-30 flex items-center gap-2 h-12 pl-4
                     pr-5 rounded-full text-white text-sm font-medium shadow-lift
                     bg-gradient-to-b from-accent-500 to-accent-600">
          <Wrench size={17} /> Report
        </Link>
      )}
    </div>
  )
}
