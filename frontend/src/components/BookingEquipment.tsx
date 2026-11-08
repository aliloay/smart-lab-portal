/**
 * Booking step "Equipment": what the person will need in the lab.
 *
 *   Smart bin   - tagged items (Breadboard 1-3 ...). One booking holds an item
 *                 for its window; items held by an overlapping booking show
 *                 as reserved and cannot be picked.
 *   Consumables - resistors, LEDs ... with a quantity (counted by weight, not reserved).
 *   Workstation - a robot (UR5e / FANUC), a lab PC, or none.
 *
 * Every group has "None", so the step never blocks the booking.
 */
import { useEffect, useState } from 'react'
import { Bot, Boxes, Check, Cpu, Monitor, Package } from 'lucide-react'
import { BookingEquipmentChoice, EquipmentOptions, api } from '../lib/api'
import { Skeleton } from './ui'

export const NO_EQUIPMENT: BookingEquipmentChoice = { bin_asset_ids: [], consumables: [], workstations: [] }

export default function BookingEquipment({ labId, start, end, value, onChange, onOptions }: {
  labId: number; start: Date; end: Date
  value: BookingEquipmentChoice; onChange: (v: BookingEquipmentChoice) => void
  onOptions?: (o: EquipmentOptions) => void
}) {
  const [opts, setOpts] = useState<EquipmentOptions | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setOpts(null); setError('')
    api.bookingEquipmentOptions(labId, start.toISOString(), end.toISOString())
      .then(o => {
        setOpts(o)
        onOptions?.(o)
        // A choice that became reserved meanwhile is dropped, not silently kept.
        const free = new Set(o.bin_items.filter(i => i.state === 'AVAILABLE').map(i => i.id))
        const kept = value.bin_asset_ids.filter(id => free.has(id))
        if (kept.length !== value.bin_asset_ids.length) onChange({ ...value, bin_asset_ids: kept })
      })
      .catch(e => setError(e instanceof Error ? e.message : 'Could not load the equipment'))
  }, [labId, start.getTime(), end.getTime()])   // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <div className="text-[13px] text-bad-soft">{error}</div>
  if (!opts) return <Skeleton className="h-48" />

  const toggleBin = (id: number) => onChange({
    ...value, bin_asset_ids: value.bin_asset_ids.includes(id)
      ? value.bin_asset_ids.filter(x => x !== id) : [...value.bin_asset_ids, id] })
  const qtyOf = (id: number) => value.consumables.find(c => c.inventory_bin_id === id)?.quantity ?? 0
  const setQty = (id: number, q: number) => onChange({
    ...value, consumables: [...value.consumables.filter(c => c.inventory_bin_id !== id),
                            ...(q > 0 ? [{ inventory_bin_id: id, quantity: q }] : [])] })

  return (
    <div className="space-y-5">
      <Group icon={<Boxes size={14} />} title="Smart bin" sub="Tagged items you take from the bin and return with a scan.">
        <Pick selected={value.bin_asset_ids.length === 0} onClick={() => onChange({ ...value, bin_asset_ids: [] })}>None</Pick>
        {opts.bin_items.map(i => {
          const reserved = i.state !== 'AVAILABLE'
          return (
            <Pick key={i.id} selected={value.bin_asset_ids.includes(i.id)} disabled={reserved}
                  onClick={() => toggleBin(i.id)}
                  note={reserved ? (i.state === 'RESERVED' ? 'reserved' : i.state.toLowerCase()) : undefined}>
              {i.name}
            </Pick>)
        })}
        {!opts.bin_items.length && <Empty>No smart-bin items in this laboratory.</Empty>}
      </Group>

      <Group icon={<Package size={14} />} title="Consumables" sub="Resistors, LEDs ... and how many you expect to use.">
        <Pick selected={value.consumables.length === 0} onClick={() => onChange({ ...value, consumables: [] })}>None</Pick>
        {opts.consumables.map(c => (
          <label key={c.id} className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-[13px]
              ${qtyOf(c.id) ? 'border-accent-400 bg-accent-500/15 text-accent-100' : 'border-ink-500 text-slate-300'}`}>
            {c.name}
            <input type="number" min={0} max={10000} value={qtyOf(c.id) || ''} placeholder="0"
                   aria-label={`${c.name} quantity`} className="input !w-20 !py-0.5 !px-2 text-right tnum"
                   onChange={e => setQty(c.id, Math.max(0, Math.min(10000, Number(e.target.value) || 0)))} />
          </label>
        ))}
        {!opts.consumables.length && <Empty>No consumables set up in this laboratory yet.</Empty>}
      </Group>

      <Group icon={<Cpu size={14} />} title="Working on" sub="Pick all you will use - a robot and a PC together is fine.">
        <Pick selected={value.workstations.length === 0} onClick={() => onChange({ ...value, workstations: [] })}>None</Pick>
        {opts.workstations.map(w => {
          const reserved = w.state !== 'AVAILABLE'
          return (
            <Pick key={w.key} selected={value.workstations.includes(w.key)} disabled={reserved}
                  onClick={() => onChange({ ...value, workstations: value.workstations.includes(w.key)
                    ? value.workstations.filter(k => k !== w.key) : [...value.workstations, w.key] })}
                  note={reserved ? (w.state === 'RESERVED' ? 'reserved' : w.state.toLowerCase()) : undefined}
                  icon={w.key === 'PC' ? <Monitor size={13} /> : <Bot size={13} />}>
              {w.name}
            </Pick>)
        })}
      </Group>
    </div>
  )
}

/** One line per chosen thing, for the Review step and booking pages. */
export function equipmentSummary(v: BookingEquipmentChoice, opts?: EquipmentOptions | null): string[] {
  const out: string[] = []
  for (const id of v.bin_asset_ids) out.push(opts?.bin_items.find(i => i.id === id)?.name ?? `Item #${id}`)
  for (const c of v.consumables)
    out.push(`${opts?.consumables.find(o => o.id === c.inventory_bin_id)?.name ?? `Consumable #${c.inventory_bin_id}`} × ${c.quantity}`)
  for (const k of v.workstations)
    out.push(opts?.workstations.find(w => w.key === k)?.name ?? k)
  return out
}

function Group({ icon, title, sub, children }: { icon: React.ReactNode; title: string; sub: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="flex items-center gap-2 text-[13px] font-medium text-white"><span className="text-accent-300">{icon}</span>{title}</div>
      <div className="text-[12px] text-slate-400 mb-2">{sub}</div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </section>)
}

function Pick({ selected, disabled, onClick, note, icon, children }: {
  selected: boolean; disabled?: boolean; onClick: () => void; note?: string; icon?: React.ReactNode; children: React.ReactNode
}) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} aria-pressed={selected}
      className={`btn btn-sm border inline-flex items-center gap-1.5 ${selected
        ? 'border-accent-400 bg-accent-500/15 text-accent-100'
        : 'border-ink-500 text-slate-300 hover:text-white'} disabled:opacity-45 disabled:cursor-not-allowed`}>
      {selected ? <Check size={13} /> : icon}
      {children}
      {note && <span className="text-[11px] text-warn-soft">· {note}</span>}
    </button>)
}

function Empty({ children }: { children: React.ReactNode }) {
  return <span className="text-[12px] text-slate-500 self-center">{children}</span>
}
