import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bot, Camera, Cpu, DoorClosed, Fingerprint, Lock, Monitor, Plus, Radio, Server, Thermometer, Wrench,
  Video,
} from 'lucide-react'
import { Device, Lab, api } from '../lib/api'
import { isAdmin, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import {
  Chip, Dot, EmptyState, ErrorBanner, Field, Modal, Notice, PageHeader, Skeleton, StateDot,
} from '../components/ui'
import { categoryMeta } from '../components/labArt'

const TYPE: Record<Device['device_type'], { label: string; icon: JSX.Element }> = {
  MASTER_CONTROLLER: { label: 'Master ESP32 controller', icon: <Cpu size={18} /> },
  CAMERA: { label: 'ESP32-CAM entry camera', icon: <Camera size={18} /> },
  FACE_SERVER: { label: 'Face recognition server', icon: <Server size={18} /> },
  SENSOR_NODE: { label: 'Sensor node', icon: <Thermometer size={18} /> },
  SECURITY_CAMERA: { label: 'Security camera', icon: <Video size={18} /> },
  ROBOT: { label: 'Robot (read-only monitoring)', icon: <Bot size={18} /> },
  PC: { label: 'Lab PC', icon: <Monitor size={18} /> },
  OTHER: { label: 'Other device', icon: <Cpu size={18} /> },
}
// A device type this page does not know yet still shows (never a crash).
const typeOf = (t: string) => TYPE[t as Device['device_type']] ?? { label: t.replace(/_/g, ' ').toLowerCase(), icon: <Cpu size={18} /> }

export default function Devices() {
  const { user } = useAuth()
  const [devices, setDevices] = useState<Device[] | null>(null)
  const [labs, setLabs] = useState<Lab[]>([])
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => api.devices().then(setDevices)
    .catch(e => { setError(e.message); setDevices([]) }), [])
  useEffect(() => {
    load()
    api.labs().then(setLabs).catch(() => {})
    const t = window.setInterval(load, 15000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => {
    if (m.type === 'access_event' && m.event.event_type.startsWith('DEVICE')) load()
    if (m.type === 'door_state') load()
  })

  const byLab = useMemo(() => {
    const m = new Map<number, Device[]>()
    // Simulations are not lab devices: they stay recorded but are not listed here.
    ;(devices ?? []).filter(d => !(d.component_state as { demo?: boolean } | null)?.demo)
      .forEach(d => m.set(d.lab_id, [...(m.get(d.lab_id) ?? []), d]))
    return [...m.entries()]
  }, [devices])

  const online = (devices ?? []).filter(d => d.state === 'ONLINE').length
  const reporting = (devices ?? []).filter(d => d.state !== 'NO_DATA').length

  return (
    <div>
      <PageHeader eyebrow="Connected devices" title="System Devices"
        sub="Each laboratory's access hardware, as last reported by the devices themselves."
        actions={isAdmin(user) ? <button className="btn-primary" onClick={() => setAdding(true)}>
          <Plus size={16} />Register device</button> : undefined} />
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      <div className="mb-5"><Notice>
        Liveness comes from heartbeats: a device silent for more than 90 seconds is offline, and
        an outage raises an alert. A device that has never reported shows <b>no data</b> - it is
        not assumed healthy or broken. {devices && <>Right now {online} of {devices.length} devices
        are online and {reporting} have ever reported.</>}
      </Notice></div>

      {devices === null ? <Skeleton className="h-64" /> : byLab.length === 0 ? (
        <div className="card"><EmptyState icon={<Cpu size={20} />} title="No devices registered"
          detail="A master controller registers itself with its first heartbeat." /></div>
      ) : byLab.map(([labId, list]) => {
        const lab = labs.find(l => l.id === labId)
        const meta = categoryMeta(lab?.category)
        const master = list.find(d => d.device_type === 'MASTER_CONTROLLER')
        const comp = (k: string) => {
          const v = master?.component_state?.[k]
          return typeof v === 'boolean' ? v : null
        }
        return (
          <section key={labId} className="card overflow-hidden mb-5">
            <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-ink-600">
              <Link to={`/labs/${labId}`} className="flex items-center gap-3 group">
                <span className="grid place-items-center w-9 h-9 rounded-xl border border-ink-500"
                      style={{ color: meta.hue, background: `${meta.hue}14` }}>{meta.icon}</span>
                <div>
                  <div className="text-[15px] text-white font-medium group-hover:text-accent-200">{lab?.name ?? `Lab ${labId}`}</div>
                  <div className="mono text-slate-400">{list[0].lab_code}</div>
                </div>
              </Link>
              <span className="text-[12.5px] text-slate-300">
                {list.filter(d => d.state === 'ONLINE').length} / {list.length} online</span>
            </div>
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-px bg-ink-600/50">
              {list.map(d => (
                <div key={d.id} className="bg-ink-800 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className={`grid place-items-center w-10 h-10 rounded-xl border ${d.state === 'ONLINE'
                        ? 'border-ok/40 bg-ok/10 text-ok-soft' : d.state === 'OFFLINE'
                        ? 'border-bad/40 bg-bad/10 text-bad-soft' : 'border-ink-500 bg-ink-700/60 text-slate-400'}`}>
                        {typeOf(d.device_type).icon}</span>
                      <div className="min-w-0">
                        <div className="text-[14px] text-white truncate">{d.name}</div>
                        <div className="text-[11.5px] text-slate-400">{typeOf(d.device_type).label}</div>
                      </div>
                    </div>
                    <Chip tone={d.state === 'ONLINE' ? 'ok' : d.state === 'OFFLINE' ? 'bad' : 'idle'} dot>
                      {d.state === 'NO_DATA' ? 'No data' : d.state.toLowerCase()}</Chip>
                  </div>
                  {d.state_note && <p className={`mt-2 text-[12px] ${d.state === 'ONLINE' ? 'text-slate-400' : 'text-warn-soft'}`}>{d.state_note}</p>}
                  <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-[12.5px]">
                    <div><dt className="text-slate-500">Last heartbeat</dt>
                      <dd className="text-slate-200">{d.last_seen_at ? relative(d.last_seen_at)
                        : d.seconds_since_seen != null ? `${d.seconds_since_seen}s ago (via door)` : 'Never'}</dd></div>
                    <div><dt className="text-slate-500">Address</dt>
                      <dd className="mono text-slate-200">{d.ip_address ?? <span className="text-warn-soft font-sans">Not configured</span>}</dd></div>
                    <div><dt className="text-slate-500">Device ID</dt>
                      <dd className="mono text-slate-200 truncate">{d.device_uid}</dd></div>
                    <div><dt className="text-slate-500">Firmware</dt>
                      <dd className="text-slate-200">{d.firmware_version ?? '—'}</dd></div>
                  </dl>
                  <div className="mt-4 flex items-center justify-between">
                    <Link to={`/issues/new?lab=${d.lab_id}&device=${d.id}`} className="text-xs link inline-flex items-center gap-1">
                      <Wrench size={12} />Report a problem</Link>
                    {isAdmin(user) && <DeviceKey id={d.id} own={!!d.has_own_key} />}
                  </div>
                </div>
              ))}
            </div>
            {master && (
              <div className="px-5 py-4 border-t border-ink-600">
              {master.state !== 'ONLINE' && master.last_seen_at && (
                <div className="mb-2.5 text-[11.5px] text-slate-500">
                  Last reported {relative(master.last_seen_at)} - the controller is offline, so these are not live.</div>
              )}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <Comp icon={<DoorClosed size={14} />} label="Door sensor" state={master.door_closed} stale={master.state !== 'ONLINE'} 
                      labels={['Closed', 'Open']} />
                <Comp icon={<Radio size={14} />} label="RFID reader" stale={master.state !== 'ONLINE'} state={comp('rfid')} labels={['Ready', 'Fault']} />
                <Comp icon={<Fingerprint size={14} />} label="Fingerprint" stale={master.state !== 'ONLINE'} state={comp('fingerprint')} labels={['Ready', 'Fault']} />
                <Comp icon={<Camera size={14} />} label="Camera" stale={master.state !== 'ONLINE'} state={comp('camera')} labels={['Ready', 'Fault']} />
                <Comp icon={<Lock size={14} />} label="Relay" stale={master.state !== 'ONLINE'} state={comp('relay_locked')} labels={['Locked', 'Unlocked']} />
              </div>
              </div>
            )}
          </section>
        )
      })}

      {adding && <AddDevice labs={labs} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); load() }} />}
    </div>
  )
}

function Comp({ icon, label, state, labels, stale }: {
  icon: JSX.Element; label: string; state: boolean | null; labels: [string, string]
  /** The value is the last report from a controller that is now offline. */
  stale?: boolean
}) {
  return (
    <div className="well px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[11.5px] text-slate-400">{icon}{label}</div>
      <div className="mt-1">{stale && state !== null ? (
        <span className="inline-flex items-center gap-2 text-xs text-slate-400">
          <Dot tone="idle" />{state ? labels[0] : labels[1]}
          <span className="text-[10.5px] text-slate-500">(last reported)</span></span>
      ) : <StateDot state={state} labels={labels} size="sm" unknown="Not reported" />}</div>
    </div>
  )
}

function AddDevice({ labs, onClose, onSaved }: { labs: Lab[]; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ device_uid: '', name: '', device_type: 'MASTER_CONTROLLER', lab_id: '', ip_address: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await api.createDevice({ ...f, lab_id: Number(f.lab_id), ip_address: f.ip_address || null })
      onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed') } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title="Register device">
      <form onSubmit={save} className="space-y-3">
        {error && <ErrorBanner message={error} />}
        <Field label="Laboratory"><select className="input" required value={f.lab_id}
          onChange={e => setF({ ...f, lab_id: e.target.value })}>
          <option value="">Choose…</option>
          {labs.map(l => <option key={l.id} value={l.id}>{l.code} · {l.name}</option>)}</select></Field>
        <Field label="Type"><select className="input" value={f.device_type}
          onChange={e => setF({ ...f, device_type: e.target.value })}>
          {Object.entries(TYPE).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></Field>
        <Field label="Device ID" hint="Must match DEVICE_ID in the firmware, e.g. MASTER_LAB02">
          <input className="input" required value={f.device_uid}
                 onChange={e => setF({ ...f, device_uid: e.target.value })} /></Field>
        <Field label="Name"><input className="input" required value={f.name}
          onChange={e => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="IP address (optional)"><input className="input" value={f.ip_address}
          onChange={e => setF({ ...f, ip_address: e.target.value })} /></Field>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Register'}</button>
        </div>
      </form>
    </Modal>
  )
}

/** Give one device its own key. Shown once; only its hash is stored. */
function DeviceKey({ id, own }: { id: number; own: boolean }) {
  const [key, setKey] = useState<string | null>(null)
  const [err, setErr] = useState('')
  async function issue() {
    if (own && !window.confirm('Replace the key of this device? The old key stops working at once.')) return
    try { setKey((await api.issueDeviceKey(id)).device_key) }
    catch (e) { setErr(e instanceof Error ? e.message : 'Failed') }
  }
  if (key) {
    return <div className="text-[11.5px] text-right max-w-[60%]">
      <div className="text-warn-soft">Copy now - not shown again:</div>
      <code className="mono text-slate-100 break-all select-all">{key}</code></div>
  }
  return <button className="text-xs link" onClick={issue} title={err || undefined}>
    {own ? 'Own key ✓ · replace' : 'Issue own key'}</button>
}
