/**
 * New WARNING / CRITICAL notifications (n8n automations and the portal) pop
 * up at the bottom right with a short chime, so they are not lost under the
 * bell. Kinds that already have their own screen are left out (the hazard
 * alarm, the environment advisories, the emergency message). Each card
 * closes itself after 12 s; CLEAR ALL closes them all.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Workflow, X } from 'lucide-react'
import { Notification } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'

const OWN_SCREEN = new Set(['ENVIRONMENT_HAZARD', 'ENVIRONMENT_ADVISORY', 'EMERGENCY'])
const SHOW_MS = 12000

function chime() {
  try {
    const c = new (window.AudioContext || (window as any).webkitAudioContext)()
    ;[740, 990].forEach((f, i) => {
      const o = c.createOscillator(), g = c.createGain(), t = c.currentTime + i * 0.14
      o.frequency.value = f
      g.gain.setValueAtTime(0.0001, t)
      g.gain.exponentialRampToValueAtTime(0.15, t + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.13)
      o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + 0.14)
    })
  } catch { /* no audio until the page has been tapped once */ }
}

export default function NotificationToasts() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [items, setItems] = useState<Notification[]>([])

  useLiveMessages(m => {
    if (m.type !== 'notification') return
    const n = m.notification
    if (n.severity === 'info' || OWN_SCREEN.has(n.kind)) return
    setItems(list => [n, ...list.filter(x => x.id !== n.id)].slice(0, 3))
    chime()
    window.setTimeout(() => setItems(list => list.filter(x => x.id !== n.id)), SHOW_MS)
  })
  useEffect(() => {
    const h = () => setItems([])
    window.addEventListener('smartlab:clear-all', h)
    return () => window.removeEventListener('smartlab:clear-all', h)
  }, [])

  if (!user || !items.length) return null
  return (
    <div className="fixed bottom-4 right-4 z-[64] flex flex-col gap-2 w-[min(380px,calc(100vw-2rem))]">
      {items.map(n => (
        <div key={n.id} role="status" data-testid="notification-toast"
          className={`rounded-xl border-2 shadow-2xl p-3 text-white bg-ink-900/95 ${
            n.severity === 'critical' ? 'border-bad' : 'border-warn'}`}>
          <div className="flex items-start gap-2.5">
            {n.source === 'n8n' ? <Workflow size={18} className="text-violet-300 mt-0.5 shrink-0" />
              : <Bell size={18} className="text-warn mt-0.5 shrink-0" />}
            <button className="min-w-0 flex-1 text-left" onClick={() => {
              setItems(l => l.filter(x => x.id !== n.id)); nav(n.link || '/notifications') }}>
              <div className="font-bold text-[14px] leading-tight">{n.title}</div>
              {n.body && <div className="text-[12.5px] text-white/75 mt-0.5 line-clamp-2">{n.body}</div>}
              <div className="text-[11px] text-white/45 mt-1">{n.source === 'n8n' ? 'n8n automation' : 'Portal'} · tap to open</div>
            </button>
            <button aria-label="Close" onClick={() => setItems(l => l.filter(x => x.id !== n.id))}
              className="text-white/60 hover:text-white"><X size={16} /></button>
          </div>
        </div>
      ))}
    </div>
  )
}
