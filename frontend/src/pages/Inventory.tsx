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
import { Asset, BinCalibration, BinItem, InventoryBin, InventoryTx, Lab, User, api } from '../lib/api'
import { fmtDateTime, relative } from '../lib/time'
import { useLiveMessages } from '../lib/live'
import {
  Chip, Drawer, EmptyState, ErrorBanner, Field, PageHeader, SectionTitle, Spinner, Tabs,
} from '../components/ui'
import { visibleInterval } from '../lib/visibleInterval'

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

  const load = useCallback((fresh = false) => {
    api.inventoryBins(fresh).then(setBins).catch(e => setError(e.message))   // fresh: a live push must not get the answer of the fetch just before it
  }, [])
  useEffect(() => {
    load()
    const t = visibleInterval(() => load(), 15000)       // fallback if the live link drops
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => { if (m.type === 'inventory_update') load(true) })   // each weighing, at once

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
                <div key={b.id} className={`card text-left ${b.low ? 'border-warn/50' : ''}`}>
                <button onClick={() => setOpen(b)} className="w-full p-5 pb-3 text-left hover:bg-ink-800/40 rounded-t-2xl transition-colors">
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
                        {/* 2026-11-17: the LIVE count while the weight moves, the booked count once it settles */}
                        {b.qty_live != null && !b.settled
                          ? <span className="text-warn-soft">~{b.qty_live}</span>
                          : b.qty_est !== null ? <>~{b.qty_est}{b.qty_err !== null &&
                          <span className="text-base text-slate-400"> ±{b.qty_err}</span>}</> : '—'}</div>
                      {b.qty_live != null && !b.settled &&
                        <div className="text-[11.5px] text-warn-soft">settling… (booked {b.qty_est ?? '—'})</div>}
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
                </button>
                <ItemSwitcher bin={b} onDone={() => load(true)} />
                {b.calibrated && <BinQuickActions bin={b} onDone={() => load(true)} />}
                </div>))}
            </div>}
      </section>

      <Drawer open={!!open} onClose={() => setOpen(null)} title={open?.item_name ?? ''} subtitle={open?.code}>
        {open && <BinDetail bin={open} onChanged={b => { setOpen(b); load() }} />}
      </Drawer>
      <Drawer open={creating} onClose={() => { setCreating(false); load(true) }} title="New bin">
        {creating && <NewBin bins={bins ?? []} onDone={() => { setCreating(false); load(true) }} />}
      </Drawer>
    </div>
  )
}

/** 2026-11-17 (lab, owner): Zero and "set as current stock" right on the card, not hidden in the drawer. */
function BinQuickActions({ bin, onDone }: { bin: InventoryBin; onDone: () => void }) {
  const [busy, setBusy] = useState('')
  const [count, setCount] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  async function zero() {
    setBusy('zero'); setMsg(null)
    try {
      const r = await api.zeroBin(bin.id)
      setMsg({ ok: true, text: r.zeroed_by === 'node' ? 'Sent to the node - it zeroes itself in a few seconds. Put the container back.'
        : `Zeroed (${r.zero_offset_g.toFixed(2)} g removed). Put the container back.` })
      onDone()
    } catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : 'Zero failed' }) }
    finally { setBusy('') }
  }
  async function setStock() {
    setBusy('count'); setMsg(null)
    try {
      const r = await api.recordBinCount(bin.id, parseInt(count, 10), 'set on the card', true)
      setMsg({ ok: true, text: `Now counting from ${r.actual_count} (was ~${r.estimate ?? '—'}).` })
      setCount(''); onDone()
    } catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : 'Failed' }) }
    finally { setBusy('') }
  }
  return (
    <div className="border-t border-ink-600/60 px-5 py-3 space-y-2">
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-ghost btn-sm" disabled={!!busy} onClick={zero}
                title="Take the container off the platform first">
          {busy === 'zero' ? 'Zeroing…' : 'Zero scale (container off)'}</button>
        <div className="flex gap-1.5 ml-auto">
          <input className="input !py-1 !text-[13px] w-24" inputMode="numeric" placeholder="Real count"
                 value={count} onChange={e => setCount(e.target.value)} />
          <button type="button" className="btn-primary btn-sm" disabled={!!busy || !/^\d+$/.test(count)} onClick={setStock}
                  title="Container on the scale: the portal re-anchors so this reading shows this count">
            {busy === 'count' ? 'Saving…' : 'Set as stock'}</button>
        </div>
      </div>
      {msg && <p className={`text-[12px] ${msg.ok ? 'text-ok-soft' : 'text-warn-soft'}`}>{msg.text}</p>}
    </div>
  )
}

/**
 * Guided calibration (2026-11-20, owner): one button; the bin node's LCD shows the same step and countdown.
 * Empty scale (held 10 s) -> the node zeroes -> empty container (held 10 s) -> parts in -> type the count ->
 * Calibrate. Nothing is booked while it runs. Backend: app/services/bin_calibration.py.
 */
const CAL_STEPS: { key: NonNullable<BinCalibration['step']>; label: string }[] = [
  { key: 'CLEAR', label: 'Empty scale' }, { key: 'ZEROING', label: 'Zero' },
  { key: 'CONTAINER', label: 'Empty container' }, { key: 'PIECES', label: 'Parts + count' }, { key: 'DONE', label: 'Saved' },
]
const CAL_HINT: Record<NonNullable<BinCalibration['step']>, string> = {
  CLEAR: 'Take everything off the platform and do not touch it. The countdown runs while the scale is steady.',
  ZEROING: 'The bin node is zeroing itself - a few seconds.',
  CONTAINER: 'Put the EMPTY container on the platform and leave it. The countdown runs while it is steady.',
  PIECES: 'Put the parts in the container, wait until it is steady, then type how many you put in and press Calibrate.',
  DONE: 'Saved. The bin counts with the new calibration from now on.',
}

function GuidedCalibration({ bin, onSaved, initialName, autoStart = false, onClosed }: {
  bin: InventoryBin; onSaved: (b: InventoryBin) => void
  /** prefilled item name; with autoStart the session starts at once (the New bin flow) */
  initialName?: string; autoStart?: boolean
  /** called when the session ends (saved or cancelled) - the New bin drawer closes then */
  onClosed?: () => void
}) {
  const [st, setSt] = useState<BinCalibration | null>(null)
  const [name, setName] = useState(initialName ?? bin.item_name)
  const [saved, setSaved] = useState(false)
  const [pieces, setPieces] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const running = !!st?.step
  useEffect(() => {
    api.binCalStatus(bin.id).then(s => {
      if (s.step) setSt(s)
      else if (autoStart) api.binCalStart(bin.id, (initialName ?? '').trim() || undefined).then(setSt).catch(e => setErr(e.message))
    }).catch(() => {})
  }, [bin.id])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!running) return
    const t = setInterval(() => { api.binCalStatus(bin.id).then(s => setSt(s.step ? s : null)).catch(() => {}) }, 1000)
    return () => clearInterval(t)
  }, [running, bin.id])

  async function start() {
    setErr(''); setBusy(true)
    try { setSt(await api.binCalStart(bin.id, name.trim() || undefined)); setPieces('') }
    catch (e) { setErr(e instanceof Error ? e.message : 'Could not start') } finally { setBusy(false) }
  }
  async function finish() {
    setErr(''); setBusy(true)
    try { const r = await api.binCalFinish(bin.id, parseInt(pieces, 10)); setSt(r); setSaved(true); onSaved(r.bin) }
    catch (e) { setErr(e instanceof Error ? e.message : 'Calibration failed') } finally { setBusy(false) }
  }
  async function cancel() {
    setErr(''); try { await api.binCalCancel(bin.id) } catch { /* already gone */ } setSt(null); onClosed?.()
  }
  // The DONE screen ends by itself (the bin goes back to counting): let the parent close too.
  useEffect(() => { if (saved && !running) onClosed?.() }, [saved, running])  // eslint-disable-line react-hooks/exhaustive-deps

  if (!running) return (
    <div className="space-y-2">
      <div className="label">Guided calibration (new container or new parts)</div>
      <p className="text-[11.5px] text-slate-400">The bin's screen walks you through it with a countdown:
        empty scale, empty container, then the parts and how many. Type a saved item's name to recalibrate it, or a
        new name to add another kind of part to this scale. Moving the scale does not need this.</p>
      {err && <p className="text-[12px] text-warn-soft">{err}</p>}
      <div className="flex gap-2">
        <input className="input flex-1" placeholder="What goes in it, e.g. Screws M3" value={name} maxLength={64}
               list={`bin-items-${bin.id}`} onChange={e => setName(e.target.value)} aria-label="Item name" />
        {/* A saved item's name recalibrates that item; a new name adds a new item to this scale. */}
        <datalist id={`bin-items-${bin.id}`}>{(bin.items ?? []).map(i => <option key={i.id} value={i.item_name} />)}</datalist>
        <button type="button" className="btn-primary" disabled={busy} onClick={start}>
          <Scale size={15} />{busy ? 'Starting…' : 'Start'}</button>
      </div>
    </div>
  )

  const idx = CAL_STEPS.findIndex(s => s.key === st!.step)
  const counting = (st!.step === 'CLEAR' || st!.step === 'CONTAINER') && st!.reading_fresh && (st!.held_s ?? 0) > 0
  return (
    <div className="space-y-3 rounded-xl border border-accent-500/30 bg-accent-500/[0.05] p-4">
      <div className="flex items-center justify-between">
        <div className="label !mb-0">Guided calibration - {st!.item_name}</div>
        {st!.step !== 'DONE' && <button type="button" className="btn-quiet btn-sm" onClick={cancel}>Cancel</button>}
      </div>
      <ol className="flex gap-1">
        {CAL_STEPS.map((s, i) => (
          <li key={s.key} className={`flex-1 text-center rounded-md px-1 py-1 text-[10.5px] ${i < idx ? 'bg-ok/15 text-ok-soft'
            : i === idx ? 'bg-accent-500/20 text-accent-200 font-semibold' : 'bg-ink-700/50 text-slate-500'}`}>{s.label}</li>))}
      </ol>
      {/* Same two lines the bin's LCD shows. */}
      <div className="mx-auto w-fit rounded-md border-4 border-ink-600 bg-[#1f3d1a] px-3 py-2 font-mono text-[15px] leading-tight text-[#b8f5a0] tracking-wider"
           aria-label="Bin screen">
        <div className="whitespace-pre">{(st!.lcd?.[0] ?? '').padEnd(16)}</div>
        <div className="whitespace-pre">{(st!.reading_fresh || st!.step === 'DONE' ? (st!.lcd?.[1] ?? '') : 'Hold still...').padEnd(16)}</div>
      </div>
      <p className="text-[12.5px] text-slate-300">{CAL_HINT[st!.step!]}</p>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-slate-400 tnum">
        <span>Scale: <b className="text-slate-200">{st!.last_g == null ? '—' : `${st!.last_g.toFixed(2)} g`}</b>
          {!st!.reading_fresh && st!.step !== 'DONE' && <span className="text-warn-soft"> (moving)</span>}</span>
        {counting && <span>Countdown: <b className="text-accent-200">{st!.countdown_s}s</b></span>}
        {st!.m0_g != null && <span>Empty container: <b className="text-slate-200">{st!.m0_g.toFixed(3)} g</b></span>}
        {st!.net_g != null && <span>Parts: <b className="text-slate-200">{st!.net_g.toFixed(3)} g</b></span>}
      </div>
      {st!.step === 'PIECES' && (
        <div className="flex gap-2">
          <input className="input w-32" inputMode="numeric" placeholder="How many?" value={pieces}
                 onChange={e => setPieces(e.target.value)} aria-label="Number of pieces put in" />
          <button type="button" className="btn-primary flex-1" disabled={busy || !st!.parts_ready || !/^\d+$/.test(pieces) || pieces === '0'}
                  onClick={finish} title={st!.parts_ready ? '' : 'Put the parts in and wait until the scale is steady'}>
            {busy ? 'Calibrating…' : st!.parts_ready ? 'Calibrate' : 'Waiting for a steady reading…'}</button>
        </div>)}
      {st!.step === 'DONE' && st!.result && (
        <p className="text-[12.5px] text-ok-soft">
          {st!.result.pieces} pieces = {st!.result.net_g.toFixed(3)} g, so one piece = <b>{st!.result.unit_mass_g.toFixed(4)} g</b>;
          empty container {st!.result.tare_g.toFixed(3)} g.</p>)}
      {err && <p className="text-[12px] text-warn-soft">{err}</p>}
    </div>
  )
}

/**
 * One scale, several items (2026-11-20, owner): the same scale and glass box count different parts, each with
 * its own saved calibration. Pick what is in the box now; optionally say how many are in it so the count is
 * anchored to the current reading. A new kind of part is added with the guided calibration.
 */
function ItemSwitcher({ bin, onDone }: { bin: InventoryBin; onDone: () => void }) {
  const items = bin.items ?? []
  const current = items.find(i => i.is_selected)
  const [pick, setPick] = useState<string>('')
  const [count, setCount] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  if (!items.length) return null
  const target = items.find(i => String(i.id) === pick)
  async function sw() {
    if (!target) return
    setBusy(true); setMsg(null)
    try {
      await api.binItemSelect(bin.id, target.id, count === '' ? undefined : parseInt(count, 10))
      setMsg({ ok: true, text: `Now counting ${target.item_name}${count !== '' ? ` from ${count}` : ''}.` })
      setPick(''); setCount(''); onDone()
    } catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : 'Switch failed' }) }
    finally { setBusy(false) }
  }
  return (
    <div className="border-t border-ink-600/60 px-5 py-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
        <span className="text-slate-400">Counting:</span>
        <b className="text-slate-100">{current?.item_name ?? bin.item_name}</b>
        {current?.unit_mass_g != null && <span className="text-slate-500 tnum">({current.unit_mass_g.toFixed(4)} g each)</span>}
      </div>
      {items.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          <select className="input !py-1 !text-[13px] flex-1 min-w-[9rem]" value={pick} onChange={e => setPick(e.target.value)}
                  aria-label="Switch to another item">
            <option value="">Switch to…</option>
            {items.filter(i => !i.is_selected).map(i => <option key={i.id} value={i.id}>{i.item_name}</option>)}
          </select>
          <input className="input !py-1 !text-[13px] w-24" inputMode="numeric" placeholder="How many in"
                 title="Optional: how many are in the box now (anchors the count)" value={count}
                 onChange={e => setCount(e.target.value)} />
          <button type="button" className="btn-primary btn-sm" disabled={busy || !target || (count !== '' && !/^\d+$/.test(count))}
                  onClick={sw}>{busy ? 'Switching…' : 'Switch'}</button>
        </div>)}
      {msg && <p className={`text-[12px] ${msg.ok ? 'text-ok-soft' : 'text-warn-soft'}`}>{msg.text}</p>}
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
  const [zeroMsg, setZeroMsg] = useState('')
  const [zeroing, setZeroing] = useState(false)
  async function zero() {
    setError(''); setZeroMsg(''); setZeroing(true)
    try {
      const r = await api.zeroBin(bin.id)
      onChanged(r)
      setF(x => ({ ...x, tare_g: r.tare_g?.toString() ?? '' }))
      setZeroMsg(r.zeroed_by === 'node'
        ? 'Sent to the bin node: it zeroes itself within a few seconds (its screen shows 0 g too). Now put the container back.'
        : `Zeroed in the portal (offset ${r.zero_offset_g.toFixed(2)} g removed). Put the container back; the node's own screen still shows raw grams.`)
    } catch (err) { setError(err instanceof Error ? err.message : 'Zero failed') }
    finally { setZeroing(false) }
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
      <GuidedCalibration bin={bin} onSaved={b => {
        onChanged(b)
        setF(x => ({ ...x, item_name: b.item_name, tare_g: b.tare_g?.toString() ?? '', unit_mass_g: b.unit_mass_g?.toString() ?? '' }))
      }} />
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

      <div className="space-y-2">
        <div className="label">Zero the scale (after moving it)</div>
        <p className="text-[11.5px] text-slate-400">Take the container OFF the platform, wait 3 s, then press. Nothing is booked;
          the next reading with the container back is the new starting point.</p>
        <button type="button" className="btn-ghost w-full" onClick={zero} disabled={zeroing}>
          {zeroing ? 'Zeroing…' : 'Zero scale (platform empty)'}</button>
        {zeroMsg && <p className="text-[12.5px] text-ok-soft">{zeroMsg}</p>}
      </div>

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

/**
 * "New bin" (owner, 2026-11-20): usually a new kind of part in the same glass box on the same scale - pick the
 * scale, name the part, and the guided calibration runs right here (the bin's screen shows the steps). A new
 * scale (another bin node with its own BIN_CODE) is the second option.
 */
function NewBin({ bins, onDone }: { bins: InventoryBin[]; onDone: () => void }) {
  const [mode, setMode] = useState<'item' | 'scale'>(bins.length ? 'item' : 'scale')
  const [scaleId, setScaleId] = useState(bins[0] ? String(bins[0].id) : '')
  const [name, setName] = useState('')
  const [go, setGo] = useState(false)
  const scale = bins.find(b => String(b.id) === scaleId)
  const taken = !!scale?.items?.some(i => i.item_name.trim().toLowerCase() === name.trim().toLowerCase())
  return (
    <div className="space-y-4">
      {!go && <Tabs id="new-bin-mode" value={mode} onChange={setMode}
        tabs={[{ key: 'item', label: 'New item on a scale' }, { key: 'scale', label: 'New scale (bin node)' }]} />}
      {mode === 'scale' ? <CreateBin onDone={onDone} />
        : !go ? (
          <div className="space-y-3">
            <p className="text-[12.5px] text-slate-400">Same scale and glass box, a different part. The scale keeps every
              item's calibration: you can switch back to any of them later on the bin card.</p>
            <Field label="Scale">
              <select className="input" value={scaleId} onChange={e => setScaleId(e.target.value)}>
                {bins.map(b => <option key={b.id} value={b.id}>{b.code} - now counting {b.item_name}</option>)}</select></Field>
            <Field label="Item" hint={taken ? 'Already saved on this scale - this recalibrates it.' : 'e.g. Screws M3'}>
              <input className="input" value={name} maxLength={64} placeholder="Screws M3"
                     onChange={e => setName(e.target.value)} /></Field>
            <button type="button" className="btn-primary w-full" disabled={!scale || !name.trim()} onClick={() => setGo(true)}>
              <Scale size={15} />Start calibration</button>
          </div>)
        : scale && <GuidedCalibration bin={scale} initialName={name.trim()} autoStart onSaved={() => {}} onClosed={onDone} />}
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
  const [tab, setTab] = useState<'items' | 'take' | 'return'>('items')
  return (
    <div className="space-y-4">
      <Tabs id="bin-tabs" value={tab} onChange={setTab} tabs={[
        { key: 'items', label: 'Items' },
        { key: 'take', label: 'Take an item' },
        { key: 'return', label: 'Return an item' }]} />
      {tab === 'items' ? <BinItemList /> : <StaffBinAction mode={tab} />}
    </div>
  )
}

/** Staff, on someone's behalf: take (the bin opens, the weight confirms) or
 *  record a return that came back without the bin (bin fault, booking over). */
function StaffBinAction({ mode }: { mode: 'take' | 'return' }) {
  const [items, setItems] = useState<BinItem[] | null>(null)
  const [people, setPeople] = useState<User[]>([])
  const [asset, setAsset] = useState('')
  const [picked, setPicked] = useState<number[]>([])
  const [person, setPerson] = useState('')
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = useCallback(() => {
    api.labs().then(ls => Promise.all(ls.map(l => api.binItems(l.id).then(r => r.items).catch(() => []))))
      .then(all => setItems(all.flat())).catch(() => setItems([]))
  }, [])
  useEffect(() => { load(); setAsset(''); setPicked([]); setMsg(''); setError('') }, [load, mode])
  // Items come and go at the bin (scans, takes): keep the lists current.
  useEffect(() => { const t = visibleInterval(load, 4000); return () => window.clearInterval(t) }, [load])
  useLiveMessages(m => { if (m.type === 'staff' || m.type === 'access_event') load() })
  useEffect(() => { if (mode === 'take') api.users().then(setPeople).catch(() => {}) }, [mode])
  const list = (items ?? []).filter(i => mode === 'take' ? i.status === 'AVAILABLE' : i.status === 'CHECKED_OUT')
  async function go(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setMsg('')
    try {
      if (mode === 'take') {
        if (!picked.length) { setError('Tick at least one item.'); return }
        setMsg((await api.staffTakeFromBin(picked, Number(person))).message); setPicked([])
      }
      else { await api.staffReturnToBin(Number(asset), note.trim()); setMsg('Return recorded. The holder was notified.'); setNote('') }
      setAsset(''); load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed'); setAsset(''); setPicked([]); load() }
    finally { setBusy(false) }
  }
  if (!items) return <Spinner />
  return (
    <form onSubmit={go} className="card p-4 space-y-3 max-w-xl">
      <p className="text-[12.5px] text-slate-400">{mode === 'take'
        ? 'Take an item out FOR someone (e.g. their booking has ended). The bin opens; its weight confirms the take, recorded against that person.'
        : 'Record that a checked-out item is back when it came back without the bin (bin fault, booking over). Logged as a staff return; the holder is notified. The bin does NOT open: to put the item back through the bin, scan its tag at the bin instead.'}</p>
      {error && <ErrorBanner message={error} />}
      {msg && <p className="text-[12.5px] text-ok-soft">{msg}</p>}
      {!list.length ? <p className="text-[12.5px] text-slate-400">
        {mode === 'take' ? 'No item is available in the bin.' : 'No item is checked out.'}</p> : <>
        {mode === 'take' ? <Field label={`Items (${picked.length} ticked)`}>
          <div className="rounded-lg border border-ink-600/70 divide-y divide-ink-600/50">
            {list.map(i => (
              <label key={i.id} className="flex items-center gap-3 px-3 py-2 text-[13px] cursor-pointer hover:bg-white/5">
                <input type="checkbox" checked={picked.includes(i.id)}
                  onChange={e => setPicked(p => e.target.checked ? [...p, i.id] : p.filter(x => x !== i.id))} />
                <span className="mono text-slate-300">{i.asset_tag}</span>
                <span className="text-white">{i.name}</span>
              </label>))}
          </div></Field> : <Field label="Item">
          <select className="input" required value={asset} onChange={e => setAsset(e.target.value)}>
            <option value="">Choose…</option>
            {list.map(i => <option key={i.id} value={i.id}>
              {i.asset_tag} · {i.name}{i.holder ? ` · with ${i.holder}` : ''}</option>)}
          </select></Field>}
        {mode === 'take' && <Field label="For">
          <select className="input" required value={person} onChange={e => setPerson(e.target.value)}>
            <option value="">Choose a person…</option>
            {people.filter(p => p.is_active !== false).map(p => <option key={p.id} value={p.id}>{p.full_name} · {p.email}</option>)}
          </select></Field>}
        {mode === 'return' && <Field label="Note (optional)">
          <input className="input" maxLength={255} value={note} onChange={e => setNote(e.target.value)}
            placeholder="e.g. lid sensor fault - item put back by hand" /></Field>}
        <button className="btn-primary w-full" disabled={busy}>
          {mode === 'take' ? `Open the bin - take ${picked.length || ''} for this person` : 'Record the return'}</button>
      </>}
    </form>
  )
}

function BinItemList() {
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
