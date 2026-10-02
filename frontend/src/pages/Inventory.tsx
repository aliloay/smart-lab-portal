/**
 * Inventory (Robotics Lab): consumable weighing bins (System 2).
 *
 * Each bin shows its measured mass and - only once its calibration has
 * been measured and entered - the estimated quantity with its error band.
 * Staff enter the calibration (empty-bin mass, unit mass, noise), record
 * physical counts next to the estimate (the estimation-error data), and
 * read the withdrawals/refills the bin produced. Nothing is estimated from
 * defaults.
 */
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Boxes, Package, Plus, Scale } from 'lucide-react'
import { InventoryBin, InventoryTx, Lab, api } from '../lib/api'
import { fmtDateTime, relative } from '../lib/time'
import {
  Chip, Drawer, EmptyState, ErrorBanner, Field, PageHeader, SectionTitle, Spinner,
} from '../components/ui'

const QUALITY: Record<InventoryBin['quality'], { tone: 'ok' | 'warn' | 'idle' | 'bad'; label: string }> = {
  VALID: { tone: 'ok', label: 'live' }, STALE: { tone: 'warn', label: 'stale' },
  MISSING: { tone: 'idle', label: 'no reading yet' }, DEVICE_OFFLINE: { tone: 'bad', label: 'node offline' },
}

export default function Inventory() {
  const [bins, setBins] = useState<InventoryBin[] | null>(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState<InventoryBin | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(() => {
    api.inventoryBins().then(setBins).catch(e => setError(e.message))
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 15000)
    return () => window.clearInterval(t)
  }, [load])

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Robotics Lab" title="Inventory"
        sub="Consumables are weighed; a quantity is shown only once the bin is calibrated."
        actions={<button className="btn-primary" onClick={() => setCreating(true)}><Plus size={15} /> New bin</button>} />
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <section>
        <SectionTitle icon={<Scale size={15} />}>Consumable bins</SectionTitle>
        {!bins ? <Spinner label="Loading bins" />
          : !bins.length ? <EmptyState icon={<Boxes size={18} />} title="No bins yet"
              detail="Create a bin with the same code as in the bin node's firmware (e.g. BIN-R10K)." />
          : <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
              {bins.map(b => (
                <button key={b.id} onClick={() => setOpen(b)}
                        className={`card p-5 text-left hover:border-ink-500 transition-colors
                                    ${b.low ? 'border-warn/50' : ''}`}>
                  <div className="flex items-start gap-2">
                    <div className="min-w-0">
                      <div className="text-white font-semibold truncate">{b.item_name}</div>
                      <div className="mono text-[11.5px] text-slate-400">{b.code} · {b.lab_code}</div>
                    </div>
                    <Chip tone={QUALITY[b.quality].tone} dot className="ml-auto shrink-0">{QUALITY[b.quality].label}</Chip>
                  </div>
                  <div className="mt-4 flex items-end gap-6">
                    <div>
                      <div className="label">Quantity</div>
                      <div className="font-display text-3xl text-white tnum">
                        {b.qty_est !== null ? <>~{b.qty_est}{b.qty_err !== null &&
                          <span className="text-base text-slate-400"> ±{b.qty_err}</span>}</> : '—'}</div>
                    </div>
                    <div>
                      <div className="label">Mass</div>
                      <div className="text-xl text-slate-200 tnum">{b.mass_g !== null ? `${b.mass_g.toFixed(1)} g` : '—'}</div>
                    </div>
                  </div>
                  <div className="mt-3 text-[12px] text-slate-400">
                    {!b.calibrated ? <span className="text-warn-soft">Not calibrated - mass only</span>
                      : b.low ? <span className="text-warn-soft">Low stock (reorder at {b.reorder_qty})</span>
                      : b.reorder_qty !== null ? `Reorder at ${b.reorder_qty}` : 'No reorder level'}
                    {b.measured_at && <> · {relative(b.measured_at)}</>}
                  </div>
                </button>))}
            </div>}
      </section>

      <Drawer open={!!open} onClose={() => setOpen(null)} title={open?.item_name ?? ''} subtitle={open?.code}>
        {open && <BinDetail bin={open} onChanged={b => { setOpen(b); load() }} />}
      </Drawer>
      <Drawer open={creating} onClose={() => setCreating(false)} title="New bin">
        {creating && <CreateBin onDone={() => { setCreating(false); load() }} />}
      </Drawer>
    </div>
  )
}

function num(v: string): number | null {
  const n = parseFloat(v)
  return v.trim() === '' || Number.isNaN(n) ? null : n
}

function BinDetail({ bin, onChanged }: { bin: InventoryBin; onChanged: (b: InventoryBin) => void }) {
  const [f, setF] = useState({
    item_name: bin.item_name, tare_g: bin.tare_g?.toString() ?? '', unit_mass_g: bin.unit_mass_g?.toString() ?? '',
    noise_g: bin.noise_g?.toString() ?? '', reorder_qty: bin.reorder_qty?.toString() ?? '' })
  const [count, setCount] = useState('')
  const [countResult, setCountResult] = useState('')
  const [txs, setTxs] = useState<InventoryTx[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => { api.binHistory(bin.id).then(h => setTxs(h.transactions)).catch(() => setTxs([])) }, [bin.id])

  async function save(e: FormEvent) {
    e.preventDefault(); setError('')
    try {
      onChanged(await api.updateBin(bin.id, {
        item_name: f.item_name, tare_g: num(f.tare_g), unit_mass_g: num(f.unit_mass_g),
        noise_g: num(f.noise_g), reorder_qty: f.reorder_qty === '' ? null : parseInt(f.reorder_qty, 10) }))
    } catch (err) { setError(err instanceof Error ? err.message : 'Save failed') }
  }
  async function recordCount(e: FormEvent) {
    e.preventDefault(); setError('')
    try {
      const r = await api.recordBinCount(bin.id, parseInt(count, 10))
      setCountResult(r.estimate === null ? `Recorded ${r.actual_count} (no estimate yet - not calibrated).`
        : `Estimate ${r.estimate}, counted ${r.actual_count}: error ${r.error! > 0 ? '+' : ''}${r.error}.`)
      setCount('')
      api.binHistory(bin.id).then(h => setTxs(h.transactions)).catch(() => {})
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed') }
  }

  return (
    <div className="space-y-5">
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      <form onSubmit={save} className="space-y-3">
        <div className="label">Calibration - measured values only</div>
        <Field label="Item"><input className="input" value={f.item_name} onChange={e => setF({ ...f, item_name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Empty bin mass m₀ (g)"><input className="input" inputMode="decimal" value={f.tare_g}
            onChange={e => setF({ ...f, tare_g: e.target.value })} /></Field>
          <Field label="Mass per item u (g)"><input className="input" inputMode="decimal" value={f.unit_mass_g}
            onChange={e => setF({ ...f, unit_mass_g: e.target.value })} /></Field>
          <Field label="Noise (g, from the noise test)"><input className="input" inputMode="decimal" value={f.noise_g}
            onChange={e => setF({ ...f, noise_g: e.target.value })} /></Field>
          <Field label="Reorder at (pieces)"><input className="input" inputMode="numeric" value={f.reorder_qty}
            onChange={e => setF({ ...f, reorder_qty: e.target.value })} /></Field>
        </div>
        <p className="text-[11.5px] text-slate-400">
          Estimate n = round((m − m₀) / u), ± noise / u. A stable change below {bin.min_change_g.toFixed(1)} g is
          treated as noise.{bin.calibrated_at && <> Calibrated {fmtDateTime(bin.calibrated_at)}.</>}
        </p>
        <button className="btn-primary w-full">Save</button>
      </form>

      <form onSubmit={recordCount} className="space-y-2">
        <div className="label">Physical count (estimation error)</div>
        <div className="flex gap-2">
          <input className="input flex-1" inputMode="numeric" placeholder="Pieces counted by hand"
                 value={count} onChange={e => setCount(e.target.value)} />
          <button className="btn-ghost" disabled={!/^\d+$/.test(count)}>Record</button>
        </div>
        {countResult && <p className="text-[12.5px] text-slate-200">{countResult}</p>}
      </form>

      <div>
        <div className="label mb-2 flex items-center gap-1.5"><Package size={13} /> Last 7 days</div>
        {!txs ? <Spinner /> : !txs.length ? <p className="text-[12.5px] text-slate-500">No changes recorded.</p>
          : <ul className="space-y-1.5">
              {txs.map(t => (
                <li key={t.id} className="flex items-baseline gap-2 text-[12.5px]">
                  <span className={t.kind === 'WITHDRAWAL' ? 'text-warn-soft' : t.kind === 'REFILL' ? 'text-ok-soft' : 'text-accent-200'}>
                    {t.kind.toLowerCase()}</span>
                  <span className="text-slate-200 tnum">
                    {t.kind === 'COUNT' ? `counted ${t.actual_count}, estimate ${t.qty_est_after ?? '—'}`
                      : `${t.delta_mass_g! > 0 ? '+' : ''}${t.delta_mass_g} g${t.delta_qty_est !== null ? ` (~${t.delta_qty_est})` : ''}`}</span>
                  {t.user_name && <span className="text-slate-400 truncate">· {t.user_name}</span>}
                  <span className="ml-auto text-slate-500 shrink-0">{relative(t.recorded_at)}</span>
                </li>))}
            </ul>}
        <p className="mt-2 text-[11px] text-slate-500">A name appears only when exactly one person was inside
          the lab - a correlation, not proof of who took it.</p>
      </div>
    </div>
  )
}

function CreateBin({ onDone }: { onDone: () => void }) {
  const [labs, setLabs] = useState<Lab[]>([])
  const [f, setF] = useState({ code: '', item_name: '', lab_id: '', reorder_qty: '' })
  const [error, setError] = useState('')
  useEffect(() => { api.labs().then(l => { setLabs(l); if (l[0]) setF(x => ({ ...x, lab_id: String(l[0].id) })) }).catch(() => {}) }, [])
  async function submit(e: FormEvent) {
    e.preventDefault(); setError('')
    try {
      await api.createBin({ code: f.code.trim().toUpperCase(), item_name: f.item_name, lab_id: Number(f.lab_id),
        reorder_qty: f.reorder_qty === '' ? null : parseInt(f.reorder_qty, 10) })
      onDone()
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed') }
  }
  return (
    <form onSubmit={submit} className="space-y-3">
      {error && <ErrorBanner message={error} />}
      <Field label="Bin code" hint="Same as BIN_CODE in the bin node's firmware, e.g. BIN-R10K.">
        <input className="input mono" required value={f.code} onChange={e => setF({ ...f, code: e.target.value })} /></Field>
      <Field label="Item"><input className="input" required placeholder="10k resistors" value={f.item_name}
        onChange={e => setF({ ...f, item_name: e.target.value })} /></Field>
      <Field label="Laboratory">
        <select className="input" value={f.lab_id} onChange={e => setF({ ...f, lab_id: e.target.value })}>
          {labs.map(l => <option key={l.id} value={l.id}>{l.code} - {l.name}</option>)}</select></Field>
      <Field label="Reorder at (pieces, optional)"><input className="input" inputMode="numeric" value={f.reorder_qty}
        onChange={e => setF({ ...f, reorder_qty: e.target.value })} /></Field>
      <button className="btn-primary w-full">Create bin</button>
    </form>
  )
}
