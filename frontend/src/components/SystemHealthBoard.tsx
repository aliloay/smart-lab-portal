/**
 * System Health: every service and device with its real state (ONLINE / DEGRADED / STALE / OFFLINE /
 * UNKNOWN / SIMULATED), last success, latency, failure reason and what to check first. Network
 * services are probed in the background by the backend; this page only reads the cache.
 */
import { useEffect, useState } from 'react'
import { Activity, Database, HardDrive, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { relative } from '../lib/time'
import { Chip, SectionTitle } from './ui'

type Health = Awaited<ReturnType<typeof api.systemHealth>>
const TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle' | 'violet'> = {
  ONLINE: 'ok', DEGRADED: 'warn', STALE: 'warn', OFFLINE: 'bad', UNKNOWN: 'idle', SIMULATION: 'violet' }
const LABEL: Record<string, string> = { SIMULATION: 'simulated' }
const GROUP: Record<string, string> = {
  door: 'Door controllers', entry_camera: 'Door camera', environment: 'Environment nodes', security_camera: 'Security cameras',
  robot: 'Robots', pc: 'Lab PCs' }

export default function SystemHealthBoard() {
  const [h, setH] = useState<Health | null>(null)
  const [error, setError] = useState('')
  const load = () => { api.systemHealth().then(r => { setH(r); setError('') }).catch(e => setError(e.message)) }
  useEffect(() => { load(); const t = window.setInterval(load, 15000); return () => window.clearInterval(t) }, [])
  const core = h?.services.filter(s => !s.group) ?? []
  const groups = Object.keys(GROUP).map(g => [g, h?.services.filter(s => s.group === g) ?? []] as const).filter(([, l]) => l.length)
  return (
    <section className="mb-8">
      <SectionTitle icon={<Activity size={15} />} sub="Real checks only: background probes for services, heartbeats for devices. Nothing is assumed healthy."
        action={<button className="btn-ghost btn-sm" onClick={load}><RefreshCw size={13} /> Refresh</button>}>System health</SectionTitle>
      {error && <p className="text-[12px] text-bad-soft mb-2">{error}</p>}
      {h && <div className="flex flex-wrap gap-2 mb-3">
        {Object.entries(h.summary).filter(([, n]) => n > 0).map(([k, n]) => <Chip key={k} tone={TONE[k]}>{n} {(LABEL[k] ?? k).toLowerCase()}</Chip>)}
        <span className="text-[12px] text-slate-500 self-center">checked {relative(h.checked_at)}</span>
      </div>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {core.map(s => <Row key={s.key} s={s} />)}
      </div>
      {groups.map(([g, list]) => (
        <div key={g} className="mt-4">
          <div className="label mb-2">{GROUP[g]}</div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{list.map(s => <Row key={s.key} s={s} />)}</div>
        </div>))}
      {h && <div className="grid gap-3 md:grid-cols-2 mt-5">
        <div className="card p-4">
          <div className="label mb-2 flex items-center gap-1.5"><Database size={13} /> Data sources (last record)</div>
          <ul className="text-[12.5px] space-y-1">{Object.entries(h.data_sources).map(([k, f]) => (
            <li key={k} className="flex items-center gap-2"><Chip tone={f.state === 'live' ? 'ok' : f.state === 'stale' ? 'warn' : f.state === 'never' ? 'idle' : 'bad'}>{f.state}</Chip>
              <span className="text-slate-200">{k}</span><span className="mono text-[11px] text-slate-500">{f.source}</span>
              <span className="ml-auto text-slate-400">{f.last ? relative(f.last) : 'never'}</span></li>))}</ul>
        </div>
        <div className="card p-4">
          <div className="label mb-2 flex items-center gap-1.5"><HardDrive size={13} /> Backups</div>
          <pre className="text-[11.5px] text-slate-300 whitespace-pre-wrap">{h.backup ? JSON.stringify(h.backup, null, 1) : 'No backup status file found.'}</pre>
        </div>
      </div>}
    </section>
  )
}

function Row({ s }: { s: Health['services'][number] }) {
  return (
    <div className="card p-3 space-y-1">
      <div className="flex items-center gap-2">
        <b className="text-slate-100 text-[13px] truncate">{s.name}</b>
        {s.device_uid && <span className="mono text-[11px] text-slate-500 truncate">{s.device_uid}</span>}
        <Chip tone={TONE[s.state] ?? 'idle'} dot className="ml-auto shrink-0">{(LABEL[s.state] ?? s.state).toLowerCase()}</Chip>
      </div>
      <div className="text-[12px] text-slate-400">{s.detail}{s.latency_ms != null ? ` · ${s.latency_ms} ms` : ''}
        {s.open_alerts ? <span className="text-warn-soft"> · {s.open_alerts} open alert{s.open_alerts > 1 ? 's' : ''}</span> : null}</div>
      {(s.last_ok || s.last_seen || s.failing_since) && <div className="text-[11.5px] text-slate-500">
        {s.failing_since ? `failing since ${relative(s.failing_since)} (${s.consecutive_failures} checks) · ` : ''}
        {s.last_ok ? `last OK ${relative(s.last_ok)}` : s.last_seen ? `last seen ${relative(s.last_seen)}` : ''}</div>}
      {s.guidance && <div className="text-[11.5px] text-sky-300">What to check: {s.guidance}</div>}
    </div>
  )
}
