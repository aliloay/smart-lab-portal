import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AnimatePresence, m as motion } from 'framer-motion'
import { Bell, BellOff } from 'lucide-react'
import { Notification, api } from '../lib/api'
import { useLive, useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import { Dot, Tone } from './ui'

export const noteTone = (n: Notification): Tone =>
  n.severity === 'critical' ? 'bad' : n.severity === 'warning' ? 'warn' : 'info'

export default function NotificationBell() {
  const { unread, refreshUnread } = useLive()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Notification[] | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const nav = useNavigate()

  const load = () => api.notifications(false, 5).then(setItems).catch(() => setItems([]))

  useEffect(() => { if (open) load() }, [open])
  useLiveMessages(m => { if (m.type === 'notification' && open) load() })

  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  async function openItem(n: Notification) {
    if (!n.is_read) await api.markRead(n.id).catch(() => {})
    refreshUnread()
    setOpen(false)
    if (n.link) nav(n.link)
  }

  // A mouse resting on the bell previews the newest five; a click, Enter or a tap opens the Notifications Center.
  const timer = useRef<number>()
  const hover = (on: boolean) => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setOpen(on), on ? 300 : 250)
  }
  useEffect(() => () => window.clearTimeout(timer.current), [])

  return (
    <div className="relative" ref={ref} onPointerEnter={e => e.pointerType === 'mouse' && hover(true)}
         onPointerLeave={e => e.pointerType === 'mouse' && hover(false)}>
      <Link to="/notifications" onClick={() => { window.clearTimeout(timer.current); setOpen(false) }} title="Notifications"
        aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        className="glass-control relative grid place-items-center w-9">
        <Bell size={16} />
        {unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1
                           rounded-full bg-accent-500 text-[10px] font-bold text-white
                           grid place-items-center ring-2 ring-ink-900 tnum">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </Link>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }} transition={{ duration: .14 }}
            className="absolute right-0 top-full pt-0 mt-2 w-[min(92vw,380px)] card pop p-0 z-40
                       overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b
                            border-ink-600">
              <div className="text-sm font-semibold text-white">Notifications</div>
              {unread > 0 && <span className="text-xs text-slate-400 tnum">{unread} unread</span>}
            </div>
            <div className="max-h-[420px] overflow-y-auto">
              {items === null ? (
                <div className="p-4 space-y-2">
                  {[0, 1, 2].map(i => <div key={i} className="skeleton h-12" />)}
                </div>
              ) : items.length === 0 ? (
                <div className="px-4 py-10 text-center text-sm text-slate-400">
                  <BellOff size={18} className="mx-auto mb-2 text-slate-500" />
                  Nothing yet. Bookings, access and maintenance updates appear here.
                </div>
              ) : (
                <ul className="divide-y divide-ink-700/60">
                  {items.map(n => (
                    <li key={n.id}>
                      <button onClick={() => openItem(n)}
                        className={`w-full text-left px-4 py-3 flex gap-3 hover:bg-ink-700/40
                                    ${n.is_read ? '' : 'bg-accent-500/[0.05]'}`}>
                        <Dot tone={noteTone(n)} className="mt-1.5" />
                        <div className="min-w-0 flex-1">
                          <div className={`text-[13px] leading-snug ${n.is_read
                            ? 'text-slate-300' : 'text-white font-medium'}`}>{n.title}</div>
                          {n.body && <div className="text-[12px] text-slate-400 mt-0.5
                                                     line-clamp-2">{n.body}</div>}
                          <div className="text-[11px] text-slate-500 mt-1">{relative(n.created_at)}</div>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <Link to="/notifications" onClick={() => setOpen(false)}
                  className="block px-4 py-2.5 text-center text-xs link border-t
                             border-ink-600 bg-ink-900/40">
              Open the Notifications Center
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
