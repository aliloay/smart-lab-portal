/**
 * Live monitor: the wall screen.
 *
 * One full-screen view, no sidebar: every laboratory as an equal tile in a
 * grid of rows and columns that fills the screen, so all labs are watched
 * at a glance. Each tile shows only what someone watching acts on: door
 * open or closed, locked or not, alarm or not, in use or idle, and who is
 * inside by role ("2 students · 1 staff"). Labs keep a fixed place (by
 * code); a lab that needs attention turns amber, an alarm turns it red.
 *
 * Open it from the sidebar (its own window) or with monitor.bat, then press
 * Full screen. Live: door, access and alert messages refresh it at once; a
 * slow poll keeps it right if the live connection drops. Values the
 * hardware never reported read "No sensor"/"No data", never a guess.
 */
import { ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, CircleCheck, DoorClosed, DoorOpen, Droplets, Expand, Lock, LockOpen,
  Maximize2, Minimize2, ShieldAlert, ShieldCheck, Siren, Thermometer, TriangleAlert,
  UsersRound, WifiOff,
} from 'lucide-react'
import { MonitorTile, Role, api } from '../lib/api'
import LiveCameraFeed from '../components/LiveCameraFeed'
import CameraFullScreen from '../components/CameraFullScreen'
import LabDetails from '../components/LabDetails'
import { useLive, useLiveMessages } from '../lib/live'
import { fmtTime, relative } from '../lib/time'
import BackToPortal from '../components/BackToPortal'
import { InstitutionLogo } from '../components/Brand'
import { Spinner } from '../components/ui'

const POLL_MS = 10_000

const EVENT_LABEL: Record<string, string> = {
  ACCESS_GRANTED: 'Access granted', ACCESS_DENIED: 'Access denied',
  IDENTITY_MISMATCH: 'Identity mismatch', DOOR_OPENED: 'Door opened',
  DOOR_CLOSED: 'Door closed', EXIT_RECORDED: 'Exit', ALARM: 'Alarm',
}
const EVENT_BAD = new Set(['ACCESS_DENIED', 'IDENTITY_MISMATCH', 'ALARM'])
const ROLE_WORD: Record<Role, [string, string]> = {
  STUDENT: ['student', 'students'], LAB_STAFF: ['staff', 'staff'], ADMIN: ['admin', 'admins'],
}

type Tone = 'ok' | 'warn' | 'bad' | 'idle'
const TEXT: Record<Tone, string> = {
  ok: 'text-ok-soft', warn: 'text-warn-soft', bad: 'text-bad-soft', idle: 'text-slate-400',
}

/** Columns for n tiles on a landscape screen: 4 labs 2x2, 6 3x2, 11 4x3, ... */
function columns(n: number): number {
  if (n <= 1) return 1
  if (n <= 4) return 2
  if (n <= 9) return 3
  if (n <= 16) return 4
  return 5
}

export default function Monitor() {
  const [labs, setLabs] = useState<MonitorTile[] | null>(null)
  const [error, setError] = useState('')
  const [now, setNow] = useState(() => new Date())
  const [full, setFull] = useState(!!document.fullscreenElement)
  const { connected } = useLive()
  const timer = useRef<number>()

  const load = useCallback(() => {
    api.monitor().then(r => { setLabs(r.labs); setError('') })
      .catch(e => setError(e instanceof Error ? e.message : 'Cannot reach the portal'))
  }, [])

  useEffect(() => {
    load()
    const t = window.setInterval(load, POLL_MS)
    return () => window.clearInterval(t)
  }, [load])

  // Door, access and alert messages refresh at once (debounced: one entry
  // produces several messages in a second).
  useLiveMessages(m => {
    if (m.type !== 'door_state' && m.type !== 'access_event' && m.type !== 'staff' && m.type !== 'hazard' && m.type !== 'env_update'
        && m.type !== 'security_state') return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(load, 300)
  })

  // The clock and the "2m ago" texts.
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(t)
  }, [])

  // A wall screen must not go to sleep. Not every browser allows it.
  useEffect(() => {
    let lock: { release: () => Promise<void> } | null = null
    const nav = navigator as Navigator & { wakeLock?: { request: (t: 'screen') => Promise<typeof lock> } }
    nav.wakeLock?.request('screen').then(l => { lock = l }).catch(() => {})
    return () => { lock?.release().catch(() => {}) }
  }, [])

  useEffect(() => {
    const f = () => setFull(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', f)
    return () => document.removeEventListener('fullscreenchange', f)
  }, [])
  const toggleFull = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
    else document.documentElement.requestFullscreen().catch(() => {})
  }

  const all = labs ?? []
  const inside = all.reduce((n, l) => n + l.people.length, 0)
  const alarms = all.filter(l => l.state === 'ALERT').length
  const inUse = all.filter(l => l.in_use).length
  const open = all.filter(l => l.door_closed === false).length
  const cols = columns(all.length)
  const rows = Math.max(1, Math.ceil(all.length / cols))
  // Up to 4 rows fill the screen exactly; more rows scroll at a fixed height.
  const fits = rows <= 4
  const size: 'lg' | 'md' | 'sm' = all.length <= 2 ? 'lg' : all.length <= 6 ? 'md' : 'sm'

  return (
    <div className="h-screen flex flex-col bg-ink-950 text-slate-100 overflow-hidden">
      <header className="shrink-0 flex items-center gap-5 px-6 py-3 border-b border-ink-600/60 bg-ink-900/80">
        <BackToPortal to="/" />
        <InstitutionLogo strong className="!h-9" />
        <div className="text-[15px] font-extrabold tracking-[0.18em] whitespace-nowrap">
          SMART <span className="text-accent-300">LAB</span>
          <span className="ml-3 text-slate-400 font-semibold tracking-[0.14em]">LIVE MONITOR</span>
        </div>
        <div className="ml-auto flex items-center gap-6 text-[15px]">
          <Stat icon={<ShieldAlert size={17} />} tone={alarms ? 'bad' : 'idle'}>
            {alarms ? `${alarms} lab${alarms === 1 ? '' : 's'} in alarm` : 'No alarms'}</Stat>
          <Stat icon={<DoorOpen size={17} />} tone={open ? 'warn' : 'idle'}>{open} open</Stat>
          <Stat icon={<CircleCheck size={17} />} tone={inUse ? 'ok' : 'idle'}>{inUse}/{all.length} in use</Stat>
          <Stat icon={<UsersRound size={17} />} tone={inside ? 'ok' : 'idle'}>{inside} inside</Stat>
          <span className={`inline-flex items-center gap-2 text-[13px] ${connected ? 'text-ok-soft' : 'text-warn-soft'}`}>
            <span className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-ok animate-pulse' : 'bg-warn'}`} />
            {connected ? 'Live' : 'Reconnecting'}</span>
          <span className="mono text-[26px] font-semibold tnum text-white">
            {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
          <button onClick={toggleFull} title={full ? 'Exit full screen' : 'Full screen'}
                  className="text-slate-400 hover:text-white">
            {full ? <Minimize2 size={20} /> : <Maximize2 size={20} />}</button>
        </div>
      </header>

      {error && (
        <div className="shrink-0 px-6 py-2 bg-bad/15 border-b border-bad/40 text-bad-soft text-sm">
          {error} - showing the last data received.</div>
      )}

      <main className="flex-1 min-h-0 p-3 overflow-auto">
        {!labs ? <div className="h-full grid place-items-center"><Spinner label="Loading laboratories" /></div>
          : !labs.length ? <div className="h-full grid place-items-center text-slate-400">No active laboratories.</div>
          : <div className="grid gap-3"
                 style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
                          gridTemplateRows: fits ? `repeat(${rows}, minmax(0, 1fr))` : undefined,
                          gridAutoRows: fits ? undefined : '300px',
                          height: fits ? '100%' : undefined }}>
              {labs.map(l => <Tile key={l.lab_id} t={l} size={size} />)}
            </div>}
      </main>
    </div>
  )
}

function Stat({ icon, tone, children }: { icon: ReactNode; tone: Tone; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-2 font-semibold whitespace-nowrap ${TEXT[tone]}`}>{icon}{children}</span>
}

const SIZES = {
  lg: { code: 'text-[clamp(26px,2.4vw,40px)]', big: 'text-[clamp(30px,3vw,52px)]', body: 'text-[clamp(16px,1.3vw,22px)]', count: 'text-[clamp(40px,4vw,72px)]', pad: 'p-6 gap-5' },
  md: { code: 'text-[clamp(20px,1.8vw,30px)]', big: 'text-[clamp(20px,1.8vw,32px)]', body: 'text-[clamp(14px,1vw,18px)]', count: 'text-[clamp(30px,2.6vw,48px)]', pad: 'p-4 gap-3' },
  sm: { code: 'text-[clamp(16px,1.25vw,24px)]', big: 'text-[clamp(14px,1.15vw,22px)]', body: 'text-[clamp(12px,0.8vw,15px)]', count: 'text-[clamp(22px,1.8vw,34px)]', pad: 'p-3 gap-2' },
}

function roleBreakdown(t: MonitorTile): string {
  return (['STUDENT', 'LAB_STAFF', 'ADMIN'] as Role[])
    .map(r => [r, t.people_by_role[r] ?? 0] as const)
    .filter(([, n]) => n > 0)
    .map(([r, n]) => `${n} ${ROLE_WORD[r][n === 1 ? 0 : 1]}`)
    .join(' · ')
}

/** Set by an administrator from the Emergency tab: shown before anything else. */
function EmergencyBanner({ e, size }: { e: NonNullable<MonitorTile['emergency']>; size: string }) {
  const what = [
    e.door_mode === 'UNLOCKED' ? `Door held OPEN${e.door_remaining_s != null
      ? ` · ${Math.ceil(e.door_remaining_s / 60)} min left` : ''}` : null,
    e.door_mode === 'LOCKDOWN' ? 'LOCKDOWN · no entry' : null,
    e.alarm ? 'Evacuation alarm' : null,
  ].filter(Boolean).join(' · ')
  return (
    <div className={`rounded-xl border border-bad/60 bg-bad/15 px-3 py-2 ${size}`}>
      <div className="flex items-center gap-1.5 font-extrabold text-bad-soft uppercase tracking-wide">
        <Siren className="w-[1em] h-[1em] shrink-0 animate-pulse" /> Emergency</div>
      {what && <div className="text-white font-semibold truncate">{what}</div>}
      {e.message && <div className="text-slate-200 truncate">“{e.message}”</div>}
    </div>
  )
}

function Tile({ t, size }: { t: MonitorTile; size: 'lg' | 'md' | 'sm' }) {
  const S = SIZES[size]
  // Static red frame; only the ALARM badge pulses - a pulsing tile would fade
  // the very text someone is trying to read.
  const frame = t.state === 'ALERT'
    ? 'border-bad/70 bg-bad/[0.08] shadow-[0_0_0_1px_rgba(239,68,68,.35),0_0_28px_-8px_rgba(239,68,68,.6)]'
    : t.state === 'WARN' ? 'border-warn/50 bg-warn/[0.04]'
    : t.in_use ? 'border-ok/40 bg-ok/[0.04]' : 'border-ink-600/70 bg-ink-800/50'
  const offline = t.has_door && t.controller_online === false
  const top = t.alerts[0]
  const others = t.alert_count - (top?.count ?? 0)

  const [big, setBig] = useState(false)
  const [details, setDetails] = useState(false)
  const cam = t.security_camera
  return (
    <section className={`relative isolate rounded-2xl border flex flex-col min-h-0 overflow-hidden [&>*]:relative ${S.pad} ${frame}`}>
      {/* The lab live, behind everything; a gradient keeps the text readable. */}
      {cam && <>
        <LiveCameraFeed deviceId={cam.device_id} intervalMs={250} className="!absolute inset-0 -z-0" />
        <div className="!absolute inset-0 bg-gradient-to-b from-ink-950/80 via-ink-950/35 to-ink-950/85 pointer-events-none" />
      </>}
      {big && cam && <CameraFullScreen deviceId={cam.device_id} title={t.code} sub={t.name}
                                       badges={<CameraBadges t={t} onOpen={() => {}} />} onClose={() => setBig(false)} />}
      {details && <LabDetails t={t} pill={<StatePill state={t.state} inUse={t.in_use} />}
                              badges={cam ? <CameraBadges t={t} onOpen={() => {}} /> : null}
                              onClose={() => setDetails(false)} />}
      {/* Lab and its overall state */}
      <div className="flex items-start gap-2 min-w-0">
        <div className="min-w-0">
          <div className={`${S.code} font-extrabold tracking-wide leading-none`}>{t.code}</div>
          <div className="text-[12px] text-slate-400 truncate mt-1">{t.name}</div>
        </div>
        <StatePill state={t.state} inUse={t.in_use} />
        <button onClick={() => setDetails(true)} title="Everything about this lab"
                className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-accent-400/40 bg-accent-500/10
                           text-accent-200 text-[11px] font-bold tracking-[0.14em] hover:bg-accent-500/20">
          <Expand size={12} /> DETAILS</button>
      </div>

      {t.emergency && <EmergencyBanner e={t.emergency} size={S.body} />}

      {t.security_camera && <CameraBadges t={t} onOpen={() => setBig(true)} />}

      {/* Door and lock */}
      {t.has_door ? (
        <div className="grid grid-cols-2 gap-2">
          <Chip size={S.big} dim={offline} label="Door"
                tone={t.door_closed === null ? 'idle' : t.door_closed ? 'ok' : 'warn'}
                icon={t.door_closed === false ? <DoorOpen /> : <DoorClosed />}
                value={t.door_closed === null ? 'No data' : t.door_closed ? 'Closed' : 'Open'} />
          <Chip size={S.big} dim={offline} label="Lock"
                tone={t.locked == null ? 'idle' : t.locked ? 'ok' : 'warn'}
                icon={t.locked === false ? <LockOpen /> : <Lock />}
                value={t.locked == null ? 'No data' : t.locked ? 'Locked' : 'Unlocked'} />
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-ink-600/60 px-3 py-2 text-slate-500 text-[12.5px]">
          No door sensor in this lab</div>
      )}

      {/* Who is inside */}
      <div className={`flex items-baseline gap-3 min-w-0 ${S.body}`}>
        <span className={`${S.count} font-extrabold leading-none tnum ${t.people.length ? 'text-white' : 'text-slate-600'}`}>
          {t.people.length}</span>
        <span className="min-w-0">
          <span className="block text-[11px] uppercase tracking-[0.16em] text-slate-400">inside</span>
          <span className={`block truncate ${t.people.length ? 'text-slate-100 font-semibold' : 'text-slate-500'}`}>
            {t.people.length ? roleBreakdown(t) || `${t.people.length} people` : 'Nobody'}</span>
        </span>
      </div>
      {size !== 'sm' && t.people.length > 0 && (
        <div className="text-[12.5px] text-slate-400 truncate -mt-1">
          {t.people.slice(0, 3).map(p => p.name ?? 'Unknown').join(', ')}
          {t.people.length > 3 && ` +${t.people.length - 3}`}</div>
      )}

      {/* Booking */}
      <div className={`${S.body} text-slate-300 truncate`}>
        {t.booking ? <>Booked by <b className="text-white">{t.booking.name ?? 'someone'}</b> · until {fmtTime(t.booking.until)}</>
          : t.next_booking_at ? <span className="text-slate-400">Free · next {fmtTime(t.next_booking_at)}</span>
          : <span className="text-slate-500">Free</span>}
      </div>

      {/* Alarm / emergency */}
      <div className={`${S.body} min-w-0`}>
        {offline && (
          <div className="flex items-center gap-1.5 text-warn-soft font-semibold truncate">
            <WifiOff className="w-[1em] h-[1em] shrink-0" /> Door controller offline</div>)}
        {t.env_online === false && (
          <div className="flex items-center gap-1.5 text-warn-soft font-semibold truncate">
            <WifiOff className="w-[1em] h-[1em] shrink-0" /> Environment node offline</div>)}
        {top ? (
          <div className={`flex items-center gap-1.5 font-semibold min-w-0
                           ${top.severity === 'CRITICAL' ? 'text-bad-soft' : 'text-warn-soft'}`}>
            <ShieldAlert className="w-[1em] h-[1em] shrink-0" />
            <span className="truncate">{top.title}</span>
            {top.count > 1 && <span className="shrink-0 px-1.5 rounded bg-white/10 text-[0.8em] tnum">×{top.count}</span>}
            {others > 0 && <span className="shrink-0 text-[0.8em] font-normal text-slate-400">+{others}</span>}
          </div>
        ) : t.faults.length ? (
          <div className="flex items-center gap-1.5 text-warn-soft truncate">
            <TriangleAlert className="w-[1em] h-[1em] shrink-0" /> {t.faults[0]} not responding</div>
        ) : !offline && t.env_online !== false && (
          <div className="flex items-center gap-1.5 text-slate-500">
            <ShieldCheck className="w-[1em] h-[1em] shrink-0" /> No alarms</div>
        )}
      </div>

      {/* Last at the door, environment */}
      <div className="mt-auto pt-2 border-t border-ink-600/50 flex items-center gap-3 text-[12px] min-w-0">
        {t.last_event ? (
          <span className="min-w-0 truncate">
            <span className={EVENT_BAD.has(t.last_event.type) ? 'text-bad-soft font-semibold'
              : t.last_event.type === 'ACCESS_GRANTED' ? 'text-ok-soft font-semibold' : 'text-slate-300'}>
              {EVENT_LABEL[t.last_event.type] ?? t.last_event.type}</span>
            {t.last_event.who && <span className="text-slate-300"> · {t.last_event.who}</span>}
            <span className="text-slate-500"> · {relative(t.last_event.at)}</span>
          </span>
        ) : <span className="text-slate-600">No door activity</span>}
        {t.env_online != null && (
          <span className="ml-auto flex items-center gap-1 shrink-0">
            {(['smoke', 'flame'] as const).map(k => {
              const bad = t.hazards.includes(k)
              const cls = t.env_online === false ? 'border-ink-600 text-slate-500'
                : bad ? 'border-bad bg-bad text-white animate-pulse' : 'border-ok/40 bg-ok/10 text-ok-soft'
              return <span key={k} title={t.env_online === false ? 'Environment node offline'
                  : bad ? `${k} DETECTED` : `${k} sensor active - no danger`}
                className={`px-1.5 rounded border text-[10.5px] font-bold uppercase tracking-wide ${cls}`}>
                {k}{bad ? '!' : ' ok'}</span>
            })}
          </span>
        )}
        {(t.environment.temperature || t.environment.humidity) && (
          <span className={`${t.env_online != null ? '' : 'ml-auto '}flex items-center gap-2 text-slate-300 shrink-0`}>
            {t.environment.temperature && <span className="inline-flex items-center gap-0.5">
              <Thermometer size={13} />{t.environment.temperature.value.toFixed(1)}°C</span>}
            {t.environment.humidity && <span className="inline-flex items-center gap-0.5">
              <Droplets size={13} />{t.environment.humidity.value.toFixed(0)}%</span>}
          </span>
        )}
      </div>
    </section>
  )
}

function CameraBadges({ t, onOpen }: { t: MonitorTile; onOpen: () => void }) {
  const c = t.security_camera!
  const live = c.online === true && c.source_ok !== false
  const extra = live && c.people !== null && c.people > c.inside
  const unknown = live && (c.unknown ?? 0) > 0
  return (
    <div className="relative flex flex-wrap items-center gap-1.5 text-[11.5px] font-semibold">
      <button onClick={onOpen} title="Open this lab's camera full screen"
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-black/70 text-[10.5px] font-bold tracking-wider text-white hover:bg-black">
        <span className={`w-1.5 h-1.5 rounded-full ${live ? 'bg-bad animate-pulse' : 'bg-slate-500'}`} />
        {live ? 'LIVE' : 'CAMERA OFFLINE'}</button>
      {live && <span className="px-2 py-0.5 rounded-md bg-black/70 text-white tnum">{c.people ?? 0} seen · {c.inside} entered</span>}
      {extra && <span className="px-2 py-0.5 rounded-md bg-bad text-white">
        {c.inside === 0 ? 'Person with no door entry' : 'Unidentified person'}</span>}
      {live && c.named.filter(n => n.entered === false).map(n => (
        <span key={n.label} className="px-2 py-0.5 rounded-md bg-orange-500 text-black">{n.name} · not entered</span>))}
      {!extra && unknown && <span className="px-2 py-0.5 rounded-md bg-warn/90 text-black">{c.unknown} not named</span>}
    </div>
  )
}

function StatePill({ state, inUse }: { state: MonitorTile['state']; inUse: boolean }) {
  const [cls, label] = state === 'ALERT' ? ['bg-bad/20 text-bad-soft border-bad/60 animate-pulse', 'ALARM']
    : state === 'WARN' ? ['bg-warn/15 text-warn-soft border-warn/40', 'CHECK']
    : inUse ? ['bg-ok/15 text-ok-soft border-ok/40', 'ACTIVE'] : ['bg-ink-700/60 text-slate-400 border-ink-500/60', 'IDLE']
  return <span className={`ml-auto shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-full border
                           text-[11px] font-bold tracking-[0.14em] ${cls}`}>
    {state === 'OK' ? null : <TriangleAlert size={12} />}{label}</span>
}

function Chip({ label, value, icon, tone, dim, size }: {
  label: string; value: string; icon: ReactNode; tone: Tone; dim?: boolean; size: string
}) {
  return (
    <div className="rounded-xl border border-ink-600/60 bg-ink-900/60 px-3 py-2 min-w-0">
      <div className="text-[10.5px] uppercase tracking-[0.16em] text-slate-400 truncate">{label}
        {dim && <span className="ml-1.5 normal-case tracking-normal text-warn-soft">last known</span>}</div>
      <div className={`flex items-center gap-2 font-extrabold leading-tight ${size} ${TEXT[tone]} ${dim ? 'opacity-60' : ''}`}>
        <span className="[&>svg]:w-[0.9em] [&>svg]:h-[0.9em] [&>svg]:shrink-0">{icon}</span>
        <span className="truncate">{value}</span></div>
    </div>
  )
}
