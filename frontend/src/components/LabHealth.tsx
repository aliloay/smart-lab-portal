/**
 * Lab Health Score (priority H) and the advisory emergency headcount (priority N), 2026-10-26.
 * Both come from the portal's own records; unknown parts are shown as unknown, never as healthy.
 */
import { useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { api } from '../lib/api'
import { relative } from '../lib/time'
import { Chip, Notice, SectionTitle, Skeleton } from './ui'

const BAND: Record<string, 'ok' | 'warn' | 'bad' | 'idle'> = { GOOD: 'ok', FAIR: 'warn', POOR: 'bad', UNKNOWN: 'idle' }
const PART: Record<string, string> = { devices: 'Devices reporting', alerts: 'Open alerts', environment: 'Environment readings',
  issues: 'Issue reports', hazards: 'Smoke / flame' }

export function LabHealth() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof api.labsHealth>> | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    const load = () => api.labsHealth().then(setRows).catch(e => setErr(e.message))
    load(); const t = window.setInterval(load, 30000); return () => window.clearInterval(t)
  }, [])
  if (err) return <p className="text-[12.5px] text-bad-soft">{err}</p>
  if (!rows) return <Skeleton className="h-40" />
  return (
    <div className="space-y-3">
      <p className="text-[12.5px] text-slate-400">0-100 per lab from the portal's own records. A part without data is left out
        (coverage shows how much is known). It ranks what needs attention; it does not certify that a lab is safe.</p>
      <div className="grid lg:grid-cols-2 gap-3">
        {rows.map(r => <div key={r.lab_id} className="card p-4 space-y-2">
          <div className="flex items-center gap-3">
            <div className="text-[30px] font-semibold text-white tabular-nums">{r.score == null ? '–' : Math.round(r.score)}</div>
            <div className="flex-1 min-w-0"><div className="text-white font-medium truncate">{r.lab_name}</div>
              <div className="text-[11.5px] text-slate-500">{r.lab_code} · coverage {Math.round(r.coverage * 100)} %</div></div>
            <Chip tone={BAND[r.band]}>{r.band}</Chip>
          </div>
          <ul className="text-[12px] space-y-1">
            {Object.entries(r.parts).map(([k, p]) => <li key={k} className="flex items-center gap-2">
              <span className="w-36 text-slate-300">{PART[k] ?? k} <span className="text-slate-500">({p.weight})</span></span>
              <span className="flex-1 h-1.5 rounded bg-ink-700 overflow-hidden">
                {p.value != null && <span className={`block h-full ${p.value >= .85 ? 'bg-emerald-500' : p.value >= .6 ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${Math.round(p.value * 100)}%` }} />}</span>
              <span className={`w-48 truncate ${p.value == null ? 'text-slate-500' : 'text-slate-400'}`} title={p.evidence}>
                {p.value == null ? 'unknown - ' : ''}{p.evidence}</span></li>)}
          </ul>
        </div>)}
      </div>
    </div>
  )
}

export function Headcount() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof api.labsHeadcount>> | null>(null)
  useEffect(() => {
    const load = () => api.labsHeadcount().then(setRows).catch(() => setRows([]))
    load(); const t = window.setInterval(load, 5000); return () => window.clearInterval(t)
  }, [])
  return (
    <section>
      <SectionTitle icon={<Users size={15} />} sub="Door record (named) next to what the cameras count now. Advisory - confirm by roll call.">
        Headcount</SectionTitle>
      {!rows ? <Skeleton className="h-24" /> : <div className="grid lg:grid-cols-2 gap-4">
        {rows.map(r => <div key={r.lab_id} className="card p-4 space-y-2">
          <div className="flex items-baseline gap-4">
            <div><div className="text-[28px] font-semibold text-white tabular-nums">{r.door_inside}</div>
              <div className="text-[11.5px] text-slate-400">inside per the door</div></div>
            <div><div className="text-[28px] font-semibold text-white tabular-nums">{r.camera_people ?? '–'}</div>
              <div className="text-[11.5px] text-slate-400">seen by a camera now</div></div>
            <div className="ml-auto text-right text-white font-medium">{r.lab_name}</div>
          </div>
          <p className={`text-[12px] ${r.camera_people != null && r.camera_people === r.door_inside ? 'text-slate-400' : 'text-warn-soft'}`}>{r.note}</p>
          {r.names.length > 0 && <ul className="text-[12px] text-slate-300 grid sm:grid-cols-2 gap-x-3">
            {r.names.map(n => <li key={n.name + n.entered_at}>{n.name} <span className="text-slate-500">· {n.role.toLowerCase()} · in {relative(new Date(n.entered_at * 1000).toISOString())}</span></li>)}</ul>}
        </div>)}
      </div>}
      <div className="mt-2"><Notice tone="info">Advisory only: never a reason to skip a search. The door record misses people who
        followed someone in; cameras miss people out of view and two cameras can see the same person (the larger single count is shown).</Notice></div>
    </section>
  )
}
