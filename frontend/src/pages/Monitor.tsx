/**
 * Live monitor: the wall screen.
 *
 * One full-screen view, no sidebar, split into one tile per laboratory with
 * only what someone watching acts on: door open or closed, locked or not,
 * who is inside, active alarms, and the last thing that happened at the
 * door. Labs with a problem sort first and are coloured, so a glance is
 * enough. Meant for a separate screen: open it from the sidebar (its own
 * window) or with monitor.bat, then press Full screen.
 *
 * Live: the door, access and alert messages refresh it at once; a slow poll
 * keeps it right if the live connection drops. Values the hardware never
 * reported read "No data", never a guess.
 */
import { ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, CircleCheck, DoorClosed, DoorOpen, Droplets, Lock, LockOpen,
  Maximize2, Minimize2, ShieldAlert, Thermometer, TriangleAlert, UsersRound, WifiOff,
} from 'lucide-react'
import { MonitorTile, api } from '../lib/api'
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

type Tone = 'ok' | 'warn' | 'bad' | 'idle'
const TEXT: Record<Tone, string> = {
  ok: 'text-ok-soft', warn: 'text-warn-soft', bad: 'text-bad-soft', idle: 'text-slate-400',
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

  const inside = labs?.reduce((n, l) => n + l.people.length, 0) ?? 0
  const alerts = labs?.reduce((n, l) => n + l.alert_count, 0) ?? 0
  // Big tiles only where there is something to watch; quiet labs (no door
  // hardware, nobody in, no booking, no alarm) go in a slim strip below.
  const watched = (l: MonitorTile) => l.has_door || l.people.length > 0 || l.alert_count > 0 || !!l.booking
  const featured = labs?.filter(watched) ?? []
  const quiet = labs?.filter(l => !watched(l)) ?? []
  const n = featured.length
  const cols = n <= 1 ? 'grid-cols-1' : n <= 4 ? 'md:grid-cols-2' : n <= 6 ? 'md:grid-cols-3' : 'md:grid-cols-4'

  return (
    <div className="h-screen flex flex-col bg-ink-950 text-slate-100 overflow-hidden">
      <header className="shrink-0 flex items-center gap-5 px-6 py-3 border-b border-ink-600/60 bg-ink-900/80">
        <Link to="/" title="Back to the portal" className="text-slate-500 hover:text-slate-200">
          <ArrowLeft size={20} /></Link>
        <InstitutionLogo strong className="!h-9" />
        <div className="text-[15px] font-extrabold tracking-[0.18em]">
          SMART <span className="text-accent-300">LAB</span>
          <span className="ml-3 text-slate-400 font-semibold tracking-[0.14em]">LIVE MONITOR</span>
        </div>
        <div className="ml-auto flex items-center gap-6 text-[15px]">
          <Stat icon={<UsersRound size={17} />} tone={inside ? 'ok' : 'idle'}>{inside} inside</Stat>
          <Stat icon={<TriangleAlert size={17} />} tone={alerts ? 'bad' : 'idle'}>
            {alerts} alert{alerts === 1 ? '' : 's'}</Stat>
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

      <main className="flex-1 min-h-0 p-4 overflow-auto flex flex-col gap-4">
        {!labs ? <div className="flex-1 grid place-items-center"><Spinner label="Loading laboratories" /></div>
          : !labs.length ? <div className="flex-1 grid place-items-center text-slate-400">No active laboratories.</div>
          : <>
              {featured.length > 0 && (
                <div className={`flex-1 grid ${cols} gap-4 auto-rows-fr`}
                     style={{ minHeight: n > 8 ? `${Math.ceil(n / 4) * 320}px` : undefined }}>
                  {featured.map(l => <Tile key={l.lab_id} t={l} wide={featured.length <= 2} />)}
                </div>)}
              {quiet.length > 0 && (
                <div className="shrink-0">
                  <div className="text-[11.5px] uppercase tracking-[0.16em] text-slate-500 mb-2">
                    Other laboratories · no door hardware, nobody inside</div>
                  <div className="flex flex-wrap gap-2">
                    {quiet.map(l => (
                      <span key={l.lab_id} title={l.name}
                            className="rounded-lg border border-ink-600/60 bg-ink-800/50 px-3 py-1.5 text-[13px]">
                        <b className="text-slate-200">{l.code}</b>
                        <span className="text-slate-500"> · {l.next_booking_at
                          ? `next ${fmtTime(l.next_booking_at)}` : 'free'}</span>
                      </span>))}
                  </div>
                </div>)}
            </>}
      </main>
    </div>
  )
}

function Stat({ icon, tone, children }: { icon: ReactNode; tone: Tone; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-2 font-semibold ${TEXT[tone]}`}>{icon}{children}</span>
}

function Tile({ t, wide }: { t: MonitorTile; wide: boolean }) {
  // Static red frame; only the ALERT badge pulses - a pulsing tile would fade
  // the very text someone is trying to read.
  const frame = t.state === 'ALERT'
    ? 'border-bad/70 bg-bad/[0.07] shadow-[0_0_0_1px_rgba(239,68,68,.35),0_0_32px_-8px_rgba(239,68,68,.6)]'
    : t.state === 'WARN' ? 'border-warn/50 bg-warn/[0.04]' : 'border-ink-600/70 bg-ink-800/60'
  const offline = t.has_door && t.controller_online === false
  const big = wide ? 'text-[clamp(34px,3.6vw,64px)]' : 'text-[clamp(22px,2vw,34px)]'
  const body = wide ? 'text-[clamp(17px,1.35vw,24px)]' : 'text-[clamp(15px,1.1vw,18px)]'

  const doorLock = t.has_door ? (
    <div className={`grid gap-3 ${wide ? 'grid-rows-2 h-full' : 'grid-cols-2'}`}>
      <Big label="Door" size={big} dim={offline}
           tone={t.door_closed === null ? 'idle' : t.door_closed ? 'ok' : 'warn'}
           icon={t.door_closed === false ? <DoorOpen /> : <DoorClosed />}
           value={t.door_closed === null ? 'No data' : t.door_closed ? 'Closed' : 'Open'} />
      <Big label="Lock" size={big} dim={offline}
           tone={t.locked == null ? 'idle' : t.locked ? 'ok' : 'warn'}
           icon={t.locked === false ? <LockOpen /> : <Lock />}
           value={t.locked == null ? 'No data' : t.locked ? 'Locked' : 'Unlocked'} />
    </div>
  ) : (
    <div className="rounded-xl border border-ink-600/60 px-4 py-3 text-slate-400">
      No door controller in this lab.</div>
  )

  const details = (
    <div className={`flex flex-col gap-5 min-h-0 ${body}`}>
      {offline && (
        <div className="flex items-center gap-2 text-warn-soft font-semibold">
          <WifiOff className="w-[1.1em] h-[1.1em] shrink-0" /> Door controller offline · last known state shown</div>
      )}
      <div>
        <Label icon={<UsersRound size={14} />}>Inside
          <span className="ml-2 tnum text-white text-[1.2em] normal-case tracking-normal font-bold">{t.people.length}</span>
        </Label>
        {t.people.length ? (
          <ul className="space-y-1 mt-1">
            {t.people.slice(0, 5).map((p, i) => (
              <li key={i} className="flex items-baseline gap-2">
                <span className="font-semibold text-white truncate">{p.name ?? 'Unknown'}</span>
                <span className="text-slate-500 text-[0.75em]">since {fmtTime(p.since)}</span>
              </li>))}
            {t.people.length > 5 && <li className="text-slate-400 text-[0.75em]">+{t.people.length - 5} more</li>}
          </ul>
        ) : <div className="text-slate-500 mt-1">Nobody inside</div>}
      </div>

      <div>
        <Label>Booking</Label>
        <div className="mt-1 text-slate-200">
          {t.booking ? <>Booked by <b className="text-white">{t.booking.name ?? 'someone'}</b> until {fmtTime(t.booking.until)}</>
            : t.next_booking_at ? <>Free · next at {fmtTime(t.next_booking_at)}</>
            : <span className="text-slate-500">Free · no more bookings</span>}
        </div>
      </div>

      {(t.alerts.length > 0 || t.faults.length > 0) && (
        <div>
          <Label icon={<ShieldAlert size={14} />}>Needs attention</Label>
          <div className="mt-1 space-y-1.5">
            {t.alerts.map((a, i) => (
              <div key={i} className={`flex items-center gap-2 font-semibold
                                       ${a.severity === 'CRITICAL' ? 'text-bad-soft' : 'text-warn-soft'}`}>
                <span className="truncate">{a.title}</span>
                {a.count > 1 && <span className="shrink-0 px-1.5 rounded-md bg-white/10 text-[0.7em] tnum">×{a.count}</span>}
                <span className="ml-auto text-[0.7em] font-normal text-slate-400 shrink-0">{relative(a.at)}</span>
              </div>))}
            {t.alert_count > shown(t) && (
              <div className="text-[0.7em] text-slate-400">+{t.alert_count - shown(t)} more</div>)}
            {t.faults.map(f => (
              <div key={f} className="text-warn-soft">{f} not responding</div>))}
          </div>
        </div>
      )}
    </div>
  )

  return (
    <section className={`rounded-2xl border p-5 xl:p-6 flex flex-col gap-5 min-h-0 ${frame}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0">
          <div className={`${wide ? 'text-[clamp(26px,2.4vw,40px)]' : 'text-[clamp(20px,1.8vw,28px)]'} font-extrabold tracking-wide leading-none`}>{t.code}</div>
          <div className="text-[14px] text-slate-400 truncate mt-1.5">{t.name}</div>
        </div>
        <StatePill state={t.state} />
      </div>

      {wide ? (
        <div className="flex-1 min-h-0 grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-8">
          {doorLock}{details}
        </div>
      ) : <>{doorLock}<div className="flex-1 min-h-0">{details}</div></>}

      <div className={`pt-3 border-t border-ink-600/50 flex items-center gap-4 ${wide ? 'text-[16px]' : 'text-[13.5px]'}`}>
        <span className="text-[11.5px] uppercase tracking-[0.16em] text-slate-500 shrink-0">Last at the door</span>
        {t.last_event ? (
          <span className="min-w-0 truncate">
            <span className={EVENT_BAD.has(t.last_event.type) ? 'text-bad-soft font-semibold'
              : t.last_event.type === 'ACCESS_GRANTED' ? 'text-ok-soft font-semibold' : 'text-slate-200'}>
              {EVENT_LABEL[t.last_event.type] ?? t.last_event.type}</span>
            {t.last_event.who && <span className="text-slate-200"> · {t.last_event.who}</span>}
            <span className="text-slate-500"> · {relative(t.last_event.at)}</span>
          </span>
        ) : <span className="text-slate-500">No door activity yet</span>}
        {(t.environment.temperature || t.environment.humidity) && (
          <span className="ml-auto flex items-center gap-3 text-slate-300 shrink-0">
            {t.environment.temperature && <span className="inline-flex items-center gap-1">
              <Thermometer size={15} />{t.environment.temperature.value.toFixed(1)}°C</span>}
            {t.environment.humidity && <span className="inline-flex items-center gap-1">
              <Droplets size={15} />{t.environment.humidity.value.toFixed(0)}%</span>}
          </span>
        )}
      </div>
    </section>
  )
}

/** How many alerts the grouped lines already account for. */
const shown = (t: MonitorTile) => t.alerts.reduce((n, a) => n + a.count, 0)

function Label({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return <div className="flex items-center gap-2 text-[12px] uppercase tracking-[0.16em] text-slate-400">
    {icon}{children}</div>
}

function StatePill({ state }: { state: MonitorTile['state'] }) {
  const cls = state === 'ALERT' ? 'bg-bad/20 text-bad-soft border-bad/60 animate-pulse'
    : state === 'WARN' ? 'bg-warn/15 text-warn-soft border-warn/40' : 'bg-ok/15 text-ok-soft border-ok/40'
  const icon = state === 'OK' ? <CircleCheck size={16} /> : <TriangleAlert size={16} />
  const label = state === 'ALERT' ? 'ALERT' : state === 'WARN' ? 'ATTENTION' : 'NORMAL'
  return <span className={`ml-auto shrink-0 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border
                           text-[13px] font-bold tracking-[0.14em] ${cls}`}>{icon}{label}</span>
}

function Big({ label, value, icon, tone, dim, size }: {
  label: string; value: string; icon: ReactNode; tone: Tone; dim?: boolean; size: string
}) {
  return (
    <div className="rounded-xl border border-ink-600/60 bg-ink-900/60 px-5 py-4 flex flex-col justify-center min-h-0">
      <div className="text-[12px] uppercase tracking-[0.18em] text-slate-400">{label}
        {dim && <span className="ml-2 normal-case tracking-normal text-warn-soft">last known</span>}</div>
      <div className={`mt-1 flex items-center gap-3 font-extrabold ${size} ${TEXT[tone]} ${dim ? 'opacity-60' : ''}`}>
        <span className="[&>svg]:w-[0.9em] [&>svg]:h-[0.9em] [&>svg]:shrink-0">{icon}</span>{value}</div>
    </div>
  )
}
