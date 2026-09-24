import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Boxes, Plus, Search, TriangleAlert, Wrench } from 'lucide-react'
import { Asset, Lab, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { assetStatusLabel, assetTone } from '../lib/labels'
import {
  Chip, EmptyState, ErrorBanner, Field, MetricCard, Modal, PageHeader, Select, Skeleton,
} from '../components/ui'

export default function Equipment() {
  const [rows, setRows] = useState<Asset[] | null>(null)
  const [labs, setLabs] = useState<Lab[]>([])
  const [q, setQ] = useState('')
  const [lab, setLab] = useState('')
  const [status, setStatus] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => api.assets().then(setRows)
    .catch(e => { setError(e.message); setRows([]) }), [])
  useEffect(() => { load(); api.labs().then(setLabs).catch(() => {}) }, [load])
  useLiveMessages(m => {
    if ((m.type === 'access_event' && m.event.event_type.startsWith('ASSET')) ||
        (m.type === 'staff' && m.kind === 'issue')) load()
  })

  const list = useMemo(() => (rows ?? []).filter(a =>
    (!lab || String(a.lab_id) === lab) && (!status || a.status === status) &&
    (!q || `${a.name} ${a.asset_tag} ${a.category} ${a.lab_code}`.toLowerCase().includes(q.toLowerCase()))),
  [rows, lab, status, q])

  async function act(fn: () => Promise<unknown>) {
    setError('')
    try { await fn(); load() } catch (e) { setError(e instanceof Error ? e.message : 'Action failed') }
  }

  const count = (s: string) => (rows ?? []).filter(a => a.status === s).length

  return (
    <div>
      <PageHeader eyebrow="Assets" title="Equipment"
        sub="Every registered instrument, machine and device, with its status and maintenance record."
        actions={<button className="btn-primary" onClick={() => setAdding(true)}><Plus size={16} />Add equipment</button>} />
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <MetricCard label="Registered" value={rows ? rows.length : null} icon={<Boxes size={15} />} />
        <MetricCard label="Available" value={rows ? count('AVAILABLE') : null} tone="ok" />
        <MetricCard label="Checked out" value={rows ? count('CHECKED_OUT') : null} tone="info" />
        <MetricCard label="In maintenance" value={rows ? count('MAINTENANCE') : null}
                    tone={rows && count('MAINTENANCE') ? 'warn' : 'idle'} />
      </div>

      <div className="card p-4 mb-4 grid sm:grid-cols-3 gap-3">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input pl-9" placeholder="Name, tag or category" value={q}
                 onChange={e => setQ(e.target.value)} aria-label="Search equipment" />
        </div>
        <Select value={lab} onChange={setLab}
                options={[['', 'All laboratories'], ...labs.map(l => [String(l.id), `${l.code} · ${l.name}`] as [string, string])]} />
        <Select value={status} onChange={setStatus}
                options={[['', 'Any status'], ...['AVAILABLE', 'CHECKED_OUT', 'MAINTENANCE', 'RETIRED']
                  .map(s => [s, assetStatusLabel(s)] as [string, string])]} />
      </div>

      <div className="card overflow-hidden">
        {rows === null ? <div className="p-4"><Skeleton className="h-60" /></div>
          : list.length === 0 ? <EmptyState icon={<Boxes size={20} />} title="No equipment matches" />
          : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px]">
                <thead><tr>
                  <th className="th">Equipment</th><th className="th">Tag</th><th className="th">Laboratory</th>
                  <th className="th">Category</th><th className="th">Status</th><th className="th">Issues</th>
                  <th className="th"></th>
                </tr></thead>
                <tbody>
                  {list.map(a => (
                    <tr key={a.id} className="tr">
                      <td className="td"><Link to={`/equipment/${a.id}`} className="text-slate-100 hover:text-accent-200">{a.name}</Link></td>
                      <td className="td mono text-slate-300">{a.asset_tag}</td>
                      <td className="td mono text-slate-300">{a.lab_code}</td>
                      <td className="td text-slate-300">{a.category || '—'}</td>
                      <td className="td"><Chip tone={assetTone(a.status)}>{assetStatusLabel(a.status)}</Chip></td>
                      <td className="td">{a.open_issues > 0
                        ? <span className="inline-flex items-center gap-1 text-warn-soft text-[12.5px]"><TriangleAlert size={13} />{a.open_issues} open</span>
                        : <span className="text-slate-600">—</span>}</td>
                      <td className="td text-right whitespace-nowrap space-x-3">
                        {a.status === 'AVAILABLE' && <button className="text-xs link" onClick={() => act(() => api.checkoutAsset(a.id))}>Check out</button>}
                        {a.status === 'CHECKED_OUT' && <button className="text-xs link" onClick={() => act(() => api.returnAsset(a.id))}>Return</button>}
                        <Link to={`/issues/new?lab=${a.lab_id}&asset=${a.id}`} className="text-xs text-slate-300 hover:text-white inline-flex items-center gap-1">
                          <Wrench size={12} />Report</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>
      {adding && <AddAsset labs={labs} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); load() }} />}
    </div>
  )
}

function AddAsset({ labs, onClose, onSaved }: { labs: Lab[]; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ asset_tag: '', name: '', category: '', lab_id: '', notes: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try { await api.createAsset({ ...f, lab_id: Number(f.lab_id) }); onSaved() }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed') } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title="Add equipment">
      <form onSubmit={save} className="space-y-3">
        {error && <ErrorBanner message={error} />}
        <Field label="Laboratory"><select className="input" required value={f.lab_id}
          onChange={e => setF({ ...f, lab_id: e.target.value })}>
          <option value="">Choose…</option>
          {labs.map(l => <option key={l.id} value={l.id}>{l.code} · {l.name}</option>)}</select></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Asset tag" hint="Unique, e.g. ROB-UR5E-001"><input className="input" required value={f.asset_tag}
            onChange={e => setF({ ...f, asset_tag: e.target.value })} /></Field>
          <Field label="Category"><input className="input" value={f.category} placeholder="Instrument"
            onChange={e => setF({ ...f, category: e.target.value })} /></Field>
        </div>
        <Field label="Name"><input className="input" required value={f.name}
          onChange={e => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Notes (optional)"><textarea className="input" value={f.notes}
          onChange={e => setF({ ...f, notes: e.target.value })} /></Field>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Add equipment'}</button>
        </div>
      </form>
    </Modal>
  )
}
