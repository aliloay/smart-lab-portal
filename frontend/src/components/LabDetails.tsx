/**
 * Live monitor -> Details: one lab enlarged over the wall, with everything the
 * portal knows about it now - the camera with its person boxes, door and lock,
 * who is inside, the environment, every open alert (the tile shows the top
 * three), the door activity, bookings, devices and issues.
 *
 * Read-only, like the monitor. The tile's data comes from the monitor (it
 * refreshes on every door / alert / sensor message); the rest reloads on the
 * same messages and every 10 s. X or Esc closes it.
 */
import { ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight, CalendarClock, Cpu, DoorClosed, DoorOpen, Droplets, Lock, LockOpen, ShieldAlert,
  ShieldCheck, Thermometer, UsersRound, Video, Wrench, X,
} from 'lucide-react'
import { AccessEvent, Alert, LabStatus, MonitorTile, Role, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { fmtDateTime, fmtTime, relative } from '../lib/time'
import {
  STATUS_LABEL, Tone, denialShort, eventLabel, eventTone, issueStatusTone, methodLabel, severityTone,
} from '../lib/labels'
import { Chip } from './ui'
import { BoxesToggle } from '../lib/cameraView'
import LiveCameraFeed, { LIVE_MS } from './LiveCameraFeed'
import CameraFullScreen from './CameraFullScreen'
import SafetyStates from './SafetyStates'

const ROLE: Record<Role, string> = { STUDENT: 'Student', LAB_STAFF: 'Staff', ADMIN: 'Admin' }
const DEVICE: Record<string, string> = {
  MASTER_CONTROLLER: 'Door controller', CAMERA: 'Door camera', FACE_SERVER: 'Face server',
  SENSOR_NODE: 'Environment node', SECURITY_CAMERA: 'Security camera',
}
const RELOAD_ON = new Set(['door_state', 'access_event', 'staff', 'hazard', 'env_update', 'env_warning'])
const TEXT: Record<Tone, string> = {
  ok: 'text-ok-soft', warn: 'text-warn-soft', bad: 'text-bad-soft', info: 'text-accent-200',
  idle: 'text-slate-400', violet: 'text-violet-300',
}

export default function LabDetails({ t, pill, badges, onClose }: {
  t: MonitorTile
  /** The tile's state pill and camera badges, so both read the same. */
  pill: ReactNode
  badges?: ReactNode
  onClose: () => void
}) {
  const [status, setStatus] = useState<LabStatus | null>(null)
  const [events, setEvents] = useState<AccessEvent[] | null>(null)
  const [alerts, setAlerts] = useState<Alert[] | null>(null)
  const [camBig, setCamBig] = useState(false)
  const navigate = useNavigate()
  const timer = useRef<number>()

  const load = useCallback(() => {
    api.lab(t.lab_id).then(setStatus).catch(() => {})
    api.labActivity(t.lab_id, 12).then(setEvents).catch(() => setEvents([]))
    api.alerts(true).then(a => setAlerts(a.filter(x => x.lab_id === t.lab_id))).catch(() => setAlerts([]))
  }, [t.lab_id])
  useEffect(() => {
    load()
    const i = window.setInterval(load, 10_000)
    return () => { window.clearInterval(i); window.clearTimeout(timer.current) }
  }, [load])
  useLiveMessages(m => {
    if (!RELOAD_ON.has(m.type)) return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(load, 400)
  })
  // Esc closes the full-screen camera first, then this window.
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape' && !camBig) onClose() }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose, camBig])

  const cam = t.security_camera
  const env = t.environment
  const doorTone: Tone = t.door_closed == null ? 'idle' : t.door_closed ? 'ok' : 'warn'
  const lockTone: Tone = t.locked == null ? 'idle' : t.locked ? 'ok' : 'warn'

  return createPortal(
    <div role="dialog" aria-modal="true" aria-label={`${t.code} details`}
         className="fixed inset-0 z-[62] flex flex-col bg-ink-950 text-slate-100">
      <header className="shrink-0 flex items-center gap-4 px-6 py-3 border-b border-ink-600/60 bg-ink-900/80">
        <div className="min-w-0">
          <div className="text-[28px] font-extrabold tracking-wide leading-none">{t.code}</div>
          <div className="text-[13px] text-slate-400 truncate mt-1">{t.name}</div>
        </div>
        <div className="flex items-center">{pill}</div>
        <button onClick={() => navigate(`/labs/${t.lab_id}`)}
                className="ml-auto inline-flex items-center gap-1 text-[13px] text-accent-300 hover:text-accent-200">
          Open the lab page <ArrowRight size={14} /></button>
        <button onClick={onClose} aria-label="Close details"
                className="inline-flex items-center gap-1 rounded-lg border border-ink-500 px-3 py-1.5 text-[13px] text-slate-200 hover:bg-white/5">
          <X size={15} /> Close</button>
      </header>

      <main className="flex-1 min-h-0 overflow-auto p-5 space-y-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="space-y-4 min-w-0">
            <Panel icon={<Video size={14} />} title="Camera" aside={cam ? <BoxesToggle /> : null}>
              {cam ? (
                <div role="button" tabIndex={0} title="Open full screen"
                     onClick={() => setCamBig(true)} onKeyDown={e => { if (e.key === 'Enter') setCamBig(true) }}
                     className="relative aspect-video rounded-xl overflow-hidden bg-black cursor-zoom-in">
                  <LiveCameraFeed deviceId={cam.device_id} intervalMs={LIVE_MS} fit="contain" className="!absolute inset-0" />
                  {badges && <div className="absolute left-2 top-2" onClick={e => e.stopPropagation()}>{badges}</div>}
                </div>
              ) : <Empty>No security camera in this lab.</Empty>}
            </Panel>
            <Panel icon={<Thermometer size={14} />} title="Environment"
                   aside={t.env_online == null ? null
                     : <Chip tone={t.env_online ? 'ok' : 'warn'} dot>{t.env_online ? 'node reporting' : 'node offline'}</Chip>}>
              <div className="flex flex-wrap gap-x-6 gap-y-1 mb-3 text-[15px]">
                <Reading icon={<Thermometer size={15} />} value={env.temperature && `${env.temperature.value.toFixed(1)} °C`}
                         at={env.temperature?.at} />
                <Reading icon={<Droplets size={15} />} value={env.humidity && `${env.humidity.value.toFixed(0)} %`}
                         at={env.humidity?.at} />
              </div>
              <SafetyStates labId={t.lab_id} />
            </Panel>
          </div>

          <div className="space-y-4 min-w-0">
            <Panel icon={<DoorClosed size={14} />} title="Door and lock"
                   aside={t.has_door && t.controller_online != null
                     ? <Chip tone={t.controller_online ? 'ok' : 'warn'} dot>
                         {t.controller_online ? 'controller online' : 'controller offline'}</Chip> : null}>
              {t.has_door ? (
                <div className="grid grid-cols-2 gap-2">
                  <Big label="Door" tone={doorTone} icon={t.door_closed === false ? <DoorOpen size={20} /> : <DoorClosed size={20} />}
                       value={t.door_closed == null ? 'No data' : t.door_closed ? 'Closed' : 'Open'} />
                  <Big label="Lock" tone={lockTone} icon={t.locked === false ? <LockOpen size={20} /> : <Lock size={20} />}
                       value={t.locked == null ? 'No data' : t.locked ? 'Locked' : 'Unlocked'} />
                </div>
              ) : <Empty>No door controller in this lab.</Empty>}
              {t.emergency && <p className="mt-2 text-[13px] font-semibold text-bad-soft">
                Emergency mode is on for this lab (set on the Emergency tab).</p>}
            </Panel>

            <Panel icon={<UsersRound size={14} />} title={`Inside now (${t.people.length})`}>
              {t.people.length ? (
                <ul className="space-y-1.5 text-[14px]">
                  {t.people.map((p, i) => (
                    <li key={i} className="flex items-center gap-2 min-w-0">
                      <span className="text-white truncate">{p.name ?? 'Unknown'}</span>
                      {p.role && <Chip tone={p.role === 'STUDENT' ? 'ok' : p.role === 'ADMIN' ? 'violet' : 'info'}>{ROLE[p.role]}</Chip>}
                      <span className="ml-auto shrink-0 text-[12px] text-slate-500">since {fmtTime(p.since)}</span>
                    </li>))}
                </ul>
              ) : <Empty>Nobody inside per the door.</Empty>}
              {cam?.online && cam.people != null && cam.people !== t.people.length && (
                <p className="mt-2 text-[12.5px] text-warn-soft">The camera sees {cam.people} right now.</p>)}
            </Panel>

            <Panel icon={<ShieldAlert size={14} />} title={`Open alerts${alerts ? ` (${alerts.length})` : ''}`}>
              {alerts === null ? <Empty>Loading…</Empty> : alerts.length ? (
                <ul className="space-y-2 text-[13.5px] max-h-72 overflow-auto pr-1">
                  {alerts.map(a => (
                    <li key={a.id} className="flex items-start gap-2 min-w-0">
                      <Chip tone={a.severity === 'CRITICAL' ? 'bad' : a.severity === 'WARNING' ? 'warn' : 'info'}>
                        {a.severity.toLowerCase()}</Chip>
                      <span className="min-w-0">
                        <span className="block text-slate-100">{a.title}</span>
                        {a.detail && <span className="block text-[12px] text-slate-400 truncate">{a.detail}</span>}
                      </span>
                      <span className="ml-auto shrink-0 text-[12px] text-slate-500">{relative(a.created_at)}</span>
                    </li>))}
                </ul>
              ) : <p className="flex items-center gap-1.5 text-[13px] text-ok-soft"><ShieldCheck size={14} /> No open alerts</p>}
            </Panel>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-4">
          <Panel icon={<DoorOpen size={14} />} title="Door activity">
            {events === null ? <Empty>Loading…</Empty> : events.length ? (
              <ul className="space-y-1.5 text-[13px]">
                {events.slice(0, 12).map(e => {
                  const why = denialShort(e.reason)
                  return (
                    <li key={e.id} className="flex items-center gap-2 min-w-0">
                      <Chip tone={eventTone(e.event_type)}>{eventLabel(e.event_type)}</Chip>
                      <span className="truncate text-slate-200">
                        {e.user_name ?? (e.method ? methodLabel(e.method) : '')}
                        {why && <span className="text-bad-soft"> · {why}</span>}</span>
                      <span className="ml-auto shrink-0 text-[12px] text-slate-500">{relative(e.created_at)}</span>
                    </li>)
                })}
              </ul>
            ) : <Empty>No door activity recorded.</Empty>}
          </Panel>

          <Panel icon={<CalendarClock size={14} />} title="Bookings">
            {status === null ? <Empty>Loading…</Empty> : <>
              <div className="text-[13.5px]">
                {status.current_booking
                  ? <>Now: <b className="text-white">{status.current_booking.user_name ?? 'booked'}</b> until {fmtTime(status.current_booking.end_time)}</>
                  : <span className="text-slate-400">Free now</span>}</div>
              {status.upcoming.length ? (
                <ul className="mt-2 space-y-1 text-[13px]">
                  {status.upcoming.slice(0, 6).map((b, i) => (
                    <li key={b.booking_id ?? i} className="flex gap-2 min-w-0">
                      <span className="shrink-0 text-slate-400 tnum">{fmtDateTime(b.start_time)}</span>
                      <span className="truncate text-slate-200">{b.user_name ?? 'Booked'}</span>
                    </li>))}
                </ul>
              ) : <p className="mt-2 text-[12.5px] text-slate-500">Nothing booked next.</p>}
            </>}
          </Panel>

          <Panel icon={<Cpu size={14} />} title="Devices">
            {status === null ? <Empty>Loading…</Empty> : status.devices.length ? (
              <ul className="space-y-1.5 text-[13px]">
                {status.devices.map(d => (
                  <li key={d.id} className="flex items-center gap-2 min-w-0">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${d.state === 'ONLINE' ? 'bg-ok'
                      : d.state === 'OFFLINE' ? 'bg-bad' : 'bg-slate-500'}`} />
                    <span className="truncate text-slate-200">{d.name}</span>
                    <span className="truncate text-[11.5px] text-slate-500">{DEVICE[d.device_type] ?? d.device_type}</span>
                    <span className="ml-auto shrink-0 text-[12px] text-slate-500">
                      {d.state === 'NO_DATA' ? 'never reported' : d.last_seen_at ? relative(d.last_seen_at) : ''}</span>
                  </li>))}
              </ul>
            ) : <Empty>No devices registered.</Empty>}
          </Panel>

          <Panel icon={<Wrench size={14} />} title={`Issues${status ? ` (${status.open_issues} open)` : ''}`}>
            {status === null ? <Empty>Loading…</Empty> : status.recent_issues.length ? (
              <ul className="space-y-1.5 text-[13px]">
                {status.recent_issues.slice(0, 6).map(i => (
                  <li key={i.id} className="flex items-center gap-2 min-w-0">
                    <Chip tone={severityTone(i.severity)}>{i.severity.toLowerCase()}</Chip>
                    <span className="truncate text-slate-200">{i.title}</span>
                    <Chip tone={issueStatusTone(i.status)} className="ml-auto shrink-0">{STATUS_LABEL[i.status] ?? i.status}</Chip>
                  </li>))}
              </ul>
            ) : <Empty>No issues reported.</Empty>}
          </Panel>
        </div>
      </main>

      {camBig && cam && <CameraFullScreen deviceId={cam.device_id} title={t.code} sub={t.name}
                                          badges={badges} onClose={() => setCamBig(false)} />}
    </div>,
    document.body)
}

function Panel({ icon, title, aside, children }: {
  icon: ReactNode; title: string; aside?: ReactNode; children: ReactNode
}) {
  return (
    <section className="rounded-2xl border border-ink-600/70 bg-ink-800/50 p-4 min-w-0">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-accent-300">{icon}</span>
        <h3 className="text-[11.5px] font-bold uppercase tracking-[0.16em] text-slate-300">{title}</h3>
        {aside && <span className="ml-auto">{aside}</span>}
      </div>
      {children}
    </section>
  )
}

const Empty = ({ children }: { children: ReactNode }) =>
  <p className="text-[13px] text-slate-500">{children}</p>

function Big({ label, value, icon, tone }: { label: string; value: string; icon: ReactNode; tone: Tone }) {
  return (
    <div className="rounded-xl border border-ink-600/60 bg-ink-900/60 px-3 py-2 min-w-0">
      <div className="text-[10.5px] uppercase tracking-[0.16em] text-slate-400">{label}</div>
      <div className={`flex items-center gap-2 text-[22px] font-extrabold leading-tight ${TEXT[tone]}`}>
        {icon}<span className="truncate">{value}</span></div>
    </div>
  )
}

function Reading({ icon, value, at }: { icon: ReactNode; value?: string | false; at?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-slate-400">{icon}</span>
      {value ? <><b className="text-white">{value}</b>{at && <span className="text-[12px] text-slate-500">{relative(at)}</span>}</>
        : <span className="text-slate-500">No data</span>}
    </span>
  )
}
