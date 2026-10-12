/**
 * System 2 - physical environment, every lab that has an environment node:
 * temperature, humidity and the safety states (smoke/gas, flame, water
 * leak and motion), each with an honest quality. Indicators only -
 * not certified fire or safety systems.
 */
import { useCallback, useEffect, useState } from 'react'
import { Droplets, Thermometer, Wind } from 'lucide-react'
import { Lab, LabEnvironment, api } from '../lib/api'
import { relative } from '../lib/time'
import { useLiveMessages } from '../lib/live'
import SafetyStates from './SafetyStates'
import { EmptyState, Spinner } from './ui'

export default function EnvironmentOverview() {
  const [rows, setRows] = useState<{ lab: Pick<Lab, 'id' | 'code' | 'name'>; env: LabEnvironment }[] | null>(null)
  // One request for every lab (it used to be one per lab).
  const load = useCallback(() => {
    api.allEnvironments().then(setRows).catch(() => setRows(r => r ?? []))
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 20000)
    return () => window.clearInterval(t)
  }, [load])
  // New readings arrive every ~10 s and on every change: show them at once.
  useLiveMessages(m => { if (m.type === 'env_update' || m.type === 'hazard') load() })

  if (!rows) return <Spinner label="Loading environment" />
  if (!rows.length) {
    return <EmptyState icon={<Wind size={18} />} title="No environment node is reporting yet"
      detail="Flash firmware/SmartLab_Environment_Node onto ESP32 #1 (see its README). It appears here on its first heartbeat." />
  }
  return (
    <div className="space-y-4">
      {rows.map(({ lab, env }) => {
        const t = env.metrics.temperature, h = env.metrics.humidity
        return (
          <section key={lab.id} className="card p-5 space-y-4">
            <div className="flex items-center gap-3">
              <div>
                <div className="text-white font-semibold">{lab.code} · {lab.name}</div>
                <div className="text-[12px] text-slate-400 mono">{env.node!.device_uid} ·{' '}
                  {env.node!.online === false ? <span className="text-bad-soft">offline</span> : 'online'}
                  {env.node!.last_seen_at && <> · {relative(env.node!.last_seen_at)}</>}</div>
              </div>
              <div className="ml-auto flex gap-6">
                <Value icon={<Thermometer size={15} />} label="Temperature"
                       v={t.quality === 'VALID' && t.value !== null ? `${t.value.toFixed(1)} °C` : t.quality.toLowerCase().replace('_', ' ')} />
                <Value icon={<Droplets size={15} />} label="Humidity"
                       v={h.quality === 'VALID' && h.value !== null ? `${h.value.toFixed(0)} %` : h.quality.toLowerCase().replace('_', ' ')} />
              </div>
            </div>
            <SafetyStates labId={lab.id} />
          </section>)
      })}
    </div>
  )
}

function Value({ icon, label, v }: { icon: JSX.Element; label: string; v: string }) {
  return <div className="text-right">
    <div className="label flex items-center gap-1 justify-end">{icon}{label}</div>
    <div className="text-xl text-white tnum">{v}</div></div>
}
