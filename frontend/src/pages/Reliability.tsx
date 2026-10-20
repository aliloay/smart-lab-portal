/**
 * Reliability centre (2026-10-18): one place to see what needs attention and why.
 *   Briefing      deterministic, evidence-linked, most urgent first
 *   Dependencies  the live state model (digital twin): who needs whom, likely roots, impact,
 *                 a SANDBOXED what-if (nothing is changed - labelled as simulation)
 *   Drift         differences from the approved baseline; accepted deviations stay visible
 *   Performance   request latency per route, regressions, service objectives with error budget
 *   Quality       alert grouping effect, noisy sources, recurrence, time to acknowledge / resolve
 *   Backups       last backup, last verified restore drill, disk and database size
 *   Policy        which actions may run automatically, need approval, or are prohibited
 * Read-only towards devices: nothing here sends a command to a door, robot, camera or PC.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Activity, BookOpen, Database, GitBranch, Gauge, ListChecks, RefreshCw, Scale, ShieldAlert } from 'lucide-react'
import { AlertQuality, DriftReport, PerfReport, RelGraph, RelNode, WhatIf, api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Chip, MetricCard, PageHeader, Tabs } from '../components/ui'

type TabKey = 'briefing' | 'graph' | 'drift' | 'performance' | 'quality' | 'backups' | 'policy'
const STATE_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle' | 'violet'> = {
  HEALTHY: 'ok', DEGRADED: 'warn', 'STALE DATA': 'warn', OFFLINE: 'bad', SIMULATED: 'violet', UNKNOWN: 'idle'
}
const fmtS = (s: number | null | undefined) => s == null ? '-' : s < 120 ? `${s} s` : s < 7200 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`

export default function Reliability() {
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as TabKey) || 'briefing'
  const setTab = (t: TabKey) => setParams({ tab: t }, { replace: true })
  return (
    <div>
      <PageHeader eyebrow="Insight" title="Reliability"
        sub="What needs attention, how the parts depend on each other, configuration and performance drift, alert quality, backups. From the portal's own checks and records - physical states still need a person on site." />
      <Tabs id="rel" value={tab} onChange={setTab} tabs={[
        { key: 'briefing', label: 'Briefing', icon: <ListChecks size={14} /> },
        { key: 'graph', label: 'Dependencies', icon: <GitBranch size={14} /> },
        { key: 'drift', label: 'Drift', icon: <Scale size={14} /> },
        { key: 'performance', label: 'Performance', icon: <Gauge size={14} /> },
        { key: 'quality', label: 'Alert quality', icon: <Activity size={14} /> },
        { key: 'backups', label: 'Backups', icon: <Database size={14} /> },
        { key: 'policy', label: 'Action policy', icon: <ShieldAlert size={14} /> },
      ]} />
      <div className="mt-4">
        {tab === 'briefing' && <Briefing />}
        {tab === 'graph' && <Graph />}
        {tab === 'drift' && <Drift />}
        {tab === 'performance' && <Performance />}
        {tab === 'quality' && <Quality />}
        {tab === 'backups' && <Backups />}
        {tab === 'policy' && <Policy />}
      </div>
    </div>
  )
}

function useLoad<T>(fn: () => Promise<T>): [T | null, string, () => void] {
  const [d, setD] = useState<T | null>(null)
  const [err, setErr] = useState('')
  const [n, setN] = useState(0)
  useEffect(() => { let live = true; fn().then(x => live && setD(x)).catch(e => live && setErr(e.message)); return () => { live = false } }, [n]) // eslint-disable-line react-hooks/exhaustive-deps
  return [d, err, () => setN(x => x + 1)]
}

function Briefing() {
  const [b, err, reload] = useLoad(api.relBriefing)
  if (err) return <p className="text-bad-soft text-sm">{err}</p>
  if (!b) return <p className="text-slate-400 text-sm">Loading…</p>
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[12px] text-slate-400">Generated {new Date(b.generated_at).toLocaleString()} · {b.note}
        <button className="btn-ghost btn-sm ml-auto" onClick={reload}><RefreshCw size={13} /> Refresh</button></div>
      {b.items.map(i => (
        <div key={i.id} className={`card p-3 ${i.priority === 1 ? 'border-red-500/40' : ''}`}>
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone={i.priority === 1 ? 'bad' : i.priority === 2 ? 'warn' : 'idle'}>{i.priority === 1 ? 'now' : i.priority === 2 ? 'soon' : 'plan'}</Chip>
            <Chip tone="idle">{i.kind}</Chip>
            <b className="text-slate-100 text-[13.5px]">{i.title}</b>
            {i.repeated && <span className="text-[11px] text-slate-500">(unchanged since the last briefing)</span>}
            <Link to={i.link} className="ml-auto text-[12px] text-accent-300 hover:underline">evidence →</Link>
          </div>
          <ul className="mt-1 text-[12.5px] text-slate-300 list-disc pl-5">{i.evidence.map((e, k) => <li key={k}>{e}</li>)}</ul>
          {i.uncertainty && <p className="text-[11.5px] text-slate-500 mt-1">Uncertainty: {i.uncertainty}</p>}
        </div>))}
    </div>
  )
}

const KIND_ORDER = ['host', 'network', 'service', 'job', 'process', 'device', 'door', 'environment', 'bin', 'security_camera',
  'robot', 'pc', 'entry_camera']

function Graph() {
  const [g, err, reload] = useLoad(api.relGraph)
  const [sel, setSel] = useState<string | null>(null)
  const [w, setW] = useState<WhatIf | null>(null)
  const [busy, setBusy] = useState(false)
  const by = useMemo(() => Object.fromEntries((g?.nodes ?? []).map(n => [n.key, n])) as Record<string, RelNode>, [g])
  if (err) return <p className="text-bad-soft text-sm">{err}</p>
  if (!g) return <p className="text-slate-400 text-sm">Loading…</p>
  const groups = KIND_ORDER.map(k => ({ k, nodes: g.nodes.filter(n => n.kind === k) })).filter(x => x.nodes.length)
  const s = sel ? by[sel] : null
  const runWhatIf = async (node: string) => { setBusy(true); try { setW(await api.relWhatIf(node)) } finally { setBusy(false) } }
  return (
    <div className="grid lg:grid-cols-[1fr_380px] gap-4">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          {Object.entries(g.summary).map(([k, v]) => <Chip key={k} tone={STATE_TONE[k] ?? 'idle'}>{k.toLowerCase()} {v}</Chip>)}
          <button className="btn-ghost btn-sm ml-auto" onClick={reload}><RefreshCw size={13} /> Refresh</button>
        </div>
        {g.likely_roots.length > 0 && <div className="card p-3 text-[12.5px]"><div className="label mb-1">Where faults most likely start (correlation, not proof)</div>
          <ul className="space-y-0.5">{g.likely_roots.map(r => <li key={r.node}>
            <button className="text-accent-300 hover:underline" onClick={() => setSel(r.node)}>{r.name}</button>
            <span className="text-slate-400"> · {r.state.toLowerCase()}{r.also_failing_because_of_it.length ? ` · ${r.also_failing_because_of_it.length} dependent part(s) also failing` : ''}</span></li>)}</ul></div>}
        {groups.map(({ k, nodes }) => (
          <div key={k}><div className="label mb-1">{k.replace('_', ' ')}</div>
            <div className="flex flex-wrap gap-1.5">{nodes.map(n => (
              <button key={n.key} onClick={() => setSel(n.key)}
                className={`text-left rounded-lg border px-2.5 py-1.5 text-[12px] ${sel === n.key ? 'border-accent-400 bg-accent-500/10' : 'border-ink-600 hover:border-ink-500'}`}>
                <div className="flex items-center gap-1.5"><Chip tone={STATE_TONE[n.state] ?? 'idle'} dot>{n.state.toLowerCase()}</Chip>
                  <span className="text-slate-100">{n.name}</span></div>
                <div className="text-[10.5px] text-slate-500">{n.evidence}{n.needs.length ? ` · needs ${n.needs.length}` : ''}{n.needed_by.length ? ` · needed by ${n.needed_by.length}` : ''}</div>
              </button>))}</div></div>))}
      </div>
      <aside className="card p-3 space-y-2 h-fit lg:sticky lg:top-4">
        {!s && <p className="text-[12.5px] text-slate-400">Select a part to see what it needs, what needs it, and to simulate its failure.</p>}
        {s && <>
          <div className="flex items-center gap-2"><Chip tone={STATE_TONE[s.state] ?? 'idle'} dot>{s.state.toLowerCase()}</Chip><b className="text-white text-[13.5px]">{s.name}</b></div>
          <p className="text-[12px] text-slate-400">{s.detail || '-'} · evidence: <b>{s.evidence}</b></p>
          {s.control && <p className="text-[12px] text-amber-300">{s.control}</p>}
          {s.guidance && <p className="text-[12px] text-slate-300">What to check: {s.guidance}</p>}
          {s.physical && <p className="text-[12px] text-violet-300">Physical validation required: {s.physical}</p>}
          <div className="text-[12px]"><span className="text-slate-400">Needs: </span>{s.needs.length === 0 ? 'nothing' :
            s.needs.map(x => <button key={x.node} className="mr-2 text-accent-300 hover:underline" onClick={() => setSel(x.node)}>
              {by[x.node]?.name ?? x.node}{x.inferred ? ' (inferred)' : ''}</button>)}</div>
          <div className="text-[12px]"><span className="text-slate-400">Needed by: </span>{s.needed_by.length === 0 ? 'nothing' :
            s.needed_by.map(k => <button key={k} className="mr-2 text-accent-300 hover:underline" onClick={() => setSel(k)}>{by[k]?.name ?? k}</button>)}</div>
          <button className="btn-ghost btn-sm" disabled={busy} onClick={() => runWhatIf(s.key)}>What if this fails? (simulation)</button>
          {w && w.node === s.key && <div className="rounded-lg border border-violet-400/40 bg-violet-500/5 p-2 text-[12px] space-y-1">
            <b className="text-violet-300">{w.kind}</b>
            <div>{w.affected.length} part(s) would be affected: {w.affected.map(a => a.name).join(', ') || 'none'}</div>
            {w.expected_alerts.length > 0 && <div className="text-slate-300">Expected alerts: {w.expected_alerts.join('; ')}</div>}
            <div className="text-slate-400">Recovery order: {w.recovery_order.map(k => by[k]?.name ?? k).join(' → ')}</div>
            <div className="text-slate-500">{w.note}</div></div>}
        </>}
      </aside>
    </div>
  )
}

function Drift() {
  const [d, err, reload] = useLoad<DriftReport>(api.relDrift)
  const { user } = useAuth()
  const accept = async (id: string) => {
    const reason = prompt('Why is this deviation accepted? (kept visible; the baseline is not changed)')
    if (!reason || reason.trim().length < 5) return
    const days = prompt('Expires after how many days? (empty = no expiry)')
    await api.relDriftAccept(id, reason.trim(), days ? Number(days) : undefined)
    reload()
  }
  if (err) return <p className="text-bad-soft text-sm">{err}</p>
  if (!d) return <p className="text-slate-400 text-sm">Loading…</p>
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
        <Chip tone={d.compliant ? 'ok' : 'warn'}>{d.compliant ? 'matches the approved baseline' : `${d.findings.filter(f => !f.accepted).length} open difference(s)`}</Chip>
        <span className="text-slate-400">baseline {d.baseline_version} · checked {new Date(d.checked_at).toLocaleString()} · secrets are only checked for being set / not a published default - never shown</span>
        <button className="btn-ghost btn-sm ml-auto" onClick={reload}><RefreshCw size={13} /> Check again</button></div>
      {d.findings.length === 0 && <p className="text-[13px] text-emerald-300">No difference from the approved baseline.</p>}
      <div className="card divide-y divide-ink-700">{d.findings.map(f => (
        <div key={f.id} className="p-3 text-[12.5px] space-y-1">
          <div className="flex flex-wrap items-center gap-2"><Chip tone={f.severity === 'high' ? 'bad' : f.severity === 'medium' ? 'warn' : 'idle'}>{f.severity}</Chip>
            <Chip tone="idle">{f.class.toLowerCase()}</Chip><b className="text-slate-100">{f.component}</b>
            {f.accepted && <Chip tone="violet">accepted</Chip>}
            {user?.role === 'ADMIN' && !f.accepted && <button className="btn-ghost btn-sm ml-auto" onClick={() => accept(f.id)}>Accept deviation…</button>}</div>
          <div className="text-slate-300">expected <b>{String(f.expected)}</b> · actual <b>{String(f.actual)}</b> · {f.impact}</div>
          <div className="text-slate-400">Remediation (preview, nothing is changed automatically): {f.remediation}</div>
          {f.accepted && <div className="text-violet-300">Accepted by {f.accepted.owner}: {f.accepted.reason}{f.accepted.expires_at ? ` (until ${new Date(f.accepted.expires_at).toLocaleDateString()})` : ''}</div>}
        </div>))}</div>
      {d.history.length > 0 && <div className="text-[12px] text-slate-400"><div className="label mb-1">Changes in the findings</div>
        {d.history.slice().reverse().map(h => <div key={h.at}>{new Date(h.at).toLocaleString()}: {h.ids.length ? h.ids.join(', ') : 'none'}</div>)}</div>}
    </div>
  )
}

function Performance() {
  const [p, err, reload] = useLoad<PerfReport>(api.relPerformance)
  const { user } = useAuth()
  if (err) return <p className="text-bad-soft text-sm">{err}</p>
  if (!p) return <p className="text-slate-400 text-sm">Loading…</p>
  const s = p.summary
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Requests measured" value={s.requests} hint={`since ${fmtS(s.since_s)} (this backend process)`} />
        <MetricCard label="p50" value={s.p50 ?? '-'} suffix=" ms" animate={false} />
        <MetricCard label="p95" value={s.p95 ?? '-'} suffix=" ms" animate={false} />
        <MetricCard label="DB pool in use" value={`${p.db_pool.checked_out}/${p.db_pool.size + Math.max(0, p.db_pool.overflow)}`} animate={false} />
      </div>
      <div className="card p-3"><div className="label mb-1">Service objectives</div>
        {p.objectives.map(o => <div key={o.key} className="text-[12.5px] flex flex-wrap gap-2 items-center">
          <Chip tone={o.met == null ? 'idle' : o.met ? 'ok' : 'bad'}>{o.met == null ? 'no data' : o.met ? 'met' : 'missed'}</Chip>
          <span className="text-slate-200">{o.objective}</span>
          <span className="text-slate-400">· {o.samples} samples over {fmtS(o.window_s)}{o.measured_p95_ms != null ? ` · p95 ${o.measured_p95_ms} ms` : ''}
            {o.error_budget_used != null ? ` · error budget used ${Math.round(o.error_budget_used * 100)} %` : ''}</span></div>)}</div>
      <div className="card p-3"><div className="flex items-center gap-2"><span className="label">Regressions (last 5 min vs the hour before)</span>
        <button className="btn-ghost btn-sm ml-auto" onClick={reload}><RefreshCw size={13} /> Refresh</button>
        {user?.role === 'ADMIN' && <button className="btn-ghost btn-sm" onClick={async () => { await api.relBaseline(); reload() }}>Capture baseline</button>}</div>
        {p.regressions.length === 0 ? <p className="text-[12.5px] text-slate-400">None (needs at least 20 samples in both windows).</p> :
          p.regressions.map(r => <div key={r.route} className="text-[12.5px] text-amber-300">{r.route}: p95 {r.baseline_p95} → {r.current_p95} ms ({r.change_pct > 0 ? '+' : ''}{r.change_pct} %) · {r.note}</div>)}
        {p.baseline.captured_at && <p className="text-[11.5px] text-slate-500 mt-1">Saved baseline {new Date(p.baseline.captured_at).toLocaleString()} ({p.baseline.note}):
          {p.baseline.compare.filter(c => Math.abs(c.change_pct) >= 25).map(c => ` ${c.route} ${c.change_pct > 0 ? '+' : ''}${c.change_pct} %`).join(';') || ' no route changed by 25 % or more'}</p>}</div>
      <div className="card overflow-x-auto"><table className="w-full text-[12px]"><thead className="text-slate-400"><tr>
        <th className="text-left p-2">Route</th><th className="p-2">n</th><th className="p-2">p50</th><th className="p-2">p95</th><th className="p-2">p99</th><th className="p-2">5xx</th></tr></thead>
        <tbody>{s.routes.map(r => <tr key={r.route} className="border-t border-ink-700"><td className="p-2 mono">{r.route}</td>
          <td className="p-2 text-center">{r.n}</td><td className="p-2 text-center">{r.p50}</td><td className="p-2 text-center">{r.p95}</td>
          <td className="p-2 text-center">{r.p99 ?? '-'}</td><td className="p-2 text-center">{r.errors_5xx}</td></tr>)}</tbody></table></div>
    </div>
  )
}

function Quality() {
  const [q, err] = useLoad<AlertQuality>(() => api.incidentQuality(30))
  if (err) return <p className="text-bad-soft text-sm">{err}</p>
  if (!q) return <p className="text-slate-400 text-sm">Loading…</p>
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Incidents (30 days)" value={q.incidents} hint={`${q.reports} reports in total`} />
        <MetricCard label="Absorbed by grouping" value={`${Math.round(q.grouped_share * 100)} %`} animate={false} hint="reports that did not become a new row" />
        <MetricCard label="Time to acknowledge" value={fmtS(q.time_to_acknowledge_s_median)} animate={false} hint="median" />
        <MetricCard label="Came back after resolution" value={q.reopened_incidents} />
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        <div className="card p-3"><div className="label mb-1">Most repeated conditions</div>
          {q.top_conditions.map(c => <div key={c.fingerprint} className="text-[12.5px] text-slate-300">{c.title} · {c.reports} reports in {c.rows} incident(s){c.reopened ? `, back ${c.reopened}×` : ''}</div>)}</div>
        <div className="card p-3"><div className="label mb-1">Noisiest devices</div>
          {q.noisy_devices.map(n => <div key={String(n.device_id)} className="text-[12.5px] text-slate-300">{n.device ?? 'portal'} · {n.reports} reports</div>)}
          {q.storms.length > 0 && <><div className="label mt-2 mb-1">Alert storms (≥ 5 new incidents in one minute)</div>
            {q.storms.map(s => <div key={s.minute} className="text-[12.5px] text-amber-300">{s.minute}: {s.new_incidents}</div>)}</>}</div>
      </div>
      <p className="text-[11.5px] text-slate-500">Repeat rows ({q.repeat_rows}) are incidents of a condition that already had one in the period - from before grouping existed, or new episodes after the 30-minute reopen window. Time to resolve (median): by staff {fmtS(q.time_to_resolve_s_median.by_staff)}, condition cleared by itself {fmtS(q.time_to_resolve_s_median.condition_cleared)}.</p>
    </div>
  )
}

function Backups() {
  const [b, err] = useLoad(api.relBackups)
  const [c] = useLoad(api.relCapacity)
  if (err) return <p className="text-bad-soft text-sm">{err}</p>
  if (!b) return <p className="text-slate-400 text-sm">Loading…</p>
  const bk = b.backup as Record<string, string | number | null>
  const rd = b.restore_drill as Record<string, string | number | boolean | null> | null
  return (
    <div className="space-y-3">
      <div className="grid md:grid-cols-2 gap-3">
        <div className="card p-3 text-[12.5px] space-y-1"><div className="label">Last backup</div>
          <Chip tone={bk.state === 'OK' ? 'ok' : 'warn'}>{String(bk.state ?? '?').toLowerCase()}</Chip>
          <div className="text-slate-300">{String(bk.file ?? '-')} · {String(bk.size_kb ?? '-')} KB · every {String(bk.every_hours ?? '?')} h · last success {bk.last_success ? new Date(String(bk.last_success)).toLocaleString() : '-'}</div>
          <div className="text-slate-500">Each dump is checked with pg_restore --list before it counts as a success.</div></div>
        <div className="card p-3 text-[12.5px] space-y-1"><div className="label">Last verified restore (isolated database)</div>
          {!rd ? <p className="text-slate-400">No drill recorded yet. {b.how}</p> : <>
            <Chip tone={rd.ok ? 'ok' : 'bad'}>{rd.ok ? 'restore verified' : 'drill failed'}</Chip>
            <div className="text-slate-300">{rd.at ? new Date(String(rd.at)).toLocaleString() : '-'} · restore {String(rd.restore_s)} s · {String(rd.tables)} tables · {String(rd.rows)} rows · {String(rd.count_mismatches)} live table(s) changed meanwhile</div>
            <div className="text-slate-500">{b.how}</div></>}</div>
      </div>
      {c && <div className="card p-3 text-[12.5px] space-y-1"><div className="label">Capacity</div>
        {c.disk && <div className="text-slate-300">Disk: {c.disk.free_gb} GB free of {c.disk.total_gb} GB ({c.disk.used_pct} % used) - {c.disk.where}</div>}
        <div className="text-slate-300">Database: {c.database_mb} MB · largest: {c.largest_tables.map(t => `${t.table} ${t.mb} MB`).join(', ')}</div>
        <div className="text-slate-500">{c.retention}</div>
        {c.warnings.map(w => <div key={w} className="text-amber-300">{w}</div>)}</div>}
    </div>
  )
}

function Policy() {
  const [p, err] = useLoad(api.relPolicy)
  if (err) return <p className="text-bad-soft text-sm">{err}</p>
  if (!p) return <p className="text-slate-400 text-sm">Loading…</p>
  const tone = (r: string): 'ok' | 'warn' | 'bad' | 'idle' => r.startsWith('ALLOWED') ? 'ok' : r === 'REQUIRES APPROVAL' ? 'warn' : r === 'PROHIBITED' ? 'bad' : 'idle'
  return (
    <div className="space-y-2">
      <p className="text-[12.5px] text-slate-400 flex items-center gap-1.5"><BookOpen size={14} /> Every automated or requested action is checked against this table. Robot motion, door logic, firmware, safety settings and production data are never automatic. The software STOP is not a safety-rated emergency stop.</p>
      <div className="card overflow-x-auto"><table className="w-full text-[12px]"><thead className="text-slate-400"><tr>
        <th className="text-left p-2">Action</th><th className="p-2">Automatically</th><th className="p-2">When a person asks</th><th className="p-2">Role</th><th className="text-left p-2">Why</th></tr></thead>
        <tbody>{p.rules.map(r => <tr key={r.action} className="border-t border-ink-700"><td className="p-2 mono">{r.action}</td>
          <td className="p-2 text-center"><Chip tone={tone(r.automatic)}>{r.automatic.toLowerCase()}</Chip></td>
          <td className="p-2 text-center"><Chip tone={tone(r.on_request)}>{r.on_request.toLowerCase()}</Chip></td>
          <td className="p-2 text-center">{r.role}</td><td className="p-2 text-slate-400">{r.why}</td></tr>)}</tbody></table></div>
    </div>
  )
}
