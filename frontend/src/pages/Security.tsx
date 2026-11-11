/**
 * Security camera (staff): the fixed camera in a lab corner, analysed on the
 * laptop by tools/security_vision.
 *
 *  All cameras - every lab's camera live, side by side; click one to enlarge it.
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
import { Camera, Check, DoorOpen, Eye, Maximize2, Pencil, ScanSearch, VideoOff, ShieldAlert, Square, Trash2, Users, Video } from 'lucide-react'
import { EquipmentSuggestion, Lab, SecurityCamera, SecurityEvent, SecurityZone, SecurityZoneIn, api, fetchBlob } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import LiveCameraFeed, { LIVE_MS } from '../components/LiveCameraFeed'
import CameraFullScreen from '../components/CameraFullScreen'
import { BoxesToggle } from '../lib/cameraView'
import { RecordButton, RecordingsPanel } from '../components/Recording'
import { isAdmin, useAuth } from '../lib/auth'
import { Chip, EmptyState, ErrorBanner, PageHeader, Spinner, Tabs } from '../components/ui'
import { visibleInterval } from '../lib/visibleInterval'

type Tab = 'wall' | 'live' | 'boxes' | 'events' | 'recordings'
const ZONE_TONE = { OK: 'ok', IN_USE: 'info', CHANGED: 'bad', MOTION: 'warn', LEARNING: 'idle' } as const
const ROLE = { ADMIN: 'Admin', LAB_STAFF: 'Staff', STUDENT: 'Student' } as Record<string, string>

/** The live bar under a lab's cameras (2026-11-11): what each camera sees now, one short line per person, from the
 *  camera service's own data (activity.py) - who, top colour, posture, the mapped box they are near. Scrolls like a
 *  news ticker when it is longer than the bar; a hover pauses it. Updates with the cameras' state (every ~2 s). */
function LiveActivity({ cams, label }: { cams: SecurityCamera[]; label: (c: SecurityCamera) => string }) {
  // 2026-11-11 (owner: "the two cameras must work together"): a NAMED person seen by both cameras is one line
  // ("Cam 1 + Cam 2"), not two. Unnamed people are not merged - two cameras' "Person 3" may be different people.
  const all = cams.flatMap(c => (c.online ? c.activity ?? [] : []).map(a => ({ ...a, cam: label(c), key: `${c.device_id}-${a.track_id}` })))
  const items: typeof all = []
  for (const a of all) {
    const same = a.named && a.label ? items.find(b => b.named && b.label === a.label) : undefined
    if (same) same.cam = `${same.cam} + ${a.cam}`
    else items.push({ ...a })
  }
  // The views overlap, so the room count is the larger camera count (adding them would count people twice).
  const inView = Math.max(0, ...cams.filter(c => c.online).map(c => c.people ?? 0))
  return (
    <div className="mt-1.5 flex items-center gap-2 rounded-xl border border-ink-600/70 bg-ink-900/80 px-2.5 py-1.5 overflow-hidden"
         aria-live="polite" aria-label="What the cameras see now">
      <span className="shrink-0 inline-flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-wider text-rose-300">
        <span className="h-2 w-2 rounded-full bg-rose-400 animate-pulse" /> Live</span>
      {inView > 0 && <span className="shrink-0 text-[12.5px] font-semibold text-white tnum">
        {inView} {inView === 1 ? 'person' : 'people'} in view ·</span>}
      {items.length === 0
        ? <span className="text-[12.5px] text-slate-400">Nobody in view right now.</span>
        : <div className="relative flex-1 overflow-hidden group">
            <div className={`flex gap-6 whitespace-nowrap text-[12.5px] ${items.length > 2 ? 'smartlab-ticker group-hover:[animation-play-state:paused]' : ''}`}
                 style={items.length > 2 ? { animationDuration: `${Math.max(14, items.length * 6)}s` } : undefined}>
              {(items.length > 2 ? [...items, ...items] : items).map((a, i) => (
                <span key={`${a.key}-${i}`} className={a.named ? 'text-white' : 'text-slate-300'}>
                  <span className="text-slate-500">{a.cam} · </span>{a.text}</span>))}
            </div>
          </div>}
      <style>{`@keyframes smartlab-ticker { from { transform: translateX(0) } to { transform: translateX(-50%) } }
               .smartlab-ticker { animation: smartlab-ticker linear infinite; will-change: transform }
               @media (prefers-reduced-motion: reduce) { .smartlab-ticker { animation: none; flex-wrap: wrap } }`}</style>
    </div>
  )
}

export default function Security() {
  const [cams, setCams] = useState<SecurityCamera[] | null>(null)
  const [camId, setCamId] = useState<number | null>(null)
  const [tab, setTab] = useState<Tab>('wall')
  const [labs, setLabs] = useState<Lab[] | null>(null)
  const [error, setError] = useState('')
  const { user } = useAuth()
  const admin = isAdmin(user)

  const load = useCallback(() => {
    api.securityCameras().then(c => {
      setCams(c)
      setCamId(id => id ?? c[0]?.device_id ?? null)
    }).catch(e => setError(e.message))
  }, [])
  useEffect(() => {
    load()
    const t = visibleInterval(load, 2000)
    return () => window.clearInterval(t)
  }, [load])
  useEffect(() => { api.labs().then(setLabs).catch(() => {}) }, [])

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
            {cams.length > 1 && tab !== 'wall' && (
              <select className="input w-auto" value={camId ?? ''} onChange={e => setCamId(Number(e.target.value))}>
                {cams.map(c => <option key={c.device_id} value={c.device_id}>{c.lab_code} · {c.name}</option>)}
              </select>)}
            <Tabs<Tab> id="security" value={tab} onChange={setTab} tabs={[
              { key: 'wall', label: 'All cameras', count: cams.length },
              { key: 'live', label: 'Live' }, { key: 'boxes', label: 'Equipment & door boxes' },
              { key: 'events', label: 'Events', count: cam?.open_events || undefined },
              ...(admin ? [{ key: 'recordings' as Tab, label: 'Recordings' }] : [])]} />
            {cam && admin && (tab === 'live' || tab === 'events') && <RecordButton deviceId={cam.device_id} />}
            {tab !== 'boxes' && tab !== 'recordings' && <span className="ml-auto"><BoxesToggle /></span>}
          </div>
          {tab === 'wall' && <Wall cams={cams} labs={labs} onPick={(id, t) => { setCamId(id); setTab(t) }} />}
          {cam && tab === 'live' && <Live cam={cam} onChange={load}
            siblings={cams.filter(c => c.lab_id === cam.lab_id).sort((a, b) => a.device_uid.localeCompare(b.device_uid))}
            onSelect={setCamId} />}
          {cam && tab === 'boxes' && <Boxes cam={cam} />}
          {cam && tab === 'events' && <Events cam={cam} onChange={load} />}
          {cam && tab === 'recordings' && admin && <RecordingsPanel deviceId={cam.device_id} />}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------- all cameras ---
function Wall({ cams, labs, onPick }: {
  cams: SecurityCamera[]
  labs: Lab[] | null
  onPick: (camId: number, tab: Tab) => void
}) {
  const [bigId, setBigId] = useState<number | null>(null)
  const big = cams.find(c => c.device_id === bigId) ?? null        // its numbers stay live
  // One frame per lab with ALL its cameras (camera 1, 2 ... by device code), side by side.
  const ofLab = (labId: number) => cams.filter(c => c.lab_id === labId).sort((a, b) => a.device_uid.localeCompare(b.device_uid))
  const frames: { key: string; lab: Lab | null; cams: SecurityCamera[] }[] = labs
    ? labs.map(l => ({ key: `lab-${l.id}`, lab: l, cams: ofLab(l.id) }))
    : cams.map(c => ({ key: `cam-${c.device_id}`, lab: null, cams: [c] }))
  const camLabel = (c: SecurityCamera) => { const same = ofLab(c.lab_id); return same.length > 1 ? `Camera ${same.indexOf(c) + 1}` : 'Camera' }
  const n = frames.length
  const cols = n <= 4 ? 2 : n <= 9 ? 3 : 4
  const go = (t: Tab) => { if (big) { setBigId(null); onPick(big.device_id, t) } }
  return (
    <div className="space-y-3">
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {frames.map(({ key, lab, cams: lc }) => !lc.length ? (
          <div key={key} className="relative aspect-video rounded-2xl border border-dashed border-ink-500/70 bg-ink-900/60
                                    grid place-items-center text-center p-3">
            <span className="absolute left-3 top-2.5 text-[16px] font-extrabold text-slate-300">{lab?.code}</span>
            <span className="absolute left-3 top-7 right-3 text-[11.5px] text-slate-500 truncate text-left">{lab?.name}</span>
            <span className="flex flex-col items-center gap-1.5 text-slate-500 text-[12.5px]">
              <VideoOff size={20} /> Camera to be installed</span>
          </div>
        ) : (
          <div key={key} style={lc.length > 1 ? { gridColumn: `span ${Math.min(2, cols)}` } : undefined}
               className={lc.length > 1 ? 'rounded-2xl border border-cyan-500/40 bg-ink-900/60 p-1.5' : ''}>
            {lc.length > 1 && <div className="flex items-center gap-2 px-1.5 pb-1.5">
              <span className="text-white font-extrabold text-[17px]">{lc[0].lab_code}</span>
              <span className="text-slate-400 text-[12px]">{lc.length} cameras · click one to enlarge, then switch or show both</span></div>}
            <div className={lc.length > 1 ? 'grid grid-cols-2 gap-1.5' : ''}>
            {lc.map(c => (
          <div key={c.device_id} role="button" tabIndex={0} title="Click to enlarge"
               onClick={() => setBigId(c.device_id)} onKeyDown={e => { if (e.key === 'Enter') setBigId(c.device_id) }}
               className="group relative aspect-video rounded-2xl overflow-hidden border border-ink-600/70 bg-black cursor-zoom-in">
            <LiveCameraFeed deviceId={c.device_id} intervalMs={cams.length > 4 ? 300 : 100} className="!absolute inset-0" />
            <div className="absolute inset-x-0 top-0 p-2.5 flex items-center gap-2 bg-gradient-to-b from-black/75 to-transparent">
              <span className="text-white font-extrabold text-[17px] leading-none">{c.lab_code}</span>
              <span className="text-slate-300 text-[12px] truncate">{lc.length > 1 ? camLabel(c) : c.name}</span>
              <span className="ml-auto"><CamState c={c} /></span>
            </div>
            <div className="absolute inset-x-0 bottom-0 p-2.5 flex flex-wrap items-center gap-1.5 text-[12px] font-semibold
                            bg-gradient-to-t from-black/80 to-transparent">
              <CamFacts c={c} />
              <span className="ml-auto inline-flex items-center gap-1 text-slate-200 opacity-0 group-hover:opacity-100 transition">
                <Maximize2 size={13} /> Enlarge</span>
            </div>
          </div>))}
            </div>
            {lc.some(c => c.online) && <LiveActivity cams={lc} label={c => lc.length > 1 ? camLabel(c) : 'Camera'} />}
          </div>))}
      </div>
      {big && (
        <CameraFullScreen deviceId={big.device_id} title={big.lab_code ?? big.name} sub={big.name}
          cameras={ofLab(big.lab_id).map(c => ({ id: c.device_id, label: camLabel(c) }))}
          badges={<div className="flex flex-wrap items-center gap-1.5 text-[12px] font-semibold"><CamFacts c={big} /></div>}
          actions={<>
            <RecordButton deviceId={big.device_id} />
            <button className="btn-ghost btn-sm" onClick={() => go('live')}>People & equipment</button>
            <button className="btn-ghost btn-sm" onClick={() => go('boxes')}>Boxes</button>
            <button className="btn-ghost btn-sm" onClick={() => go('events')}>
              Events{big.open_events ? ` (${big.open_events})` : ''}</button>
          </>}
          onClose={() => setBigId(null)} />)}
    </div>
  )
}

function CamState({ c }: { c: SecurityCamera }) {
  const live = c.online === true && c.source_ok !== false
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-black/70 text-[10.5px] font-bold tracking-wider text-white">
      <span className={`w-1.5 h-1.5 rounded-full ${live ? 'bg-bad animate-pulse' : 'bg-slate-500'}`} />
      {live ? 'LIVE' : c.online ? 'NO PICTURE' : 'OFFLINE'}</span>
  )
}

function CamFacts({ c }: { c: SecurityCamera }) {
  const live = c.online === true && c.source_ok !== false
  if (!live) return <span className="text-slate-300">Camera not reporting</span>
  const seen = c.people ?? 0
  return <>
    <span className="px-2 py-0.5 rounded-md bg-black/70 text-white tnum">{seen} seen · {c.inside} entered</span>
    {seen > c.inside && <span className="px-2 py-0.5 rounded-md bg-bad text-white">
      {c.inside === 0 ? 'Person with no door entry' : 'More people than entered'}</span>}
    {c.named.filter(n => n.face).map(n => (
      <span key={`m${n.label}`} className="px-2 py-0.5 rounded-md bg-bad text-white">{n.name}: face says {n.face}</span>))}
    {c.named.filter(n => n.entered === false).map(n => (
      <span key={n.label} className="px-2 py-0.5 rounded-md bg-orange-500 text-black">{n.name} · not entered</span>))}
    {(c.unknown ?? 0) > 0 && <span className="px-2 py-0.5 rounded-md bg-warn/90 text-black">{c.unknown} Unknown</span>}
    {c.open_events > 0 && <span className="px-2 py-0.5 rounded-md bg-white/15 text-white">
      {c.open_events} event{c.open_events === 1 ? '' : 's'} to check</span>}
  </>
}

function Live({ cam, onChange, siblings = [], onSelect }: {
  cam: SecurityCamera; onChange: () => void; siblings?: SecurityCamera[]; onSelect?: (id: number) => void
}) {
  const [split, setSplit] = useState(true)
  const live = cam.online === true && cam.source_ok !== false
  const extra = live && (cam.people ?? 0) > cam.inside
  async function accept(zoneId: number) {
    await api.acceptSecurityZone(cam.device_id, zoneId).catch(() => {})
    onChange()
  }
  return (
    <div className="space-y-4">
    {siblings.length > 1 && <div className="flex items-center gap-2 text-[12.5px]">
      <label className="flex items-center gap-1.5 text-slate-300"><input type="checkbox" checked={split} onChange={e => setSplit(e.target.checked)} />
        Show all {siblings.length} cameras of {cam.lab_code} side by side</label>
      {split && <span className="text-slate-500">· click a picture to show its details on the right</span>}</div>}
    {siblings.length > 1 && split && (
      <div className="grid md:grid-cols-2 gap-3">
        {siblings.map(c => {
          const ok = c.online === true && c.source_ok !== false
          return (
            <button key={c.device_id} type="button" onClick={() => onSelect?.(c.device_id)}
                    className={`relative text-left rounded-2xl overflow-hidden border-2 ${c.device_id === cam.device_id ? 'border-accent-400/80' : 'border-ink-600/70'}`}>
              <LiveCameraFeed deviceId={c.device_id} intervalMs={LIVE_MS} fit="contain" className="aspect-video" />
              <div className="absolute top-2 left-2 right-2 flex items-center gap-2 pointer-events-none">
                <span className="px-2 py-0.5 rounded-md bg-ink-950/80 text-[12px] text-white font-semibold">{c.name} <span className="mono text-slate-400">{c.device_uid}</span></span>
                <Chip tone={ok ? 'ok' : 'bad'} dot className="ml-auto">{ok ? 'live' : c.online ? 'no picture' : 'offline'}</Chip>
              </div>
            </button>)
        })}
      </div>)}
    <div className={siblings.length > 1 && split ? '' : 'grid xl:grid-cols-[1fr_340px] gap-4'}>
      {!(siblings.length > 1 && split) &&
      <LiveCameraFeed deviceId={cam.device_id} intervalMs={LIVE_MS} fit="contain"
                      className="rounded-2xl border border-ink-600/70 aspect-video" />}
      <div className={siblings.length > 1 && split ? 'grid md:grid-cols-2 xl:grid-cols-3 gap-3 items-start' : 'space-y-3'}>
        <div className="card p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Camera size={15} className="text-accent-300" />
            <span className="font-semibold text-white">{cam.lab_code} · {cam.name}</span>
            <Chip tone={live ? 'ok' : 'bad'} dot className="ml-auto">{live ? 'live' : cam.online ? 'no picture' : 'offline'}</Chip>
          </div>
          <div className="text-[12px] text-slate-400">
            {cam.fps ? `Analysing ${cam.fps} times a second` : 'Not analysing'} · last report{' '}
            {cam.last_seen_at ? relative(cam.last_seen_at) : 'never'}</div>
          {cam.door_open != null && (
            <div className="flex items-center gap-2 text-[12.5px] text-slate-300">
              <DoorOpen size={13} className="text-slate-400" /> Door (seen by the camera)
              <Chip tone={cam.door_open ? 'warn' : 'ok'} dot className="ml-auto">{cam.door_open ? 'open' : 'closed'}</Chip>
            </div>)}
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
            {cam.inside === 0 ? 'Someone is in the lab and nobody entered at the door.'
              : 'More people than entered: someone may have followed another person in.'}</p>}
          <ul className="mt-3 space-y-1 text-[13px]">
            {cam.named.map(n => (
              <li key={n.label} className="flex items-center gap-2">
                <span className="mono text-[11px] text-slate-400 w-14">{n.label}</span>
                <span className="text-white">{n.name}</span>
                {n.role && <Chip tone={n.role === 'STUDENT' ? 'ok' : n.role === 'ADMIN' ? 'violet' : 'info'}>{ROLE[n.role]}</Chip>}
                {n.face ? <Chip tone="bad">face says {n.face}</Chip>
                  : n.source === 'look' ? <Chip tone="warn">? guess by look · not confirmed</Chip>
                  : n.source === 'desk' ? <Chip tone="warn">? guess by desk · not confirmed</Chip>
                  : n.source === 'peer' ? <span className="text-[11px] text-slate-500">from the other camera</span>
                  : n.entered === false ? <Chip tone="warn">by face · not entered</Chip>
                  : n.verified ? <Chip tone="ok">✔ verified</Chip>
                  : <span className="text-[11px] text-slate-500">{n.source === 'face' ? 'by face' : 'by door'}</span>}
              </li>))}
            {(cam.unknown ?? 0) > 0 && live && (
              <li className="text-warn-soft">{cam.unknown} person{cam.unknown === 1 ? '' : 's'} not named (Unknown)</li>)}
            {!cam.named.length && !(cam.unknown ?? 0) && <li className="text-slate-500">Nobody in view</li>}
          </ul>
          <p className="mt-2 text-[11px] text-slate-500">Names come from the door, or from the face of a registered person
            (two clear matches). A face name stays <b>not entered</b> until the door records the entry; everyone else
            stays Unknown rather than guessed.</p>
        </div>
        <div className="card p-4">
          <div className="label mb-2 flex items-center gap-1.5"><Eye size={13} /> Watched equipment</div>
          {!cam.zones.length ? <p className="text-[12.5px] text-slate-500">No boxes yet - draw them under Equipment & door boxes.</p> : (
            <ul className="space-y-1.5 text-[13px]">
              {cam.zones.map(z => (
                <li key={z.id} className="flex items-center gap-2">
                  <span className="text-slate-100 flex-1 truncate">{z.name}</span>
                  <Chip tone={ZONE_TONE[z.status] ?? 'idle'} dot>{z.status === 'MOTION' ? 'moving' : z.status.toLowerCase().replace('_', ' ')}</Chip>
                  {(z.status === 'CHANGED' || z.status === 'MOTION') && (
                    <button className="btn-ghost btn-sm" title="The new position/look is fine - relearn it"
                            onClick={() => accept(z.id)}><Check size={13} /> Accept</button>)}
                </li>))}
            </ul>)}
        </div>
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
  // YOLO's proposals: shown dashed, nothing is saved until "Add selected".
  const [found, setFound] = useState<(EquipmentSuggestion & { pick: boolean })[] | null>(null)
  const [finding, setFinding] = useState(false)
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
  async function findEquipment() {
    setFinding(true); setError('')
    try {
      const s = await api.securitySuggestions(cam.device_id)
      setFound(s.map(x => ({ ...x, replaces: x.replaces ?? null, pick: true })))
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not look for equipment') }
    setFinding(false)
  }
  async function addFound() {
    for (const f of (found ?? []).filter(f => f.pick && f.name.trim())) {
      const old = f.replaces != null ? zones.find(z => z.id === f.replaces) : undefined
      try {
        // Moving a saved box keeps its name, history and settings.
        if (old) await api.updateSecurityZone(cam.device_id, old.id, { name: old.name, kind: old.kind,
          asset_id: old.asset_id, alert_on_motion: old.alert_on_motion, x: f.x, y: f.y, w: f.w, h: f.h })
        else await api.addSecurityZone(cam.device_id, { name: f.name.trim(), kind: 'EQUIPMENT', asset_id: null,
          alert_on_motion: true, x: f.x, y: f.y, w: f.w, h: f.h })
      } catch (e) { setError(e instanceof Error ? e.message : `Could not save ${f.name}`) }
    }
    setFound(null); load()
  }

  function edit(z: SecurityZone) {
    setEditing(z); setDraft(null)
    setForm({ name: z.name, kind: z.kind, alert_on_motion: z.alert_on_motion })
  }

  const pct = (v: number) => `${v * 100}%`
  const shown = draft ?? (editing ? { x: editing.x, y: editing.y, w: editing.w, h: editing.h } : null)
  // Far monitors on camera 1 are ~1 % of the picture wide: 0.5 % is the smallest box (as the API).
  const bigEnough = !!shown && shown.w > 0.005 && shown.h > 0.005
  const canSave = bigEnough && form.name.trim().length > 0

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
          {found?.map((f, i) => (
            <div key={`f${i}`} className={`absolute border-2 border-dashed ${f.pick ? 'border-ok bg-ok/10' : 'border-slate-500'}`}
                 style={{ left: pct(f.x), top: pct(f.y), width: pct(f.w), height: pct(f.h) }}>
              <span className="absolute left-0 -top-0 px-1.5 py-0.5 text-[11px] font-semibold bg-black/70 text-white">
                {f.replaces != null ? `${zones.find(z => z.id === f.replaces)?.name ?? f.name} → here` : f.name}</span>
            </div>))}
          {shown && <div className="absolute border-2 border-warn bg-warn/10"
                         style={{ left: pct(shown.x), top: pct(shown.y), width: pct(shown.w), height: pct(shown.h) }} />}
        </div>
        <p className="mt-2 text-[12px] text-slate-400">Drag on the picture to draw a box tightly around one fixed item
          (a PC, a robot), or around the door so people walking in get the name of the person who just entered.
          A box is learnt the first time nobody is in it. To change a saved box press Edit and draw it again.
          Add as many as you need. Deleting a box keeps its past events.</p>
      </div>
      <div className="space-y-3">
        {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
        <div className="card p-4 space-y-2">
          <div className="label">Find equipment automatically</div>
          <p className="text-[12px] text-slate-400">The detector (YOLO) looks for every monitor and laptop in the picture
            and proposes a numbered box for each - you choose which to keep. A saved box that is off its monitor
            (e.g. after the camera turned) is offered as "Move PC-xx" - pick the right box for each monitor.
            Robots and other machines it does not know: draw those by hand below.</p>
          {!found ? (
            <button className="btn-primary btn-sm w-full" disabled={finding} onClick={findEquipment}>
              <ScanSearch size={14} /> {finding ? 'Looking…' : 'Find PCs automatically'}</button>
          ) : !found.length ? (
            <p className="text-[12.5px] text-slate-400">Nothing found that is not already boxed.
              <button className="ml-1 underline" onClick={() => setFound(null)}>OK</button></p>
          ) : (<>
            <ul className="space-y-1.5 max-h-56 overflow-auto">
              {found.map((f, i) => (
                <li key={i} className="flex items-center gap-2 text-[13px]">
                  <input type="checkbox" className="accent-emerald-500" checked={f.pick}
                         onChange={e => setFound(l => l!.map((x, k) => k === i ? { ...x, pick: e.target.checked } : x))} />
                  <select className="input py-1 w-24" value={f.replaces ?? ''} title="New box, or move a saved box onto this item"
                          onChange={e => setFound(l => l!.map((x, k) => k === i ? { ...x, replaces: e.target.value ? Number(e.target.value) : null } : x))}>
                    <option value="">New</option>
                    {zones.filter(z => z.kind === 'EQUIPMENT').map(z => <option key={z.id} value={z.id}>Move {z.name}</option>)}
                  </select>
                  {f.replaces == null
                    ? <input className="input py-1 flex-1 min-w-0" value={f.name} maxLength={64}
                             onChange={e => setFound(l => l!.map((x, k) => k === i ? { ...x, name: e.target.value } : x))} />
                    : <span className="flex-1 truncate text-slate-300">{zones.find(z => z.id === f.replaces)?.name} here</span>}
                  <span className="text-[11px] text-slate-500 w-20 text-right">{f.kind} {Math.round(f.score * 100)}%</span>
                </li>))}
            </ul>
            <div className="flex gap-2">
              <button className="btn-ghost btn-sm" onClick={() => setFound(null)}>Cancel</button>
              <button className="btn-primary btn-sm flex-1" disabled={!found.some(f => f.pick)} onClick={addFound}>
                Save selected ({found.filter(f => f.pick).length})</button>
            </div>
          </>)}
        </div>
        <div className="card p-4 space-y-3">
          <div className="label">{editing ? `Edit "${editing.name}"` : 'New box'}</div>
          {!shown && <p className="text-[12.5px] text-slate-400">Draw a box on the picture first.</p>}
          {shown && !bigEnough && <p className="text-[12.5px] text-amber-300">That box is too small - drag a little wider.</p>}
          {bigEnough && !form.name.trim() && <p className="text-[12.5px] text-slate-400">Type a name to add the box.</p>}
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
                  <span className="text-slate-100 flex-1 truncate">{z.name}</span>
                  {z.kind === 'EQUIPMENT' && !z.alert_on_motion && <span className="text-[11px] text-slate-500">no motion alert</span>}
                  <button className="btn-ghost btn-sm" onClick={() => edit(z)} title="Rename, redraw or change it">
                    <Pencil size={12} /> Edit</button>
                  <button className="btn-ghost btn-sm hover:text-bad-soft" aria-label={`Delete ${z.name}`} onClick={() => remove(z)}>
                    <Trash2 size={12} /> Delete</button>
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
  // Checked events leave the list (owner, 2026-10-18); they are kept - "Show checked" lists them.
  const [showChecked, setShowChecked] = useState(false)
  const load = useCallback(() => {
    api.securityEvents({ lab_id: cam.lab_id, limit: 60, open_only: !showChecked })
      .then(setEvents).catch(() => setEvents([]))
  }, [cam.lab_id, showChecked])
  useEffect(load, [load])
  useLiveMessages(m => { if (m.type === 'staff' && m.kind === 'security_event') load() })
  async function ack(id: number) {
    if (!showChecked) setEvents(es => es && es.filter(e => e.id !== id))   // gone at once
    await api.ackSecurityEvent(id).catch(() => {})
    load(); onChange()
  }
  const toggle = (
    <div className="flex justify-end">
      <button type="button" className="btn-ghost btn-sm" onClick={() => setShowChecked(v => !v)}>
        {showChecked ? 'Hide checked events' : 'Show checked events'}</button>
    </div>)
  if (!events) return <Spinner label="Loading events" />
  if (!events.length) return <div className="space-y-3">{toggle}
    <EmptyState compact icon={<ShieldAlert size={18} />} title={showChecked ? 'Nothing flagged' : 'Nothing left to check'}
      detail="Events appear here with a snapshot: more people than entered, a person when nobody entered, equipment moved, movement at equipment with nobody there." /></div>
  return (
    <ul className="space-y-3">
      <li>{toggle}</li>
      {events.map(e => (
        <li key={e.id} className={`card p-3 flex gap-3 ${e.acknowledged_at ? 'opacity-60' : ''}`}>
          {e.has_snapshot ? <Snapshot id={e.id} /> : <div className="w-44 aspect-video rounded-lg bg-ink-900 grid place-items-center text-[11px] text-slate-500">no snapshot</div>}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className={`font-semibold ${e.kind === 'PERSON_NO_ENTRY' || e.kind === 'FACE_MISMATCH' ? 'text-bad-soft' : 'text-warn-soft'}`}>
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
