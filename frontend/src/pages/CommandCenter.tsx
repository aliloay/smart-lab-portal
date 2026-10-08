/**
 * Smart Lab Command Center: "what is happening in the lab right now?"
 *
 * One screen (staff), all from the existing backend - no second source of truth:
 *   top     every service checked for real (/system/services), the live stream
 *   left    the lab camera with its MEASURED latency, the people the camera
 *           sees with how sure each name is (identity.py)
 *   right   robots (state / home / telemetry), lab state per lab, and one
 *           timeline of camera + robot events
 * Updates arrive over the WebSocket; the slow polls only catch what has no
 * push. Nothing on this page can open a door or move a robot.
 */
import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, Bot, Cctv, DoorClosed, DoorOpen, Radar, ShieldAlert, Thermometer, Users } from 'lucide-react'
import { MonitorTile, RobotEventRow, SecurityCamera, SecurityEvent, ServiceHealth, api } from '../lib/api'
import { useLive, useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import LiveCameraFeed from '../components/LiveCameraFeed'
import { Chip, Dot, ErrorBanner, Skeleton, Timeline, Tone } from '../components/ui'
import { modelFor } from '../components/robot/kinematics'
import { DemoBadge, HomeChip, RobotStateChip, useRobots } from '../components/robot/robotLive'

const RobotTwin = lazy(() => import('../components/robot/RobotTwin'))
const SVC_TONE: Record<string, Tone> = { ONLINE: 'ok', DEGRADED: 'warn', OFFLINE: 'bad', UNKNOWN: 'idle', SIMULATION: 'violet' }
const ID_TONE: Record<string, Tone> = {
  FUSED_CONFIRMED: 'ok', DOOR_CONFIRMED: 'ok', FACE_CONFIRMED: 'ok', REID_CONFIRMED: 'info',
  OCCLUDED: 'idle', IDENTITY_UNCERTAIN: 'warn', IDENTITY_CONFLICT: 'bad',
}
const ID_TEXT: Record<string, string> = {
  FUSED_CONFIRMED: 'door + face', DOOR_CONFIRMED: 'door', FACE_CONFIRMED: 'face', REID_CONFIRMED: 'kept by look',
  OCCLUDED: 'occluded', IDENTITY_UNCERTAIN: 'uncertain', IDENTITY_CONFLICT: 'CONFLICT',
}

function HealthBar() {
  const { connected } = useLive()
  const [svc, setSvc] = useState<ServiceHealth[] | null>(null)
  useEffect(() => {
    const load = () => api.systemServices().then(r => setSvc(r.services)).catch(() => setSvc([]))
    load()
    const t = window.setInterval(load, 15000)
    return () => window.clearInterval(t)
  }, [])
  const items = svc ?? []
  const bad = items.filter(s => s.state === 'OFFLINE' || s.state === 'DEGRADED').length
  return (
    <div className="card px-3 py-2.5 flex flex-wrap items-center gap-1.5" aria-label="System health">
      <span className="flex items-center gap-1.5 text-[12px] font-semibold text-slate-200 mr-1">
        <Activity size={14} className="text-accent-300" /> System</span>
      <Chip tone={connected ? 'ok' : 'warn'} dot>Live stream {connected ? 'connected' : 'reconnecting'}</Chip>
      {svc === null ? <Skeleton className="h-6 w-96" /> : items.filter(s => s.key !== 'websocket').map(s => (
        <span key={s.key} title={`${s.detail}${s.latency_ms != null ? ` · ${s.latency_ms} ms` : ''}`}>
          <Chip tone={SVC_TONE[s.state] ?? 'idle'} dot>{s.name}: {s.state.toLowerCase()}</Chip></span>))}
      {svc && <span className="ml-auto text-[11.5px] text-slate-500">{bad ? `${bad} need attention` : 'all reporting'}</span>}
    </div>)
}

function LabStrip({ tiles }: { tiles: MonitorTile[] | null }) {
  if (!tiles) return <Skeleton className="h-20" />
  return (
    <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
      {tiles.map(t => {
        const temp = t.environment?.temperature, hum = t.environment?.humidity
        return (
          <Link key={t.lab_id} to={`/labs/${t.lab_id}`} className="card p-3 hover:border-accent-500/40 transition-colors">
            <div className="flex items-center gap-2">
              <Dot tone={t.state === 'ALERT' ? 'bad' : t.state === 'WARN' ? 'warn' : 'ok'} live={t.state !== 'OK'} />
              <span className="font-semibold text-white">{t.code}</span>
              <span className="text-[12px] text-slate-400 truncate">{t.name}</span>
              {t.hazards.length > 0 && <Chip tone="bad" className="ml-auto">{t.hazards.join(', ')}</Chip>}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-slate-300">
              <span className="flex items-center gap-1"><Users size={13} /> {t.people.length} inside</span>
              {t.has_door && <span className="flex items-center gap-1">
                {t.door_closed === false && t.controller_online ? <DoorOpen size={13} /> : <DoorClosed size={13} />}
                {/* A door state from a controller that is not reporting is not the door's state now. */}
                {!t.controller_online ? 'door: controller offline' : t.door_closed == null ? 'door: no data'
                  : t.door_closed ? (t.locked ? 'closed, locked' : 'closed') : 'OPEN'}</span>}
              {temp && <span className="flex items-center gap-1"><Thermometer size={13} /> {temp.value.toFixed(1)}{temp.unit}
                {hum ? ` · ${hum.value.toFixed(0)}${hum.unit}` : ''}</span>}
              {t.alert_count > 0 && <span className="text-warn-soft">{t.alert_count} alert{t.alert_count > 1 ? 's' : ''}</span>}
            </div>
          </Link>)
      })}
    </div>)
}

function CameraPanel({ cam }: { cam: SecurityCamera }) {
  const m = cam.metrics ?? {}
  const age = m.frame_age_ms_p50
  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-ink-700/60 text-[12.5px]">
        <Cctv size={14} className="text-accent-300" /><span className="text-slate-200 font-medium">{cam.lab_code} · camera</span>
        <Chip tone={cam.online && cam.source_ok !== false ? 'ok' : 'bad'} dot>{cam.online ? (cam.source_ok === false ? 'no picture' : 'live') : 'offline'}</Chip>
        {cam.door_open != null && <Chip tone={cam.door_open ? 'warn' : 'idle'}>door {cam.door_open ? 'open' : 'closed'}</Chip>}
        <span className="ml-auto text-slate-500 tnum" title="Measured by the camera service (latency.py): frame age when analysis starts, p50">
          {cam.online && m.input_fps != null ? `in ${m.input_fps} fps · analysed ${m.analysis_fps} /s · frame age ${age ?? '—'} ms` : 'latency: not reported'}</span>
      </div>
      <LiveCameraFeed deviceId={cam.device_id} intervalMs={60} className="aspect-video" fit="contain" />
    </div>)
}

function People({ cam }: { cam: SecurityCamera }) {
  return (
    <div className="card p-4">
      <div className="label mb-2 flex items-center gap-1.5"><Users size={13} /> People in view
        <span className="ml-auto text-slate-500 normal-case tracking-normal">{cam.people ?? 0} seen · {cam.inside} entered at the door</span></div>
      {!cam.named.length && !(cam.unknown ?? 0) ? <p className="text-[12.5px] text-slate-500">Nobody in view.</p> : (
        <ul className="space-y-1.5 text-[13px]">
          {cam.named.map(n => (
            <li key={`${n.label}-${n.track_id ?? ''}`} className="flex items-center gap-2">
              <span className="text-slate-100 font-medium">{n.name}</span>
              <span className="text-[11px] text-slate-500">{n.label}{n.track_id != null ? ` · track ${n.track_id}` : ''}</span>
              {!n.entered && <Chip tone="warn">not entered</Chip>}
              <span className="ml-auto flex items-center gap-1.5">
                {n.identity_state && <Chip tone={ID_TONE[n.identity_state] ?? 'idle'}>{ID_TEXT[n.identity_state] ?? n.identity_state}</Chip>}
                {n.confidence != null && <span className="mono text-[11.5px] text-slate-400 tnum w-9 text-right">{Math.round(n.confidence * 100)}%</span>}
              </span>
            </li>))}
          {(cam.unknown ?? 0) > 0 && <li className="flex items-center gap-2 text-slate-400">
            <span>{cam.unknown} Unknown</span><span className="text-[11.5px]">- no door entry or face match; never guessed</span></li>}
        </ul>)}
    </div>)
}

type Ev = { key: string; at: string; title: string; detail: string; tone: Tone }

export default function CommandCenter() {
  const [tiles, setTiles] = useState<MonitorTile[] | null>(null)
  const [cams, setCams] = useState<SecurityCamera[] | null>(null)
  const [secEvents, setSecEvents] = useState<SecurityEvent[]>([])
  const [robEvents, setRobEvents] = useState<(RobotEventRow & { robot: string })[]>([])
  const [error, setError] = useState('')
  const { robots } = useRobots()

  const loadLab = useCallback(() => {
    api.monitor().then(r => setTiles(r.labs)).catch(e => setError(e instanceof Error ? e.message : 'Failed'))
    api.securityCameras().then(setCams).catch(() => setCams([]))
    api.securityEvents({ limit: 15 }).then(setSecEvents).catch(() => {})
  }, [])
  useEffect(() => { loadLab(); const t = window.setInterval(loadLab, 20000); return () => window.clearInterval(t) }, [loadLab])
  const robotIds = (robots ?? []).map(r => r.device_id).join(',')
  const loadRobotEvents = useCallback(() => {
    Promise.all((robots ?? []).map(r => api.robotEvents(r.device_id, 10)
      .then(ev => ev.map(e => ({ ...e, robot: r.name }))).catch(() => [])))
      .then(lists => setRobEvents(lists.flat()))
  }, [robotIds])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadRobotEvents() }, [loadRobotEvents])
  useLiveMessages(m => {
    if (m.type === 'security_state' || m.type === 'door_state' || m.type === 'env_update' || m.type === 'hazard') loadLab()
    if (m.type === 'robot_status' || (m.type === 'staff' && m.kind === 'robot_event')) loadRobotEvents()
  })

  const timeline: Ev[] = useMemo(() => [
    ...secEvents.map(e => ({ key: `s${e.id}`, at: e.created_at, title: e.title, tone: (e.acknowledged_at ? 'idle' : 'warn') as Tone,
                             detail: `${e.lab_code ?? ''} camera · ${e.detail}` })),
    ...robEvents.map(e => ({ key: `r${e.id}`, at: e.occurred_at,
                             title: `${e.robot}: ${e.kind === 'JOINT_MOVED' && e.joint != null ? `J${e.joint + 1} ${e.detail?.delta_deg}°` : e.kind.toLowerCase().replace(/_/g, ' ')}`,
                             tone: (e.severity === 'CRITICAL' ? 'bad' : e.severity === 'WARNING' ? 'warn' : e.severity === 'NOTICE' ? 'info' : 'idle') as Tone,
                             detail: `${e.source}${e.context?.booking ? ` · booking ${e.context.booking.holder ?? ''}` : ' · no booking'}${e.provenance === 'DEMO_DATA' ? ' · demo data' : ''}` })),
  ].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 12), [secEvents, robEvents])

  const cam = cams?.[0] ?? null
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <div className="eyebrow flex items-center gap-1.5"><Radar size={13} /> Smart Lab</div>
          <h1 className="text-2xl font-bold text-white font-display">Command Center</h1>
        </div>
        <p className="text-[12.5px] text-slate-400 max-w-xl">Everything below is reported by the lab's own devices and services and checked live.
          Unknown means unknown - nothing is shown green without a report.</p>
      </div>
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      <HealthBar />
      <LabStrip tiles={tiles} />
      <div className="grid 2xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] gap-4">
        <div className="space-y-4">
          {cams === null ? <Skeleton className="aspect-video" /> : cam ? <><CameraPanel cam={cam} /><People cam={cam} /></>
            : <div className="card p-4 text-[12.5px] text-slate-500">No security camera registered.</div>}
        </div>
        <div className="space-y-4">
          <div className="card p-4">
            <div className="label mb-3 flex items-center gap-1.5"><Bot size={13} /> Robots
              <Link to="/robots" className="ml-auto text-accent-300 normal-case tracking-normal text-[12px]">All robots</Link></div>
            {robots === null ? <Skeleton className="h-40" /> : !robots.length ? (
              <p className="text-[12.5px] text-slate-500">No robot is reporting yet (collectors: tools/robot_monitor; the UR5e needs the lab switch).</p>
            ) : (
              <div className="grid sm:grid-cols-2 gap-3">
                {robots.map(r => (
                  <Link key={r.device_id} to={`/robots/${r.device_id}`} className="rounded-xl border border-ink-600/70 overflow-hidden hover:border-accent-500/40">
                    <Suspense fallback={<Skeleton className="h-40 rounded-none" />}>
                      <RobotTwin model={modelFor(r.model)} q={r.q ?? null} moving={r.joints_moving} className="h-40 bg-ink-950/40" />
                    </Suspense>
                    <div className="p-2.5 space-y-1.5">
                      <div className="text-[13px] font-semibold text-white">{r.name}</div>
                      <div className="flex flex-wrap gap-1">{r.demo && <DemoBadge />}<RobotStateChip state={r.state} /><HomeChip home={r.home} state={r.state} /></div>
                    </div>
                  </Link>))}
              </div>)}
          </div>
          <div className="card p-4">
            <div className="label mb-3 flex items-center gap-1.5"><ShieldAlert size={13} /> Timeline
              <Link to="/admin/security" className="ml-auto text-accent-300 normal-case tracking-normal text-[12px]">Camera events</Link></div>
            {!timeline.length ? <p className="text-[12.5px] text-slate-500">Nothing recorded yet.</p> : (
              <Timeline dense items={timeline.map(e => ({ key: e.key, time: relative(e.at), title: e.title, detail: e.detail, tone: e.tone }))} />)}
          </div>
        </div>
      </div>
    </div>)
}
