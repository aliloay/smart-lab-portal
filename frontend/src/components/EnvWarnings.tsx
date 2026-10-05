/**
 * Orange advisory pop-ups for staff (no siren - not danger):
 *   - temperature / humidity above the comfort limit, with advice
 *     (ventilation, AC). The portal only advises; it switches nothing.
 *   - motion while the lab is closed (no booking, nobody checked in).
 * Each shows once with a short two-tone chime and stays until dismissed;
 * "back to normal" closes its card. The alerts themselves are on the
 * Alerts page.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Droplets, Thermometer, X } from 'lucide-react'
import { isStaff, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'

interface Warning {
  alert_id: number; kind: string; lab_id: number; lab_code: string
  title: string; detail: string; at: string
}
const ICON: Record<string, typeof Activity> = {
  temp_high: Thermometer, humidity_high: Droplets, motion_closed: Activity,
}

function chime() {
  try {
    const c = new (window.AudioContext || (window as any).webkitAudioContext)()
    ;[880, 660].forEach((f, i) => {
      const o = c.createOscillator(), g = c.createGain(), t = c.currentTime + i * 0.18
      o.frequency.value = f
      g.gain.setValueAtTime(0.0001, t)
      g.gain.exponentialRampToValueAtTime(0.18, t + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16)
      o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + 0.17)
    })
  } catch { /* no audio until the page has been tapped once */ }
}

export default function EnvWarnings() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [items, setItems] = useState<Warning[]>([])

  useLiveMessages(m => {
    if (m.type !== 'env_warning') return
    if (m.state === 'raised') {
      setItems(list => [{ alert_id: m.alert_id, kind: m.kind, lab_id: m.lab_id,
        lab_code: m.lab_code, title: m.title, detail: m.detail, at: m.at },
        ...list.filter(x => x.alert_id !== m.alert_id)].slice(0, 4))
      chime()
    } else {
      setItems(list => list.filter(x => !(x.lab_id === m.lab_id && x.kind === m.kind)))
    }
  })

  if (!isStaff(user) || items.length === 0) return null
  return (
    <div className="fixed top-20 right-4 z-[65] flex flex-col gap-3 w-[min(420px,calc(100vw-2rem))]">
      {items.map(w => {
        const Icon = ICON[w.kind] ?? Activity
        return (
          <div key={w.alert_id} role="alert"
            className="rounded-xl border-2 border-warn bg-[#3a2606]/95 text-white shadow-2xl p-4">
            <div className="flex items-start gap-3">
              <Icon className="text-warn shrink-0 mt-0.5" size={26} />
              <div className="min-w-0 flex-1">
                <div className="text-lg font-extrabold leading-tight">{w.title}</div>
                <div className="mt-1 text-sm text-white/85">{w.detail}</div>
                <div className="mt-1 text-xs text-white/50">{new Date(w.at).toLocaleTimeString()}</div>
                <div className="mt-3 flex gap-2">
                  <button onClick={() => { nav(`/labs/${w.lab_id}`)
                      setItems(l => l.filter(x => x.alert_id !== w.alert_id)) }}
                    className="rounded-lg bg-warn text-black font-bold text-sm px-3 py-1.5">
                    See the lab</button>
                  <button onClick={() => setItems(l => l.filter(x => x.alert_id !== w.alert_id))}
                    className="rounded-lg border border-white/40 text-sm px-3 py-1.5">Dismiss</button>
                </div>
              </div>
              <button aria-label="Dismiss" onClick={() => setItems(l => l.filter(x => x.alert_id !== w.alert_id))}
                className="text-white/60 hover:text-white"><X size={18} /></button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
