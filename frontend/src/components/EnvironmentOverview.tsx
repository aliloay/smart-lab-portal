/**
 * System 2 - physical environment, every lab that has an environment node:
 * temperature, humidity and the safety states (smoke/gas, flame, water
 * leak, emergency, motion), each with an honest quality. Indicators only -
 * not certified fire or safety systems.
 */
import { useEffect, useState } from 'react'
import { Droplets, Thermometer, Wind } from 'lucide-react'
import { Lab, LabEnvironment, api } from '../lib/api'
import { relative } from '../lib/time'
import SafetyStates from './SafetyStates'
import { EmptyState, Spinner } from './ui'

export default function EnvironmentOverview() {
  const [rows, setRows] = useState<{ lab: Lab; env: LabEnvironment }[] | null>(null)
  useEffect(() => {
    const load = () => api.labs().then(labs => Promise.all(labs.map(l =>
      api.labEnvironment(l.id).then(env => ({ lab: l, env })).catch(() => null))))
      .then(list => setRows(list.filter((x): x is { lab: Lab; env: LabEnvironment } => !!x && !!x.env.node)))
      .catch(() => setRows([]))
    load()
    const t = window.setInterval(load, 20000)
    return () => window.clearInterval(t)
  }, [])

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
