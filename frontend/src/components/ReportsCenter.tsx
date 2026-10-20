/**
 * Reports Centre: per-subsystem exports (CSV, print/PDF) with their source table and warnings,
 * the cross-system timeline (co-occurrence = timing only), and inventory discrepancies.
 * Everything is a recorded row; "no records" is shown as missing data, never as zero.
 */
import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Download, Printer, RefreshCw } from 'lucide-react'
import { api, fetchBlob } from '../lib/api'
import { Chip, SectionTitle, Tabs } from './ui'

type Tab = 'exports' | 'timeline' | 'inventory' | 'assets'
type Report = Awaited<ReturnType<typeof api.reportCenter>>
type Timeline = Awaited<ReturnType<typeof api.reportTimeline>>
type Disc = Awaited<ReturnType<typeof api.inventoryDiscrepancies>>

const today = () => new Date().toISOString().slice(0, 10)
const ago = (d: number) => new Date(Date.now() - d * 86400000).toISOString().slice(0, 10)
const fmt = (v: unknown) => v == null ? '' : typeof v === 'string' && /^\d{4}-\d\d-\d\dT/.test(v)
  ? new Date(v).toLocaleString() : String(v)
const esc = (s: string) => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))

function printReport(r: Report) {
  const w = window.open('', '_blank')
  if (!w) return
  const head = r.columns.map(c => `<th>${esc(c)}</th>`).join('')
  const body = r.rows.map(row => `<tr>${r.columns.map(c => `<td>${esc(fmt(row[c]))}</td>`).join('')}</tr>`).join('')
  w.document.write(`<!doctype html><title>${esc(r.title)}</title><style>body{font:11px Arial;margin:18px}
    table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:3px 5px;text-align:left}th{background:#e0f2fe}
    .w{color:#b45309}</style><h2>${esc(r.title)}</h2>
    <p>Source table: <b>${esc(r.source)}</b> · ${esc(fmt(r.start))} - ${esc(fmt(r.end))} · generated ${esc(fmt(r.generated_at))} · ${r.count} rows</p>
    <p>${esc(r.description)}</p>${r.warnings.map(x => `<p class="w">Warning: ${esc(x)}</p>`).join('')}
    <table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`)
  w.document.close()
  w.focus()
  w.print()
}

export default function ReportsCenter() {
  const [tab, setTab] = useState<Tab>('exports')
  return (
    <section className="mb-8">
      <SectionTitle sub="Exports from every subsystem with their source table, the cross-system timeline and stock discrepancies.">
        Reports Centre</SectionTitle>
      <Tabs id="reports-center" value={tab} onChange={setTab} tabs={[
        { key: 'exports', label: 'Data exports' }, { key: 'timeline', label: 'Cross-system timeline' },
        { key: 'inventory', label: 'Inventory discrepancies' }, { key: 'assets', label: 'Equipment lifecycle' }]} />
      <div className="mt-4">
        {tab === 'exports' && <Exports />}
        {tab === 'timeline' && <TimelineView />}
        {tab === 'inventory' && <Discrepancies />}
        {tab === 'assets' && <Lifecycle />}
      </div>
    </section>
  )
}

function Exports() {
  const [cat, setCat] = useState<{ kind: string; title: string; description: string; source: string }[]>([])
  const [kind, setKind] = useState('access')
  const [start, setStart] = useState(ago(7))
  const [end, setEnd] = useState(today())
  const [r, setR] = useState<Report | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api.reportCatalogue().then(setCat).catch(e => setError(e.message)) }, [])
  const load = async () => {
    if (busy) return
    setBusy(true); setError('')
    try { setR(await api.reportCenter(kind, start, end)) } catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy(false) }
  }
  const csv = async () => {
    try {
      const b = await fetchBlob(`/reports-center/${kind}?start=${start}&end=${end}&format=csv`)
      const a = document.createElement('a')
      a.href = URL.createObjectURL(b); a.download = `smartlab_${kind}_${start}_${end}.csv`; a.click()
      setTimeout(() => URL.revokeObjectURL(a.href), 2000)
    } catch (e) { setError(e instanceof Error ? e.message : 'Export failed') }
  }
  return (
    <div className="card p-4 space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-[12px] text-slate-400">Report<select className="input !py-1.5 block mt-1" value={kind} onChange={e => { setKind(e.target.value); setR(null) }}>
          {cat.map(c => <option key={c.kind} value={c.kind}>{c.title}</option>)}</select></label>
        <label className="text-[12px] text-slate-400">From<input type="date" className="input !py-1.5 block mt-1" value={start} max={end} onChange={e => setStart(e.target.value)} /></label>
        <label className="text-[12px] text-slate-400">To<input type="date" className="input !py-1.5 block mt-1" value={end} min={start} onChange={e => setEnd(e.target.value)} /></label>
        <button className="btn-primary btn-sm" disabled={busy} onClick={load}><RefreshCw size={13} /> {busy ? 'Loading…' : 'Show'}</button>
        <button className="btn-ghost btn-sm" onClick={csv}><Download size={13} /> CSV</button>
        <button className="btn-ghost btn-sm" disabled={!r} onClick={() => r && printReport(r)}><Printer size={13} /> Print / PDF</button>
      </div>
      <p className="text-[12px] text-slate-400">{cat.find(c => c.kind === kind)?.description} Source: <span className="mono">{cat.find(c => c.kind === kind)?.source}</span></p>
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}
      {r && <>
        {r.warnings.map(w => <p key={w} className="text-[12px] text-warn-soft flex gap-1.5"><AlertTriangle size={13} className="mt-0.5" />{w}</p>)}
        <p className="text-[12px] text-slate-400">{r.count} rows{r.truncated ? ' (truncated)' : ''} · generated {fmt(r.generated_at)}</p>
        {r.count > 0 && <div className="overflow-auto max-h-[420px] rounded-lg border border-ink-600">
          <table className="w-full text-[12px]"><thead className="sticky top-0 bg-ink-800"><tr>{r.columns.map(c => <th key={c} className="text-left px-2 py-1.5 text-slate-300">{c}</th>)}</tr></thead>
            <tbody>{r.rows.slice(0, 300).map((row, i) => <tr key={i} className="border-t border-ink-700">
              {r.columns.map(c => <td key={c} className="px-2 py-1 text-slate-200 whitespace-nowrap">{fmt(row[c])}</td>)}</tr>)}</tbody></table>
          {r.count > 300 && <p className="p-2 text-[11.5px] text-slate-500">Showing 300 of {r.count}; the CSV has all rows.</p>}
        </div>}
      </>}
    </div>
  )
}

const SRC_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle' | 'violet'> = {
  door: 'ok', camera: 'violet', robot: 'idle', alert: 'bad', environment: 'warn', pc: 'idle', 'pc-action': 'idle' }

function TimelineView() {
  const [days, setDays] = useState(2)
  const [src, setSrc] = useState('')
  const [t, setT] = useState<Timeline | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { setT(null); api.reportTimeline(days, src).then(setT).catch(e => setError(e.message)) }, [days, src])
  const groups = useMemo(() => new Set((t?.items ?? []).filter(i => i.group != null).map(i => i.group)).size, [t])
  return (
    <div className="card p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select className="input !py-1.5 w-auto" value={days} onChange={e => setDays(+e.target.value)}>
          {[1, 2, 7, 30].map(d => <option key={d} value={d}>Last {d} day{d > 1 ? 's' : ''}</option>)}</select>
        <select className="input !py-1.5 w-auto" value={src} onChange={e => setSrc(e.target.value)}>
          <option value="">All subsystems</option>
          {['door', 'camera', 'robot', 'alert', 'environment', 'pc', 'pc-action'].map(s => <option key={s} value={s}>{s}</option>)}</select>
        {t && <span className="text-[12px] text-slate-400">{t.count} records · {groups} co-occurring group{groups === 1 ? '' : 's'}</span>}
      </div>
      {t && <p className="text-[11.5px] text-slate-500">{t.note}</p>}
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}
      {t && t.count === 0 && <p className="text-[12.5px] text-slate-400">No records in this period.</p>}
      <ul className="space-y-1 max-h-[520px] overflow-auto">
        {t?.items.map(i => (
          <li key={i.ref} className={`flex flex-wrap items-center gap-2 text-[12.5px] px-2 py-1 rounded ${i.group != null ? 'border-l-2 border-accent-400/70 bg-accent-500/5' : ''}`}>
            <span className="mono text-slate-400 w-40 shrink-0">{new Date(i.time).toLocaleString()}</span>
            <Chip tone={SRC_TONE[i.source] ?? 'idle'}>{i.source}</Chip>
            {i.lab && <span className="mono text-slate-400">{i.lab}</span>}
            <b className="text-slate-100">{i.kind}</b>
            <span className="text-slate-300">{i.summary}</span>
            {i.person && <span className="text-slate-400">· {i.person}</span>}
            {i.group != null && <span className="text-[11px] text-accent-300">co-occurring #{i.group}</span>}
            <span className="ml-auto mono text-[11px] text-slate-500">{i.ref}</span>
          </li>))}
      </ul>
    </div>
  )
}

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle'> = { OK: 'ok', DISCREPANCY: 'bad', NO_BASELINE_COUNT: 'warn', NOT_CALIBRATED: 'idle' }

function Discrepancies() {
  const [d, setD] = useState<Disc | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { api.inventoryDiscrepancies().then(setD).catch(e => setError(e.message)) }, [])
  return (
    <div className="card p-4 space-y-3">
      {d && <p className="text-[12px] text-slate-400">{d.note}</p>}
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}
      {d && d.bins.length === 0 && <p className="text-[12.5px] text-slate-400">No active bins.</p>}
      {d && d.bins.length > 0 && <div className="overflow-auto rounded-lg border border-ink-600">
        <table className="w-full text-[12.5px]"><thead className="bg-ink-800 text-slate-300"><tr>
          {['Bin', 'Item', 'Status', 'Measured (scale)', 'Last count', 'Change since count', 'Expected', 'Difference', 'Unattributed withdrawals'].map(h => <th key={h} className="text-left px-2 py-1.5">{h}</th>)}</tr></thead>
          <tbody>{d.bins.map(b => <tr key={b.bin_id} className="border-t border-ink-700 text-slate-200">
            <td className="px-2 py-1 mono">{b.bin}</td><td className="px-2 py-1">{b.item}</td>
            <td className="px-2 py-1"><Chip tone={STATUS_TONE[b.status] ?? 'idle'}>{b.status.replaceAll('_', ' ').toLowerCase()}</Chip></td>
            <td className="px-2 py-1">{b.measured_qty ?? '-'}{b.measured_error ? ` ±${b.measured_error}` : ''}{b.last_measured_at ? <span className="text-slate-500"> · {new Date(b.last_measured_at).toLocaleString()}</span> : ''}</td>
            <td className="px-2 py-1">{b.last_count ?? 'never counted'}{b.last_count_at ? <span className="text-slate-500"> · {new Date(b.last_count_at).toLocaleDateString()}</span> : ''}</td>
            <td className="px-2 py-1">{b.net_since_count >= 0 ? '+' : ''}{b.net_since_count} ({b.transactions_since_count} tx)</td>
            <td className="px-2 py-1">{b.expected_qty ?? '-'}</td>
            <td className={`px-2 py-1 ${b.status === 'DISCREPANCY' ? 'text-bad-soft font-semibold' : ''}`}>{b.difference ?? '-'}</td>
            <td className="px-2 py-1">{b.unattributed_withdrawals}</td></tr>)}</tbody></table></div>}
      <p className="text-[11.5px] text-slate-500">To correct a bin, record a physical count in Lab Equipment → Consumables; the count is kept as an auditable transaction and becomes the new baseline.</p>
    </div>
  )
}

function Lifecycle() {
  const [d, setD] = useState<Awaited<ReturnType<typeof api.assetLifecycle>> | null>(null)
  const [only, setOnly] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api.assetLifecycle().then(setD).catch(e => setError(e.message)) }, [])
  const rows = (d?.assets ?? []).filter(a => !only || a.flags.length)
  const day = (v: string | null) => v ? new Date(v).toLocaleDateString() : '-'
  return (
    <div className="card p-4 space-y-3">
      {d && <div className="flex flex-wrap items-center gap-3 text-[12.5px]">
        <span className="text-slate-300">{d.count} assets · <b className={d.flagged ? 'text-warn-soft' : ''}>{d.flagged} need attention</b></span>
        <label className="flex items-center gap-1 text-slate-400"><input type="checkbox" checked={only} onChange={e => setOnly(e.target.checked)} /> only flagged</label>
      </div>}
      {d && <p className="text-[11.5px] text-slate-500">{d.note}</p>}
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}
      {d && <div className="overflow-auto rounded-lg border border-ink-600 max-h-[480px]">
        <table className="w-full text-[12.5px]"><thead className="bg-ink-800 text-slate-300 sticky top-0"><tr>
          {['Asset', 'Name', 'Lab', 'Status', 'Custodian', 'Checked out', 'Due back', 'Next maintenance', 'Faults', 'Last movement', 'Attention'].map(h =>
            <th key={h} className="text-left px-2 py-1.5 whitespace-nowrap">{h}</th>)}</tr></thead>
          <tbody>{rows.map(a => <tr key={a.id} className="border-t border-ink-700 text-slate-200">
            <td className="px-2 py-1 mono"><a className="text-accent-300" href={`/equipment/${a.id}`}>{a.asset_tag}</a></td>
            <td className="px-2 py-1">{a.name}</td><td className="px-2 py-1 mono">{a.lab ?? '-'}</td>
            <td className="px-2 py-1">{a.status.toLowerCase()}</td><td className="px-2 py-1">{a.holder ?? '-'}</td>
            <td className="px-2 py-1">{day(a.checked_out_at)}</td><td className="px-2 py-1">{day(a.due_back)}</td>
            <td className="px-2 py-1">{a.next_maintenance_at ? day(a.next_maintenance_at) : <span className="text-slate-500">not tracked</span>}</td>
            <td className="px-2 py-1">{a.open_issues || '-'}</td><td className="px-2 py-1">{day(a.last_movement)}</td>
            <td className="px-2 py-1">{a.flags.map(f => <Chip key={f} tone="warn">{f.toLowerCase()}</Chip>)}</td></tr>)}</tbody></table></div>}
    </div>
  )
}
