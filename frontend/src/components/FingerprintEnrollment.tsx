/**
 * Fingerprint enrollment inside Users & roles -> Edit user.
 *
 * The portal only leaves a request; the door controller fetches it while
 * idle, guides the person on its LCD and the tablet, and reports each step,
 * which shows here live. Finishing marks the fingerprint as registered.
 * The controller stays the authority: it refuses while the door is in use.
 */
import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Circle, CircleDot, Fingerprint, XCircle } from 'lucide-react'
import { DeviceCommand, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { fmtDateTime } from '../lib/time'
import { ErrorBanner } from './ui'

const STEPS: { key: string; label: string }[] = [
  { key: 'WAIT', label: 'Door controller takes the request' },
  { key: 'PLACE_FINGER', label: 'Place the finger on the door sensor' },
  { key: 'REMOVE_FINGER', label: 'Remove the finger' },
  { key: 'PLACE_AGAIN', label: 'Place the same finger again' },
  { key: 'STORED', label: 'Stored on the sensor' },
]
const ACTIVE = new Set(['PENDING', 'SENT', 'RUNNING'])

function stepIndex(c: DeviceCommand): number {
  if (c.status === 'DONE') return STEPS.length
  const i = STEPS.findIndex(s => s.key === c.step)
  return i >= 0 ? i : 0
}

export default function FingerprintEnrollment({ userId, savedSubject, enrolledAt, onEnrolled }: {
  userId: number
  savedSubject: string | null
  enrolledAt: string | null
  onEnrolled: () => void
}) {
  const [cmd, setCmd] = useState<DeviceCommand | null>(null)
  const [force, setForce] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [doneAt, setDoneAt] = useState<string | null>(enrolledAt)

  const refresh = useCallback((id: number) => {
    api.deviceCommand(id).then(c => {
      setCmd(c)
      if (c.status === 'DONE') { setDoneAt(c.completed_at); onEnrolled() }
    }).catch(() => {})
  }, [onEnrolled])

  // Live steps from the controller, with a poll in case the socket is down.
  useLiveMessages(m => {
    if (m.type === 'staff' && m.kind === 'device_command' && cmd && m.command_id === cmd.id) refresh(cmd.id)
  })
  useEffect(() => {
    if (!cmd || !ACTIVE.has(cmd.status)) return
    const t = window.setInterval(() => refresh(cmd.id), 1500)
    return () => window.clearInterval(t)
  }, [cmd, refresh])

  const slot = /^USER(\d{1,3})$/.exec(savedSubject ?? '')?.[1]
  if (!slot) {
    return <p className="text-[12px] text-slate-500">
      Fingerprint: save a door identity USERn first, then reopen this to enroll the finger.
    </p>
  }

  async function start() {
    setBusy(true); setError('')
    try { setCmd(await api.fingerprintEnroll(userId, force)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed') }
    finally { setBusy(false) }
  }
  async function cancel() {
    if (!cmd) return
    try { setCmd(await api.cancelDeviceCommand(cmd.id)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Cancel failed') }
  }

  const running = !!cmd && ACTIVE.has(cmd.status)
  const at = cmd ? stepIndex(cmd) : -1
  const failed = !!cmd && ['FAILED', 'EXPIRED', 'CANCELLED'].includes(cmd.status)

  return (
    <div className="rounded-lg border border-ink-600/70 bg-ink-800/40 p-3 space-y-2.5">
      <div className="flex items-center gap-2 text-sm text-slate-200">
        <Fingerprint size={15} className="text-accent-300" />
        <span className="font-medium">Fingerprint</span>
        <span className="mono text-[11px] text-slate-400">slot {slot}</span>
        {doneAt && <span className="ml-auto text-[12px] text-ok-soft">registered {fmtDateTime(doneAt)}</span>}
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {cmd && (
        <ol className="space-y-1.5">
          {STEPS.map((s, i) => {
            const done = cmd.status === 'DONE' || i < at
            const now = running && i === at
            return (
              <li key={s.key} className={`flex items-center gap-2 text-[12.5px]
                  ${done ? 'text-ok-soft' : now ? 'text-white font-semibold' : 'text-slate-500'}`}>
                {done ? <CheckCircle2 size={14} /> : now ? <CircleDot size={14} className="text-accent-300 animate-pulse" />
                  : <Circle size={14} />}
                {s.label}
              </li>)
          })}
        </ol>
      )}

      {failed && (
        <p className="flex items-start gap-1.5 text-[12px] text-warn-soft">
          <XCircle size={14} className="shrink-0 mt-px" />
          {cmd?.message || (cmd?.status === 'EXPIRED' ? 'The request expired.' : 'Not stored.')}
        </p>
      )}
      {cmd?.status === 'DONE' && (
        <p className="text-[12px] text-ok-soft">Stored. Their booking QR now works with this finger.</p>)}

      {running ? (
        <div className="flex items-center gap-2">
          <p className="flex-1 text-[11.5px] text-slate-400">
            {cmd?.status === 'PENDING' ? 'Waiting for the door controller (it takes requests only while the door is idle)…'
              : 'Follow the prompts on the door screen.'}</p>
          {cmd?.status === 'PENDING' &&
            <button type="button" className="btn-ghost btn-sm" onClick={cancel}>Cancel</button>}
        </div>
      ) : (
        <>
          {doneAt && (
            <label className="flex items-center gap-2 text-[12px] text-slate-300">
              <input type="checkbox" className="accent-sky-500" checked={force}
                     onChange={e => setForce(e.target.checked)} />
              Replace the finger already stored in slot {slot}</label>)}
          <button type="button" className="btn-ghost btn-sm w-full" disabled={busy} onClick={start}>
            <Fingerprint size={14} /> {cmd ? 'Enroll again' : doneAt ? 'Re-enroll fingerprint' : 'Enroll fingerprint at the door'}
          </button>
        </>
      )}
    </div>
  )
}
