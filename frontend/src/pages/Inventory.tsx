/**
 * Inventory (Robotics Lab): consumables (System 3, weighing bins) and
 * reusables (System 4, the NFC smart bin). Both sections also appear as
 * tabs on the Equipment page.
 *
 * Each bin shows its measured mass and - only once its calibration has
 * been measured and entered - the estimated quantity with its error band.
 * Staff enter the calibration (empty-bin mass, unit mass, noise), record
 * physical counts next to the estimate (the estimation-error data), and
 * read the withdrawals/refills the bin produced. Nothing is estimated from
 * defaults.
 */
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Boxes, Nfc, Package, Plus, Scale } from 'lucide-react'
import { Asset, InventoryBin, InventoryTx, Lab, api } from '../lib/api'
import { fmtDateTime, relative } from '../lib/time'
import {
  Chip, Drawer, EmptyState, ErrorBanner, Field, PageHeader, SectionTitle, Spinner,
} from '../components/ui'

const QUALITY: Record<InventoryBin['quality'], { tone: 'ok' | 'warn' | 'idle' | 'bad'; label: string }> = {
  VALID: { tone: 'ok', label: 'live' }, STALE: { tone: 'warn', label: 'stale' },
  MISSING: { tone: 'idle', label: 'no reading yet' }, DEVICE_OFFLINE: { tone: 'bad', label: 'node offline' },
}

export default function Inventory() {
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Robotics Lab" title="Inventory"
        sub="Consumables are weighed; reusable items live in the NFC smart bin." />
      <ConsumableBins />
      <ReusableItems />
    </div>
  )
}

/** System 3: consumable weighing bins. */
export function ConsumableBins() {
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
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <section>
        <SectionTitle icon={<Scale size={15} />}
          sub="Weighed; a quantity is shown only once the bin is calibrated."
          action={<button className="btn-primary btn-sm" onClick={() => setCreating(true)}><Plus size={14} /> New bin</button>}>
          Consumable bins</SectionTitle>
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

// ------------------------------------------------------- reusable items ---
/** Equipment with its NFC tag (System 4). Tag an item: scan the sticker at
 *  the bin (it shows "UNKNOWN TAG"), then "Use last scanned tag" here. */
export function ReusableItems() {
  const [assets, setAssets] = useState<Asset[] | null>(null)
  const [editing, setEditing] = useState<Asset | null>(null)
  const [adding, setAdding] = useState(false)
  // The bin's load cell checks every return / checkout against this mass.
  async function setMass(a: Asset) {
    const v = window.prompt(`Mass of ${a.asset_tag} in grams (empty = learn it from the next return):`,
      a.unit_mass_g?.toString() ?? '')
    if (v === null) return
    const g = v.trim() ? Number(v) : null
    if (g !== null && !(g > 0)) { window.alert('Enter a positive number of grams.'); return }
    await api.setItemMass(a.id, g).catch(e => window.alert(e.message))
    load()
  }
  // Only what is kept in the smart bin - not fixed lab equipment.
  const load = useCallback(() => {
    api.assets().then(a => setAssets(a.filter(x => x.bin_item || x.nfc_uid))).catch(() => setAssets([]))
  }, [])
  useEffect(load, [load])
  return (
    <section>
      <SectionTitle icon={<Nfc size={15} />}
        sub="Arduinos, breadboards, microcontrollers... each with an NFC sticker."
        action={<button className="btn-primary btn-sm" onClick={() => setAdding(true)}><Plus size={14} /> Add bin item</button>}>
        Reusable items (smart bin)</SectionTitle>
      {!assets ? <Spinner /> : !assets.length
        ? <EmptyState icon={<Boxes size={18} />} title="No bin items yet"
            detail="Add the items kept in the smart bin, e.g. ARDUINO-001, BREADBOARD-001." />
        : <div className="card divide-y divide-ink-600/50">
            {assets.map(a => (
              <div key={a.id} className="px-4 py-2.5 flex items-center gap-3 text-[13px]">
                <span className="mono text-slate-300 w-40 truncate">{a.asset_tag}</span>
                <span className="text-white flex-1 truncate">{a.name}</span>
                <span className="text-slate-400 w-28">{a.status.replace('_', ' ').toLowerCase()}</span>
                <span className={`mono w-40 truncate ${a.nfc_uid ? 'text-slate-200' : 'text-slate-500'}`}>
                  {a.nfc_uid ?? 'no tag'}</span>
                <button className="tnum w-24 text-left text-slate-300 hover:text-white" title="Mass on the bin's load cell"
                  onClick={() => setMass(a)}>
                  {a.unit_mass_g != null ? `${a.unit_mass_g.toFixed(1)} g` : <span className="text-slate-500">learn on return</span>}</button>
                <button className="btn-ghost btn-sm" onClick={() => setEditing(a)}>{a.nfc_uid ? 'Change tag' : 'Assign tag'}</button>
              </div>))}
          </div>}
      <Drawer open={!!editing} onClose={() => setEditing(null)} title="NFC tag" subtitle={editing?.asset_tag}>
        {editing && <AssignTag asset={editing} onDone={() => { setEditing(null); load() }} />}
      </Drawer>
      <Drawer open={adding} onClose={() => setAdding(false)} title="Add bin item">
        {adding && <AddBinItem onDone={() => { setAdding(false); load() }} />}
      </Drawer>
    </section>
  )
}

function AssignTag({ asset, onDone }: { asset: Asset; onDone: () => void }) {
  const [uid, setUid] = useState(asset.nfc_uid ?? '')
  const [error, setError] = useState('')
  const [hint, setHint] = useState('')
  async function useLast() {
    const last = await api.lastUnknownTag().catch(() => null)
    if (last) { setUid(last.nfc_uid); setHint(`Scanned at ${last.device_uid} ${relative(last.at)}.`) }
    else setHint('No unknown tag scanned yet - hold the sticker at the bin reader first.')
  }
  async function save(e: FormEvent) {
    e.preventDefault(); setError('')
    try { await api.assignTag(asset.id, uid.trim() || null); onDone() }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed') }
  }
  return (
    <form onSubmit={save} className="space-y-3">
      {error && <ErrorBanner message={error} />}
      <p className="text-[12.5px] text-slate-400">Stick an NTAG213 on {asset.name}, hold it at the smart bin's reader
        (the bin shows UNKNOWN TAG), then use it here. The tag identifies the item; it authenticates nobody.</p>
      <Field label="Tag UID (hex)"><input className="input mono" value={uid} onChange={e => setUid(e.target.value)}
        placeholder="04A1B2C3D4E5F6" /></Field>
      <button type="button" className="btn-ghost btn-sm" onClick={useLast}>Use last scanned unknown tag</button>
      {hint && <p className="text-[12px] text-slate-400">{hint}</p>}
      <button className="btn-primary w-full">{uid.trim() ? 'Save tag' : 'Remove tag'}</button>
    </form>
  )
}

const BIN_CATEGORIES = ['Microcontroller board', 'Breadboard', 'Sensor module', 'Kit', 'Tool', 'Other']

function AddBinItem({ onDone }: { onDone: () => void }) {
  const [labs, setLabs] = useState<Lab[]>([])
  const [f, setF] = useState({ asset_tag: '', name: '', category: BIN_CATEGORIES[0], lab_id: '' })
  const [error, setError] = useState('')
  useEffect(() => { api.labs().then(l => { setLabs(l); if (l[0]) setF(x => ({ ...x, lab_id: String(l[0].id) })) }).catch(() => {}) }, [])
  async function submit(e: FormEvent) {
    e.preventDefault(); setError('')
    try {
      await api.createAsset({ asset_tag: f.asset_tag.trim().toUpperCase(), name: f.name, category: f.category,
        lab_id: Number(f.lab_id), bin_item: true })
      onDone()
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed') }
  }
  return (
    <form onSubmit={submit} className="space-y-3">
      {error && <ErrorBanner message={error} />}
      <Field label="Item code"><input className="input mono" required placeholder="ARDUINO-001" value={f.asset_tag}
        onChange={e => setF({ ...f, asset_tag: e.target.value })} /></Field>
      <Field label="Name"><input className="input" required placeholder="Arduino Uno R3" value={f.name}
        onChange={e => setF({ ...f, name: e.target.value })} /></Field>
      <Field label="Type">
        <select className="input" value={f.category} onChange={e => setF({ ...f, category: e.target.value })}>
          {BIN_CATEGORIES.map(c => <option key={c}>{c}</option>)}</select></Field>
      <Field label="Laboratory">
        <select className="input" value={f.lab_id} onChange={e => setF({ ...f, lab_id: e.target.value })}>
          {labs.map(l => <option key={l.id} value={l.id}>{l.code} - {l.name}</option>)}</select></Field>
      <p className="text-[12px] text-slate-400">Then assign its NFC sticker (hold it at the bin's reader).</p>
      <button className="btn-primary w-full">Add item</button>
    </form>
  )
}
