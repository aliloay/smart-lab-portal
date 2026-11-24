/**
 * Health Center: what needs attention, why, and what to check - one page instead of four. It only reads: services and
 * devices from /system/health, the reasoning from /metrics/diagnose, data coverage and the event timeline. Nothing here
 * restarts, resets or switches anything.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Clock, HeartPulse, RefreshCw, Search, Stethoscope } from 'lucide-react'
import { Diagnosis, MetricCoverage, MetricTimeline, ServiceHealth, api } from '../lib/api'
import { fmtDateTime, relative } from '../lib/time'
import { visibleInterval } from '../lib/visibleInterval'
import { Chip, Drawer, EmptyState, ErrorBanner, MetricCard, PageHeader, ProgressBar, Select, Spinner, Tabs } from '../components/ui'

type Health = Awaited<ReturnType<typeof api.systemHealth>>
type Tab = 'now' | 'coverage' | 'timeline'
type Tone = 'ok' | 'warn' | 'bad' | 'idle' | 'violet'
const TONE: Record<string, Tone> = { ONLINE: 'ok', DEGRADED: 'warn', STALE: 'warn', OFFLINE: 'bad', UNKNOWN: 'idle', SIMULATION: 'violet' }
const ORDER = ['OFFLINE', 'DEGRADED', 'STALE', 'UNKNOWN', 'ONLINE', 'SIMULATION']
const GROUPS: [string, string][] = [['', 'Services'], ['door', 'Door controllers'], ['entry_camera', 'Door camera'],
  ['environment', 'Environment and bin nodes'], ['security_camera', 'Security cameras'], ['robot', 'Robots'], ['pc', 'Lab PCs']]
const KINDS = ['alert', 'robot', 'maintenance', 'pc', 'door', 'automation']
const problem = (s: ServiceHealth) => ['OFFLINE', 'DEGRADED', 'STALE'].includes(s.state)

export default function HealthCenter() {
  const [tab, setTab] = useState<Tab>('now')
  const [h, setH] = useState<Health | null>(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [only, setOnly] = useState<'problems' | 'all'>('problems')
  const [sel, setSel] = useState<ServiceHealth | null>(null)
  const load = () => { api.systemHealth().then(r => { setH(r); setError('') }).catch(e => setError(e.message)) }
  useEffect(() => { load(); const t = visibleInterval(load, 15000); return () => window.clearInterval(t) }, [])

  const rows = useMemo(() => (h?.services ?? [])
    .filter(s => only === 'all' || problem(s))
    .filter(s => `${s.name} ${s.device_uid ?? ''} ${s.detail}`.toLowerCase().includes(q.trim().toLowerCase()))
    .sort((a, b) => ORDER.indexOf(a.state) - ORDER.indexOf(b.state)), [h, only, q])
  const bad = h?.services.filter(problem) ?? []
  const worst = bad.filter(s => s.state === 'OFFLINE').length
  const db = h?.services.find(s => s.key === 'database')

  return (
    <>
      <PageHeader eyebrow="Intelligence" title="Health Center"
        sub="What needs attention, the recorded evidence, and what to check first. Read only: nothing is restarted or switched from here."
        actions={<button className="btn-ghost btn-sm" onClick={load}><RefreshCw size={13} /> Refresh</button>} />
      {error && <div className="mb-4"><ErrorBanner title={h ? 'Update failed: the values below are from the last good check' : 'Could not read the health state'} message={error} /></div>}
      {!h && !error && <Spinner label="Reading service and device states" />}
      {h && <>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 mb-5">
          <MetricCard label="Need attention" value={bad.length} tone={worst ? 'bad' : bad.length ? 'warn' : 'ok'} animate={false}
            hint={bad.length ? `${worst} offline, ${bad.length - worst} stale or degraded` : 'no known problem'} icon={<HeartPulse size={15} />} />
          <MetricCard label="Online" value={h.summary.ONLINE ?? 0} tone="ok" animate={false}
            hint={`of ${h.services.length} checked parts, ${h.summary.UNKNOWN ?? 0} unknown, ${h.summary.SIMULATION ?? 0} simulated`} />
          <MetricCard label="Database answer" value={db?.latency_ms ?? null} suffix=" ms" animate={false} hint={db?.detail} tone={db?.state === 'ONLINE' ? 'idle' : 'bad'} />
          <MetricCard label="Last check" value={relative(h.checked_at)} animate={false} hint={fmtDateTime(h.checked_at)} icon={<Clock size={15} />} />
        </div>
        <Tabs<Tab> id="health" value={tab} onChange={setTab} tabs={[{ key: 'now', label: 'Now', count: bad.length }, { key: 'coverage', label: 'Data coverage' }, { key: 'timeline', label: 'Timeline' }]} />
        <div className="pt-4">
          {tab === 'now' && <>
            <div className="flex flex-wrap items-end gap-3 mb-4">
              <label className="relative flex-1 min-w-[180px] max-w-sm"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input className="input !pl-9" placeholder="Search a service or device" aria-label="Search a service or device" value={q} onChange={e => setQ(e.target.value)} /></label>
              <div className="flex gap-1" role="group" aria-label="Filter">
                {(['problems', 'all'] as const).map(k => <button key={k} aria-pressed={only === k} onClick={() => setOnly(k)}
                  className={`btn-sm ${only === k ? 'btn-primary' : 'btn-ghost'}`}>{k === 'problems' ? 'Needs attention' : 'Everything'}</button>)}
              </div>
            </div>
            {rows.length === 0 && <EmptyState compact title={q ? 'Nothing matches' : 'No known problem'} detail={q ? 'Try another word or show everything.' : 'No checked part reports offline, stale or degraded. Parts in the unknown state are listed under Everything.'} />}
            {GROUPS.map(([g, title]) => {
              const list = rows.filter(s => (s.group ?? '') === g)
              return list.length ? (
                <section key={g} className="mb-5"><h2 className="label mb-2">{title}</h2>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{list.map(s => <Card key={s.key} s={s} onOpen={() => setSel(s)} />)}</div>
                </section>) : null
            })}
            {rows.some(s => !GROUPS.some(([g]) => g === (s.group ?? ''))) && <section className="mb-5"><h2 className="label mb-2">Other</h2>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{rows.filter(s => !GROUPS.some(([g]) => g === (s.group ?? ''))).map(s => <Card key={s.key} s={s} onOpen={() => setSel(s)} />)}</div></section>}
          </>}
          {tab === 'coverage' && <Coverage />}
          {tab === 'timeline' && <TimelineTab />}
        </div>
      </>}
      <Drawer open={!!sel} onClose={() => setSel(null)} width="sm:w-[520px]" title={sel?.name ?? ''} subtitle={sel?.device_uid}>
        {sel?.device_id != null && <DiagnosisView key={sel.device_id} id={sel.device_id} />}
      </Drawer>
    </>
  )
}

function Card({ s, onOpen }: { s: ServiceHealth; onOpen: () => void }) {
  return (
    <div className="card p-3.5 space-y-1">
      <div className="flex items-center gap-2">
        <b className="text-slate-100 text-[13px] truncate">{s.name}</b>
        <Chip tone={TONE[s.state] ?? 'idle'} dot className="ml-auto shrink-0">{s.state === 'SIMULATION' ? 'simulated' : s.state.toLowerCase()}</Chip>
      </div>
      <div className="text-[12px] text-slate-400 break-words">{s.detail}{s.latency_ms != null ? ` · ${s.latency_ms} ms` : ''}
        {s.open_alerts ? <span className="text-warn-soft"> · {s.open_alerts} open alert{s.open_alerts > 1 ? 's' : ''}</span> : null}</div>
      <div className="text-[11.5px] text-slate-500">{s.failing_since ? `failing since ${relative(s.failing_since)}` : s.last_seen ? `last seen ${relative(s.last_seen)}` : s.last_ok ? `last OK ${relative(s.last_ok)}` : ''}</div>
      {s.guidance && problem(s) && <div className="text-[11.5px] text-sky-300">Check: {s.guidance}</div>}
      {s.device_id != null && <button className="btn-ghost btn-sm mt-1" onClick={onOpen}><Stethoscope size={13} /> Why?</button>}
    </div>
  )
}

function DiagnosisView({ id }: { id: number }) {
  const [d, setD] = useState<Diagnosis | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { let on = true; api.metricDiagnose(id).then(r => on && setD(r)).catch(e => on && setError(e.message)); return () => { on = false } }, [id])
  if (error) return <ErrorBanner message={error} />
  if (!d) return <Spinner label="Reading the records" />
  return (
    <div className="space-y-5 text-[13px] text-slate-300">
      <div><Chip tone={TONE[d.state] ?? 'idle'} dot>{d.state.toLowerCase()}</Chip>
        <p className="mt-2 text-slate-100">{d.what_happened}</p>
        <p className="mt-1 text-[12px] text-slate-400">{d.human_action ? 'A person should look at it.' : 'No action needed.'}</p></div>
      <Block title="Likely causes">
        {d.causes.length === 0 ? <p className="text-slate-400">No cause is supported by the records.</p> : <ul className="space-y-2">{d.causes.map(c => (
          <li key={c.cause} className="card p-3"><div className="flex gap-2"><span className="text-slate-100 flex-1">{c.cause}</span>
            <Chip tone={c.confidence === 'high' ? 'bad' : c.confidence === 'medium' ? 'warn' : 'idle'}>{c.confidence} confidence</Chip></div>
            <ul className="mt-1 list-disc pl-4 text-[12px] text-slate-400">{c.evidence.map(e => <li key={e}>{e}</li>)}</ul></li>))}</ul>}
      </Block>
      <Lines title="What to check" items={d.checks} />
      <Lines title="Evidence" items={d.evidence} />
      <Lines title="Not known (no record)" items={d.missing_evidence} />
      {d.similar_incidents.length > 0 && <Block title="Earlier alerts, 30 days"><ul className="space-y-1">{d.similar_incidents.map((x, n) => (
        <li key={n} className="flex gap-2"><span className="flex-1">{x.title}{x.occurrences > 1 ? ` (${x.occurrences}×)` : ''}</span>
          <span className="text-slate-500 shrink-0">{relative(x.at)}{x.resolved ? ', resolved' : ''}</span></li>))}</ul></Block>}
      <p className="text-[11.5px] text-slate-500">{d.statement}</p>
      <Link className="btn-ghost btn-sm" to="/admin/sensors">Open sensor analytics</Link>
    </div>
  )
}
const Block = ({ title, children }: { title: string; children: React.ReactNode }) => <div><div className="label mb-1.5">{title}</div>{children}</div>
const Lines = ({ title, items }: { title: string; items: string[] }) => items.length
  ? <Block title={title}><ul className="list-disc pl-4 space-y-0.5 break-words">{items.map(x => <li key={x}>{x}</li>)}</ul></Block> : null

function Coverage() {
  const [days, setDays] = useState('7')
  const [rows, setRows] = useState<MetricCoverage[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { let on = true; setRows(null); setError(''); api.metricCoverage(+days).then(r => on && setRows(r)).catch(e => on && setError(e.message)); return () => { on = false } }, [days])
  return (
    <div className="max-w-3xl">
      <div className="flex flex-wrap items-end gap-3 mb-3"><div className="w-40"><Select label="Window" value={days} onChange={setDays} options={[['1', '1 day'], ['7', '7 days'], ['30', '30 days'], ['90', '90 days']]} /></div>
        <p className="text-[12px] text-slate-400 flex-1">Hours with at least one stored reading. This is data coverage, not uptime: a device that is switched off on purpose lowers it, and a door node sends events, not readings.</p></div>
      {error && <ErrorBanner message={error} />}
      {!rows && !error && <Spinner label="Counting readings" />}
      {rows?.length === 0 && <EmptyState compact title="No readings in this window" detail="No device stored a measurement. Choose a longer window." />}
      <ul className="space-y-2">{rows?.map(r => (
        <li key={r.device_id} className="card p-3"><div className="flex justify-between gap-3 text-[13px]"><span className="text-slate-100">{r.device_name} <span className="mono text-[11px] text-slate-500">{r.device_uid}</span></span>
          <b className="tnum text-slate-100">{r.coverage_pct} %</b></div>
          <div className="my-1.5"><ProgressBar value={r.coverage_pct} /></div>
          <div className="text-[11.5px] text-slate-500">{r.hours_with_data} of {r.window_hours} h · {r.readings.toLocaleString()} readings · last {relative(r.last)}</div></li>))}</ul>
    </div>
  )
}

function TimelineTab() {
  const [hours, setHours] = useState('24')
  const [kinds, setKinds] = useState<string[]>(KINDS)
  const [t, setT] = useState<MetricTimeline | null>(null)
  const [error, setError] = useState('')
  const key = kinds.join(',')
  useEffect(() => {
    let on = true
    setError('')
    if (!key) { setT(null); return }
    api.metricTimeline(+hours, key).then(r => on && setT(r)).catch(e => on && setError(e.message))
    return () => { on = false }
  }, [hours, key])
  return (
    <div className="max-w-4xl">
      <div className="flex flex-wrap items-end gap-3 mb-3"><div className="w-40"><Select label="Window" value={hours} onChange={setHours} options={[['24', '24 hours'], ['72', '3 days'], ['168', '7 days'], ['720', '30 days']]} /></div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Event kinds">{KINDS.map(k => <button key={k} aria-pressed={kinds.includes(k)} className={`btn-sm ${kinds.includes(k) ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setKinds(v => v.includes(k) ? v.filter(x => x !== k) : KINDS.filter(x => v.includes(x) || x === k))}>{k}</button>)}</div></div>
      {error && <ErrorBanner message={error} />}
      {!key && <EmptyState compact title="Choose at least one kind of event" />}
      {t && key && <>
        {t.unavailable.length > 0 && <p className="text-[12px] text-warn-soft mb-2">Could not read: {t.unavailable.join(', ')}</p>}
        {t.items.length === 0 ? <EmptyState compact title="No events in this window" /> :
          <ul className="card divide-y divide-ink-600/50">{t.items.map(x => (
            <li key={`${x.kind}-${x.id}`} className="px-4 py-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[12.5px]">
              <span className="mono text-slate-500 w-[130px] shrink-0">{fmtDateTime(x.at)}</span>
              <span className="w-24 shrink-0 text-slate-400">{x.kind}</span>
              <span className="text-slate-200 flex-1 min-w-[160px]">{x.text}</span>
              <span className="mono text-slate-500">{x.device_uid ?? ''}</span>
              {x.level !== 'INFO' && <Chip tone={/CRIT|HIGH|FAIL|DENIED/.test(x.level) ? 'bad' : 'warn'}>{x.level.toLowerCase()}</Chip>}
            </li>))}</ul>}
        <p className="mt-2 text-[11.5px] text-slate-500">{t.privacy}{t.truncated ? ' Only the newest 200 events are listed.' : ''}</p>
      </>}
    </div>
  )
}
