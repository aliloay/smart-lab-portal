/** The grouped sidebar menu. Groups open and close (remembered per browser), a closed group shows the sum of its
 *  badges, and the compact mode keeps only the icons. Data and roles: lib/nav.ts. */
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { BadgeKey, NavEntry, isHere, navFor } from '../lib/nav'
import { useAuth } from '../lib/auth'
import { warmRoute } from '../lib/warm'

const KEY = 'smartlab.nav.open'
function readOpen(): Record<string, boolean> {
  try { const v = JSON.parse(localStorage.getItem(KEY) || '{}'); return v && typeof v === 'object' ? v : {} } catch { return {} }
}
/** Hidden in compact mode (desktop only; the phone drawer is always full). */
export const WIDE = 'lg:group-data-[compact=true]/side:hidden'

export default function SideNav({ badges, onNavigate }: { badges: Record<BadgeKey, number>; onNavigate: () => void }) {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const groups = navFor(user?.role)
  const [open, setOpen] = useState(readOpen)
  // Arriving on a page (link, search) opens its group once; the person may close it again.
  useEffect(() => {
    const g = groups.find(x => x.items.some(e => isHere(e, pathname)))
    if (g && !g.pinned) setOpen(o => ({ ...o, [g.id]: true }))
  }, [pathname, groups])
  const toggle = (id: string, was: boolean) => setOpen(o => {
    const next = { ...o, [id]: !was }          // from the newest state: two quick clicks must both count
    try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* private mode: not remembered */ }
    return next
  })
  return (
    <>
      {groups.map(g => {
        const shown = !!g.pinned || (open[g.id] ?? !g.closed)
        const sum = shown ? 0 : g.items.reduce((n, x) => n + (x.badge ? badges[x.badge] : 0), 0)
        return (
          <div key={g.id} data-group={g.id} className="pt-3 first:pt-1">
            {g.pinned
              ? <div className={`label !text-[10.5px] !text-slate-400 px-3.5 pb-1.5 ${WIDE}`}>{g.title}</div>
              : <button type="button" aria-expanded={shown} aria-controls={`nav-${g.id}`} onClick={() => toggle(g.id, shown)}
                  className={`label !text-[10.5px] !text-slate-400 hover:!text-slate-200 w-full min-h-[32px] flex items-center gap-1.5 px-3.5 rounded-lg ${WIDE}`}>
                  <span className="flex-1 text-left">{g.title}</span>
                  {sum > 0 && <span className="tnum text-[10.5px] px-1.5 rounded bg-ink-600 text-slate-100">{sum > 99 ? '99+' : sum}</span>}
                  <ChevronRight size={13} className={`transition-transform ${shown ? 'rotate-90' : ''}`} />
                </button>}
            <div className="hidden lg:group-data-[compact=true]/side:block h-px bg-ink-600/60 mx-3 mb-2" aria-hidden />
            <div id={`nav-${g.id}`} className={`space-y-0.5 ${shown ? '' : 'hidden lg:group-data-[compact=true]/side:block'}`}>
              {g.items.map(x => <Entry key={x.to} item={x} badge={x.badge ? badges[x.badge] : undefined} onNavigate={onNavigate} />)}
            </div>
          </div>)
      })}
    </>
  )
}

const ROW = `group relative flex items-center gap-3 pl-3.5 pr-2.5 py-2 min-h-[40px] rounded-xl text-[13.5px] transition-colors
  lg:group-data-[compact=true]/side:justify-center lg:group-data-[compact=true]/side:px-0`
const REST = 'text-slate-300 hover:text-white hover:bg-white/[0.04]'
const BADGE = `min-w-[20px] h-5 px-1.5 rounded-md grid place-items-center text-[11px] font-semibold tnum bg-ink-600 text-slate-100
  lg:group-data-[compact=true]/side:absolute lg:group-data-[compact=true]/side:top-0 lg:group-data-[compact=true]/side:right-0
  lg:group-data-[compact=true]/side:!h-4 lg:group-data-[compact=true]/side:text-[9.5px]`

function Entry({ item, badge, onNavigate }: { item: NavEntry; badge?: number; onNavigate: () => void }) {
  const { user } = useAuth()
  const isActive = isHere(item, useLocation().pathname)
  const Icon = item.icon
  const warm = () => warmRoute(user?.role, item.to)
  return (
    <Link to={item.to} aria-current={isActive ? 'page' : undefined} onClick={onNavigate} title={item.label}
      aria-label={badge ? `${item.label}, ${badge}` : item.label}
      onPointerEnter={warm} onFocus={warm} onTouchStart={warm}
      className={`${ROW} ${isActive ? 'text-white font-medium bg-accent-400/[0.12]' : REST}`}>
          {/* plain span: a shared layout animation cost up to 200 ms of main thread per click (2026-10-20) */}
          {isActive && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-accent-400" />}
          <span className={isActive ? 'text-accent-300' : 'text-slate-400 group-hover:text-slate-200'}><Icon size={17} /></span>
          <span className={`flex-1 ${WIDE}`}>{item.label}</span>
          {!!badge && <span className={BADGE}>{badge > 99 ? '99+' : badge}</span>}
    </Link>
  )
}
