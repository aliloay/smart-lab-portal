/**
 * Overall status, claiming only what the portal actually knows.
 *
 * API: the status request itself succeeded. Database: the API ran a query.
 * Live stream: this browser's socket is open. Controllers: heartbeats the
 * devices actually sent. A controller that has never reported is "no data",
 * not "offline" and not "healthy".
 */
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity } from 'lucide-react'
import { SystemStatus, api } from '../lib/api'
import { useLive } from '../lib/live'
import { relative } from '../lib/time'
import { Dot } from './ui'

export default function SystemHealth() {
  const { connected } = useLive()
  const [s, setS] = useState<SystemStatus | null>(null)
  const [apiUp, setApiUp] = useState<boolean | null>(null)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const load = () => api.systemStatus()
      .then(r => { setS(r); setApiUp(true) })
      .catch(() => setApiUp(false))
    load()
    const t = window.setInterval(load, 30000)
    return () => window.clearInterval(t)
  }, [])

  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  const healthy = apiUp === true && s?.database === true
  const label = apiUp === null ? 'Checking' : healthy ? 'System healthy'
    : apiUp === false ? 'API unreachable' : 'Degraded'
  const tone = apiUp === null ? 'idle' : healthy ? 'ok' : 'bad'

  const rows: { name: string; tone: 'ok' | 'bad' | 'idle' | 'warn'; value: string }[] = [
    { name: 'API', tone: apiUp === null ? 'idle' : apiUp ? 'ok' : 'bad',
      value: apiUp === null ? 'Checking' : apiUp ? 'Online' : 'Unreachable' },
    { name: 'Database', tone: !s ? 'idle' : s.database ? 'ok' : 'bad',
      value: !s ? 'Unknown' : s.database ? 'Online' : 'Offline' },
    { name: 'Live stream', tone: connected ? 'ok' : 'warn',
      value: connected ? 'Connected' : 'Reconnecting' },
    {
      name: 'Access controllers',
      tone: !s || s.controllers_total === 0 ? 'idle'
        : s.controllers_online === s.controllers_total ? 'ok'
        : s.devices_reporting === 0 ? 'idle' : 'warn',
      value: !s ? 'Unknown' : s.controllers_total === 0 ? 'None registered'
        : `${s.controllers_online} / ${s.controllers_total} online`,
    },
  ]

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)} aria-expanded={open}
        className="flex items-center gap-2 h-9 px-3 rounded-xl border border-ink-600
                   bg-ink-800/70 hover:border-ink-500 text-[12.5px] text-slate-200">
        <Dot tone={tone} live={healthy} />
        <span className="hidden md:inline">{label}</span>
        <Activity size={14} className="md:hidden text-slate-300" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }} transition={{ duration: .14 }}
            className="absolute right-0 mt-2 w-72 card p-4 z-40">
            <div className="label mb-2">System health</div>
            <ul className="space-y-2.5">
              {rows.map(r => (
                <li key={r.name} className="flex items-center justify-between text-[13px]">
                  <span className="text-slate-300">{r.name}</span>
                  <span className="flex items-center gap-2 text-slate-200">
                    <Dot tone={r.tone} />{r.value}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-3 pt-3 divider text-[11.5px] text-slate-400 leading-relaxed">
              {s?.last_heartbeat_at
                ? `Last device heartbeat ${relative(s.last_heartbeat_at)}.`
                : 'No device has sent a heartbeat yet, so hardware state is unknown rather than assumed.'}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
