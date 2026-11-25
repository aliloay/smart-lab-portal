import { ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useNewVersion } from '../lib/freshness'
import { startJankProbe } from '../lib/jankProbe'
import { AnimatePresence, m as motion } from 'framer-motion'
import { ChevronDown, LogOut, Menu, PanelLeftClose, PanelLeftOpen, Search, Sparkles, UserRound, Wrench, X } from 'lucide-react'
import DoorStatus from './DoorStatus'
import { ChatBubble, openChat, useChatAvailable } from './ai'
import CommandPalette, { openPalette } from './CommandPalette'
import { AccessSetupBanner } from './AccessSetup'
import ErrorBoundary from './ErrorBoundary'
import { InstitutionLogo, SmartLabMark, Wordmark } from './Brand'
import NotificationBell from './NotificationBell'
import HazardAlarm from './HazardAlarm'
import EmergencyMessage from './EmergencyMessage'
import NotificationToasts from './NotificationToasts'
import EnvWarnings from './EnvWarnings'
import SystemHealth from './SystemHealth'
import { Avatar } from './ui'
import { GridBackdrop } from './visual'
import { Summary, api } from '../lib/api'
import { BadgeKey, pagesFor } from '../lib/nav'
import PageTabs from './PageTabs'
import SideNav, { WIDE } from './SideNav'
import { isStaff, roleLabel, useAuth } from '../lib/auth'
import { useDebounced, useLive, useLiveMessages } from '../lib/live'
import { isCapturing, syncShare } from '../lib/screenShare'
import { visibleInterval } from '../lib/visibleInterval'

/** Sidebar entry for the AI chat: opens the same panel as the round button. */
function AssistantNav({ onNavigate }: { onNavigate: () => void }) {
  const { user } = useAuth()
  if (!useChatAvailable()) return null
  return (
    <div>
      <div className={`label !text-[10.5px] !text-slate-400 px-3.5 pb-1.5 pt-4 ${WIDE}`}>Assistant</div>
      <button type="button" title="Ask the assistant" aria-label="Ask the assistant" onClick={() => { openChat(); onNavigate() }}
        className="lg:group-data-[compact=true]/side:justify-center group w-full flex items-center gap-3 pl-3.5 pr-2.5 py-2 rounded-xl text-[13.5px]
                   text-slate-300 hover:text-white hover:bg-white/[0.04] transition-colors">
        <span className="text-violet-300 group-hover:text-violet-200"><Sparkles size={17} /></span>
        <span className={`flex-1 text-left ${WIDE}`}>{isStaff(user) ? 'Ask the lab' : 'Ask Smart Lab'}</span>
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-violet-500/15 text-violet-200 ${WIDE}`}>AI</span>
      </button>
    </div>
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
            className="absolute right-0 mt-2 w-60 card pop p-2 z-40">
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
  const pages = useMemo(() => pagesFor(user?.role), [user?.role])
  const outdated = useNewVersion(loc.pathname)
  useEffect(() => { if (staff) startJankProbe() }, [staff])

  // A permanent column on a desktop, an off-canvas drawer on a phone - a fixed
  // sidebar on a 390px screen would squeeze the entry QR to an unscannable
  // thumbnail.
  const [open, setOpen] = useState(false)
  useEffect(() => { setOpen(false) }, [loc.pathname])

  // Desktop only: icons without words, remembered per browser.
  const [compact, setCompact] = useState(() => { try { return localStorage.getItem('smartlab.nav.compact') === '1' } catch { return false } })
  const flip = () => setCompact(c => {
    try { localStorage.setItem('smartlab.nav.compact', c ? '0' : '1') } catch { /* not remembered */ }
    return !c
  })

  // Workload badges for staff, recounted from the database, refreshed live.
  const [summary, setSummary] = useState<Summary | null>(null)
  useEffect(() => {
    if (!staff) return
    const load = () => api.summary().then(setSummary).catch(() => {})
    load()
    const t = visibleInterval(load, 60000)
    return () => window.clearInterval(t)
  }, [staff])
  const refreshSummary = useDebounced(() => { api.summary().then(setSummary).catch(() => {}) })
  useLiveMessages(m => {
    if (staff && m.type === 'staff') refreshSummary()
    if (m.type === 'share_state' && isCapturing()) void syncShare(user?.id)   // Stop pressed elsewhere: release now
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
        <Link to="/" className="flex items-center gap-3 min-w-0" aria-label="Smart Lab - dashboard" title="Dashboard">
          <SmartLabMark size={38} animated />
          <span className={WIDE}><Wordmark tight /></span>
        </Link>
        {/* Pinned inside the drawer: in the brand row it overflowed the
            264px column and showed through while the drawer was closed. */}
        <button onClick={() => setOpen(false)} aria-label="Close navigation"
                className="lg:hidden absolute top-2 right-2 grid place-items-center w-10 h-10 rounded-lg text-slate-400 hover:text-white">
          <X size={18} />
        </button>
      </div>

      {/* Navigation first. The status card sits at the bottom when there is
          room, and simply follows the menu on short screens - it never takes
          space from a navigation item. */}
      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col">
        <button type="button" onClick={openPalette} aria-label="Search (Ctrl K)" title="Search (Ctrl K)"
          className="lg:group-data-[compact=true]/side:justify-center mx-3 mb-2 flex items-center gap-2 rounded-xl border border-ink-600 px-3 py-1.5 text-[12.5px] text-slate-400 hover:text-slate-200 hover:border-ink-500">
          <Search size={14} /> <span className={WIDE}>Search</span> <kbd className={`ml-auto text-[10px] border border-ink-600 rounded px-1 ${WIDE}`}>Ctrl K</kbd></button>
        <nav className="px-3 pb-3" aria-label="Main">
          <SideNav badges={badges} onNavigate={() => setOpen(false)} />
          <AssistantNav onNavigate={() => setOpen(false)} />
        </nav>

        <div className="mt-auto pt-2">
          {/* The spare space under the navigation: the door, at a glance. */}
          <div className={WIDE}><DoorStatus onNavigate={() => setOpen(false)} /></div>

          {/* Phones have no desktop top bar, so the university mark sits here. */}
          <div className="lg:hidden px-5 pb-3">
            <InstitutionLogo strong className="!h-8" textClass="!text-[10px] !tracking-[0.12em] !text-slate-200" />
          </div>
        </div>
      </div>

      <div className="p-3 border-t border-ink-600/60">
        <button type="button" onClick={flip} aria-pressed={compact} aria-label={compact ? 'Show menu names' : 'Compact menu'}
          title={compact ? 'Show menu names' : 'Compact menu'}
          className="hidden lg:flex w-full items-center justify-center gap-2 h-8 rounded-lg text-[12px] text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]">
          {compact ? <PanelLeftOpen size={16} /> : <><PanelLeftClose size={16} /> Compact menu</>}</button>
        <div className="flex items-center gap-3 px-2 py-2 lg:group-data-[compact=true]/side:px-0 lg:group-data-[compact=true]/side:justify-center">
          <span className={WIDE}><Avatar name={user?.full_name} size={34} /></span>
          <div className={`min-w-0 flex-1 ${WIDE}`}>
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
                         bg-ink-900 border-b border-white/[0.07]">
        <button onClick={() => setOpen(v => !v)} aria-label="Open navigation"
                className="p-2 -ml-2 text-slate-300 hover:text-white">
          <Menu size={20} />
        </button>
        <Link to="/" className="flex items-center gap-2 flex-1 min-w-0" aria-label="Smart Lab - dashboard" title="Dashboard">
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

      <aside data-compact={compact} className={`group/side lg:data-[compact=true]:w-[76px] fixed lg:sticky top-0 lg:h-screen inset-y-0 left-0 z-50 w-[264px]
                         shrink-0 flex flex-col border-r border-white/[0.07] overflow-hidden
                         bg-ink-900/95 lg:bg-ink-900/85
                         transition-transform duration-200 ease-out
                         ${open ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}>
        {sidebar}
      </aside>

      <div className="flex-1 min-w-0 relative z-10 flex flex-col">
        {/* desktop top bar */}
        {/* Left: the university. Right: system and account actions. */}
        <div className="hidden lg:flex sticky top-0 z-30 items-center gap-2.5
                        h-16 px-8 bg-ink-900 border-b border-white/[0.07]">
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
          {outdated && (
            <div className="sticky top-0 z-30 flex items-center gap-3 bg-accent-500/15 border-b border-accent-400/40 px-4 py-1.5 text-[12.5px] text-slate-200">
              A new version of the portal is ready - it loads on your next page change.
              <button type="button" className="btn-primary btn-sm ml-auto" onClick={() => window.location.reload()}>Reload now</button>
            </div>)}
          {/* Bottom padding on phones keeps the last content clear of the
              floating Report button. */}
          <div className="max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-24 lg:py-8">
            <AccessSetupBanner />
            <PageTabs />
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
        <ChatBubble />
      </div>
      <CommandPalette staff={staff} pages={pages} />
      <HazardAlarm />
      <EmergencyMessage />
      <NotificationToasts />
      <EnvWarnings />

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
