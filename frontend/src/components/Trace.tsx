/**
 * The access-session story, shared by the booking trace and the session
 * detail: step 1, step 2, result, door, then entry/exit/duration and the
 * event timeline. Everything shown comes from recorded events; an exit and
 * a duration appear only when an exit was actually recorded.
 */
import {
  CalendarClock, CheckCircle2, DoorClosed, DoorOpen, Fingerprint, KeyRound, LogIn,
  LogOut, QrCode, ScanFace, ShieldCheck, ShieldX, Timer, XCircle,
} from 'lucide-react'
import type { AccessEvent, TraceSummary } from '../lib/api'
import { denialShort, denialText, endReasonText, eventLabel, eventTone, methodLabel } from '../lib/labels'
import { fmtDuration, fmtTime, fmtTimeSec } from '../lib/time'
import { EmptyState, Timeline } from './ui'

export function AccessSteps({ s }: { s: TraceSummary }) {
  return (
    <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
      <Step n={1} title="First factor" icon={s.first_factor === 'RFID' ? <KeyRound size={16} /> : <QrCode size={16} />}
            ok={s.qr_result ? s.qr_result === 'VALID' : s.first_factor ? true : null}
            value={s.first_factor ? `${methodLabel(s.first_factor)}${s.qr_result === 'VALID' ? ' · valid' : ''}` : 'Not presented'}
            detail={s.first_factor_identity ? `Identity ${s.first_factor_identity}`
              : s.qr_result && s.qr_result !== 'VALID' ? denialShort(s.qr_result) ?? undefined : undefined} />
      <Step n={2} title="Second factor"
            icon={s.second_factor === 'FINGERPRINT' ? <Fingerprint size={16} /> : <ScanFace size={16} />}
            ok={s.second_factor ? true : s.denial_reason === 'IDENTITY_MISMATCH' ? false : null}
            value={s.second_factor ? `${methodLabel(s.second_factor)} · match` : 'Not recorded'}
            detail={s.second_factor_identity ? `Identity ${s.second_factor_identity}`
              : s.denial_reason === 'IDENTITY_MISMATCH' ? 'Did not match step 1' : undefined} />
      <Step n={3} title="Result" icon={s.result === 'DENIED' ? <ShieldX size={16} /> : <ShieldCheck size={16} />}
            ok={s.result === 'GRANTED' ? true : s.result === 'DENIED' ? false : null}
            value={s.result ? (s.result === 'GRANTED' ? 'Access granted' : 'Access denied') : 'No attempt yet'}
            detail={s.result === 'DENIED' ? denialText(s.denial_reason) ?? undefined
              : s.attempts ? `${s.attempts} attempt${s.attempts > 1 ? 's' : ''}${s.denials ? `, ${s.denials} denied` : ''}` : undefined} />
      <Step n={4} title="Door" icon={s.door_opened_at ? <DoorOpen size={16} /> : <DoorClosed size={16} />}
            ok={s.door_opened_at ? true : null}
            value={s.door_opened_at ? `Opened ${fmtTimeSec(s.door_opened_at)}` : 'Not opened'}
            detail={s.door_closed_at ? `Closed ${fmtTimeSec(s.door_closed_at)}` : undefined} />
    </div>
  )
}

/** Reserved vs actual: the distinction the thesis depends on. */
export function EntryFacts({ s, reserved, delayMinutes }: {
  s: TraceSummary
  reserved?: { start: string; end: string } | null
  delayMinutes?: number | null
}) {
  return (
    <div className="card p-5 grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
      <Big icon={<CalendarClock size={15} />} label="Reserved"
           value={reserved ? `${fmtTime(reserved.start)}–${fmtTime(reserved.end)}` : 'No booking'}
           sub={reserved ? undefined : 'Entry by card without a reservation'} />
      <Big icon={<LogIn size={15} />} label="Entry"
           value={s.entry_at ? fmtTimeSec(s.entry_at) : '—'}
           sub={typeof delayMinutes === 'number'
             ? delayMinutes > 0 ? `${delayMinutes} min after the booked start`
             : delayMinutes < 0 ? `${-delayMinutes} min early` : 'on time'
             : s.entry_at ? undefined : 'No entry recorded'} />
      <Big icon={<LogOut size={15} />} label="Exit"
           value={s.exit_recorded && s.exit_at ? fmtTimeSec(s.exit_at) : 'Not recorded'}
           sub={s.exit_recorded ? 'Observed exit' : s.entry_at ? endReasonText(s.session_end_reason) : undefined} />
      <Big icon={<Timer size={15} />} label="Duration inside"
           value={s.duration_minutes != null ? fmtDuration(s.duration_minutes) : '—'}
           sub={s.duration_minutes != null ? 'Entry to recorded exit'
             : 'Only measured when an exit is recorded'} />
    </div>
  )
}

export function EventTimeline({ events, onSelect }: {
  events: AccessEvent[]; onSelect?: (e: AccessEvent) => void
}) {
  if (events.length === 0) return <EmptyState compact title="No events yet" />
  return (
    <Timeline items={events.map(e => ({
      key: e.id,
      time: fmtTimeSec(e.created_at),
      title: onSelect
        ? <button onClick={() => onSelect(e)} className="hover:underline underline-offset-2 text-left">
            {eventLabel(e.event_type)}</button>
        : eventLabel(e.event_type),
      tone: eventTone(e.event_type),
      icon: iconFor(e.event_type),
      detail: <>
        {e.reason ? <span className="text-bad-soft">{denialText(e.reason)} </span> : null}
        {e.message}
        {e.method && <span className="text-slate-500"> · {methodLabel(e.method)}</span>}
        {e.device_name && <span className="text-slate-500"> · {e.device_name}</span>}
      </>,
    }))} />
  )
}

function Step({ n, title, icon, ok, value, detail }: {
  n: number; title: string; icon: React.ReactNode; ok: boolean | null; value: string; detail?: string
}) {
  const tone = ok === true ? 'border-ok/40 bg-ok/[0.06]' : ok === false ? 'border-bad/40 bg-bad/[0.06]'
    : 'border-ink-600'
  return (
    <div className={`card p-4 ${tone}`}>
      <div className="flex items-center justify-between">
        <span className="label">Step {n} · {title}</span>
        {ok === true ? <CheckCircle2 size={16} className="text-ok-soft" />
          : ok === false ? <XCircle size={16} className="text-bad-soft" />
          : <span className="w-4 h-4 rounded-full border border-ink-500" />}
      </div>
      <div className="mt-2.5 flex items-center gap-2 text-[15px] text-white font-medium">
        <span className="text-accent-300">{icon}</span>{value}
      </div>
      {detail && <div className="mt-1 text-[12.5px] text-slate-400">{detail}</div>}
    </div>
  )
}

function Big({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 label"><span className="text-accent-300">{icon}</span>{label}</div>
      <div className="mt-1.5 font-display text-[22px] text-white tnum">{value}</div>
      {sub && <div className="text-[12px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export function iconFor(t: string) {
  if (t.startsWith('QR')) return <QrCode size={14} />
  if (t.startsWith('RFID')) return <KeyRound size={14} />
  if (t.startsWith('FACE')) return <ScanFace size={14} />
  if (t.startsWith('FINGERPRINT')) return <Fingerprint size={14} />
  if (t === 'DOOR_OPENED') return <DoorOpen size={14} />
  if (t === 'DOOR_CLOSED') return <DoorClosed size={14} />
  if (t === 'EXIT_RECORDED') return <LogOut size={14} />
  if (t === 'ACCESS_GRANTED') return <ShieldCheck size={14} />
  if (t === 'ACCESS_DENIED' || t === 'IDENTITY_MISMATCH') return <ShieldX size={14} />
  if (t.startsWith('BOOKING')) return <CalendarClock size={14} />
  return undefined
}
