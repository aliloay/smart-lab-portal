/**
 * Orange advisory pop-ups for staff (no siren - not danger):
 *   - temperature / humidity above the comfort limit, with advice
 *     (ventilation, AC). The portal only advises; it switches nothing.
 *   - motion started: a BLUE note, silent (motion is normal activity).
 * Temperature / humidity play a short chime once; motion never makes a sound.
 * CLEAR closes a card, CLEAR ALL resets every pop-up (and the red bar) on
 * this screen. "Back to normal" closes its card by itself.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Droplets, Thermometer, X } from 'lucide-react'
import { isStaff, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'

interface Warning {
  key: string; kind: string; lab_id: number; lab_code: string
  title: string; detail: string; at: string
}
const ICON: Record<string, typeof Activity> = {
  temp_high: Thermometer, humidity_high: Droplets, motion: Activity,
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
      const key = `${m.lab_id}:${m.kind}`          // one card per lab and kind
      setItems(list => [{ key, kind: m.kind, lab_id: m.lab_id,
        lab_code: m.lab_code, title: m.title, detail: m.detail, at: m.at },
        ...list.filter(x => x.key !== key)].slice(0, 4))
      if (m.kind !== 'motion') chime()               // motion is silent
    } else {
      setItems(list => list.filter(x => !(x.lab_id === m.lab_id && x.kind === m.kind)))
    }
  })

  // CLEAR ALL also resets the red hazard bar on this screen.
  useEffect(() => {
    const h = () => setItems([])
    window.addEventListener('smartlab:clear-all', h)
    return () => window.removeEventListener('smartlab:clear-all', h)
  }, [])

  if (!isStaff(user) || items.length === 0) return null
  const drop = (key: string) => setItems(l => l.filter(x => x.key !== key))
  return (
    <div className="fixed top-20 right-4 z-[65] flex flex-col gap-3 w-[min(420px,calc(100vw-2rem))]">
      <button onClick={() => window.dispatchEvent(new Event('smartlab:clear-all'))}
        className="self-end rounded-lg bg-ink-900/90 border border-white/30 text-white text-xs font-bold px-3 py-1.5">
        CLEAR ALL</button>
      {items.map(w => {
        const Icon = ICON[w.kind] ?? Activity
        const motion = w.kind === 'motion'
        return (
          <div key={w.key} role="alert"
            className={`rounded-xl border-2 text-white shadow-2xl p-4 ${motion
              ? 'border-sky-400 bg-[#0b2a45]/95' : 'border-warn bg-[#3a2606]/95'}`}>
            <div className="flex items-start gap-3">
              <Icon className={`shrink-0 mt-0.5 ${motion ? 'text-sky-300' : 'text-warn'}`} size={26} />
              <div className="min-w-0 flex-1">
                <div className="text-lg font-extrabold leading-tight">{w.title}</div>
                <div className="mt-1 text-sm text-white/85">{w.detail}</div>
                <div className="mt-1 text-xs text-white/50">{new Date(w.at).toLocaleTimeString()}</div>
                <div className="mt-3 flex gap-2">
                  <button onClick={() => { nav(`/labs/${w.lab_id}`); drop(w.key) }}
                    className={`rounded-lg font-bold text-sm px-3 py-1.5 ${motion
                      ? 'bg-sky-400 text-black' : 'bg-warn text-black'}`}>See the lab</button>
                  <button onClick={() => drop(w.key)}
                    className="rounded-lg border border-white/50 font-bold text-sm px-3 py-1.5">CLEAR</button>
                </div>
              </div>
              <button aria-label="Clear" onClick={() => drop(w.key)}
                className="text-white/60 hover:text-white"><X size={18} /></button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
