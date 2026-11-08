/**
 * The environment node's states (Robotics Lab, System 2): smoke/gas,
 * flame, water leak and motion, each NORMAL / DETECTED
 * with an honest quality - "No sensor yet", "Stale", "Node offline" are
 * shown as such and never as NORMAL. These indicators supplement, and do
 * not replace, certified fire and safety systems.
 */
import { useCallback, useEffect, useState } from 'react'
import { Activity, Droplets, Flame, Wind } from 'lucide-react'
import { EnvQuality, LabEnvironment, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import { visibleInterval } from '../lib/visibleInterval'

const ITEMS = [
  { key: 'smoke', label: 'Smoke / gas', icon: Wind, hazard: true },
  { key: 'flame', label: 'Flame', icon: Flame, hazard: true },
  { key: 'water_leak', label: 'Water leak', icon: Droplets, hazard: true },
  { key: 'motion', label: 'Motion', icon: Activity, hazard: false },
] as const

const NOT_VALID: Record<Exclude<EnvQuality, 'VALID'>, string> = {
  MISSING: 'No sensor yet', STALE: 'Stale', DEVICE_OFFLINE: 'Node offline',
  OUT_OF_RANGE: 'Sensor fault',
}

export default function SafetyStates({ labId }: { labId: number }) {
  const [env, setEnv] = useState<LabEnvironment | null>(null)
  const load = useCallback(() => {
    api.labEnvironment(labId).then(setEnv).catch(() => setEnv(null))
  }, [labId])
  useEffect(() => {
    load()
    const t = visibleInterval(load, 15000)
    return () => window.clearInterval(t)
  }, [load])
  // A hazard raises an alarm event for this lab: refresh at once.
  useLiveMessages(m => {
    if (m.type === 'access_event' && m.event.lab_id === labId) load()
    if ((m.type === 'hazard' || m.type === 'env_update') && m.lab_id === labId) load()
  })

  if (!env) return null
  if (!env.node) {
    return <p className="text-[12px] text-slate-500">
      No environment node in this laboratory yet - smoke, flame and leak
      states appear here once one reports.</p>
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {ITEMS.map(({ key, label, icon: Icon, hazard }) => {
        const m = env.metrics[key]
        const valid = m.quality === 'VALID'
        const on = valid && (m.value ?? 0) >= 0.5
        const cls = !valid ? 'border-ink-600/70 text-slate-500'
          : on && hazard ? 'border-bad/60 bg-bad/10 text-bad-soft'
          : on ? 'border-accent-500/40 bg-accent-500/[0.06] text-accent-200'
          : 'border-ok/30 bg-ok/[0.05] text-ok-soft'
        const value = !valid ? NOT_VALID[m.quality as Exclude<EnvQuality, 'VALID'>]
          : hazard ? (on ? 'DETECTED' : 'Normal') : (on ? 'Detected' : 'None')
        return (
          <div key={key} className={`rounded-lg border px-3 py-2 ${cls}`}
               title={m.at ? `Last report ${new Date(m.at).toLocaleString()}` : 'Never reported'}>
            <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.12em] text-slate-400">
              <Icon size={13} />{label}</div>
            <div className={`mt-0.5 text-[14px] font-semibold ${on && hazard ? 'animate-pulse' : ''}`}>{value}</div>
            {m.at && <div className="text-[10.5px] text-slate-500">{relative(m.at)}</div>}
          </div>
        )
      })}
    </div>
  )
}
