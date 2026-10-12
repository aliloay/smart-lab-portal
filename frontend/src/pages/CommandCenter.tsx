/**
 * Smart Lab Command Center.
 *
 * This view combines existing staff APIs and live updates. Missing reports stay
 * unknown; the page does not issue door, robot, inventory, or safety commands.
 */
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, AlertTriangle, ArrowRight, Bot, Cctv, Clock3, Database, DoorClosed,
  DoorOpen, Expand, Flame, Minimize2, MonitorUp, Radar, RefreshCw, ShieldAlert, Thermometer,
  Users, XCircle,
} from 'lucide-react'
import {
  AccessEvent, ActiveHazard, Alert, LabEnvironment, MonitorTile, RobotEventRow,
  SecurityCamera, SecurityEvent, ServiceHealth, api,
} from '../lib/api'
import { useLive, useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import LabFloor from '../components/LabFloor'
import LiveCameraFeed from '../components/LiveCameraFeed'
import { Chip, ErrorBanner, Skeleton, Tone } from '../components/ui'
import { modelFor } from '../components/robot/kinematics'
import { DemoBadge, RobotStateChip, useRobots } from '../components/robot/robotLive'
import './CommandCenterWall.css'

const RobotTwin = lazy(() => import('../components/robot/RobotTwin'))

type HealthState = 'ONLINE' | 'DEGRADED' | 'OFFLINE' | 'STALE' | 'UNKNOWN' | 'SIMULATION'
type EventKind = 'ACCESS' | 'VISION' | 'ROBOTS' | 'ENVIRONMENT'
type DashboardEvent = {
  key: string
  at: string | null
  title: string
  detail: string
  source: string
  kind: EventKind
  tone: Tone
  labId: number | null
  href: string
}
type RobotActivity = RobotEventRow & { robot: string; robotId: number; labId: number }

const HEALTH_TONE: Record<HealthState, Tone> = {
  ONLINE: 'ok', DEGRADED: 'bad', OFFLINE: 'bad', STALE: 'warn', UNKNOWN: 'idle', SIMULATION: 'violet',
}
const HEALTH_LABEL: Record<HealthState, string> = {
  ONLINE: 'Online', DEGRADED: 'Offline', OFFLINE: 'Offline', STALE: 'Stale data',
  UNKNOWN: 'Unknown', SIMULATION: 'Simulated',
}
const EVENT_LABEL: Record<EventKind | 'ALL', string> = {
  ALL: 'All events', ACCESS: 'Access', VISION: 'People & vision', ROBOTS: 'Robots', ENVIRONMENT: 'Environment',
}

function stateOf(state: string | null | undefined): HealthState {
  if (state === 'ONLINE' || state === 'DEGRADED' || state === 'OFFLINE' || state === 'STALE'
    || state === 'UNKNOWN' || state === 'SIMULATION') return state
  if (state === 'TELEMETRY_STALE') return 'STALE'
  return 'UNKNOWN'
}

function aggregateHealth(states: HealthState[]): HealthState {
  if (!states.length) return 'UNKNOWN'
  if (states.every(state => state === 'OFFLINE')) return 'OFFLINE'
  if (states.some(state => state === 'OFFLINE' || state === 'DEGRADED')) return 'DEGRADED'
  if (states.some(state => state === 'STALE')) return 'STALE'
  if (states.some(state => state === 'UNKNOWN')) return 'UNKNOWN'
  if (states.some(state => state === 'SIMULATION')) return 'SIMULATION'
  return 'ONLINE'
}

function titleCase(value: string) {
  return value.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase())
}

function formatValue(value: number | null | undefined, unit: string | null | undefined) {
  if (value == null) return '—'
  const digits = Math.abs(value) < 10 && !Number.isInteger(value) ? 1 : 0
  return value.toFixed(digits) + (unit ? ' ' + unit : ' · raw')
}

function Clock({ compact = false }: { compact?: boolean }) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return (
    <div className={'text-right ' + (compact ? 'wall-clock' : '')}>
      <div className={'font-mono font-semibold tracking-tight text-white tabular-nums ' + (compact ? 'text-lg' : 'text-2xl sm:text-3xl')}>
        {now.toLocaleTimeString([], { hour12: false })}
      </div>
      <div className={compact ? 'text-[10px] text-slate-400' : 'text-xs text-slate-400'}>
        {now.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })}
      </div>
    </div>
  )
}

function HealthBadge({ state, label }: { state: HealthState; label?: string }) {
  return <Chip tone={HEALTH_TONE[state]} dot>{label ?? HEALTH_LABEL[state]}</Chip>
}

function MetricLink({ to, label, value, sub, tone = 'neutral', icon, compact = false }: {
  to: string; label: string; value: string | number; sub: string
  tone?: 'neutral' | 'good' | 'warn' | 'bad'; icon: ReactNode; compact?: boolean
}) {
  const valueTone = tone === 'good' ? 'text-emerald-300' : tone === 'warn' ? 'text-amber-300'
    : tone === 'bad' ? 'text-rose-300' : 'text-white'
  return (
    <Link to={to} className={'group min-w-0 rounded-xl border border-white/[.08] bg-[#151d27] transition hover:border-cyan-400/40 hover:bg-[#19232e] focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 ' + (compact ? 'wall-metric p-2' : 'p-4')}>
      <div className="flex items-center justify-between gap-3">
        <span className={compact ? 'truncate text-[10px] font-medium text-slate-400' : 'text-xs font-medium text-slate-400'}>{label}</span>
        <span className="shrink-0 text-slate-500 transition group-hover:text-cyan-300">{icon}</span>
      </div>
      <div className={(compact ? 'mt-0.5 text-lg' : 'mt-2 text-2xl') + ' truncate font-semibold tabular-nums ' + valueTone}>{value}</div>
      <div className={'mt-0.5 flex min-w-0 items-center justify-between gap-2 text-slate-500 ' + (compact ? 'text-[9px]' : 'text-[11px]')}>
        <span className="truncate">{sub}</span><ArrowRight size={13} className={'shrink-0 opacity-0 transition group-hover:opacity-100 ' + (compact ? 'hidden' : '')} />
      </div>
    </Link>
  )
}

function HealthPanel({ services, serviceError, connected, compact = false }: {
  services: ServiceHealth[] | null; serviceError: boolean; connected: boolean; compact?: boolean
}) {
  const platform = services?.filter(service => service.device_id == null) ?? []
  const devices = services?.filter(service => service.device_id != null) ?? []
  const platformStates: HealthState[] = services === null ? ['UNKNOWN']
    : platform.map(service => service.key === 'websocket'
      ? (connected ? 'ONLINE' : 'DEGRADED')
      : stateOf(service.state))
  const deviceStates = services === null ? ['UNKNOWN' as HealthState] : devices.map(service => stateOf(service.state))
  const platformHealth = aggregateHealth(platformStates)
  const labHealth = aggregateHealth(deviceStates)
  const overall = aggregateHealth([...platformStates, ...deviceStates])
  const reporting = devices.filter(service => ['ONLINE', 'DEGRADED', 'SIMULATION'].includes(service.state)).length
  const failures = services?.filter(service => ['DEGRADED', 'OFFLINE'].includes(service.state)).length ?? 0
  const unknown = services?.filter(service => service.state === 'UNKNOWN').length ?? 0
  const summary = overall === 'ONLINE' ? 'All monitored sources are reporting'
    : overall === 'DEGRADED' || overall === 'OFFLINE' ? 'Investigation required'
      : overall === 'STALE' ? 'Some readings are stale'
        : overall === 'SIMULATION' ? 'Simulation data is present'
          : 'Some subsystem states are unknown'

  if (compact) return (
    <div className="wall-health-summary" aria-label="System health summary" title={summary}>
      <div className="wall-health-overall"><span>System</span><HealthBadge state={overall} label={overall === 'ONLINE' ? 'Operational' : HEALTH_LABEL[overall]} /></div>
      <div className="wall-health-item"><span>Platform</span><HealthBadge state={platformHealth} /></div>
      <div className="wall-health-item"><span>Lab devices</span><HealthBadge state={labHealth} /></div>
      <div className="wall-health-item"><span>Live</span><Chip tone={connected ? 'ok' : 'warn'} dot>{connected ? 'Connected' : 'Reconnecting'}</Chip></div>
      {serviceError && <span className="wall-health-error">Check unavailable</span>}
    </div>
  )

  return (
    <section className="rounded-2xl border border-white/[.09] bg-[#121922] p-4 sm:p-5" aria-label="System health">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl border border-cyan-300/20 bg-cyan-300/[.08] text-cyan-200">
            <Activity size={18} />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-white">System condition</h2>
              <HealthBadge state={overall} label={overall === 'ONLINE' ? 'Operational' : HEALTH_LABEL[overall]} />
              <span className="text-xs text-slate-500">{summary}</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">Platform services and laboratory devices are assessed separately. Missing reports stay unknown.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="rounded-lg border border-white/[.07] bg-black/15 px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Platform</div>
            <div className="mt-1"><HealthBadge state={platformHealth} /></div>
          </div>
          <div className="rounded-lg border border-white/[.07] bg-black/15 px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Lab devices</div>
            <div className="mt-1"><HealthBadge state={labHealth} /></div>
          </div>
          <div className="rounded-lg border border-white/[.07] bg-black/15 px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Live updates</div>
            <div className="mt-1"><Chip tone={connected ? 'ok' : 'warn'} dot>{connected ? 'Connected' : 'Reconnecting'}</Chip></div>
          </div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-white/[.06] pt-3 text-[11px] text-slate-500">
        <span>Devices reporting: <b className="text-slate-200 tabular-nums">{services === null ? '—' : reporting + '/' + devices.length}</b></span>
        <span>Needs attention: <b className={failures ? 'text-rose-300 tabular-nums' : 'text-slate-200 tabular-nums'}>{services === null ? '—' : failures}</b></span>
        <span>Unknown: <b className="text-slate-200 tabular-nums">{services === null ? '—' : unknown}</b></span>
        {serviceError && <span className="text-amber-300">Service check failed; state is unknown.</span>}
        <details className="ml-auto">
          <summary className="cursor-pointer select-none text-cyan-300 hover:text-cyan-200">Subsystem details</summary>
          <div className="mt-3 grid w-full gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {services?.map(service => (
              <div key={service.key} className="rounded-lg border border-white/[.07] bg-black/20 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-slate-200">{service.name}</span>
                  <HealthBadge state={stateOf(service.state)} />
                </div>
                <p className="mt-1 break-words text-[11px] text-slate-500">
                  {service.detail}{service.latency_ms != null ? ' · ' + service.latency_ms + ' ms' : ''}
                </p>
              </div>
            ))}
            {services?.length === 0 && <p className="text-xs text-slate-500">No subsystem report is available.</p>}
          </div>
        </details>
      </div>
    </section>
  )
}

function AttentionPanel({ alerts, failed, scopeId, compact = false }: {
  alerts: Alert[] | null; failed: boolean; scopeId: number | null; compact?: boolean
}) {
  const visible = (alerts ?? []).filter(alert => scopeId == null || alert.lab_id === scopeId)
    .slice().sort((a, b) => {
      const rank: Record<string, number> = { CRITICAL: 0, WARNING: 1, INFO: 2 }
      const bySeverity = (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3)
      return bySeverity || b.created_at.localeCompare(a.created_at)
    })
  const critical = visible.filter(alert => alert.severity === 'CRITICAL').length

  return (
    <section className={'flex min-h-0 min-w-0 flex-col rounded-2xl border border-white/[.09] bg-[#151a21] ' + (compact ? 'wall-attention p-3' : 'min-h-[330px] p-4 sm:p-5')} aria-labelledby={compact ? 'wall-attention-heading' : 'attention-heading'}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert size={16} className="text-amber-300" />
            <h2 id={compact ? 'wall-attention-heading' : 'attention-heading'} className="text-sm font-semibold text-white">{compact ? 'Priority incidents' : 'Needs attention'}</h2>
          </div>
          {!compact && <p className="mt-1 text-xs text-slate-500">Open alerts, ordered by severity. Original records remain available.</p>}
        </div>
        <Link to="/admin/alerts" className="shrink-0 text-xs font-medium text-cyan-300 hover:text-cyan-200">View all <ArrowRight size={12} className="inline" /></Link>
      </div>
      {alerts === null && failed ? (
        <div className="my-auto py-10 text-center">
          <AlertTriangle size={22} className="mx-auto text-amber-300" />
          <p className="mt-3 text-sm font-medium text-slate-200">Alert status unavailable</p>
          <p className="mt-1 text-xs text-slate-500">The alert source could not be reached. No zero count is inferred.</p>
        </div>
      ) : alerts === null ? (
        <div className="mt-4 space-y-3"><Skeleton className="h-16" /><Skeleton className="h-16" /><Skeleton className="h-16" /></div>
      ) : !visible.length ? (
        <div className="my-auto py-10 text-center">
          <div className="mx-auto grid h-10 w-10 place-items-center rounded-full border border-emerald-300/20 bg-emerald-300/[.06] text-emerald-300"><ShieldAlert size={17} /></div>
          <p className="mt-3 text-sm font-medium text-slate-200">No open alerts in this scope</p>
          <p className="mt-1 text-xs text-slate-500">The alert service returned no unresolved records.</p>
        </div>
      ) : (
        <>
          <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-500">
            {critical > 0 && <Chip tone="bad" dot>{critical} critical</Chip>}
            <span>{visible.length} open · {compact ? 'highest priority first' : 'in scope'}</span>
          </div>
          <ul className={'mt-2 min-h-0 flex-1 ' + (compact ? 'wall-alert-list space-y-1.5' : 'space-y-2')}>
            {visible.slice(0, compact ? 4 : 5).map(alert => {
              const tone: Tone = alert.severity === 'CRITICAL' ? 'bad' : alert.severity === 'WARNING' ? 'warn' : 'info'
              return (
                <li key={alert.id} className={'rounded-xl border border-white/[.07] bg-black/20 ' + (compact ? 'wall-alert-item p-2' : 'p-3')}>
                  <div className="flex items-start gap-2">
                    <span className={'mt-1 h-2 w-2 shrink-0 rounded-full ' + (alert.severity === 'CRITICAL' ? 'bg-rose-400' : alert.severity === 'WARNING' ? 'bg-amber-300' : 'bg-cyan-300')} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={compact ? 'wall-alert-title text-xs font-medium text-slate-100' : 'text-[13px] font-medium text-slate-100'}>{alert.title}</span>
                        <Chip tone={tone}>{alert.severity.toLowerCase()}</Chip>
                      </div>
                      <p className={'mt-1 text-slate-400 ' + (compact ? 'line-clamp-1 text-[10px]' : 'line-clamp-2 text-xs leading-relaxed')}>{alert.detail}</p>
                      <div className={'mt-1 flex flex-wrap gap-x-3 gap-y-1 text-slate-500 ' + (compact ? 'text-[9px]' : 'text-[10.5px]')}>
                        <span>{alert.lab_code ?? 'Lab not reported'}</span>
                        {alert.device_id != null && <Link to="/admin/devices" className="text-cyan-300 hover:text-cyan-200">Device {alert.device_id}</Link>}
                        <span>Open since {relative(alert.created_at)}</span>
                      </div>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
          {visible.length > (compact ? 4 : 5) && <Link to="/admin/alerts" className="mt-2 inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200">{visible.length - (compact ? 4 : 5)} more incidents <ArrowRight size={13} /></Link>}
        </>
      )}
    </section>
  )
}

function CameraPanel({ cam, loading, failed, compact = false }: {
  cam: SecurityCamera | null; loading: boolean; failed: boolean; compact?: boolean
}) {
  const online = cam?.online === true
  const sourceOk = cam?.source_ok === true
  const frameAge = cam?.metrics?.frame_age_ms_p50
  const status: HealthState = !cam ? 'UNKNOWN' : cam.online === false ? 'OFFLINE'
    : cam.online == null || cam.source_ok == null ? 'UNKNOWN'
      : cam.source_ok === false ? 'DEGRADED' : 'ONLINE'
  const hint = failed ? 'Camera health could not be retrieved from the portal.'
    : !cam ? 'No security camera is registered for this scope.'
    : !online ? 'The camera service has no recent online report.'
      : cam.source_ok === false ? 'The service responds, but its camera source is not sending frames.'
        : cam.source_ok == null ? 'The camera source has not reported its frame state.'
          : null

  return (
    <section id="camera-panel" className={'overflow-hidden rounded-2xl border border-white/[.09] bg-[#121922] ' + (compact ? 'wall-subpanel wall-camera-panel' : '')} aria-labelledby={compact ? 'wall-camera-heading' : 'camera-heading'}>
      <div className={'flex items-center justify-between gap-3 border-b border-white/[.07] ' + (compact ? 'px-2.5 py-1.5' : 'px-4 py-3')}>
        <div className="flex min-w-0 items-center gap-2">
          <Cctv size={15} className="shrink-0 text-cyan-300" />
          <div className="min-w-0">
            <h2 id={compact ? 'wall-camera-heading' : 'camera-heading'} className="truncate text-sm font-semibold text-white">Camera</h2>
            {!compact && <p className="truncate text-[11px] text-slate-500">{cam?.lab_code ?? 'Camera data'}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <HealthBadge state={status} label={compact ? HEALTH_LABEL[status] : status === 'ONLINE' ? 'Source reports frames' : HEALTH_LABEL[status]} />
          <Link to="/admin/security" aria-label="Open security camera page" className="text-slate-400 hover:text-cyan-300"><ArrowRight size={15} /></Link>
        </div>
      </div>
      {loading ? <Skeleton className={compact ? 'wall-camera-preview' : 'aspect-video rounded-none'} /> : online && sourceOk && cam ? (
        <div className={'relative aspect-video bg-[#090d12] ' + (compact ? 'wall-camera-preview' : '')}>
          <LiveCameraFeed deviceId={cam.device_id} intervalMs={1000} className="h-full w-full" fit="contain" />
          <div className={'absolute bottom-1 left-1 flex flex-wrap gap-1 ' + (compact ? 'wall-camera-meta' : 'bottom-2 left-2 gap-2')}>
            <Chip tone="ok" dot>Source connected</Chip>
            {frameAge != null && <Chip tone="idle">{compact ? `${Math.round(frameAge)} ms` : `Measured frame age ${Math.round(frameAge)} ms`}</Chip>}
          </div>
        </div>
      ) : (
        <div className={'flex aspect-video flex-col items-center justify-center bg-[radial-gradient(ellipse_at_center,_rgba(34,48,62,.45),_rgba(10,14,19,.98))] text-center ' + (compact ? 'wall-camera-preview wall-camera-placeholder px-2' : 'px-6')}>
          {status === 'OFFLINE' ? <XCircle size={23} className="text-rose-300" />
            : status === 'DEGRADED' ? <AlertTriangle size={23} className="text-amber-300" />
              : <Cctv size={23} className="text-slate-500" />}
          <p className={compact ? 'mt-1 text-[10px] font-medium text-slate-200' : 'mt-3 text-sm font-medium text-slate-200'}>{failed ? 'Camera status unavailable' : status === 'DEGRADED' ? 'No current camera frames' : status === 'OFFLINE' ? 'Camera unavailable' : 'Camera state unknown'}</p>
          {!compact && <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">{hint}</p>}
          {compact && <p className="text-[9px] text-slate-500">{hint}</p>}
          {cam?.last_seen_at && <p className={compact ? 'text-[9px] text-slate-500' : 'mt-2 text-[11px] text-slate-500'}>Last seen {relative(cam.last_seen_at)} · frame {frameAge == null ? 'not measured' : Math.round(frameAge) + ' ms'}</p>}
        </div>
      )}
      {cam && (online || cam.people != null || cam.inside > 0) && (
        <div className={'flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-white/[.07] ' + (compact ? 'px-2.5 py-1 text-[9px]' : 'px-4 py-3 text-xs')}>
          <span className="inline-flex items-center gap-1.5 text-slate-300"><Users size={13} className="text-cyan-300" />
            Camera: <b className="text-white tabular-nums">{online && sourceOk && cam.people != null ? cam.people : '—'}</b></span>
          <span className="inline-flex items-center gap-1.5 text-slate-400"><DoorClosed size={13} />
            Door records: <b className="text-slate-200 tabular-nums">{cam.inside}</b></span>
          {!compact && <span className="text-slate-500">Counts come from separate sources.</span>}
        </div>
      )}
    </section>
  )
}

function EnvironmentPanel({ environment, loading, failed, labCode, compact = false }: {
  environment: LabEnvironment | null; loading: boolean; failed: boolean; labCode: string; compact?: boolean
}) {
  const metrics = environment?.metrics
  const rows: { key: keyof LabEnvironment['metrics']; label: string; icon: ReactNode }[] = [
    { key: 'temperature', label: 'Temperature', icon: <Thermometer size={14} /> },
    { key: 'humidity', label: 'Humidity', icon: <Activity size={14} /> },
    { key: 'smoke', label: 'Smoke / gas signal', icon: <Activity size={14} /> },
    { key: 'flame', label: 'Flame sensor', icon: <Flame size={14} /> },
    { key: 'water_leak', label: 'Water leak', icon: <Activity size={14} /> },
    { key: 'motion', label: 'Motion', icon: <Activity size={14} /> },
    { key: 'emergency', label: 'Emergency', icon: <ShieldAlert size={14} /> },
  ]
  const wallRows = rows.filter(row => row.key !== 'water_leak')
  if (compact) return (
    <section className="wall-subpanel wall-environment-panel" aria-labelledby="wall-environment-heading">
      <div className="wall-subpanel-heading">
        <div className="flex min-w-0 items-center gap-1.5"><Activity size={13} className="shrink-0 text-cyan-300" /><h2 id="wall-environment-heading" className="truncate text-xs font-semibold text-white">Environment</h2></div>
        <Link to="/admin/operations" className="shrink-0 text-[10px] text-cyan-300 hover:text-cyan-200">Details <ArrowRight size={11} className="inline" /></Link>
      </div>
      {loading ? <div className="grid min-h-0 flex-1 grid-cols-3 gap-1.5 p-2"><Skeleton className="h-full" /><Skeleton className="h-full" /><Skeleton className="h-full" /><Skeleton className="h-full" /><Skeleton className="h-full" /><Skeleton className="h-full" /></div>
        : !environment ? <p className="m-2 text-[10px] text-slate-400">{failed ? 'Environment data unavailable.' : 'No environment report for ' + labCode + '.'}</p>
          : <>
            <div className="flex items-center gap-1.5 px-2 pt-1 text-[9px] text-slate-400">
              <span className={'h-1.5 w-1.5 rounded-full ' + (environment.node?.online === true ? 'bg-emerald-400' : environment.node?.online === false ? 'bg-rose-400' : 'bg-slate-500')} />
              <span>Sensor node {environment.node?.online === true ? 'online' : environment.node?.online === false ? 'offline' : 'unknown'}</span>
              {environment.node?.last_seen_at && <span className="ml-auto truncate">{relative(environment.node.last_seen_at)}</span>}
            </div>
            <div className="wall-environment-values">
              {wallRows.map(row => {
                const metric = metrics?.[row.key]
                const tone = metric?.quality === 'VALID' ? 'text-emerald-300'
                  : metric?.quality === 'STALE' ? 'text-amber-300'
                    : metric?.quality === 'OUT_OF_RANGE' ? 'text-rose-300' : 'text-slate-500'
                return <div key={row.key} className="wall-environment-value" title={`${row.label}: ${metric ? formatValue(metric.value, metric.unit) + ' · ' + (metric.quality ?? 'No data') : 'No data'}`}>
                  <span className="truncate text-[8px] font-semibold text-slate-400">{row.label}</span>
                  <b className={'truncate text-[11px] tabular-nums ' + tone}>{metric ? formatValue(metric.value, metric.unit) : '—'}</b>
                  <span className={'truncate text-[7px] font-semibold ' + tone}>{metric?.quality ? titleCase(metric.quality) : 'No data'}</span>
                </div>
              })}
            </div>
          </>}
    </section>
  )
  return (
    <section className="rounded-2xl border border-white/[.09] bg-[#121922] p-4" aria-labelledby="environment-heading">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Activity size={15} className="text-cyan-300" /><h2 id="environment-heading" className="text-sm font-semibold text-white">Environment</h2></div>
          <p className="mt-1 text-[11px] text-slate-500">{labCode || 'Selected lab'} · sensor data as reported</p>
        </div>
        <Link to="/admin/operations" className="text-xs text-cyan-300 hover:text-cyan-200">Details <ArrowRight size={12} className="inline" /></Link>
      </div>
      {loading ? <div className="mt-4 grid grid-cols-2 gap-2"><Skeleton className="h-16" /><Skeleton className="h-16" /><Skeleton className="h-16" /><Skeleton className="h-16" /></div>
        : !environment ? <p className="mt-5 rounded-lg border border-white/[.06] bg-black/15 p-4 text-xs text-slate-500">{failed ? 'Environment data could not be retrieved.' : 'No environment report is available for this lab.'}</p>
          : (
            <>
              <div className="mt-3 flex items-center gap-2 text-[11px]">
                <span className={'h-1.5 w-1.5 rounded-full ' + (environment.node?.online === true ? 'bg-emerald-400' : environment.node?.online === false ? 'bg-rose-400' : 'bg-slate-500')} />
                <span className="text-slate-400">Sensor node</span>
                <span className="font-medium text-slate-200">{environment.node?.online === true ? 'online' : environment.node?.online === false ? 'offline' : 'unknown'}</span>
                {environment.node?.last_seen_at && <span className="ml-auto text-slate-500">Reported {relative(environment.node.last_seen_at)}</span>}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {rows.map(row => {
                  const metric = metrics?.[row.key]
                  const qTone: Tone = metric?.quality === 'VALID' ? 'ok'
                    : metric?.quality === 'STALE' ? 'warn'
                      : metric?.quality === 'OUT_OF_RANGE' ? 'bad' : 'idle'
                  return (
                    <div key={row.key} className="min-w-0 rounded-xl border border-white/[.07] bg-black/20 p-3">
                      <div className="flex items-center gap-1.5 text-[10.5px] text-slate-500">{row.icon}<span className="truncate">{row.label}</span></div>
                      <div className="mt-2 truncate text-base font-semibold tabular-nums text-slate-100">
                        {metric ? formatValue(metric.value, metric.unit) : '—'}
                      </div>
                      <div className="mt-1"><Chip tone={qTone}>{metric?.quality ? titleCase(metric.quality) : 'No data'}</Chip></div>
                    </div>
                  )
                })}
              </div>
              <p className="mt-2 text-[10.5px] text-slate-600">Smoke/gas values are raw sensor readings; no ppm calibration is implied.</p>
            </>
          )}
    </section>
  )
}

function RobotPanel({ robots, labId, compact = false }: {
  robots: ReturnType<typeof useRobots>['robots']; labId: number | null; compact?: boolean
}) {
  const scoped = (robots ?? []).filter(robot => labId == null || robot.lab_id === labId)
  if (compact) return (
    <section className="wall-subpanel wall-robot-panel" aria-labelledby="wall-robots-heading">
      <div className="wall-subpanel-heading">
        <div className="flex min-w-0 items-center gap-1.5"><Bot size={13} className="shrink-0 text-cyan-300" /><h2 id="wall-robots-heading" className="truncate text-xs font-semibold text-white">Robot fleet</h2></div>
        <Link to="/robots" className="shrink-0 text-[10px] text-cyan-300 hover:text-cyan-200">Details <ArrowRight size={11} className="inline" /></Link>
      </div>
      {robots === null ? <p className="m-2 text-[10px] text-slate-400">Robot telemetry unavailable · movement unknown.</p>
        : scoped.length === 0 ? <p className="m-2 text-[10px] text-slate-400">No robot telemetry · movement unknown.</p>
          : <div className="wall-robot-list">
            {scoped.slice(0, 3).map(robot => (
              <Link key={robot.device_id} to={'/robots/' + robot.device_id} className="wall-robot-row">
                <span className="min-w-0 truncate text-[10px] font-medium text-slate-100">{robot.name}</span>
                {robot.demo && <DemoBadge />}
                <RobotStateChip state={robot.state} />
                <span className="ml-auto truncate text-[9px] text-slate-500">{robot.last_seen_at ? relative(robot.last_seen_at) : 'time unknown'}</span>
              </Link>
            ))}
            {scoped.length > 3 && <Link to="/robots" className="px-2 text-[9px] text-cyan-300">+{scoped.length - 3} more robots</Link>}
          </div>}
    </section>
  )
  return (
    <section className="rounded-2xl border border-white/[.09] bg-[#121922] p-4" aria-labelledby="robots-heading">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2"><Bot size={15} className="text-cyan-300" /><h2 id="robots-heading" className="text-sm font-semibold text-white">Robot fleet</h2></div>
        <Link to="/robots" className="text-xs text-cyan-300 hover:text-cyan-200">Fleet details <ArrowRight size={12} className="inline" /></Link>
      </div>
      {robots === null ? <div className="mt-3 space-y-2"><Skeleton className="h-16" /><Skeleton className="h-16" /></div>
        : scoped.length === 0 ? <div className="mt-4 rounded-lg border border-white/[.06] bg-black/15 p-4 text-xs text-slate-500">No robot telemetry is reporting in this scope. Movement state is unknown.</div>
          : <div className="mt-3 space-y-2">
            {scoped.slice(0, 3).map(robot => (
              <Link key={robot.device_id} to={'/robots/' + robot.device_id} className="flex items-center gap-3 rounded-xl border border-white/[.07] bg-black/20 p-2.5 transition hover:border-cyan-400/30">
                <Suspense fallback={<Skeleton className="h-12 w-16 shrink-0" />}>
                  <RobotTwin model={modelFor(robot.model)} q={robot.q ?? null} moving={robot.state === 'MOVING' ? robot.joints_moving : null} stale={robot.state === 'TELEMETRY_STALE'} compact className="h-12 w-16 shrink-0 bg-transparent" />
                </Suspense>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-xs font-medium text-slate-100">{robot.name}</span>
                    {robot.demo && <DemoBadge />}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5"><RobotStateChip state={robot.state} /></div>
                  <div className="mt-1 text-[10px] text-slate-500">{robot.last_seen_at ? 'Last telemetry ' + relative(robot.last_seen_at) : 'Telemetry time unavailable'}</div>
                </div>
                <ArrowRight size={14} className="shrink-0 text-slate-600" />
              </Link>
            ))}
            {scoped.length > 3 && <Link to="/robots" className="block pt-1 text-center text-[11px] text-cyan-300 hover:text-cyan-200">View {scoped.length - 3} more</Link>}
          </div>}
    </section>
  )
}

function WallRecentEvents({ events, sourceError }: { events: DashboardEvent[]; sourceError: boolean }) {
  return (
    <section className="wall-subpanel wall-recent-panel" aria-labelledby="wall-recent-heading">
      <div className="wall-subpanel-heading">
        <div className="flex min-w-0 items-center gap-1.5"><Clock3 size={13} className="shrink-0 text-cyan-300" /><h2 id="wall-recent-heading" className="truncate text-xs font-semibold text-white">Recent events</h2></div>
        <Link to="/command#events-heading" className="shrink-0 text-[10px] text-cyan-300 hover:text-cyan-200">Full timeline <ArrowRight size={11} className="inline" /></Link>
      </div>
      {sourceError && <p className="px-2 pt-1 text-[9px] text-amber-300">Some event sources unavailable · list may be incomplete.</p>}
      {!events.length ? <p className="m-2 text-[10px] text-slate-400">No recent events returned.</p>
        : <ol className="wall-recent-list">
          {events.slice(0, 3).map(event => (
            <li key={event.key}>
              <Link to={event.href} className="wall-recent-event">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[10px] font-medium text-slate-200">{event.title}</span>
                  <span className="block truncate text-[9px] text-slate-500">{event.source}{event.detail ? ' · ' + event.detail : ''}</span>
                </span>
                <span className="shrink-0 text-[9px] text-slate-500">{event.at ? relative(event.at) : 'Time unknown'}</span>
              </Link>
            </li>
          ))}
        </ol>}
    </section>
  )
}

function EventStream({ events, active, onChange, sourceError }: {
  events: DashboardEvent[]; active: 'ALL' | EventKind; onChange: (kind: 'ALL' | EventKind) => void; sourceError: boolean
}) {
  const filters: ('ALL' | EventKind)[] = ['ALL', 'ACCESS', 'VISION', 'ROBOTS', 'ENVIRONMENT']
  const visible = active === 'ALL' ? events : events.filter(event => event.kind === active)
  return (
    <section id="events-timeline" className="rounded-2xl border border-white/[.09] bg-[#121922] p-4 sm:p-5" aria-labelledby="events-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Clock3 size={15} className="text-cyan-300" /><h2 id="events-heading" className="text-sm font-semibold text-white">Event timeline</h2></div>
          <p className="mt-1 text-xs text-slate-500">Recent access, vision, robot, and environment records from their existing sources.</p>
        </div>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Filter events">
          {filters.map(filter => (
            <button key={filter} type="button" aria-pressed={active === filter} onClick={() => onChange(filter)}
              className={'rounded-lg px-2.5 py-1.5 text-[11px] transition ' + (active === filter ? 'bg-cyan-300/15 text-cyan-200' : 'text-slate-500 hover:bg-white/[.05] hover:text-slate-200')}>
              {EVENT_LABEL[filter]}
            </button>
          ))}
        </div>
      </div>
      {sourceError && <p role="status" className="mt-3 rounded-lg border border-amber-300/15 bg-amber-300/[.04] px-3 py-2 text-[11px] text-amber-200/80">One or more event sources could not be read. The timeline may be incomplete.</p>}
      {!visible.length ? <div className="mt-4 rounded-xl border border-white/[.06] bg-black/15 p-6 text-center text-xs text-slate-500">No matching events were returned by the selected sources.</div>
        : <ol className="mt-4 divide-y divide-white/[.06]">
          {visible.slice(0, 20).map(event => (
            <li key={event.key}>
              <Link to={event.href} className="grid gap-2 py-3 transition hover:bg-white/[.02] sm:grid-cols-[110px_minmax(0,1fr)_auto] sm:items-start sm:px-2">
                <time className="font-mono text-[10.5px] tabular-nums text-slate-500">{event.at ? relative(event.at) : 'Time unavailable'}</time>
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-2">
                    <Chip tone={event.tone}>{EVENT_LABEL[event.kind]}</Chip>
                    <span className="text-xs font-medium text-slate-200">{event.title}</span>
                  </span>
                  <span className="mt-1 block truncate text-[11px] text-slate-500">{event.source}{event.detail ? ' · ' + event.detail : ''}</span>
                </span>
                <ArrowRight size={13} className="hidden text-slate-600 sm:block" />
              </Link>
            </li>
          ))}
        </ol>}
      <div className="mt-2 flex flex-wrap items-center gap-3 border-t border-white/[.06] pt-3 text-[11px]">
        <Link to="/admin/access" className="text-cyan-300 hover:text-cyan-200">Access history</Link>
        <Link to="/admin/security" className="text-cyan-300 hover:text-cyan-200">Vision events</Link>
        <Link to="/robots" className="text-cyan-300 hover:text-cyan-200">Robot events</Link>
        <Link to="/admin/operations" className="text-cyan-300 hover:text-cyan-200">Operations analytics</Link>
      </div>
    </section>
  )
}

function LabCards({ tiles, onSelect }: { tiles: MonitorTile[] | null; onSelect: (id: number) => void }) {
  if (tiles === null) return <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3"><Skeleton className="h-20" /><Skeleton className="h-20" /></div>
  if (!tiles.length) return null
  return (
    <section aria-label="Laboratory status" className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold text-slate-300">Laboratories</h2>
        <Link to="/labs" className="text-[11px] text-cyan-300 hover:text-cyan-200">All labs <ArrowRight size={12} className="inline" /></Link>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {tiles.map(tile => {
          const hasProblem = tile.hazards.length > 0 || tile.faults.length > 0 || tile.alert_count > 0
            || tile.controller_online === false || tile.env_online === false
          const hasUnknown = (tile.has_door && tile.controller_online == null) || tile.env_online == null
          const status: HealthState = hasProblem ? 'DEGRADED' : hasUnknown ? 'UNKNOWN' : 'ONLINE'
          return (
            <button type="button" key={tile.lab_id} onClick={() => onSelect(tile.lab_id)} className="rounded-xl border border-white/[.07] bg-[#121922] p-3 text-left transition hover:border-cyan-400/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400">
              <div className="flex items-center gap-2">
                <span className={'h-2 w-2 rounded-full ' + (status === 'ONLINE' ? 'bg-emerald-400' : status === 'DEGRADED' ? 'bg-rose-400' : 'bg-slate-500')} />
                <span className="text-xs font-semibold text-white">{tile.code}</span>
                <span className="min-w-0 truncate text-[11px] text-slate-500">{tile.name}</span>
                {tile.alert_count > 0 && <span className="ml-auto shrink-0 text-[10px] text-amber-300">{tile.alert_count} open</span>}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] text-slate-500">
                <span><Users size={11} className="mr-1 inline" />{tile.people.length} by door records</span>
                {tile.has_door && <span>{tile.controller_online === true ? (tile.door_closed === false ? <><DoorOpen size={11} className="mr-1 inline" />Door open</> : <><DoorClosed size={11} className="mr-1 inline" />Controller online</>) : tile.controller_online === false ? 'Controller offline' : 'Door state unknown'}</span>}
                {tile.hazards.length > 0 && <span className="text-rose-300">{tile.hazards.join(', ')}</span>}
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}

export default function CommandCenter({ wall = false }: { wall?: boolean }) {
  const [tiles, setTiles] = useState<MonitorTile[] | null>(null)
  const [cams, setCams] = useState<SecurityCamera[] | null>(null)
  const [services, setServices] = useState<ServiceHealth[] | null>(null)
  const [serviceError, setServiceError] = useState(false)
  const [alerts, setAlerts] = useState<Alert[] | null>(null)
  const [alertError, setAlertError] = useState(false)
  const [cameraError, setCameraError] = useState(false)
  const [environmentError, setEnvironmentError] = useState(false)
  const [eventSourceError, setEventSourceError] = useState(false)
  const [accessEvents, setAccessEvents] = useState<AccessEvent[]>([])
  const [secEvents, setSecEvents] = useState<SecurityEvent[]>([])
  const [hazards, setHazards] = useState<ActiveHazard[]>([])
  const [environments, setEnvironments] = useState<{ lab: { id: number; code: string; name: string }; env: LabEnvironment }[] | null>(null)
  const [robotEvents, setRobotEvents] = useState<RobotActivity[]>([])
  const [error, setError] = useState('')
  const [scope, setScope] = useState('all')
  const [eventFilter, setEventFilter] = useState<'ALL' | EventKind>('ALL')
  const [refreshAt, setRefreshAt] = useState<string | null>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const [fullscreenError, setFullscreenError] = useState('')
  const refreshTimer = useRef<number | null>(null)
  const { connected } = useLive()
  const { robots } = useRobots()

  const loadPageData = useCallback(async () => {
    const [monitorResult, cameraResult, serviceResult, alertResult, accessResult, securityResult, hazardResult, environmentResult] = await Promise.allSettled([
      api.monitor(), api.securityCameras(), api.systemServices(), api.alerts(true),
      api.events({ limit: 40 }), api.securityEvents({ limit: 30 }), api.activeHazards(), api.allEnvironments(),
    ])
    if (monitorResult.status === 'fulfilled') { setTiles(monitorResult.value.labs); setError('') }
    else { setTiles(null); setError('Could not retrieve laboratory status. Check the monitoring service.') }
    if (cameraResult.status === 'fulfilled') { setCams(cameraResult.value); setCameraError(false) }
    else { setCams(null); setCameraError(true) }
    if (serviceResult.status === 'fulfilled') {
      setServices(serviceResult.value.services)
      setServiceError(false)
      setRefreshAt(serviceResult.value.checked_at)
    } else { setServices([]); setServiceError(true) }
    if (alertResult.status === 'fulfilled') { setAlerts(alertResult.value); setAlertError(false) }
    else { setAlerts(null); setAlertError(true) }
    if (accessResult.status === 'fulfilled') setAccessEvents(accessResult.value)
    else setAccessEvents([])
    if (securityResult.status === 'fulfilled') setSecEvents(securityResult.value)
    else setSecEvents([])
    if (hazardResult.status === 'fulfilled') setHazards(hazardResult.value)
    else setHazards([])
    setEventSourceError(accessResult.status === 'rejected' || securityResult.status === 'rejected' || hazardResult.status === 'rejected')
    if (environmentResult.status === 'fulfilled') { setEnvironments(environmentResult.value); setEnvironmentError(false) }
    else { setEnvironments(null); setEnvironmentError(true) }
  }, [])

  const scheduleRefresh = useCallback(() => {
    if (refreshTimer.current != null) window.clearTimeout(refreshTimer.current)
    refreshTimer.current = window.setTimeout(loadPageData, 400)
  }, [loadPageData])

  useEffect(() => {
    loadPageData()
    const timer = window.setInterval(loadPageData, 20000)
    return () => {
      window.clearInterval(timer)
      if (refreshTimer.current != null) window.clearTimeout(refreshTimer.current)
    }
  }, [loadPageData])

  useEffect(() => {
    const syncFullscreen = () => {
      setFullscreen(Boolean(document.fullscreenElement))
      setFullscreenError('')
    }
    document.addEventListener('fullscreenchange', syncFullscreen)
    syncFullscreen()
    return () => document.removeEventListener('fullscreenchange', syncFullscreen)
  }, [])

  const robotIds = (robots ?? []).map(robot => robot.device_id).join(',')
  const loadRobotEvents = useCallback(() => {
    if (!robots?.length) { setRobotEvents([]); return }
    Promise.all(robots.map(robot => api.robotEvents(robot.device_id, 8)
      .then(events => events.map(event => ({ ...event, robot: robot.name, robotId: robot.device_id, labId: robot.lab_id })))
      .catch(() => [] as RobotActivity[])))
      .then(rows => setRobotEvents(rows.flat()))
  }, [robotIds]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadRobotEvents() }, [loadRobotEvents])

  useLiveMessages(message => {
    if (['security_state', 'door_state', 'env_update', 'hazard', 'device_state', 'alert'].includes(message.type)) scheduleRefresh()
    if (message.type === 'robot_status' || (message.type === 'staff' && message.kind === 'robot_event')) {
      scheduleRefresh()
      loadRobotEvents()
    }
  })

  const selectedLabId = scope === 'all' ? null : Number(scope)
  const scopedTiles = useMemo(() => (tiles ?? []).filter(tile => selectedLabId == null || tile.lab_id === selectedLabId), [tiles, selectedLabId])
  const currentCam = useMemo(() => {
    if (!cams?.length) return null
    return selectedLabId == null ? cams[0] : cams.find(camera => camera.lab_id === selectedLabId) ?? null
  }, [cams, selectedLabId])
  const currentTile = useMemo(() => {
    if (!scopedTiles.length) return null
    return (currentCam && scopedTiles.find(tile => tile.lab_id === currentCam.lab_id)) ?? scopedTiles[0]
  }, [scopedTiles, currentCam])
  const currentRobots = useMemo(() => (robots ?? []).filter(robot => selectedLabId == null || robot.lab_id === selectedLabId), [robots, selectedLabId])
  const floorRobots = useMemo(() => currentTile ? (robots ?? []).filter(robot => robot.lab_id === currentTile.lab_id) : [], [robots, currentTile])
  const environment = environments?.find(row => row.lab.id === currentTile?.lab_id)?.env ?? null
  const scopedAlerts = (alerts ?? []).filter(alert => selectedLabId == null || alert.lab_id === selectedLabId)
  const criticalAlerts = scopedAlerts.filter(alert => alert.severity === 'CRITICAL').length
  const peopleInside = tiles === null ? null : scopedTiles.reduce((count, tile) => count + tile.people.length, 0)
  const reportedDevices = services?.filter(service => service.device_id != null
    && ['ONLINE', 'DEGRADED', 'SIMULATION'].includes(service.state)).length ?? null
  const expectedDevices = services?.filter(service => service.device_id != null).length ?? null
  const reportingRobots = currentRobots.filter(robot => robot.state === 'MOVING' || robot.state === 'STATIONARY').length
  const movingRobots = currentRobots.filter(robot => !robot.demo && robot.state === 'MOVING').length
  const simulatedRobots = currentRobots.filter(robot => robot.demo && (robot.state === 'MOVING' || robot.state === 'STATIONARY')).length

  const dashboardEvents = useMemo<DashboardEvent[]>(() => {
    const rows: DashboardEvent[] = [
      ...accessEvents.map((event): DashboardEvent => ({
        key: 'a' + event.id, at: event.created_at,
        title: titleCase(event.event_type) + (event.result ? ' · ' + titleCase(event.result) : ''),
        detail: [event.user_name, event.method ? titleCase(event.method) : null, event.reason].filter(Boolean).join(' · '),
        source: event.lab_code ?? 'Access system', kind: 'ACCESS',
        tone: event.result?.toUpperCase() === 'DENIED' ? 'bad' : event.result?.toUpperCase() === 'GRANTED' ? 'ok' : 'idle',
        labId: event.lab_id, href: '/admin/access',
      })),
      ...secEvents.map((event): DashboardEvent => ({
        key: 's' + event.id, at: event.created_at, title: event.title,
        detail: [event.zone_name, event.detail].filter(Boolean).join(' · '),
        source: event.lab_code ?? 'Security camera', kind: 'VISION',
        tone: event.acknowledged_at ? 'idle' : 'warn',
        labId: tiles?.find(tile => tile.code === event.lab_code)?.lab_id ?? null, href: '/admin/security',
      })),
      ...robotEvents.map((event): DashboardEvent => {
        const delta = typeof event.detail?.delta_deg === 'number' ? ' · ' + event.detail.delta_deg.toFixed(1) + '°' : ''
        return {
          key: 'r' + event.id, at: event.occurred_at,
          title: event.kind === 'JOINT_MOVED' && event.joint != null
            ? event.robot + ' · Joint ' + (event.joint + 1) + ' moved' + delta
            : event.robot + ' · ' + titleCase(event.kind),
          detail: event.source + (event.provenance === 'DEMO_DATA' ? ' · simulation data' : ''),
          source: 'Robot telemetry', kind: 'ROBOTS',
          tone: event.severity === 'CRITICAL' ? 'bad' : event.severity === 'WARNING' ? 'warn' : 'idle',
          labId: event.labId, href: '/robots/' + event.robotId,
        }
      }),
      ...hazards.map((hazard): DashboardEvent => ({
        key: 'h' + hazard.alert_id, at: hazard.at, title: hazard.title,
        detail: hazard.label + ' · ' + hazard.detail, source: hazard.lab_code,
        kind: 'ENVIRONMENT', tone: 'warn', labId: hazard.lab_id, href: '/admin/operations',
      })),
    ]
    return rows.filter(event => selectedLabId == null || event.labId === selectedLabId)
      .sort((a, b) => (b.at ?? '').localeCompare(a.at ?? ''))
  }, [accessEvents, secEvents, robotEvents, hazards, tiles, selectedLabId])

  const compactEvents = dashboardEvents.slice(0, 3)
  const fullscreenAvailable = document.fullscreenEnabled && typeof document.documentElement.requestFullscreen === 'function'
  const toggleFullscreen = async () => {
    setFullscreenError('')
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else if (fullscreenAvailable) await document.documentElement.requestFullscreen()
      else setFullscreenError('Browser fullscreen is unavailable here. Use the browser controls.')
    } catch {
      setFullscreenError('Browser fullscreen was blocked. Use the browser controls instead.')
    }
  }
  const chooseLab = (id: number) => setScope(String(id))
  const scopeName = selectedLabId == null ? 'All laboratories' : scopedTiles.find(tile => tile.lab_id === selectedLabId)?.code ?? 'Selected laboratory'

  if (wall) return (
    <div className="command-wall">
      <header className="wall-header">
        <div className="wall-title">
          <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[.16em] text-cyan-300"><Radar size={12} /> Smart Lab · Control room</div>
          <h1 className="truncate text-lg font-semibold leading-tight text-white">IoT Dashboard</h1>
        </div>
        <label className="wall-scope">
          <span>Lab scope</span>
          <select value={scope} onChange={event => setScope(event.target.value)} aria-label="Laboratory scope">
            <option value="all">All laboratories</option>
            {tiles?.map(tile => <option key={tile.lab_id} value={tile.lab_id}>{tile.code} · {tile.name}</option>)}
          </select>
        </label>
        <HealthPanel services={services} serviceError={serviceError} connected={connected} compact />
        <div className="wall-header-actions">
          <Clock compact />
          <button type="button" className="wall-fullscreen-button" onClick={toggleFullscreen}
            disabled={!fullscreenAvailable} title={fullscreenAvailable ? (fullscreen ? 'Exit fullscreen' : 'Enter fullscreen') : 'Fullscreen unavailable in this browser'}>
            {fullscreen ? <Minimize2 size={14} /> : <Expand size={14} />}
            <span>{fullscreen ? 'Exit screen' : 'Full screen'}</span>
          </button>
          {fullscreenError && <span className="wall-fullscreen-error" role="status">{fullscreenError}</span>}
        </div>
      </header>

      <section aria-label="Operational metrics" className="wall-metrics">
        <MetricLink compact to="/admin/devices" label="Devices reporting"
          value={serviceError || reportedDevices == null || expectedDevices == null ? '—' : reportedDevices + ' / ' + expectedDevices}
          sub={serviceError ? 'Device status unavailable' : 'Configured devices'} tone={serviceError ? 'warn' : reportedDevices === expectedDevices && expectedDevices !== 0 ? 'good' : reportedDevices === 0 ? 'bad' : 'warn'} icon={<Database size={13} />} />
        <MetricLink compact to="/admin/access" label="People inside" value={peopleInside == null ? '—' : peopleInside}
          sub="Door access records" icon={<Users size={13} />} />
        <MetricLink compact to="/robots" label="Robot telemetry"
          value={robots === null ? '—' : reportingRobots + ' / ' + currentRobots.length}
          sub={robots === null ? 'Movement unknown' : movingRobots + ' physical moving · ' + simulatedRobots + ' simulated'} tone={movingRobots ? 'good' : reportingRobots === 0 ? 'warn' : 'neutral'} icon={<Bot size={13} />} />
        <MetricLink compact to="/admin/alerts" label="Open incidents" value={alerts === null ? '—' : scopedAlerts.length}
          sub={alerts === null ? 'Alert source unavailable' : criticalAlerts + ' critical · ' + scopeName} tone={alertError ? 'warn' : criticalAlerts ? 'bad' : scopedAlerts.length ? 'warn' : 'good'} icon={<ShieldAlert size={13} />} />
      </section>

      <main className="wall-main">
        <div className="wall-left-stack">
        <section className="wall-floor-card" aria-labelledby="wall-floor-heading">
          <div className="wall-panel-heading">
            <div className="min-w-0">
              <h2 id="wall-floor-heading" className="truncate text-sm font-semibold text-white">Laboratory digital twin</h2>
              <p className="truncate text-[10px] text-slate-500">{currentTile?.code ?? scopeName} · approximate floor plan, not to scale</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {error && <span className="max-w-48 truncate text-[10px] text-amber-300" title={error}>Lab state unavailable</span>}
              {refreshAt && <span className="hidden text-[9px] text-slate-500 lg:inline">Updated {relative(refreshAt)}</span>}
              <Link to="/labs" className="text-[10px] text-cyan-300 hover:text-cyan-200">Labs <ArrowRight size={11} className="inline" /></Link>
            </div>
          </div>
          <div className="wall-floor-stage">
            {tiles === null && !error ? <Skeleton className="h-full w-full" />
              : currentTile && currentCam?.lab_id === currentTile.lab_id ? <LabFloor tile={currentTile} cam={currentCam} robots={floorRobots} compact />
                : <div className="wall-floor-unavailable"><Radar size={20} /><span>No verified floor layout for {scopeName}.</span><Link to="/labs">Lab details</Link></div>}
          </div>
        </section>
        <section className="wall-media" aria-label="Camera and robot fleet">
          <CameraPanel cam={currentCam} loading={cams === null && !cameraError} failed={cameraError} compact />
          <RobotPanel robots={robots} labId={selectedLabId} compact />
        </section>
        </div>
        <aside className="wall-right-stack" aria-label="Incidents and laboratory summaries">
          <EnvironmentPanel environment={environment} loading={environments === null && !environmentError}
            failed={environmentError} labCode={currentTile?.code ?? scopeName} compact />
          <AttentionPanel alerts={alerts} failed={alertError} scopeId={selectedLabId} compact />
          <WallRecentEvents events={compactEvents} sourceError={eventSourceError} />
        </aside>
      </main>

    </div>
  )

  return (
    <div className={wall ? 'min-h-screen space-y-4 bg-[#0c1118] p-3 text-slate-200 sm:p-5 2xl:p-7' : 'space-y-5 text-slate-200'}>
      <header className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-white/[.07] bg-[#111821] px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.18em] text-cyan-300">
            <Radar size={13} /> Smart Lab <span className="text-slate-600">/</span> Control room
          </div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white sm:text-3xl">Command center</h1>
          <p className="mt-1 max-w-xl text-xs text-slate-500">Current laboratory conditions, open issues, and the sources behind each status.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 rounded-xl border border-white/[.08] bg-black/20 px-3 py-2 text-xs text-slate-400">
            <span>Scope</span>
            <select className="max-w-[190px] bg-transparent text-sm text-slate-100 outline-none" value={scope}
              onChange={event => setScope(event.target.value)} aria-label="Laboratory scope">
              <option value="all">All laboratories</option>
              {tiles?.map(tile => <option key={tile.lab_id} value={tile.lab_id}>{tile.code} · {tile.name}</option>)}
            </select>
          </label>
          <div className="hidden sm:block"><Clock /></div>
          {wall ? (
            <button type="button" className="btn-ghost btn-sm" onClick={toggleFullscreen}><Expand size={14} /> Full screen</button>
          ) : (
            <>
              <Link className="btn-ghost btn-sm" to="/wall" title="Open the wall display in this tab">
                <MonitorUp size={14} /> Wall mode
              </Link>
              {/* Only on click - never opened automatically. */}
              <a className="btn-ghost btn-sm" href="/wall" target="_blank" rel="noopener noreferrer"
                 title="Open the wall display in a new browser tab">
                <MonitorUp size={14} /> Wall in new tab
              </a>
            </>
          )}
        </div>
      </header>

      {error && <ErrorBanner title="Laboratory state could not be loaded" message={error} onDismiss={() => setError('')} action={
        <button type="button" className="inline-flex items-center gap-1 text-xs text-cyan-200" onClick={loadPageData}><RefreshCw size={12} /> Retry</button>
      } />}

      <HealthPanel services={services} serviceError={serviceError} connected={connected} />

      <section aria-label="Operational summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricLink to="/admin/devices" label="Devices reporting" value={serviceError || reportedDevices == null || expectedDevices == null ? '—' : reportedDevices + ' / ' + expectedDevices}
          sub={serviceError ? 'Device status unavailable' : 'Configured devices · platform and lab'} tone={serviceError ? 'warn' : reportedDevices === expectedDevices && expectedDevices !== 0 ? 'good' : reportedDevices === 0 ? 'bad' : 'warn'} icon={<Database size={16} />} />
        <MetricLink to="/admin/access" label="People inside" value={peopleInside == null ? '—' : peopleInside}
          sub="Door access records · camera count shown separately" icon={<Users size={16} />} />
        <MetricLink to="/robots" label="Robot fleet" value={robots === null ? '—' : reportingRobots + ' / ' + currentRobots.length}
          sub={robots === null ? 'Waiting for telemetry' : movingRobots + ' physical moving · ' + simulatedRobots + ' simulated'} tone={movingRobots ? 'good' : reportingRobots === 0 ? 'warn' : 'neutral'} icon={<Bot size={16} />} />
        <MetricLink to="/admin/alerts" label="Open alerts" value={alerts === null ? '—' : scopedAlerts.length}
          sub={alerts === null ? 'Alert source unavailable' : criticalAlerts + ' critical · ' + scopeName} tone={alertError ? 'warn' : criticalAlerts ? 'bad' : scopedAlerts.length ? 'warn' : 'good'} icon={<ShieldAlert size={16} />} />
      </section>

      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.55fr)_minmax(360px,.85fr)]">
        <section className="rounded-2xl border border-white/[.09] bg-[#121922] p-4 sm:p-5" aria-labelledby="floor-heading">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2"><Radar size={15} className="text-cyan-300" /><h2 id="floor-heading" className="text-sm font-semibold text-white">Laboratory digital twin</h2></div>
              <p className="mt-1 text-[11px] text-slate-500">{currentTile?.name ?? scopeName} · 2D schematic, not to scale</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone="idle">2D schematic</Chip>
              <button type="button" className="btn-quiet btn-sm" onClick={() => document.getElementById('camera-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>
                <Cctv size={13} /> Camera
              </button>
              <Link to="/admin/operations" className="btn-quiet btn-sm">Lab details <ArrowRight size={13} /></Link>
            </div>
          </div>
          {tiles === null && !error && cams === null && !cameraError ? <Skeleton className="aspect-[1.55] w-full" />
            : currentTile && currentCam?.lab_id === currentTile.lab_id ? (
              <div className="rounded-xl border border-white/[.06] bg-[#0d131a] p-2 sm:p-3">
                <LabFloor tile={currentTile} cam={currentCam} robots={floorRobots} />
              </div>
            ) : (
              <div className="flex min-h-[250px] flex-col items-center justify-center rounded-xl border border-dashed border-white/[.12] bg-black/15 px-5 text-center">
                <Radar size={22} className="text-slate-600" />
                <p className="mt-3 text-sm font-medium text-slate-300">No verified floor layout for this scope</p>
                <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">The available Robotics Lab drawing is a camera-based schematic. A measured layout for this laboratory has not been configured.</p>
              </div>
            )}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-white/[.06] pt-3 text-[10.5px] text-slate-500">
            <span>Door state is shown only when the controller or camera reports it.</span>
            <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Confirmed online</span>
            <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-amber-300" />Stale / impaired</span>
            <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-slate-500" />Unknown</span>
          </div>
        </section>
        <AttentionPanel alerts={alerts} failed={alertError} scopeId={selectedLabId} />
      </div>

      <section aria-label="Live system panels" className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-4">
        <CameraPanel cam={currentCam} loading={cams === null && !cameraError} failed={cameraError} />
        <RobotPanel robots={robots} labId={selectedLabId} />
        <EnvironmentPanel environment={environment} loading={environments === null && !environmentError} failed={environmentError} labCode={currentTile?.code ?? scopeName} />
        <section className="rounded-2xl border border-white/[.09] bg-[#121922] p-4" aria-labelledby="recent-heading">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2"><Clock3 size={15} className="text-cyan-300" /><h2 id="recent-heading" className="text-sm font-semibold text-white">Recent events</h2></div>
            <button type="button" className="text-xs text-cyan-300 hover:text-cyan-200" onClick={() => document.getElementById('events-heading')?.scrollIntoView({ behavior: 'smooth' })}>Timeline <ArrowRight size={12} className="inline" /></button>
          </div>
          {!dashboardEvents.length ? <p className="mt-4 rounded-lg border border-white/[.06] bg-black/15 p-4 text-xs text-slate-500">No events have been returned by the available sources.</p>
            : <ul className="mt-3 space-y-2">
              {compactEvents.map(event => (
                <li key={event.key}>
                  <Link to={event.href} className="block rounded-xl border border-white/[.06] bg-black/15 p-3 hover:border-cyan-400/25">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-medium text-slate-200">{event.title}</span>
                      <Chip tone={event.tone}>{EVENT_LABEL[event.kind]}</Chip>
                    </div>
                    <div className="mt-1 flex justify-between gap-2 text-[10px] text-slate-500"><span className="truncate">{event.source}</span><span className="shrink-0">{event.at ? relative(event.at) : 'Time unavailable'}</span></div>
                  </Link>
                </li>
              ))}
            </ul>}
        </section>
      </section>

      <EventStream events={dashboardEvents} active={eventFilter} onChange={setEventFilter} sourceError={eventSourceError} />
      <LabCards tiles={tiles} onSelect={id => setScope(String(id))} />
      <div className="flex flex-wrap items-center justify-between gap-2 text-[10.5px] text-slate-600">
        <span>Source timestamps and freshness are preserved where the APIs report them. Unknown values are not treated as zero.</span>
        <span>{refreshAt ? 'Service check ' + relative(refreshAt) : serviceError ? 'Service check unavailable' : 'Checking service status…'}</span>
      </div>
    </div>
  )
}
