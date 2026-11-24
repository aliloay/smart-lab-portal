/** Tabs shared by pages that belong together (Live Monitoring, Analytics & health). Each tab is the page's own address:
 *  deep links, refresh and the back button work, and only the open page is mounted - no camera stream in the background. */
import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { MonitorPlay } from 'lucide-react'
import { SCREENS, tabsFor } from '../lib/nav'
import { useAuth } from '../lib/auth'
import { warmRoute } from '../lib/warm'

export default function PageTabs() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const set = tabsFor(user?.role, pathname)
  if (!set) return null
  return (
    <div className="mb-5 flex items-center gap-3 border-b border-ink-600 print:hidden" data-page-tabs={set.id}>
      <span className="hidden md:block text-[12px] font-semibold text-slate-400 pr-3 border-r border-ink-600/70">{set.title}</span>
      <nav aria-label={set.title} className="flex gap-1 overflow-x-auto no-scrollbar min-w-0">
        {set.tabs.map(t => {
          const Icon = t.icon
          const warm = () => warmRoute(user?.role, t.to)
          return (
            <NavLink key={t.to} to={t.to} onPointerEnter={warm} onFocus={warm}
              className={({ isActive }) => `relative flex items-center gap-2 px-3.5 py-2.5 min-h-[42px] text-sm whitespace-nowrap transition-colors duration-150
                ${isActive ? 'text-white' : 'text-slate-400 hover:text-slate-200'}`}>
              {({ isActive }) => <><Icon size={15} className={isActive ? 'text-accent-300' : ''} />{t.label}
                {isActive && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent-400" />}</>}
            </NavLink>)
        })}
      </nav>
      {set.id === 'live' && <span className="ml-auto pb-1"><Screens /></span>}
    </div>
  )
}

/** Full-screen displays, in their own window (a second screen), only on click. */
function Screens() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const out = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', out)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', out); document.removeEventListener('keydown', esc) }
  }, [open])
  return (
    <div className="relative" ref={ref}>
      <button type="button" aria-expanded={open} className="btn-ghost btn-sm" onClick={() => setOpen(o => !o)}>
        <MonitorPlay size={14} /> Screens</button>
      {open && <div className="absolute right-0 mt-1.5 w-52 card p-1.5 z-40">
        {SCREENS.map(s => (
          <a key={s.to} href={s.to} className="block px-3 py-2 rounded-lg text-[13px] text-slate-200 hover:bg-ink-700/60" onClick={e => {
            e.preventDefault(); setOpen(false)
            window.open(s.to, `smartlab${s.to.replace(/\//g, '-')}`, 'popup,width=1600,height=900')
          }}>{s.label}<span className="block text-[11px] text-slate-500">opens in its own window</span></a>))}
      </div>}
    </div>
  )
}
