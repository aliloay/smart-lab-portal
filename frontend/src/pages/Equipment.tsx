import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Boxes, CalendarClock, Plus, Search, TriangleAlert, Wrench } from 'lucide-react'
import { Asset, Lab, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import NetworkedEquipment from '../components/NetworkedEquipment'
import AddEquipment from '../components/AddEquipment'
import RobotTwinPanels from '../components/robot/RobotTwinPanel'
import EnvironmentOverview from '../components/EnvironmentOverview'
import { ConsumableBins, ReusableItems } from './Inventory'
import { assetStatusLabel, assetTone } from '../lib/labels'
import { fmtDate } from '../lib/time'
import {
  Chip, EmptyState, ErrorBanner, Field, MetricCard, Modal, PageHeader, Select, Skeleton, Tabs,
} from '../components/ui'

function EquipmentRegister() {
  const [rows, setRows] = useState<Asset[] | null>(() => api.peek(() => api.assets()))
  const [labs, setLabs] = useState<Lab[]>(() => api.peek(() => api.labs()) ?? [])
  const [q, setQ] = useState('')
  const [lab, setLab] = useState('')
  const [status, setStatus] = useState('')
  const [dueOnly, setDueOnly] = useState(false)
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
    (!dueOnly || a.maintenance_due) &&
    (!q || `${a.name} ${a.asset_tag} ${a.category} ${a.lab_code}`.toLowerCase().includes(q.toLowerCase()))),
  [rows, lab, status, q, dueOnly])

  async function act(fn: () => Promise<unknown>) {
    setError('')
    try { await fn(); load() } catch (e) { setError(e instanceof Error ? e.message : 'Action failed') }
  }

  const count = (s: string) => (rows ?? []).filter(a => a.status === s).length

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-4">
        <p className="text-[13px] text-slate-400">Every registered instrument, machine and device, with its status
          and maintenance record.</p>
        <button className="btn-primary shrink-0" onClick={() => setAdding(true)}><Plus size={16} />Add equipment</button>
      </div>
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}


      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <MetricCard label="Registered" value={rows ? rows.length : null} icon={<Boxes size={15} />} />
        <MetricCard label="Available" value={rows ? count('AVAILABLE') : null} tone="ok" />
        <MetricCard label="Checked out" value={rows ? count('CHECKED_OUT') : null} tone="info" />
        <MetricCard label="In maintenance" value={rows ? count('MAINTENANCE') : null}
                    tone={rows && count('MAINTENANCE') ? 'warn' : 'idle'}
                    hint={rows ? `${rows.filter(a => a.maintenance_due).length} with maintenance overdue` : undefined} />
      </div>

      <div className="card p-4 mb-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
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
        <button onClick={() => setDueOnly(v => !v)} aria-pressed={dueOnly}
          className={`btn border ${dueOnly ? 'bg-bad/10 text-bad-soft border-bad/40'
            : 'border-ink-500 text-slate-300 hover:text-white bg-ink-800/40'}`}>
          <CalendarClock size={15} />Maintenance due</button>
      </div>

      <div className="card overflow-hidden">
        {rows === null ? <div className="p-4"><Skeleton className="h-60" /></div>
          : list.length === 0 ? <EmptyState icon={<Boxes size={20} />} title="No equipment matches" />
          : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px]">
                <thead><tr>
                  <th className="th">Equipment</th><th className="th">Laboratory</th>
                  <th className="th">Status</th><th className="th">Maintenance</th>
                  <th className="th">Issues</th><th className="th"></th>
                </tr></thead>
                <tbody>
                  {list.map(a => (
                    <tr key={a.id} className="tr">
                      <td className="td">
                        <Link to={`/equipment/${a.id}`} className="text-slate-100 hover:text-accent-200">{a.name}</Link>
                        <div className="text-[11.5px] text-slate-400 whitespace-nowrap">
                          <span className="mono !text-[11px] text-accent-200">{a.asset_tag}</span>
                          {' · '}{a.category || '—'}
                          {a.serial_number && <span className="mono !text-[11px]"> · SN {a.serial_number}</span>}
                        </div>
                      </td>
                      <td className="td mono text-slate-300 whitespace-nowrap">{a.lab_code}</td>
                      <td className="td">
                        <Chip tone={assetTone(a.status)}>{assetStatusLabel(a.status)}</Chip>
                        {a.status === 'CHECKED_OUT' && a.holder_name &&
                          <div className="mt-1 text-[12px] text-slate-300">{a.holder_name}</div>}
                      </td>
                      <td className="td text-[12.5px] whitespace-nowrap">
                        <div className="text-slate-300">Inspected: {a.last_inspected_at ? fmtDate(a.last_inspected_at)
                          : <span className="text-slate-500">not recorded</span>}</div>
                        <div className={a.maintenance_due ? 'text-bad-soft font-medium' : 'text-slate-400'}>
                          Next: {a.next_maintenance_at ? <>{fmtDate(a.next_maintenance_at)}{a.maintenance_due && ' · overdue'}</>
                            : <span className="text-slate-500">not scheduled</span>}</div>
                      </td>
                      <td className="td whitespace-nowrap">{a.open_issues > 0
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
      {adding && <AddEquipment onClose={() => setAdding(false)} onSaved={() => { setAdding(false); load() }} />}
    </div>
  )
}

function AddAsset({ labs, onClose, onSaved }: { labs: Lab[]; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ asset_tag: '', name: '', category: '', lab_id: '', notes: '',
                               serial_number: '', next: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await api.createAsset({ asset_tag: f.asset_tag, name: f.name, category: f.category,
        lab_id: Number(f.lab_id), notes: f.notes, serial_number: f.serial_number.trim() || null,
        next_maintenance_at: f.next ? new Date(`${f.next}T09:00`).toISOString() : null })
      onSaved()
    }
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
        <div className="grid grid-cols-2 gap-3">
          <Field label="Serial number (optional)"><input className="input mono" value={f.serial_number}
            onChange={e => setF({ ...f, serial_number: e.target.value })} /></Field>
          <Field label="Next maintenance (optional)"><input className="input" type="date" value={f.next}
            onChange={e => setF({ ...f, next: e.target.value })} /></Field>
        </div>
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

// ---------------------------------------------------------------------------
// The Robotics Lab's four systems, one tab each, plus the full register.
// ---------------------------------------------------------------------------
type Tab = 'environment' | 'noncons' | 'consumables' | 'reusables' | 'register'
const TABS: { key: Tab; label: string }[] = [
  { key: 'environment', label: '1 · Physical environment' },
  { key: 'noncons', label: '2 · Robots & PCs' },
  { key: 'consumables', label: '3 · Consumables' },
  { key: 'reusables', label: '4 · Reusables' },
  { key: 'register', label: 'Equipment register' },
]

export default function Equipment() {
  const [params, setParams] = useSearchParams()
  const tab = (TABS.some(t => t.key === params.get('tab')) ? params.get('tab') : 'environment') as Tab
  const [adding, setAdding] = useState(false)
  const [version, setVersion] = useState(0)        // remounts the shown system after an addition
  // Robots & PCs stays mounted (hidden) once opened (2026-10-21, owner: "very slow, freezes"): starting a
  // robot's 3D view costs ~1 s of the main thread (WebGL context, model, shaders - profiled), and leaving the
  // tab threw both views away, so every return paid it again. Hidden, the views draw nothing (off screen).
  const [robotsOpened, setRobotsOpened] = useState(tab === 'noncons')
  useEffect(() => { if (tab === 'noncons') setRobotsOpened(true) }, [tab])
  return (
    <div className="space-y-5">
      <PageHeader eyebrow="Robotics Lab" title="Equipment"
        sub="The lab's four systems: environment, robots & PCs, consumables and reusables."
        actions={<button className="btn-primary" onClick={() => setAdding(true)}><Plus size={16} />Add equipment</button>} />
      {adding && <AddEquipment onClose={() => setAdding(false)}
        onSaved={t => { setAdding(false); setParams({ tab: t }, { replace: true }); setVersion(v => v + 1) }} />}
      <Tabs id="equipment" tabs={TABS} value={tab} onChange={k => setParams({ tab: k }, { replace: true })} />
      <div key={version} className="contents">
      {tab === 'environment' && <EnvironmentOverview />}
      {robotsOpened && <div className={tab === 'noncons' ? 'space-y-5' : 'hidden'}><RobotTwinPanels /><NetworkedEquipment /></div>}
      {tab === 'consumables' && <ConsumableBins />}
      {tab === 'reusables' && <ReusableItems />}
      {tab === 'register' && <EquipmentRegister />}
      </div>
    </div>
  )
}
