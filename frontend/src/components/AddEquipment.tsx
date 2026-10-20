/**
 * Add equipment (owner, 2026-10-18): first choose WHICH of the lab's systems it belongs to, then a
 * short form that creates it in that system - nothing is kept in a separate list.
 *
 *   Physical environment  new sensor node (device)  or  a sensor on the existing node (register)
 *   PC / Robot            device record (monitoring, key issued later)  +  register entry
 *   Consumables           parts into an existing bin (its scale books the refill)  or  a new bin
 *   Reusables             register item kept in the reusable bin (its NFC tag is linked at the bin)
 *   Other instrument      register entry
 *
 * The server checks every permission (devices: administrators).
 */
import { FormEvent, ReactNode, useEffect, useState } from 'react'
import { Bot, Boxes, Monitor, Package, Thermometer, Wrench } from 'lucide-react'
import { InventoryBin, Lab, api } from '../lib/api'
import { ErrorBanner, Field, Modal } from './ui'

type Kind = 'environment' | 'pc' | 'robot' | 'consumable' | 'reusable' | 'other'
export type EquipmentTab = 'environment' | 'noncons' | 'consumables' | 'reusables' | 'register'
const TAB_OF: Record<Kind, EquipmentTab> = {
  environment: 'environment', pc: 'noncons', robot: 'noncons', consumable: 'consumables',
  reusable: 'reusables', other: 'register',
}
const KINDS: { kind: Kind; title: string; sub: string; icon: ReactNode }[] = [
  { kind: 'environment', title: 'Physical environment', sub: 'Sensor node or a sensor (temperature, gas, flame...)', icon: <Thermometer size={18} /> },
  { kind: 'pc', title: 'PC', sub: 'Lab workstation (agent after IT approval)', icon: <Monitor size={18} /> },
  { kind: 'robot', title: 'Robot', sub: 'Arm or cell, read-only monitoring', icon: <Bot size={18} /> },
  { kind: 'consumable', title: 'Consumables', sub: 'Parts into an existing bin, or a new bin', icon: <Package size={18} /> },
  { kind: 'reusable', title: 'Reusables', sub: 'Tool kept in the reusable bin (Arduino, breadboard...)', icon: <Boxes size={18} /> },
  { kind: 'other', title: 'Other instrument', sub: 'Anything else for the equipment register', icon: <Wrench size={18} /> },
]

export default function AddEquipment({ onClose, onSaved }: {
  onClose: () => void; onSaved: (tab: EquipmentTab) => void
}) {
  const [kind, setKind] = useState<Kind | null>(null)
  const [labs, setLabs] = useState<Lab[]>([])
  const [bins, setBins] = useState<InventoryBin[]>([])
  const [envMode, setEnvMode] = useState<'node' | 'sensor'>('sensor')
  const [binMode, setBinMode] = useState<'existing' | 'new'>('existing')
  const [f, setF] = useState({ lab_id: '', name: '', asset_tag: '', device_uid: '', ip: '', serial: '', notes: '',
                               bin_id: '', code: '', reorder: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState('')
  useEffect(() => {
    api.labs().then(l => { setLabs(l); if (l.length === 1) setF(v => ({ ...v, lab_id: String(l[0].id) })) }).catch(() => {})
    api.inventoryBins().then(setBins).catch(() => {})
  }, [])
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF(v => ({ ...v, [k]: e.target.value }))
  const lab = Number(f.lab_id)

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!kind) return
    setBusy(true); setError('')
    const asset = (category: string, binItem = false) => api.createAsset({
      asset_tag: f.asset_tag.trim(), name: f.name.trim(), category, lab_id: lab, notes: f.notes,
      serial_number: f.serial.trim() || null, bin_item: binItem })
    try {
      if (kind === 'environment' && envMode === 'node') {
        await api.createDevice({ device_uid: f.device_uid.trim(), name: f.name.trim(), device_type: 'SENSOR_NODE',
                                 lab_id: lab, ip_address: f.ip.trim() || null })
      } else if (kind === 'environment') {
        await asset('Environment sensor')
      } else if (kind === 'pc' || kind === 'robot') {
        await api.createDevice({ device_uid: f.device_uid.trim(), name: f.name.trim(),
                                 device_type: kind === 'pc' ? 'PC' : 'ROBOT', lab_id: lab, ip_address: f.ip.trim() || null })
        if (f.asset_tag.trim()) await asset(kind === 'pc' ? 'PC' : 'Robot')
      } else if (kind === 'consumable' && binMode === 'new') {
        await api.createBin({ code: f.code.trim(), lab_id: lab, item_name: f.name.trim(),
                              reorder_qty: f.reorder ? Number(f.reorder) : null })
      } else if (kind === 'consumable') {
        setDone('Put the parts into the bin: its scale books the refill by itself and the count goes up. '
          + 'If the count is wrong afterwards, correct it on the Consumables tab.')
        setBusy(false)
        return
      } else if (kind === 'reusable') {
        await asset('Reusable', true)
      } else {
        await asset('Instrument')
      }
      onSaved(TAB_OF[kind])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
    } finally { setBusy(false) }
  }

  const labField = <Field label="Laboratory"><select className="input" required value={f.lab_id} onChange={set('lab_id')}>
    <option value="">Choose…</option>
    {labs.map(l => <option key={l.id} value={l.id}>{l.code} · {l.name}</option>)}</select></Field>
  const nameField = (label: string, hint?: string) => <Field label={label} hint={hint}>
    <input className="input" required minLength={2} value={f.name} onChange={set('name')} /></Field>
  const tagField = (required: boolean) => <Field label={required ? 'Asset tag' : 'Asset tag (optional - also adds it to the register)'}
    hint="Unique, e.g. PC-LAB01-12"><input className="input" required={required} value={f.asset_tag} onChange={set('asset_tag')} /></Field>
  const uidField = (hint: string) => <Field label="Device ID" hint={hint}>
    <input className="input mono" required pattern="[A-Za-z0-9_\-]{3,48}" value={f.device_uid} onChange={set('device_uid')} /></Field>
  const ipField = <Field label="IP address (optional)"><input className="input mono" value={f.ip} onChange={set('ip')} placeholder="192.168.1.x" /></Field>

  return (
    <Modal open onClose={onClose} title={kind ? `Add · ${KINDS.find(k => k.kind === kind)!.title}` : 'Add equipment - which system?'}>
      {!kind ? (
        <div className="grid sm:grid-cols-2 gap-2.5">
          {KINDS.map(k => (
            <button key={k.kind} type="button" onClick={() => setKind(k.kind)}
              className="text-left rounded-xl border border-ink-600 hover:border-accent-400/70 hover:bg-accent-500/10 p-3 flex gap-3 transition-colors">
              <span className="grid place-items-center w-9 h-9 shrink-0 rounded-lg bg-ink-700/70 text-accent-300">{k.icon}</span>
              <span className="min-w-0"><span className="block text-[13.5px] font-medium text-white">{k.title}</span>
                <span className="block text-[11.5px] text-slate-400">{k.sub}</span></span>
            </button>))}
        </div>
      ) : (
        <form onSubmit={save} className="space-y-3">
          {error && <ErrorBanner message={error} />}
          {done && <p className="rounded-lg border border-ok/40 bg-ok/10 p-3 text-[13px] text-ok-soft">{done}</p>}
          {kind === 'environment' && <>
            <div className="flex gap-2 text-[12.5px]">
              {(['sensor', 'node'] as const).map(m => <button key={m} type="button" onClick={() => setEnvMode(m)}
                className={`px-2.5 py-1 rounded-md border ${envMode === m ? 'border-accent-400/70 bg-accent-500/15 text-white' : 'border-ink-600 text-slate-300'}`}>
                {m === 'sensor' ? 'A sensor on the existing node' : 'A new sensor node (ESP32)'}</button>)}
            </div>
            {labField}
            {envMode === 'node' ? <>{nameField('Name', 'e.g. Environment node 2')}{uidField('e.g. ENV_LAB02 - the firmware must use the same ID')}{ipField}
              <p className="text-[11.5px] text-slate-500">Then issue its own key on System Devices and put it in the node's firmware.</p></>
              : <>{nameField('Sensor', 'e.g. MQ-135 air quality')}{tagField(true)}
              <p className="text-[11.5px] text-slate-500">Its readings appear once the node's firmware reports it.</p></>}
          </>}
          {(kind === 'pc' || kind === 'robot') && <>
            {labField}{nameField('Name', kind === 'pc' ? 'e.g. PC-12' : 'e.g. UR3e (physical)')}
            {uidField(kind === 'pc' ? 'e.g. PC_LAB01_12 - the PC agent uses this ID' : 'e.g. UR3E_01 - the collector uses this ID')}
            {ipField}{tagField(false)}
            <p className="text-[11.5px] text-slate-500">{kind === 'pc'
              ? 'The PC shows as offline until its agent is installed (university IT approval).'
              : 'Monitoring only: no robot command is ever enabled by adding it.'}</p>
          </>}
          {kind === 'consumable' && <>
            <div className="flex gap-2 text-[12.5px]">
              {(['existing', 'new'] as const).map(m => <button key={m} type="button" onClick={() => { setBinMode(m); setDone('') }}
                className={`px-2.5 py-1 rounded-md border ${binMode === m ? 'border-accent-400/70 bg-accent-500/15 text-white' : 'border-ink-600 text-slate-300'}`}>
                {m === 'existing' ? 'Into a bin we have' : 'A new bin'}</button>)}
            </div>
            {binMode === 'existing'
              ? <Field label="Bin"><select className="input" required value={f.bin_id} onChange={set('bin_id')}>
                  <option value="">Choose…</option>
                  {bins.map(b => <option key={b.id} value={b.id}>{b.code} · {b.item_name}</option>)}</select></Field>
              : <>{labField}{nameField('What it holds', 'e.g. 220 Ohm resistors')}
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Bin code" hint="e.g. BIN-R220"><input className="input mono" required value={f.code} onChange={set('code')} /></Field>
                    <Field label="Reorder below (optional)"><input className="input" type="number" min={0} value={f.reorder} onChange={set('reorder')} /></Field>
                  </div>
                  <p className="text-[11.5px] text-slate-500">Then weigh it: tare the empty bin and the mass of one part on the Consumables tab.</p></>}
          </>}
          {kind === 'reusable' && <>{labField}{nameField('Name', 'e.g. Arduino Uno #4')}{tagField(true)}
            <p className="text-[11.5px] text-slate-500">Stick an NFC tag on it; scanning it at the reusable bin links the tag.</p></>}
          {kind === 'other' && <>{labField}{nameField('Name')}{tagField(true)}
            <Field label="Serial number (optional)"><input className="input mono" value={f.serial} onChange={set('serial')} /></Field>
            <Field label="Notes (optional)"><textarea className="input" value={f.notes} onChange={set('notes')} /></Field></>}
          <div className="flex justify-between gap-2 pt-2">
            <button type="button" className="btn-quiet" onClick={() => { setKind(null); setError(''); setDone('') }}>Back</button>
            <span className="flex gap-2">
              <button type="button" className="btn-quiet" onClick={onClose}>{done ? 'Close' : 'Cancel'}</button>
              {!done && <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : kind === 'consumable' && binMode === 'existing' ? 'Continue' : 'Add'}</button>}
            </span>
          </div>
        </form>
      )}
    </Modal>
  )
}
