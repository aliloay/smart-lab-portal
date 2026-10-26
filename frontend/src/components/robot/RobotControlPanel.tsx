/**
 * Robot control for ONE robot: Home, global STOP, recovery.
 *
 * Everything is enforced by the server; the buttons only ask. The state shown (Ready / Homing /
 * Home reached / Blocked / Failed) comes from joint FEEDBACK, never from a command reply. In
 * ROBOT_CONTROL=dry_run (the default until commissioning) every check runs and nothing is sent.
 * STOP is a software stop - NOT a safety-rated emergency stop: the robot's own E-stop is.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Hand, Home, Lock, OctagonX, RotateCcw, ShieldAlert, Timer, Unlock, Zap } from 'lucide-react'
import { RobotCommandResult, RobotControl, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { Chip } from '../ui'

const newId = () => (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`)
const PHASE: Record<string, { label: string; tone: 'ok' | 'warn' | 'bad' | 'idle' }> = {
  READY: { label: 'Ready', tone: 'idle' }, HOMING: { label: 'Homing…', tone: 'warn' },
  HOME_REACHED: { label: 'Home reached', tone: 'ok' }, BLOCKED: { label: 'Blocked', tone: 'bad' },
  FAILED: { label: 'Failed', tone: 'bad' }, STOP_REQUESTED: { label: 'Stop requested', tone: 'warn' },
  STOPPED: { label: 'Stopped', tone: 'bad' },
}
const READINESS: Record<string, { label: string; tone: 'ok' | 'warn' | 'bad' }> = {
  READY: { label: 'Ready (live)', tone: 'ok' },
  READY_FOR_PHYSICAL_TEST: { label: 'Ready for supervised physical test', tone: 'warn' },
  BLOCKED: { label: 'Blocked', tone: 'bad' },
}
const JOINTS = ['Base', 'Shoulder', 'Elbow', 'Wrist 1', 'Wrist 2', 'Wrist 3']
// Who moves the arm, as the controller reports it (Local-mode agent, 2026-10-26).
const DRIVER: Record<string, string> = {
  PORTAL_PROGRAM: 'portal program playing on the pendant - Home / Stop go through it',
  OTHER_PROGRAM: 'another pendant program is running - the portal cannot stop it in Local mode',
  PENDANT_MANUAL: 'moved from the teach pendant (jog / Freedrive) - only the pendant or E-stop stops it',
  IDLE: 'no program running - press Play on the portal program on the pendant to enable Home / Stop',
}
const fmtAge = (s: number) => s < 120 ? `${s.toFixed(1)} s` : s < 7200 ? `${Math.round(s / 60)} min`
  : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} days`

export default function RobotControlPanel({ robotId, robotName }: { robotId: number; robotName: string }) {
  const { user } = useAuth()
  const [st, setSt] = useState<RobotControl | null>(null)
  const [busy, setBusy] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [last, setLast] = useState<RobotCommandResult | null>(null)
  const [error, setError] = useState('')
  const inFlight = useRef(false)
  const stopFlight = useRef(false)

  const load = useCallback(() => { api.robotControl(robotId).then(setSt).catch(e => setError(e.message)) }, [robotId])
  const homing = st?.master?.phase === 'HOMING'
  const countdown = st?.master?.auto_home?.phase === 'COUNTDOWN'
  useEffect(() => { load(); const t = window.setInterval(load, homing || countdown ? 1000 : 5000); return () => window.clearInterval(t) }, [load, homing, countdown])
  // The countdown ticks locally between the 1 s refreshes (the server's remaining_s is the truth on each refresh).
  const [tick, setTick] = useState(0)
  const seenAt = useRef(0)
  useEffect(() => { seenAt.current = Date.now(); setTick(0) }, [st])
  useEffect(() => {
    if (!countdown) return
    const t = window.setInterval(() => setTick((Date.now() - seenAt.current) / 1000), 200)
    return () => window.clearInterval(t)
  }, [countdown])

  const mine = !!st?.owner && st.owner.user_id === user?.id
  const caps = st?.capabilities
  const m = st?.master
  const dry = st?.control_mode === 'dry_run'
  const run = async (fn: () => Promise<unknown>) => {
    if (inFlight.current) return                     // no double submissions
    inFlight.current = true; setBusy(true); setError('')
    try { await fn() } catch (e) { setError(e instanceof Error ? e.message : 'Request failed') }
    finally { inFlight.current = false; setBusy(false); load() }
  }
  const home = () => run(async () => {
    const pose = m ? m.home_q_deg.map((v, i) => `${JOINTS[i]} ${v.toFixed(2)}°`).join(', ') : ''
    if (!confirm(`Move ${robotName} to HOME?\n${pose}\n\nLook at the robot first: the work area must be clear.`)) return
    setLast(await api.robotCommand(robotId, { action: 'home', command_id: newId(), confirmed: true }))
  })
  // STOP has its own lock and is never blocked by another request in flight: it always goes out.
  const stop = async () => {
    if (stopFlight.current) return
    stopFlight.current = true; setStopping(true); setError('')
    try { const r = await api.robotGlobalStop(robotId, newId()); setLast(r); setSt(r) }
    catch (e) { setError(e instanceof Error ? e.message : 'STOP request failed - use the robot E-stop') }
    finally { stopFlight.current = false; setStopping(false) }
  }
  const recover = () => run(async () => {
    if (!confirm('Clear the latched STOP?\n\nThe arm must be still and the cause understood. Nothing will restart by itself.')) return
    setSt(await api.robotStopRecover(robotId))
  })
  const ph = m ? PHASE[m.phase] : null
  // Home asks the server for control first when this user does not hold it (owner, 2026-10-18:
  // "just buttons for Home and STOP"); every check stays on the server.
  const homeOrTakeControl = () => mine ? home() : run(async () => {
    await api.robotControlRequest(robotId)
    const pose = m ? m.home_q_deg.map((v, i) => `${JOINTS[i]} ${v.toFixed(2)}°`).join(', ') : ''
    if (!confirm(`Move ${robotName} to HOME?\n${pose}\n\nLook at the robot first: the work area must be clear.`)) return
    setLast(await api.robotCommand(robotId, { action: 'home', command_id: newId(), confirmed: true }))
  })
  const homeDisabled = busy || (!!st?.owner && !mine) || !caps?.home || !!m?.stop_latched || homing

  return (
    <div className="card p-3 space-y-2.5">
      <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
        {m && <Chip tone={ph?.tone ?? 'idle'}>{ph?.label ?? m.phase}</Chip>}
        {dry && <Chip tone="idle">DRY RUN</Chip>}
        {st?.simulated && <Chip tone="warn">SIMULATED</Chip>}
        {st?.readiness && <span className="ml-auto"><Chip tone={READINESS[st.readiness.readiness]?.tone ?? 'bad'}>
          {READINESS[st.readiness.readiness]?.label ?? st.readiness.readiness}</Chip></span>}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button type="button" className="rounded-xl py-2.5 font-semibold border border-accent-400/50 bg-accent-500/10 text-white disabled:opacity-50 flex items-center justify-center gap-2"
                disabled={homeDisabled} title={caps?.unavailable_reason ?? (st?.owner && !mine ? `${st.owner.name} has control` : '')}
                onClick={homeOrTakeControl}><Home size={16} /> {homing ? 'Homing…' : 'Home'}</button>
        <button type="button" onClick={m ? stop : undefined} disabled={stopping || !m}
          className="rounded-xl py-2.5 font-bold tracking-wide text-white bg-red-600 hover:bg-red-500 disabled:opacity-60 flex items-center justify-center gap-2">
          <OctagonX size={16} /> {stopping ? 'STOPPING…' : 'STOP'}</button>
      </div>
      <p className="text-center text-[10.5px] text-red-300/90">{m?.relay?.configured ? 'Stops the robot through its safeguard stop input, whoever drives it' : 'Software stop'} - not an emergency stop. In danger use the pendant / cell E-stop.</p>
      {m?.path === 'local_agent' && <div className="text-[11.5px] rounded-lg border border-ink-600 px-2.5 py-1.5 space-y-0.5">
        {m.local?.controller
          ? <><div className="text-slate-300">Controller: <b>{m.local.controller.control_mode === 'LOCAL' ? 'Local mode' : m.local.controller.control_mode === 'REMOTE' ? 'Remote mode' : 'mode unknown'}</b>
              {m.local.state?.robot_mode ? ` · ${m.local.state.robot_mode.toLowerCase()}` : ''}{m.local.state?.safety ? ` · safety ${m.local.state.safety.toLowerCase()}` : ''}</div>
            <div className={m.local.controller.driver === 'PORTAL_PROGRAM' ? 'text-emerald-300' : 'text-warn-soft'}>{DRIVER[m.local.controller.driver] ?? m.local.controller.driver}</div></>
          : <div className="text-warn-soft">Local-mode agent not running - Home / Stop cannot reach the robot (nothing is sent).</div>}
        {m.local_limits && <div className="text-slate-500">{m.local_limits}</div>}
      </div>}
      {m?.auto_home && m.auto_home.enabled && (countdown
        ? <div role="alert" className="rounded-lg border border-warn/60 bg-warn/10 px-2.5 py-2 flex items-center gap-3">
            <Timer size={18} className="text-warn-soft shrink-0" />
            <div className="flex-1 text-[12.5px] text-slate-100">Nobody used the robot for {Math.round(m.auto_home.idle_s / 60 * 10) / 10} min -
              it goes <b>Home in {Math.max(0, Math.ceil((m.auto_home.remaining_s ?? 0) - tick))} s</b>. Clear the work area or cancel.</div>
            <button type="button" className="btn-ghost btn-sm border border-warn/50" disabled={busy}
                    onClick={() => run(async () => setSt(await api.robotAutoHomeCancel(robotId)))}>Cancel</button>
          </div>
        : <p className="text-[11px] text-slate-500"><Timer size={11} className="inline mr-1" />Automatic Home after {Math.round(m.auto_home.idle_s)} s idle
            ({m.auto_home.countdown_s} s countdown): {m.auto_home.phase === 'WAITING' && m.auto_home.idle_for_s != null
              ? `idle ${Math.round(m.auto_home.idle_for_s)} s` : m.auto_home.reason || m.auto_home.phase.toLowerCase()}
            {m.auto_home.last ? ` · last automatic Home: ${m.auto_home.last.status === 'DRY_RUN' ? 'dry run' : m.auto_home.last.status.toLowerCase()}` : ''}</p>)}
      {m?.relay && <p className={`text-[11.5px] ${!m.relay.online ? 'text-warn-soft' : m.relay.in_sync ? 'text-slate-400' : 'text-bad-soft'}`}>
        <Zap size={11} className="inline mr-1" />Hardware stop relay (safeguard stop input): {!m.relay.online
          ? `OFFLINE${m.relay.last_poll_s != null ? ` (${fmtAge(m.relay.last_poll_s)} ago)` : ''} - holding its last state`
          : `${m.relay.relay === 'STOP' ? 'STOP - robot held in safeguard stop' : 'RUN'}${m.relay.in_sync ? '' : ` - switching to ${m.relay.wanted}`}${m.relay.latency_ms != null ? ` · last switch ${m.relay.latency_ms} ms after the click` : ''}`}</p>}
      {m?.stop_latched && <p className="text-[12px] text-bad-soft">STOP latched by {m.stop?.by}{m.stop?.restored ? ' (kept through a portal restart)' : ''} - Home is refused until an administrator recovers.</p>}
      {m?.stop_latched && user?.role === 'ADMIN' && <button className="btn-ghost btn-sm w-full" disabled={busy} onClick={recover}>
        <RotateCcw size={13} /> Recover after STOP (admin)</button>}
      {last && <p className={`text-[12px] ${last.status === 'DRY_RUN' ? 'text-sky-300' : 'text-slate-300'}`}>Last request: <b>{last.status === 'DRY_RUN' ? 'DRY RUN (test)' : last.status}</b> - {last.reason}</p>}
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}

      <details className="text-[12px]">
        <summary className="cursor-pointer text-slate-400 hover:text-slate-200 select-none">Details: readiness, interface, control · {robotName}</summary>
        <div className="mt-2 space-y-2.5">
      {m && <div className="rounded-lg border border-ink-600 p-3 flex flex-wrap items-center gap-3">
        <span className="text-[12px] text-slate-300">{m.detail || (m.max_error_deg != null ? `max joint error to Home ${m.max_error_deg}°` : 'no joint feedback')}</span>
        <span className="text-[11px] text-slate-500 w-full">Home: {m.home_q_deg.map((v, i) => `${JOINTS[i]} ${v.toFixed(2)}°`).join(' · ')} (±{m.tolerance_deg}°, confirmed from feedback)</span>
        <span className="text-[11px] text-slate-500 w-full"><Hand size={11} className="inline mr-1" />controller {st?.controller_mode?.toLowerCase().replaceAll('_', ' ') ?? '…'}{dry ? ' · DRY RUN - nothing is sent' : ''}</span>
      </div>}

      {st?.readiness && <div className="rounded-lg border border-ink-600 p-3 space-y-1.5">
        <div className="flex items-center gap-2 text-[12.5px]">
          <span className="text-slate-300 font-medium">Physical test readiness</span>
          <Chip tone={READINESS[st.readiness.readiness]?.tone ?? 'bad'}>{READINESS[st.readiness.readiness]?.label ?? st.readiness.readiness}</Chip>
          {dry && <span className="text-[11px] text-slate-500 ml-auto">DRY RUN: checks run, nothing is sent</span>}
        </div>
        <ul className="grid sm:grid-cols-2 gap-x-4 gap-y-0.5 text-[11.5px]">
          {st.readiness.checks.map(c => <li key={c.key} className="flex gap-1.5">
            <span className={c.ok ? 'text-emerald-400' : 'text-bad-soft'}>{c.ok ? '✓' : '✗'}</span>
            <span className="text-slate-300">{c.name}</span><span className="text-slate-500 truncate" title={c.detail}>· {c.detail}</span></li>)}
        </ul>
        {st.readiness.dependencies.length > 0 && <div className="text-[11.5px] text-warn-soft">
          <div className="font-medium">Needed before any command can exist for this robot:</div>
          <ol className="list-decimal pl-5 text-slate-400">{st.readiness.dependencies.map(d => <li key={d}>{d}</li>)}</ol></div>}
        {m?.path === 'local_agent' ? <div className="text-[11px] text-slate-500">Home method: one joint move to the verified Home pose
          through the pendant-started portal program, only from an operator-verified start pose; completion from joint feedback</div>
        : m?.home_method && <div className="text-[11px] text-slate-500">Home method: {m.home_method === 'program'
          ? <>the pendant's validated program <b className="text-slate-300">{m.home_program}</b> (load + play), completion from joint feedback</>
          : 'direct joint move (movej) - only with operator approval'}</div>}
      </div>}

      {caps?.unavailable_reason && (
        <p className="text-[12px] text-warn-soft leading-relaxed">Motion commands unavailable: {caps.unavailable_reason}</p>)}
      <p className="text-[12px] text-slate-400">Interface: {caps?.interface ?? '…'} · telemetry {st?.telemetry_age_s == null ? 'none'
          : `${fmtAge(st.telemetry_age_s)} old`} · {st?.owner
          ? <>control: <b className="text-slate-200">{st.owner.name}</b> ({Math.max(0, st.owner.expires_in_s)} s left)</>
          : 'nobody has portal control'}
      </p>
      <div className="grid grid-cols-2 gap-2">
        {mine
          ? <button className="btn-ghost btn-sm" disabled={busy} onClick={() => run(() => api.robotControlRelease(robotId))}><Unlock size={13} /> Release control</button>
          : <button className="btn-ghost btn-sm" disabled={busy || !!st?.owner} onClick={() => run(() => api.robotControlRequest(robotId))}><Lock size={13} /> Request control</button>}
        {!m && <button className="btn-ghost btn-sm text-warn-soft border border-warn/40" disabled={busy || !mine || !caps?.stop}
                onClick={() => run(async () => setLast(await api.robotCommand(robotId, { action: 'stop', command_id: newId(), confirmed: false })))}>
          <OctagonX size={13} /> Software stop request</button>}
      </div>
      <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-[11.5px] text-red-200 flex gap-2">
        <ShieldAlert size={15} className="shrink-0 mt-0.5" />
        <span><b>Emergency stop:</b> {m?.estop_note ?? 'This portal has no safety-rated emergency stop.'} The teach pendant can always take over.</span>
      </div>
        </div>
      </details>
    </div>
  )
}
