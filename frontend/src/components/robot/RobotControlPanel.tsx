/**
 * Robot control (Home / approved routines / software stop) for ONE robot.
 *
 * Everything is enforced by the server; the buttons only ask. Until a controller interface is
 * commissioned, the server answers UNAVAILABLE and says why - shown here, never hidden. A request
 * never moves the twin: the twin follows measured telemetry only. A browser button is NOT an
 * emergency stop - the robot's own E-stop and safety system are.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Hand, Home, Lock, OctagonX, Unlock } from 'lucide-react'
import { RobotCommandResult, RobotControl, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { Chip } from '../ui'

const newId = () => (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`)

export default function RobotControlPanel({ robotId, robotName }: { robotId: number; robotName: string }) {
  const { user } = useAuth()
  const [st, setSt] = useState<RobotControl | null>(null)
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState<RobotCommandResult | null>(null)
  const [error, setError] = useState('')
  const inFlight = useRef(false)

  const load = useCallback(() => { api.robotControl(robotId).then(setSt).catch(e => setError(e.message)) }, [robotId])
  useEffect(() => { load(); const t = window.setInterval(load, 5000); return () => window.clearInterval(t) }, [load])

  const mine = !!st?.owner && st.owner.user_id === user?.id
  const caps = st?.capabilities
  const run = async (fn: () => Promise<unknown>) => {
    if (inFlight.current) return                     // no double submissions
    inFlight.current = true; setBusy(true); setError('')
    try { await fn() } catch (e) { setError(e instanceof Error ? e.message : 'Request failed') }
    finally { inFlight.current = false; setBusy(false); load() }
  }
  const command = (action: 'home' | 'stop') => run(async () => {
    if (action === 'home' && !confirm(`Run the HOME program${caps?.home_program ? ` (${caps.home_program})` : ''} on ${robotName}?\n\nLook at the robot first: the work area must be clear.`)) return
    setLast(await api.robotCommand(robotId, { action, command_id: newId(), confirmed: action === 'home' }))
  })

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm">
        <Hand size={14} className="text-accent-300" />
        <span className="font-medium text-slate-200">Control · {robotName}</span>
        <span className="ml-auto"><Chip tone={st?.controller_mode === 'REMOTE_READY' ? 'ok' : 'warn'}>
          controller {st?.controller_mode?.toLowerCase().replaceAll('_', ' ') ?? '…'}</Chip></span>
      </div>
      {caps?.unavailable_reason && (
        <p className="text-[12px] text-warn-soft leading-relaxed">Motion commands unavailable: {caps.unavailable_reason}</p>)}
      <p className="text-[12px] text-slate-400">
        {caps?.home_program && <>Home program: <b className="text-slate-200">{caps.home_program}</b> · </>}Interface: {caps?.interface ?? '…'} · telemetry {st?.telemetry_age_s == null ? 'none'
          : `${st.telemetry_age_s.toFixed(1)} s old`} · {st?.owner
          ? <>control: <b className="text-slate-200">{st.owner.name}</b> ({Math.max(0, st.owner.expires_in_s)} s left)</>
          : 'nobody has portal control'}
      </p>
      <div className="grid grid-cols-2 gap-2">
        {mine
          ? <button className="btn-ghost btn-sm" disabled={busy} onClick={() => run(() => api.robotControlRelease(robotId))}><Unlock size={13} /> Release control</button>
          : <button className="btn-ghost btn-sm" disabled={busy || !!st?.owner} onClick={() => run(() => api.robotControlRequest(robotId))}><Lock size={13} /> Request control</button>}
        <button className="btn-ghost btn-sm" disabled={busy || !mine || !caps?.home} title={caps?.unavailable_reason ?? ''}
                onClick={() => command('home')}><Home size={13} /> Home</button>
        <button className="btn-ghost btn-sm col-span-2 text-warn-soft border border-warn/40" disabled={busy || !mine || !caps?.stop}
                title={caps?.unavailable_reason ?? ''} onClick={() => command('stop')}>
          <OctagonX size={13} /> Software stop request (not an emergency stop)</button>
      </div>
      {caps && caps.routines.length === 0 && <p className="text-[11.5px] text-slate-500">No approved routines for this robot yet.</p>}
      {last && <p className={`text-[12px] ${last.status === 'DRY_RUN' ? 'text-sky-300' : 'text-slate-300'}`}>Last request: <b>{last.status === 'DRY_RUN' ? 'DRY RUN (test)' : last.status}</b> - {last.reason}
        {last.status === 'REQUESTED' && ' (the robot state below shows whether it actually moved or stopped)'}</p>}
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}
      <p className="text-[11px] text-slate-500">The teach pendant can always take over. In danger use the robot's own emergency stop.</p>
    </div>
  )
}
