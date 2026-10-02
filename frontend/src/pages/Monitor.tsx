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
  ArrowLeft, CircleCheck, DoorClosed, DoorOpen, Droplets, Lock, LockOpen,
  Maximize2, Minimize2, ShieldAlert, ShieldCheck, Thermometer, TriangleAlert,
  UsersRound, WifiOff,
} from 'lucide-react'
import { MonitorTile, Role, api } from '../lib/api'
import { useLive, useLiveMessages } from '../lib/live'
import { fmtTime, relative } from '../lib/time'
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
    if (m.type !== 'door_state' && m.type !== 'access_event' && m.type !== 'staff') return
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
        <Link to="/" title="Back to the portal" className="text-slate-500 hover:text-slate-200">
          <ArrowLeft size={20} /></Link>
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

  return (
    <section className={`rounded-2xl border flex flex-col min-h-0 overflow-hidden ${S.pad} ${frame}`}>
      {/* Lab and its overall state */}
      <div className="flex items-start gap-2 min-w-0">
        <div className="min-w-0">
          <div className={`${S.code} font-extrabold tracking-wide leading-none`}>{t.code}</div>
          <div className="text-[12px] text-slate-400 truncate mt-1">{t.name}</div>
        </div>
        <StatePill state={t.state} inUse={t.in_use} />
      </div>

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
        ) : !offline && (
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
        {(t.environment.temperature || t.environment.humidity) && (
          <span className="ml-auto flex items-center gap-2 text-slate-300 shrink-0">
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
