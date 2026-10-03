/**
 * Security camera (staff): the fixed camera in a lab corner, analysed on the
 * laptop by tools/security_vision.
 *
 *  Live   - the annotated view: every person boxed, named only when the door
 *           makes it certain (else "Unknown"); people seen vs entered; the
 *           state of each watched item.
 *  Boxes  - draw a box around each fixed item (PC, robot) and the door area.
 *  Events - what the camera flagged, with its snapshot; staff acknowledge.
 *
 * The camera's opinion is something for staff to check, never a decision:
 * nothing here locks, unlocks or moves anything.
 */
import { MouseEvent as RMouseEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Camera, Check, DoorOpen, Eye, ShieldAlert, Square, Trash2, Users, Video } from 'lucide-react'
import { SecurityCamera, SecurityEvent, SecurityZone, SecurityZoneIn, api, fetchBlob } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import LiveCameraFeed from '../components/LiveCameraFeed'
import { Chip, EmptyState, ErrorBanner, PageHeader, Spinner, Tabs } from '../components/ui'

type Tab = 'live' | 'boxes' | 'events'
const ZONE_TONE = { OK: 'ok', IN_USE: 'info', CHANGED: 'bad', MOTION: 'warn', LEARNING: 'idle' } as const
const ROLE = { ADMIN: 'Admin', LAB_STAFF: 'Staff', STUDENT: 'Student' } as Record<string, string>

export default function Security() {
  const [cams, setCams] = useState<SecurityCamera[] | null>(null)
  const [camId, setCamId] = useState<number | null>(null)
  const [tab, setTab] = useState<Tab>('live')
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.securityCameras().then(c => {
      setCams(c)
      setCamId(id => id ?? c[0]?.device_id ?? null)
    }).catch(e => setError(e.message))
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 2000)
    return () => window.clearInterval(t)
  }, [load])

  const cam = cams?.find(c => c.device_id === camId) ?? null

  return (
    <div>
      <PageHeader eyebrow="Security" title="Security camera"
        sub="A fixed camera in each lab corner: people seen and named from the door entries, and the fixed equipment watched." />
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {cams === null ? <Spinner label="Loading cameras" /> : !cams.length ? (
        <EmptyState icon={<Video size={20} />} title="No security camera yet"
          detail="Start the camera service on the laptop (tools/security_vision - see its README). It registers here on its first report. Until the Mercusys camera arrives, it can use the laptop webcam." />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3 mb-4">
            {cams.length > 1 && (
              <select className="input w-auto" value={camId ?? ''} onChange={e => setCamId(Number(e.target.value))}>
                {cams.map(c => <option key={c.device_id} value={c.device_id}>{c.lab_code} · {c.name}</option>)}
              </select>)}
            <Tabs<Tab> id="security" value={tab} onChange={setTab} tabs={[
              { key: 'live', label: 'Live' }, { key: 'boxes', label: 'Equipment & door boxes' },
              { key: 'events', label: 'Events', count: cam?.open_events || undefined }]} />
          </div>
          {cam && tab === 'live' && <Live cam={cam} onChange={load} />}
          {cam && tab === 'boxes' && <Boxes cam={cam} />}
          {cam && tab === 'events' && <Events cam={cam} onChange={load} />}
        </>
      )}
    </div>
  )
}

function Live({ cam, onChange }: { cam: SecurityCamera; onChange: () => void }) {
  const live = cam.online === true && cam.source_ok !== false
  const extra = live && (cam.people ?? 0) > cam.inside
  async function accept(zoneId: number) {
    await api.acceptSecurityZone(cam.device_id, zoneId).catch(() => {})
    onChange()
  }
  return (
    <div className="grid xl:grid-cols-[1fr_340px] gap-4">
      <LiveCameraFeed deviceId={cam.device_id} intervalMs={120} fit="contain"
                      className="rounded-2xl border border-ink-600/70 aspect-video" />
      <div className="space-y-3">
        <div className="card p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Camera size={15} className="text-accent-300" />
            <span className="font-semibold text-white">{cam.lab_code} · {cam.name}</span>
            <Chip tone={live ? 'ok' : 'bad'} dot className="ml-auto">{live ? 'live' : cam.online ? 'no picture' : 'offline'}</Chip>
          </div>
          <div className="text-[12px] text-slate-400">
            {cam.fps ? `Analysing ${cam.fps} times a second` : 'Not analysing'} · last report{' '}
            {cam.last_seen_at ? relative(cam.last_seen_at) : 'never'}</div>
        </div>
        <div className={`card p-4 ${extra ? 'border-bad/60' : ''}`}>
          <div className="label mb-2 flex items-center gap-1.5"><Users size={13} /> People</div>
          <div className="flex items-baseline gap-4">
            <div><span className="text-3xl font-extrabold text-white tnum">{live ? cam.people ?? 0 : '–'}</span>
              <span className="ml-1.5 text-slate-400 text-[12.5px]">seen</span></div>
            <div><span className="text-3xl font-extrabold text-slate-200 tnum">{cam.inside}</span>
              <span className="ml-1.5 text-slate-400 text-[12.5px]">entered at the door</span></div>
          </div>
          {extra && <p className="mt-2 text-[12.5px] text-bad-soft font-semibold">
            More people than entered: someone may have followed another person in.</p>}
          <ul className="mt-3 space-y-1 text-[13px]">
            {cam.named.map(n => (
              <li key={n.label} className="flex items-center gap-2">
                <span className="mono text-[11px] text-slate-400 w-14">{n.label}</span>
                <span className="text-white">{n.name}</span>
                {n.role && <Chip tone={n.role === 'STUDENT' ? 'ok' : n.role === 'ADMIN' ? 'violet' : 'info'}>{ROLE[n.role]}</Chip>}
              </li>))}
            {(cam.unknown ?? 0) > 0 && live && (
              <li className="text-warn-soft">{cam.unknown} person{cam.unknown === 1 ? '' : 's'} not named (Unknown)</li>)}
            {!cam.named.length && !(cam.unknown ?? 0) && <li className="text-slate-500">Nobody in view</li>}
          </ul>
          <p className="mt-2 text-[11px] text-slate-500">A name is shown only when the door makes it certain;
            everyone else stays Unknown rather than guessed.</p>
        </div>
        <div className="card p-4">
          <div className="label mb-2 flex items-center gap-1.5"><Eye size={13} /> Watched equipment</div>
          {!cam.zones.length ? <p className="text-[12.5px] text-slate-500">No boxes yet - draw them under Equipment & door boxes.</p> : (
            <ul className="space-y-1.5 text-[13px]">
              {cam.zones.map(z => (
                <li key={z.id} className="flex items-center gap-2">
                  <span className="text-slate-100 flex-1 truncate">{z.name}</span>
                  <Chip tone={ZONE_TONE[z.status] ?? 'idle'} dot>{z.status.toLowerCase().replace('_', ' ')}</Chip>
                  {(z.status === 'CHANGED' || z.status === 'MOTION') && (
                    <button className="btn-ghost btn-sm" title="The new position/look is fine - relearn it"
                            onClick={() => accept(z.id)}><Check size={13} /> Accept</button>)}
                </li>))}
            </ul>)}
        </div>
      </div>
    </div>
  )
}

// --------------------------------------------------------------- boxes ---
type Rect = { x: number; y: number; w: number; h: number }

function Boxes({ cam }: { cam: SecurityCamera }) {
  const [zones, setZones] = useState<SecurityZone[]>([])
  const [ratio, setRatio] = useState(16 / 9)
  const [draft, setDraft] = useState<Rect | null>(null)
  const [editing, setEditing] = useState<SecurityZone | null>(null)
  const [form, setForm] = useState({ name: '', kind: 'EQUIPMENT' as 'EQUIPMENT' | 'DOOR', alert_on_motion: true })
  const [error, setError] = useState('')
  const start = useRef<{ x: number; y: number } | null>(null)
  const area = useRef<HTMLDivElement>(null)

  const load = useCallback(() => {
    api.securityZones(cam.device_id).then(setZones).catch(e => setError(e.message))
  }, [cam.device_id])
  useEffect(load, [load])

  function point(e: RMouseEvent) {
    const r = area.current!.getBoundingClientRect()
    return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
             y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) }
  }
  function down(e: RMouseEvent) { start.current = point(e); setDraft(null) }
  function move(e: RMouseEvent) {
    if (!start.current) return
    const p = point(e), s = start.current
    setDraft({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) })
  }
  function up() { start.current = null }

  async function save() {
    if (!draft && !editing) return
    const r = draft ?? editing!
    const body: SecurityZoneIn = { name: form.name.trim(), kind: form.kind, asset_id: editing?.asset_id ?? null,
      alert_on_motion: form.alert_on_motion, x: r.x, y: r.y, w: r.w, h: r.h }
    try {
      if (editing) await api.updateSecurityZone(cam.device_id, editing.id, body)
      else await api.addSecurityZone(cam.device_id, body)
      setDraft(null); setEditing(null); setForm({ name: '', kind: 'EQUIPMENT', alert_on_motion: true })
      load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save') }
  }
  async function remove(z: SecurityZone) {
    if (!window.confirm(`Delete the box "${z.name}"?`)) return
    await api.deleteSecurityZone(cam.device_id, z.id).catch(e => setError(e.message))
    if (editing?.id === z.id) setEditing(null)
    load()
  }
  function edit(z: SecurityZone) {
    setEditing(z); setDraft(null)
    setForm({ name: z.name, kind: z.kind, alert_on_motion: z.alert_on_motion })
  }

  const pct = (v: number) => `${v * 100}%`
  const shown = draft ?? (editing ? { x: editing.x, y: editing.y, w: editing.w, h: editing.h } : null)
  const canSave = !!shown && shown.w > 0.02 && shown.h > 0.02 && form.name.trim().length > 0

  return (
    <div className="grid xl:grid-cols-[1fr_340px] gap-4">
      <div>
        <div ref={area} className="relative rounded-2xl overflow-hidden border border-ink-600/70 cursor-crosshair select-none"
             style={{ aspectRatio: ratio }} onMouseDown={down} onMouseMove={move} onMouseUp={up} onMouseLeave={up}>
          <LiveCameraFeed deviceId={cam.device_id} raw intervalMs={1000} className="!absolute inset-0"
                          onFrame={(w, h) => setRatio(w / h)} />
          {zones.filter(z => z.id !== editing?.id).map(z => (
            <div key={z.id} className={`absolute border-2 ${z.kind === 'DOOR' ? 'border-slate-300 border-dashed' : 'border-accent-400'}`}
                 style={{ left: pct(z.x), top: pct(z.y), width: pct(z.w), height: pct(z.h) }}>
              <span className="absolute -top-0 left-0 px-1.5 py-0.5 text-[11px] font-semibold bg-black/70 text-white">{z.name}</span>
            </div>))}
          {shown && <div className="absolute border-2 border-warn bg-warn/10"
                         style={{ left: pct(shown.x), top: pct(shown.y), width: pct(shown.w), height: pct(shown.h) }} />}
        </div>
        <p className="mt-2 text-[12px] text-slate-400">Drag on the picture to draw a box tightly around one fixed item
          (a PC, a robot), or around the door so people walking in get the name of the person who just entered.
          A box is learnt the first time nobody is in it.</p>
      </div>
      <div className="space-y-3">
        {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
        <div className="card p-4 space-y-3">
          <div className="label">{editing ? `Edit "${editing.name}"` : 'New box'}</div>
          {!shown && <p className="text-[12.5px] text-slate-400">Draw a box on the picture first.</p>}
          <input className="input w-full" placeholder="Name, e.g. PC-01 or UR5e" maxLength={64}
                 value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          <div className="flex gap-2">
            <button type="button" className={`btn-sm flex-1 ${form.kind === 'EQUIPMENT' ? 'btn-primary' : 'btn-ghost'}`}
                    onClick={() => setForm({ ...form, kind: 'EQUIPMENT' })}><Square size={13} /> Equipment</button>
            <button type="button" className={`btn-sm flex-1 ${form.kind === 'DOOR' ? 'btn-primary' : 'btn-ghost'}`}
                    onClick={() => setForm({ ...form, kind: 'DOOR' })}><DoorOpen size={13} /> Door area</button>
          </div>
          {form.kind === 'EQUIPMENT' && (
            <label className="flex items-center gap-2 text-[12.5px] text-slate-300">
              <input type="checkbox" className="accent-sky-500" checked={form.alert_on_motion}
                     onChange={e => setForm({ ...form, alert_on_motion: e.target.checked })} />
              Alert on movement with nobody at it (turn off for a robot that runs programs alone)</label>)}
          <div className="flex gap-2">
            {(editing || draft) && <button className="btn-ghost btn-sm" onClick={() => { setEditing(null); setDraft(null) }}>Cancel</button>}
            <button className="btn-primary btn-sm flex-1" disabled={!canSave} onClick={save}>
              {editing ? 'Save changes' : 'Add box'}</button>
          </div>
        </div>
        <div className="card p-4">
          <div className="label mb-2">Boxes ({zones.length})</div>
          {!zones.length ? <p className="text-[12.5px] text-slate-500">None yet.</p> : (
            <ul className="space-y-1.5 text-[13px]">
              {zones.map(z => (
                <li key={z.id} className="flex items-center gap-2">
                  {z.kind === 'DOOR' ? <DoorOpen size={14} className="text-slate-400" /> : <Square size={14} className="text-accent-300" />}
                  <button className="text-left text-slate-100 hover:underline flex-1 truncate" onClick={() => edit(z)}>{z.name}</button>
                  {z.kind === 'EQUIPMENT' && !z.alert_on_motion && <span className="text-[11px] text-slate-500">no motion alert</span>}
                  <button className="text-slate-500 hover:text-bad-soft" aria-label={`Delete ${z.name}`} onClick={() => remove(z)}>
                    <Trash2 size={14} /></button>
                </li>))}
            </ul>)}
        </div>
      </div>
    </div>
  )
}

// -------------------------------------------------------------- events ---
function Snapshot({ id }: { id: number }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let url: string | null = null
    fetchBlob(`/security/events/${id}/snapshot.jpg`).then(b => { url = URL.createObjectURL(b); setSrc(url) }).catch(() => {})
    return () => { if (url) URL.revokeObjectURL(url) }
  }, [id])
  return src ? <a href={src} target="_blank" rel="noreferrer">
    <img src={src} alt="Snapshot" className="w-44 aspect-video object-cover rounded-lg border border-ink-600/70" /></a>
    : <div className="w-44 aspect-video rounded-lg bg-ink-900 border border-ink-600/70" />
}

function Events({ cam, onChange }: { cam: SecurityCamera; onChange: () => void }) {
  const [events, setEvents] = useState<SecurityEvent[] | null>(null)
  const load = useCallback(() => {
    api.securityEvents({ lab_id: cam.lab_id, limit: 60 }).then(setEvents).catch(() => setEvents([]))
  }, [cam.lab_id])
  useEffect(load, [load])
  useLiveMessages(m => { if (m.type === 'staff' && m.kind === 'security_event') load() })
  async function ack(id: number) {
    await api.ackSecurityEvent(id).catch(() => {})
    load(); onChange()
  }
  if (!events) return <Spinner label="Loading events" />
  if (!events.length) return <EmptyState compact icon={<ShieldAlert size={18} />} title="Nothing flagged"
    detail="Events appear here with a snapshot: more people than entered, a person when nobody entered, equipment moved, movement at equipment with nobody there." />
  return (
    <ul className="space-y-3">
      {events.map(e => (
        <li key={e.id} className={`card p-3 flex gap-3 ${e.acknowledged_at ? 'opacity-60' : ''}`}>
          {e.has_snapshot ? <Snapshot id={e.id} /> : <div className="w-44 aspect-video rounded-lg bg-ink-900 grid place-items-center text-[11px] text-slate-500">no snapshot</div>}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className={`font-semibold ${e.kind === 'PERSON_NO_ENTRY' ? 'text-bad-soft' : 'text-warn-soft'}`}>
                {e.title}{e.zone_name ? `: ${e.zone_name}` : ''}</span>
              <span className="ml-auto text-[12px] text-slate-500 shrink-0">{relative(e.created_at)}</span>
            </div>
            <p className="text-[12.5px] text-slate-300 mt-0.5">{e.detail}</p>
            <p className="text-[11.5px] text-slate-500 mt-0.5">{e.people_seen} seen · {e.people_inside} entered at the door</p>
            <div className="mt-2">
              {e.acknowledged_at
                ? <span className="text-[12px] text-slate-400">Checked by {e.acknowledged_by} · {relative(e.acknowledged_at)}</span>
                : <button className="btn-ghost btn-sm" onClick={() => ack(e.id)}><Check size={13} /> Checked</button>}
            </div>
          </div>
        </li>))}
      <li className="text-[11.5px] text-slate-500">Snapshots of checked events are deleted after 30 days. A camera can be wrong: look at the snapshot before acting.</li>
    </ul>
  )
}
