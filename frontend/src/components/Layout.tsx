import { useEffect, useState, ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import ErrorBoundary from './ErrorBoundary'
import {
  Activity, Boxes, Building2, CalendarPlus, CalendarRange, Cpu, Gauge,
  LayoutDashboard, LogOut, Menu, ShieldAlert, TriangleAlert, Users, X,
} from 'lucide-react'
import { useAuth } from '../lib/auth'
import { GridBackdrop } from './visual'

interface Item { to: string; label: string; icon: ReactNode }
interface Section { title: string; items: Item[] }

/**
 * Navigation is built per ROLE, not filtered per permission.
 *
 * An administrator seeing "New booking" and "My bookings" as primary
 * navigation is a student workflow wearing an admin's badge. Staff and
 * admins do not reserve laboratories as their main job; they run them. So
 * each role gets a sidebar composed for what that person actually does,
 * rather than one list with rows hidden.
 *
 * The routes still exist for every role - an admin CAN open /book - they are
 * simply not the front door of an operational interface.
 */
const STUDENT_NAV: Section[] = [
  { title: 'Laboratory', items: [
    { to: '/',         label: 'Dashboard',    icon: <LayoutDashboard size={16} /> },
    { to: '/labs',     label: 'Laboratories', icon: <Building2 size={16} /> },
    { to: '/book',     label: 'New booking',  icon: <CalendarPlus size={16} /> },
    { to: '/bookings', label: 'My bookings',  icon: <CalendarRange size={16} /> },
  ]},
]

const STAFF_NAV: Section[] = [
  { title: 'Operations', items: [
    { to: '/',                   label: 'Dashboard',     icon: <Gauge size={16} /> },
    { to: '/labs',               label: 'Laboratories',  icon: <Building2 size={16} /> },
    { to: '/admin/bookings',     label: 'Reservations',  icon: <CalendarRange size={16} /> },
    { to: '/admin/access-events',label: 'Access monitor',icon: <ShieldAlert size={16} /> },
  ]},
  { title: 'Facility', items: [
    { to: '/admin/devices', label: 'Devices',   icon: <Cpu size={16} /> },
    { to: '/admin/assets',  label: 'Equipment', icon: <Boxes size={16} /> },
    { to: '/admin/alerts',  label: 'Alerts',    icon: <TriangleAlert size={16} /> },
  ]},
  { title: 'Personal', items: [
    { to: '/book',     label: 'New booking', icon: <CalendarPlus size={16} /> },
    { to: '/bookings', label: 'My bookings', icon: <CalendarRange size={16} /> },
  ]},
]

const ADMIN_NAV: Section[] = [
  { title: 'Operations', items: [
    { to: '/',      label: 'Overview',     icon: <Gauge size={16} /> },
    { to: '/labs',  label: 'Laboratories', icon: <Building2 size={16} /> },
  ]},
  { title: 'Access & audit', items: [
    { to: '/admin/bookings',      label: 'Bookings',      icon: <CalendarRange size={16} /> },
    { to: '/admin/access-events', label: 'Access events', icon: <ShieldAlert size={16} /> },
    { to: '/admin/reports',       label: 'Reports',       icon: <Activity size={16} /> },
  ]},
  { title: 'Administration', items: [
    { to: '/admin/users',   label: 'Users & roles', icon: <Users size={16} /> },
    { to: '/admin/devices', label: 'Devices',       icon: <Cpu size={16} /> },
    { to: '/admin/assets',  label: 'Equipment',     icon: <Boxes size={16} /> },
    { to: '/admin/alerts',  label: 'Alerts',        icon: <TriangleAlert size={16} /> },
  ]},
]

function navFor(role: string | undefined): Section[] {
  if (role === 'ADMIN') return ADMIN_NAV
  if (role === 'LAB_STAFF') return STAFF_NAV
  return STUDENT_NAV
}

function NavItem({ item, onNavigate }: { item: Item; onNavigate: () => void }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/' || item.to === '/admin'}
      onClick={onNavigate}
      className={({ isActive }) =>
        `group relative flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm
         transition-colors ${
          isActive
            ? 'text-accent-300 bg-accent-500/[0.09]'
            : 'text-slate-400 hover:text-slate-100 hover:bg-ink-700/60'}`
      }
    >
      {({ isActive }) => (
        <>
          {/* The active marker is a shared layout element, so it slides
              between items instead of blinking out and back in. */}
          {isActive && (
            <motion.span
              layoutId="nav-active"
              className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full
                         bg-accent-400"
              transition={{ type: 'spring', stiffness: 500, damping: 40 }}
            />
          )}
          <span className={isActive
            ? 'text-accent-400'
            : 'text-slate-500 group-hover:text-slate-300'}>
            {item.icon}
          </span>
          {item.label}
        </>
      )}
    </NavLink>
  )
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const loc = useLocation()

  // A permanent column on a desktop, an off-canvas drawer on a phone.
  // Not merely narrower on mobile: a fixed sidebar on a 390px screen would
  // squeeze the entry QR down to an unscannable thumbnail, and holding that
  // QR up to the door camera is the most important thing this app does.
  const [open, setOpen] = useState(false)
  useEffect(() => { setOpen(false) }, [loc.pathname])

  const close = () => setOpen(false)

  const sidebar = (
    <>
      <div className="px-5 py-5 border-b border-ink-600/60 flex items-center
                      justify-between">
        <div className="flex items-center gap-3">
          <div className="relative w-9 h-9 rounded-lg bg-gradient-to-br
                          from-accent-500 to-accent-700 grid place-items-center
                          text-white font-bold text-[11px]
                          shadow-[0_0_20px_-4px_rgba(14,165,233,.7)]">
            SL
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-50 leading-tight">
              Smart Lab
            </div>
            <div className="text-[9.5px] uppercase tracking-technical text-slate-500">
              Access Portal
            </div>
          </div>
        </div>
        <button onClick={close} aria-label="Close navigation"
                className="lg:hidden text-slate-500 hover:text-white p-1">
          <X size={16} />
        </button>
      </div>

      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {navFor(user?.role).map((section, i) => (
          <div key={section.title}>
            <div className={`label px-3 pb-1.5 ${i === 0 ? 'pt-2' : 'pt-5'}`}>
              {section.title}
            </div>
            {section.items.map(item => (
              <NavItem key={item.to} item={item} onNavigate={close} />
            ))}
          </div>
        ))}
      </nav>

      <div className="p-3 border-t border-ink-600/60">
        <div className="px-3 py-2">
          <div className="text-sm text-slate-200 truncate">{user?.full_name}</div>
          <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
            {user?.role === 'LAB_STAFF' ? 'Lab staff'
              : user?.role === 'ADMIN' ? 'Administrator' : 'Student'}
            {user?.auth_subject && (
              <span className="mono text-slate-600">· {user.auth_subject}</span>
            )}
          </div>
        </div>
        <button onClick={logout}
                className="w-full mt-1 flex items-center gap-2.5 px-3 py-2
                           rounded-lg text-sm text-slate-400 hover:text-white
                           hover:bg-ink-700/60 transition-colors">
          <LogOut size={15} className="text-slate-500" />
          Sign out
        </button>
      </div>
    </>
  )

  return (
    <div className="min-h-full lg:flex relative">
      <GridBackdrop className="fixed inset-0 z-0" />

      <header className="lg:hidden sticky top-0 z-30 flex items-center gap-3 px-4
                         h-14 bg-ink-900/90 backdrop-blur border-b
                         border-ink-600/60">
        <button onClick={() => setOpen(v => !v)} aria-label="Toggle navigation"
                className="p-2 -ml-2 text-slate-400 hover:text-white">
          <Menu size={19} />
        </button>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-accent-600 grid place-items-center
                          text-white font-bold text-[9px]">SL</div>
          <span className="text-sm font-semibold text-slate-100">Smart Lab</span>
        </div>
      </header>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={close}
            className="lg:hidden fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
          />
        )}
      </AnimatePresence>

      <aside className={`
        bg-ink-900/95 lg:bg-ink-900/70 backdrop-blur-md border-r
        border-ink-600/60 flex flex-col
        fixed lg:sticky top-0 lg:h-screen inset-y-0 left-0 z-50 w-[248px] shrink-0
        transition-transform duration-200 ease-out
        ${open ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0
      `}>
        {sidebar}
      </aside>

      <main className="flex-1 min-w-0 relative z-10">
        <div className="max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8
                        py-5 lg:py-8">
          {/*
            Keyed fade-IN only. No exit animation, and deliberately NOT
            wrapped in <AnimatePresence mode="wait">.

            That combination gates MOUNTING of the next page on the previous
            page's exit animation reporting completion. If that callback is
            ever missed - an interrupted transition, a dropped frame, a Fast
            Refresh landing mid-animation - the old element has left and the
            new one never mounts, so <main> renders empty until a full reload
            rebuilds the tree. That is the "blank page, fixed by refresh"
            failure, and the only robust cure is to stop making a mount
            depend on an animation finishing.

            React Router swaps `children` synchronously; the key restarts the
            fade. Nothing here can strand the page.
          */}
          <ErrorBoundary resetKey={loc.pathname}>
            <motion.div
              key={loc.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            >
              {children}
            </motion.div>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  )
}
