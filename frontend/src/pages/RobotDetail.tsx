/**
 * One robot: interactive 3D twin driven by its telemetry, every joint (position,
 * velocity, moving, distance from HOME), telemetry health, HOME calibration
 * (administrators), the lab camera next to it, and its events with the
 * evidence stored for each. Monitoring only.
 */
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Bot, Crosshair, Home, RotateCcw } from 'lucide-react'
import { RobotDetail as RD, RobotEventRow, SecurityCamera, api } from '../lib/api'
import { isAdmin, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import LiveCameraFeed from '../components/LiveCameraFeed'
import { Chip, ErrorBanner, KV, PageHeader, Skeleton, Timeline, Tone } from '../components/ui'
import { deg, modelFor } from '../components/robot/kinematics'
import { DemoBadge, FUSION, FusionChip, HomeChip, RobotStateChip, effective, useNow } from '../components/robot/robotLive'
import Replay, { ReplayFrame } from '../components/robot/Replay'
import { MonitoringOnly } from '../components/robot/MonitoringOnly'
import { tipPosition, urdfFor } from '../components/robot/robotModels'
import { visibleInterval } from '../lib/visibleInterval'

const RobotTwin = lazy(() => import('../components/robot/RobotTwin'))
const SEV: Record<string, Tone> = { INFO: 'idle', NOTICE: 'info', WARNING: 'warn', CRITICAL: 'bad' }
const KIND: Record<string, string> = {
  MOVEMENT_STARTED: 'Started moving', MOVEMENT_STOPPED: 'Stopped', JOINT_MOVED: 'Joint moved',
  TELEMETRY_STALE: 'Telemetry lost', TELEMETRY_RESTORED: 'Telemetry back', HOME_LEFT: 'Left HOME',
  HOME_RETURNED: 'Returned HOME',
}

function eventTitle(e: RobotEventRow) {
  const d = e.detail ?? {}
  if (e.kind === 'JOINT_MOVED' && e.joint != null)
    return `J${e.joint + 1} ${Number(d.delta_deg) > 0 ? '+' : ''}${d.delta_deg}°`
  if (e.kind === 'MOVEMENT_STARTED' && Array.isArray(d.joints)) return `Started moving (${(d.joints as string[]).join(', ')})`
  return KIND[e.kind] ?? e.kind
}

/** The last ~30 s of one joint (live robot_state samples, ~5 a second). */
function Trace({ values, moving }: { values: number[]; moving: boolean }) {
  if (values.length < 2) return <svg width="84" height="18" />
  const lo = Math.min(...values), hi = Math.max(...values)
  const span = Math.max(hi - lo, 0.5)                      // degrees: a still joint stays a flat line
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 84},${16 - ((v - lo) / span) * 14}`).join(' ')
  return <svg width="84" height="18" aria-hidden><polyline points={pts} fill="none" strokeWidth="1.4"
    stroke={moving ? '#22c55e' : '#38bdf8'} strokeLinejoin="round" /></svg>
}

function Evidence({ e }: { e: RobotEventRow }) {
  const c = e.context
  if (!c) return null
  const people = c.camera_named.filter(n => n.name)
  return (
    <div className="flex flex-wrap gap-1.5 text-[11.5px]">
      <Chip tone={c.booking ? 'ok' : 'warn'}>{c.booking ? `Booking: ${c.booking.holder ?? '#' + c.booking.id}` : 'No booking in force'}</Chip>
      <Chip tone={c.inside_per_door.length ? 'info' : 'warn'}>
        {c.inside_per_door.length ? `Inside (door): ${c.inside_per_door.join(', ')}` : 'Nobody entered at the door'}</Chip>
      {c.camera && c.camera !== 'online' && <Chip tone="idle">Camera {c.camera === 'none' ? 'not installed' : 'offline - no visual evidence'}</Chip>}
      {c.camera_robot_box && <Chip tone={c.camera_robot_box.status === 'IN_USE' ? 'info' : 'idle'}>
        Camera, robot box: {c.camera_robot_box.status.toLowerCase().replace('_', ' ')}</Chip>}
      {people.map(p => <Chip key={p.label} tone="idle">Camera: {p.name} ({Math.round((p.confidence ?? 0) * 100)}%)</Chip>)}
      {e.provenance === 'DEMO_DATA' && <Chip tone="violet">demo data</Chip>}
    </div>)
}

export default function RobotDetail() {
  const { id } = useParams()
  const rid = Number(id)
  const { user } = useAuth()
  const [r, setR] = useState<RD | null>(null)
  const [error, setError] = useState('')
  const [sel, setSel] = useState<number | null>(null)
  const [ghost, setGhost] = useState(true)
  const [reset, setReset] = useState(0)
  const [cam, setCam] = useState<SecurityCamera | null>(null)
  const [busy, setBusy] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const hist = useRef<number[][]>([])                       // degrees per joint, last 150 samples
  const histQ = useRef<number[][]>([])                      // the same in radians (tool trail)
  const [replay, setReplay] = useState<ReplayFrame | null>(null)
  const now = useNow()

  const load = useCallback(() => {
    api.robot(rid).then(setR).catch(e => setError(e instanceof Error ? e.message : 'Could not load the robot'))
  }, [rid])
  useEffect(() => { load(); const t = visibleInterval(load, 10000); return () => window.clearInterval(t) }, [load])
  useEffect(() => {
    if (!r) return
    api.securityCameras().then(cs => setCam(cs.find(c => c.lab_id === r.lab_id) ?? null)).catch(() => {})
  }, [r?.lab_id])   // eslint-disable-line react-hooks/exhaustive-deps
  useLiveMessages(m => {
    if (m.type === 'robot_state' && m.device_id === rid && m.q) {
      hist.current = [...hist.current, m.q.map(deg)].slice(-150)
      histQ.current = [...histQ.current, m.q].slice(-150)
    }
    if (m.type === 'robot_state' && m.device_id === rid)
      setR(p => p && { ...p, state: m.state as RD['state'], q: m.q, qd: m.qd, joints_moving: m.joints_moving,
                       home: m.home as RD['home'], telemetry_age_ms: m.telemetry_age_ms, last_seen_at: new Date().toISOString() })
    if (m.type === 'robot_status' && m.device_id === rid) load()
    if (m.type === 'staff' && m.kind === 'robot_event') load()
  })

  const model = useMemo(() => modelFor(r?.model), [r?.model])
  async function calibrate() {
    if (!r || !window.confirm(`Take the pose the ${r.name} is in NOW as its HOME?\nIt must be standing still. Older calibrations are kept.`)) return
    setBusy(true)
    try { await api.calibrateHome(rid, { tolerance_deg: 1.0 }); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Calibration failed') }
    setBusy(false)
  }

  if (!r) return error ? <ErrorBanner message={error} /> : <Skeleton className="h-[70vh]" />
  const live = effective(r, now)
  const urdf = urdfFor(r.model)
  const q = replay ? replay.q : r.q ?? null
  // Tool path: the whole replayed movement, or the last ~30 s live.
  const trail = (replay ? replay.path : histQ.current).map(p => tipPosition(urdf, p))
  const home = r.home_calibration?.home_q ?? null
  return (
    <div className="space-y-4">
      <Link to="/robots" className="btn-ghost btn-sm w-fit"><ArrowLeft size={13} /> Robots</Link>
      <PageHeader eyebrow="Robot" title={r.name} sub={`${model.label} · read-only monitoring`}
        actions={<div className="flex flex-wrap gap-1.5">
          {replay && <span className="chip bg-violet-500/15 text-violet-200 border border-violet-400/40 font-bold">REPLAY</span>}
          {r.demo && <DemoBadge />}<RobotStateChip state={live.state} /><HomeChip home={r.home} state={live.state} /></div>} />
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {/* 2026-10-29 (owner): monitoring and analysis only - no Home / Stop from the portal */}
      <MonitoringOnly />
      <div className="grid xl:grid-cols-[1fr_400px] gap-4 items-start">
        <div className="card overflow-hidden flex flex-col h-[min(880px,calc(100vh-140px))] min-h-[560px] xl:sticky xl:top-20">
          <div className="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-ink-700/60 text-[12.5px]">
            <Bot size={14} className="text-accent-300" /><span className="text-slate-200 font-medium">Digital twin</span>
            {!model.exact && <span title="The lab arm is an ER-4iA; the 3D arm uses LR Mate 200iD meshes and link lengths as a stand-in"><Chip tone="warn">3D arm: stand-in geometry</Chip></span>}
            <span className="ml-auto flex gap-1.5">
              {home && <button className={`btn-sm ${ghost ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setGhost(g => !g)}>
                <Home size={12} /> HOME pose</button>}
              <button className="btn-ghost btn-sm" onClick={() => setReset(k => k + 1)}><RotateCcw size={12} /> Reset view</button>
            </span>
          </div>
          <div className="flex-1 relative">
            <div className="absolute inset-0">
              <Suspense fallback={<Skeleton className="h-full rounded-none" />}>
                <RobotTwin model={model} q={q} homeQ={ghost ? home : null} selected={sel} moving={replay ? null : r.joints_moving}
                           trail={trail} trailColor={replay ? '#a78bfa' : undefined} stale={!replay && live.stale}
                           onSelect={j => setSel(s => s === j ? null : j)} resetKey={reset}
                           className="h-full bg-ink-950/40" />
              </Suspense>
            </div>
          </div>
          <p className="px-4 py-2 text-[11.5px] text-slate-500 border-t border-ink-700/60">{model.note} Drag to orbit, scroll to zoom, click a joint to select it.
            {ghost && home ? ' The faint arm is the calibrated HOME pose.' : ''}</p>
        </div>
        <div className="space-y-4">
          <div className="card p-4">
            <div className="label mb-2">Joints</div>
            <table className="w-full text-[12.5px] tnum">
              <thead><tr className="text-slate-500 text-left">
                <th className="font-medium pb-1">Joint</th><th className="font-medium pb-1 text-right">Position</th>
                <th className="font-medium pb-1 text-right">Velocity</th><th className="font-medium pb-1 text-right">From HOME</th>
                <th className="font-medium pb-1 text-right">Last 30 s</th></tr></thead>
              <tbody>
                {Array.from({ length: 6 }, (_, i) => {
                  const moving = !!r.joints_moving?.[i]
                  return (
                    <tr key={i} onClick={() => setSel(s => s === i ? null : i)}
                        className={`cursor-pointer border-t border-ink-700/50 ${sel === i ? 'bg-accent-500/10' : 'hover:bg-ink-700/30'}`}>
                      <td className="py-1.5 flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${moving ? 'bg-ok animate-pulse' : 'bg-ink-500'}`} />
                        J{i + 1}{moving && <span className="text-ok-soft text-[11px]">moving</span>}</td>
                      <td className="text-right mono">{q ? `${deg(q[i]).toFixed(2)}°` : '—'}</td>
                      <td className="text-right mono">{r.qd ? `${deg(r.qd[i]).toFixed(1)}°/s` : '—'}</td>
                      <td className="text-right mono">{r.deviation_deg ? `${r.deviation_deg[i].toFixed(1)}°` : '—'}</td>
                      <td className="text-right pl-2"><Trace values={hist.current.map(h => h[i])} moving={moving} /></td>
                    </tr>)
                })}
              </tbody>
            </table>
            {sel != null && <div className="mt-3 p-2.5 rounded-lg bg-ink-900/60 text-[12px] text-slate-300 flex items-center gap-2">
              <Crosshair size={13} className="text-accent-300" /> J{sel + 1} selected · limits {model.limitsDeg[sel][0]}° to {model.limitsDeg[sel][1]}°</div>}
          </div>
          <Replay robotId={rid} active onFrame={setReplay} />
          <div className="card p-4 space-y-2">
            <div className="label flex items-center gap-2">Telemetry + camera <span className="ml-auto"><FusionChip fusion={r.fusion} /></span></div>
            <p className="text-[12px] text-slate-400">{(FUSION[r.fusion ?? 'UNKNOWN'] ?? FUSION.UNKNOWN).why}</p>
            {r.fusion_evidence && <ul className="space-y-1 text-[12px]">
              {r.fusion_evidence.map(e => <li key={e.source} className="flex gap-2">
                <span className="text-slate-500 w-20 shrink-0 capitalize">{e.source}</span>
                <span className="text-slate-200 font-medium">{e.value}</span>
                <span className="text-slate-500 truncate" title={e.detail}>{e.detail}</span></li>)}
            </ul>}
          </div>
          <div className="card p-4 space-y-1.5">
            <div className="label mb-1">Telemetry</div>
            <KV label="Source">{r.source ?? '—'}</KV>
            <KV label="Samples a second">{r.rate_hz ?? '—'}</KV>
            <KV label="Data age at the collector">{r.telemetry_age_ms != null ? `${r.telemetry_age_ms} ms` : '—'}</KV>
            <KV label="Collector → portal">{r.transport_ms != null ? `${r.transport_ms} ms` : '—'}</KV>
            <KV label="Last report">{r.last_seen_at ? relative(r.last_seen_at) : 'never'}</KV>
            {r.extra && Object.entries(r.extra).map(([k, v]) => <KV key={k} label={k.replace(/_/g, ' ')} mono>{String(v)}</KV>)}
          </div>
          <div className="card p-4 space-y-2">
            <div className="label">HOME calibration</div>
            {r.home_calibration ? <p className="text-[12.5px] text-slate-300">Version {r.home_calibration.version}, ±{r.home_calibration.tolerance_deg}° per joint, taken {relative(r.home_calibration.created_at)}.
              {r.worst_joint && r.home !== 'HOME' && <> Furthest: {r.worst_joint} at {r.worst_deg}°.</>}</p>
              : <p className="text-[12.5px] text-slate-400">Not calibrated: put the robot in its home pose, then take it here.</p>}
            {isAdmin(user) && <button className="btn-primary btn-sm" disabled={busy || r.state !== 'STATIONARY'} onClick={calibrate}
                                      title={r.state !== 'STATIONARY' ? 'Needs live telemetry and a still robot' : ''}>
              <Home size={13} /> {r.home_calibration ? 'Recalibrate HOME (new version)' : 'Calibrate HOME'}</button>}
          </div>
        </div>
      </div>
      <div className="grid xl:grid-cols-[1fr_380px] gap-4">
        <div className="card p-4">
          <div className="label mb-3">Events{r.last_24h && Object.keys(r.last_24h).length ? ` · last 24 h: ${Object.entries(r.last_24h).map(([k, n]) => `${n} ${(KIND[k] ?? k).toLowerCase()}`).join(', ')}` : ''}</div>
          {!r.events.length ? <p className="text-[12.5px] text-slate-500">No events yet.</p> : (<>
            <Timeline dense items={r.events.slice(0, showAll ? 30 : 8).map(e => ({
              key: e.id, time: new Date(e.occurred_at).toLocaleTimeString(), title: eventTitle(e),
              tone: SEV[e.severity] ?? 'idle',
              detail: <>{e.severity !== 'INFO' && <b className="mr-1">{e.severity}</b>}{e.source}{e.kind === 'JOINT_MOVED' && e.detail ? ` · peak ${Number(e.detail.peak_velocity_rad_s ?? 0).toFixed(2)} rad/s · ${e.detail.duration_s}s` : ''}</>,
              meta: <Evidence e={e} /> }))} />
            {r.events.length > 8 && <button className="btn-ghost btn-sm mt-3" onClick={() => setShowAll(v => !v)}>
              {showAll ? 'Show fewer' : `Show ${Math.min(30, r.events.length) - 8} more`}</button>}</>)}
        </div>
        <div className="card overflow-hidden">
          <div className="px-4 py-2.5 border-b border-ink-700/60 text-[12.5px] text-slate-200 font-medium">Lab camera</div>
          {cam ? <LiveCameraFeed deviceId={cam.device_id} intervalMs={250} className="aspect-video" fit="contain" />
            : <p className="p-4 text-[12.5px] text-slate-500">No camera in this lab.</p>}
        </div>
      </div>
    </div>)
}
