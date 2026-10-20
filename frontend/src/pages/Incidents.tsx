/**
 * Incidents: the portal's alerts handled as incidents (acknowledge, owner, notes, recovery,
 * resolve with a reason, reopen). Related records are shown BY TIME ONLY; an AI hypothesis is
 * labelled as such. Nothing here controls a door, robot, PLC or alarm.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Repeat, Search, Siren, X } from 'lucide-react'
import { Investigation, api } from '../lib/api'
import { relative } from '../lib/time'
import { Chip, PageHeader } from '../components/ui'

type List = Awaited<ReturnType<typeof api.incidents>>
type Detail = Awaited<ReturnType<typeof api.incident>>
const STATE_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle' | 'violet'> = { OPEN: 'bad', ACKNOWLEDGED: 'warn', INVESTIGATING: 'violet', MITIGATED: 'idle', RESOLVED: 'ok' }
const CONF_TONE: Record<string, 'ok' | 'warn' | 'idle'> = { high: 'ok', medium: 'warn', low: 'idle' }
const POLICY_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle'> = { 'ALLOWED AUTOMATICALLY': 'ok', 'REQUIRES APPROVAL': 'warn',
  'DRY RUN ONLY': 'idle', PROHIBITED: 'bad', 'INSUFFICIENT EVIDENCE': 'idle' }
const PROV: Record<string, string> = { SOFTWARE_TEST: 'software test', UNKNOWN_PROVENANCE: 'unknown origin', BENCH_TEST: 'bench test',
  PHYSICAL_TEST: 'physical test', DEMO_DATA: 'demo data', REAL_OPERATION: 'real operation' }
/** Same kind of incident: numbers and ids removed from the title, plus the device. Display only - nothing is merged. */
const groupKey = (i: { title: string; device: string | null }) => i.title.replace(/(PC[-_])?\d+(\.\d+)?/g, '#') + '|' + (i.device ?? '')
const SEV_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle'> = { CRITICAL: 'bad', WARNING: 'warn', INFO: 'idle' }

export default function Incidents() {
  const [state, setState] = useState('ACTIVE')
  const [severity, setSeverity] = useState('')
  const [q, setQ] = useState('')
  const [grouped, setGrouped] = useState(true)
  const [list, setList] = useState<List | null>(null)
  const [params] = useSearchParams()
  const [open, setOpen] = useState<number | null>(params.get('open') ? Number(params.get('open')) : null)
  const [error, setError] = useState('')
  const load = useCallback(() => {
    api.incidents({ state, severity, q }).then(setList).catch(e => setError(e.message))
  }, [state, severity, q])
  useEffect(() => { const t = window.setTimeout(load, q ? 300 : 0); return () => window.clearTimeout(t) }, [load, q])
  useEffect(() => { const t = window.setInterval(load, 20000); return () => window.clearInterval(t) }, [load])
  const groups = useMemo(() => {
    const m = new Map<string, NonNullable<typeof list>['incidents']>()
    for (const i of list?.incidents ?? []) { const k = groupKey(i); m.set(k, [...(m.get(k) ?? []), i]) }
    return [...m.values()]
  }, [list])
  const rows = grouped ? groups.map(g => ({ ...g[0], similar: g.length, oldest: g[g.length - 1].created_at })) :
    (list?.incidents ?? []).map(i => ({ ...i, similar: 1, oldest: i.created_at }))
  return (
    <div>
      <PageHeader eyebrow="Operations" title="Incidents"
        sub="Every alert as an incident: acknowledge, assign, record what was done, close with a reason. A condition that repeats is ONE incident with a count; the original events stay in their own records." />
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <select className="input !py-1.5 w-auto" value={state} onChange={e => setState(e.target.value)}>
          <option value="ACTIVE">Active (not resolved)</option><option value="">All</option>
          {['OPEN', 'ACKNOWLEDGED', 'INVESTIGATING', 'MITIGATED', 'RESOLVED'].map(s => <option key={s} value={s}>{s.toLowerCase()}</option>)}</select>
        <select className="input !py-1.5 w-auto" value={severity} onChange={e => setSeverity(e.target.value)}>
          <option value="">All severities</option>{['CRITICAL', 'WARNING', 'INFO'].map(s => <option key={s} value={s}>{s.toLowerCase()}</option>)}</select>
        <input className="input !py-1.5 w-56" placeholder="Search title or detail" value={q} onChange={e => setQ(e.target.value)} />
        <label className="flex items-center gap-1 text-[12.5px] text-slate-300"><input type="checkbox" checked={grouped} onChange={e => setGrouped(e.target.checked)} /> group similar</label>
        {list && <span className="text-[12px] text-slate-400">{list.incidents.length} shown{list.reports != null && list.reports > list.incidents.length ? ` (${list.reports} reports grouped)` : ''} · {list.counts.OPEN} open · {list.counts.ACKNOWLEDGED + list.counts.INVESTIGATING + (list.counts.MITIGATED ?? 0)} in progress
          {list.escalations > 0 && <b className="text-bad-soft"> · {list.escalations} need escalation</b>}</span>}
        <Link to="/admin/reliability?tab=quality" className="ml-auto text-[12px] text-accent-300 hover:underline">Alert quality</Link>
      </div>
      {error && <p className="text-[12px] text-bad-soft mb-2">{error}</p>}
      <div className="card divide-y divide-ink-700">
        {list?.incidents.length === 0 && <p className="p-4 text-[13px] text-slate-400">No incidents match.</p>}
        {rows.map(i => (
          <button key={i.id} type="button" onClick={() => setOpen(i.id)} className="w-full text-left px-4 py-2.5 flex flex-wrap items-center gap-2 hover:bg-ink-800/60">
            <span className="mono text-[12px] text-slate-400 w-24">{i.code}</span>
            <Chip tone={SEV_TONE[i.severity] ?? 'idle'}>{i.severity.toLowerCase()}</Chip>
            <Chip tone={STATE_TONE[i.state] ?? 'idle'} dot>{i.state.toLowerCase()}</Chip>
            {i.escalate && <span title={i.escalation_reason ?? ''}><Chip tone="bad">escalate</Chip></span>}
            <b className="text-slate-100 text-[13px]">{i.title}</b>
            {(i.occurrences ?? 1) > 1 && <span title={`last seen ${i.last_seen_at ? new Date(i.last_seen_at).toLocaleString() : '?'}`}>
              <Chip tone="warn">×{i.occurrences}</Chip></span>}
            {(i.reopened_count ?? 0) > 0 && <Chip tone="violet"><Repeat size={10} /> back {i.reopened_count}×</Chip>}
            {i.similar > 1 && <Chip tone="violet">{i.similar} similar since {new Date(i.oldest).toLocaleDateString()}</Chip>}
            {i.provenance && i.provenance !== 'REAL_OPERATION' && <span className="text-[11px] text-slate-500">({PROV[i.provenance] ?? i.provenance})</span>}
            <span className="text-[12px] text-slate-400">{i.lab ?? ''}{i.device ? ` · ${i.device}` : ''}</span>
            <span className="ml-auto text-[12px] text-slate-500">{i.owner ? `${i.owner} · ` : ''}{relative(i.created_at)}
              {(i.occurrences ?? 1) > 1 && i.last_seen_at ? ` · last ${relative(i.last_seen_at)}` : ''}</span>
          </button>))}
      </div>
      {open != null && <IncidentDrawer id={open} onClose={() => setOpen(null)} onChange={load} />}
    </div>
  )
}

function IncidentDrawer({ id, onClose, onChange }: { id: number; onClose: () => void; onChange: () => void }) {
  const [d, setD] = useState<Detail | null>(null)
  const [staff, setStaff] = useState<{ id: number; full_name: string }[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [inv, setInv] = useState<Investigation | null>(null)
  const [invBusy, setInvBusy] = useState(false)
  useEffect(() => { api.incident(id).then(setD).catch(e => setError(e.message)) }, [id])
  const investigate = async () => {
    setInvBusy(true)
    try { setInv(await api.investigate(id)) } catch (e) { setError(e instanceof Error ? e.message : 'Failed') } finally { setInvBusy(false) }
  }
  useEffect(() => { api.users().then(u => setStaff(u.filter(x => x.role !== 'STUDENT' && x.is_active))).catch(() => {}) }, [])
  const act = async (action: string, extra: Record<string, unknown> = {}) => {
    if (busy) return
    setBusy(true); setError('')
    try { setD(await api.incidentAction(id, { action, text, ...extra })); setText(''); onChange() }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed') } finally { setBusy(false) }
  }
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex justify-end" onClick={onClose}>
      <aside className="w-full max-w-2xl h-full overflow-auto bg-ink-900 border-l border-ink-600 p-5 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2"><Siren size={18} className="text-accent-300" />
          <h2 className="text-white font-semibold">{d?.code} · {d?.title}</h2>
          <button className="btn-ghost btn-sm ml-auto" onClick={onClose}><X size={14} /></button></div>
        {d && <>
          <div className="flex flex-wrap gap-2">
            <Chip tone={SEV_TONE[d.severity] ?? 'idle'}>{d.severity.toLowerCase()}</Chip>
            <Chip tone={STATE_TONE[d.state] ?? 'idle'} dot>{d.state.toLowerCase()}</Chip>
            <span className="text-[12px] text-slate-400">source: {d.source}{d.device ? ` (${d.device})` : ''} · {d.lab ?? 'no lab'} · owner: {d.owner ?? 'nobody'}</span>
          </div>
          {((d.occurrences ?? 1) > 1 || (d.reopened_count ?? 0) > 0 || d.escalation_reason) && (
            <p className="text-[12px] text-slate-300">
              {(d.occurrences ?? 1) > 1 && <>Reported <b>{d.occurrences}×</b> since {new Date(d.created_at).toLocaleString()} (last {d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : '?'}). </>}
              {(d.reopened_count ?? 0) > 0 && <>Came back <b>{d.reopened_count}×</b> after being resolved. </>}
              {d.escalation_reason && <b className="text-bad-soft">Escalate: {d.escalation_reason}.</b>}</p>)}
          <div className="card p-3"><div className="label mb-1">Confirmed facts</div>
            <ul className="text-[12.5px] text-slate-200 list-disc pl-5 space-y-0.5">{d.facts.map((f, i) => <li key={i}>{f}</li>)}</ul>
            {d.resolution && <p className="text-[12.5px] text-emerald-300 mt-2">Resolution: {d.resolution}</p>}</div>
          <div className="space-y-2">
            <textarea className="input w-full !text-[13px]" rows={2} placeholder="Note, recovery action, or closure reason…" value={text} maxLength={2000} onChange={e => setText(e.target.value)} />
            <div className="flex flex-wrap gap-1.5">
              {d.state === 'OPEN' && <button className="btn-ghost btn-sm" disabled={busy} onClick={() => act('acknowledge')}>Acknowledge</button>}
              {d.state !== 'RESOLVED' && d.state !== 'INVESTIGATING' && d.state !== 'MITIGATED' && <button className="btn-ghost btn-sm" disabled={busy} onClick={() => act('investigate')}>Start investigating</button>}
              {d.state !== 'RESOLVED' && d.state !== 'MITIGATED' && <button className="btn-ghost btn-sm" disabled={busy || text.trim().length < 5}
                title="Impact limited (e.g. a workaround) - still open until the cause is resolved" onClick={() => act('mitigate')}>Mitigated (what was done above)</button>}
              <button className="btn-ghost btn-sm" disabled={busy || !text.trim()} onClick={() => act('note')}>Add note</button>
              <button className="btn-ghost btn-sm" disabled={busy || !text.trim()} onClick={() => act('recovery')}>Log recovery action</button>
              <button className="btn-ghost btn-sm" disabled={busy || !text.trim()} onClick={() => act('ai_hypothesis')} title="Stored and shown as a hypothesis, never as a fact">Add as AI hypothesis</button>
              {d.state !== 'RESOLVED'
                ? <button className="btn-primary btn-sm" disabled={busy || text.trim().length < 5} onClick={() => act('resolve')}>Resolve (reason above)</button>
                : <button className="btn-ghost btn-sm" disabled={busy} onClick={() => act('reopen')}>Reopen</button>}
              <select className="input !py-1 !text-[12px] w-auto" value="" onChange={e => e.target.value && act('assign', { owner_id: +e.target.value })}>
                <option value="">Assign owner…</option>{staff.map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}</select>
            </div>
            {error && <p className="text-[12px] text-bad-soft">{error}</p>}
          </div>
          <div className="card p-3 space-y-2">
            <div className="flex items-center gap-2"><Search size={14} className="text-accent-300" />
              <span className="label">Investigation</span>
              <button className="btn-ghost btn-sm ml-auto" disabled={invBusy} onClick={investigate}>{invBusy ? 'Checking…' : inv ? 'Again' : 'Investigate'}</button></div>
            {!inv && <p className="text-[12px] text-slate-500">Ranks explanations from the records (other devices failing at the same time, what this one depends on, portal restarts, repeats). Correlation, not proof.</p>}
            {inv && <>
              <p className="text-[11.5px] text-slate-500">{inv.statement} Earliest related warning: {new Date(inv.earliest_warning).toLocaleString()}.</p>
              <ol className="space-y-2">{inv.hypotheses.map(h => <li key={h.id} className="rounded-lg border border-ink-600 p-2 text-[12.5px]">
                <div className="flex flex-wrap items-center gap-2"><Chip tone={CONF_TONE[h.confidence] ?? 'idle'}>{h.confidence}</Chip><b className="text-slate-100">{h.title}</b></div>
                {h.supporting.length > 0 && <ul className="mt-1 text-emerald-300/90 list-disc pl-5">{h.supporting.map((x, k) => <li key={k}>{x}</li>)}</ul>}
                {h.contradicting.length > 0 && <ul className="mt-1 text-amber-300/90 list-disc pl-5">{h.contradicting.map((x, k) => <li key={k}>against: {x}</li>)}</ul>}
                <div className="mt-1 text-slate-400">To tell apart: {h.checks.join(' · ')}</div></li>)}</ol>
              {inv.affected_components.length > 0 && <p className="text-[12px] text-slate-300">Depends on this: {inv.affected_components.map(c => `${c.name} (${c.state.toLowerCase()})`).join(', ')}</p>}
              <div className="flex flex-wrap gap-1.5">{inv.suggestions.map(sg => <span key={sg.action} className="text-[11.5px] rounded border border-ink-600 px-2 py-1 text-slate-300">
                {sg.text} <Chip tone={POLICY_TONE[sg.policy.result] ?? 'idle'}>{sg.policy.result.toLowerCase()}</Chip></span>)}</div>
              <p className="text-[11px] text-slate-500">Unknown: {inv.unknowns.join('; ')}.</p></>}
          </div>
          <div><div className="label mb-1">Activity</div>
            {d.notes.length === 0 && <p className="text-[12px] text-slate-500">No activity yet.</p>}
            <ul className="space-y-1.5">{d.notes.map(n => <li key={n.id} className={`text-[12.5px] rounded p-2 ${n.kind === 'AI_HYPOTHESIS' ? 'bg-violet-500/10 border border-violet-400/30' : 'bg-ink-800/60'}`}>
              <span className="text-slate-400">{new Date(n.at).toLocaleString()} · {n.by ?? 'system'} · {n.kind.toLowerCase().replace('_', ' ')}</span>
              {n.label && <b className="text-violet-300"> · {n.label}</b>}<div className="text-slate-200">{n.text}</div></li>)}</ul></div>
          <div><div className="label mb-1">Related records (same lab, ±10 min)</div>
            <p className="text-[11.5px] text-slate-500 mb-1">{d.related_note}</p>
            {d.related.length === 0 && <p className="text-[12px] text-slate-500">None.</p>}
            <ul className="space-y-1">{d.related.map(r => <li key={r.ref} className="text-[12px] text-slate-300 flex flex-wrap gap-2">
              <span className="mono text-slate-500">{new Date(r.time).toLocaleTimeString()}</span><Chip tone="idle">{r.source}</Chip>
              <b>{r.kind}</b><span>{r.summary}</span>{r.person && <span className="text-slate-400">· {r.person} (from the record)</span>}
              <span className="mono text-[11px] text-slate-500 ml-auto">{r.ref}</span></li>)}</ul></div>
        </>}
      </aside>
    </div>
  )
}
