/**
 * One booking, traced end to end: reservation, credential, both factors,
 * the door, and what is known about the exit. This is the page used to
 * demonstrate - and afterwards reconstruct - a physical access session.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, CalendarClock, CheckCircle2, Clock, DoorClosed, DoorOpen, Fingerprint,
  KeyRound, LogIn, LogOut, QrCode, ScanFace, ShieldCheck, ShieldX, Timer, UserRound,
  Wrench, XCircle,
} from 'lucide-react'
import { BookingTrace, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import {
  denialShort, denialText, endReasonText, eventLabel, eventTone, methodLabel,
} from '../lib/labels'
import { fmtDateLong, fmtDuration, fmtTime, fmtTimeSec, relative } from '../lib/time'
import {
  BookingStatusChip, Chip, EmptyState, ErrorBanner, KV, SectionTitle, Skeleton, Timeline,
} from '../components/ui'
import { LabArt } from '../components/labArt'

export default function BookingDetail() {
  const { id } = useParams()
  const bid = Number(id)
  const { user } = useAuth()
  const [t, setT] = useState<BookingTrace | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.trace(bid).then(setT).catch(e => setError(e.message))
  }, [bid])
  useEffect(() => { setT(null); setError(''); load() }, [load])
  useLiveMessages(m => {
    if (m.type === 'access_event' && (m.event.booking_id === bid ||
        (t && m.event.user_id === t.user.id && m.event.lab_id === t.lab.id))) load()
  })

  if (error) return (
    <div className="max-w-lg space-y-4">
      <ErrorBanner message={error} />
      <Link to="/" className="btn-ghost"><ArrowLeft size={15} />Back</Link>
    </div>
  )
  if (!t) return <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-72" /></div>

  const { booking: b, summary: s } = t
  const back = isStaff(user) ? '/admin/bookings' : '/bookings'

  return (
    <div className="space-y-6">
      <Link to={back} className="inline-flex items-center gap-1.5 text-[13px] text-slate-400 hover:text-white">
        <ArrowLeft size={14} />{isStaff(user) ? 'Reservations' : 'My bookings'}</Link>

      {/* ---------------------------------------------------------- header */}
      <section className="relative card overflow-hidden">
        <div className="absolute inset-y-0 right-0 w-1/2 hidden md:block">
          <LabArt category={t.lab.category} className="w-full h-full" />
          <div className="absolute inset-0 bg-gradient-to-r from-ink-800 to-ink-800/20" />
        </div>
        <div className="relative p-6 sm:p-7 max-w-2xl">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="mono text-slate-400">BOOKING #{b.id}</span>
            <BookingStatusChip status={b.status} />
            {b.currently_inside && <Chip tone="violet" dot>Inside now</Chip>}
          </div>
          <h1 className="mt-2 page-title">{t.lab.name}</h1>
          <p className="page-sub">
            <span className="mono text-accent-200">{t.lab.code}</span> · {fmtDateLong(b.start_time)}
            {' · '}<span className="tnum">{fmtTime(b.start_time)} → {fmtTime(b.end_time)}</span>
          </p>
          {b.reason && <p className="mt-2 text-[13.5px] text-slate-300">“{b.reason}”</p>}
          <div className="mt-5 flex gap-2 flex-wrap">
            {b.qr_active && <Link to={`/bookings/${b.id}/qr`} className="btn-primary"><QrCode size={16} />Access code</Link>}
            <Link to={`/issues/new?lab=${t.lab.id}`} className="btn-ghost"><Wrench size={16} />Report an issue</Link>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------- session summary */}
      <section>
        <SectionTitle icon={<ShieldCheck size={15} />}
          sub="Reconstructed from the door's own events. Nothing here is estimated.">
          Access session
        </SectionTitle>
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
          <Step n={1} title="First factor" icon={s.first_factor === 'RFID' ? <KeyRound size={16} /> : <QrCode size={16} />}
                ok={s.qr_result ? s.qr_result === 'VALID' : s.first_factor ? true : null}
                value={s.first_factor ? methodLabel(s.first_factor) : 'Not presented'}
                detail={s.first_factor_identity ? `Identity ${s.first_factor_identity}`
                  : s.qr_result && s.qr_result !== 'VALID' ? denialShort(s.qr_result) ?? undefined : undefined} />
          <Step n={2} title="Second factor"
                icon={s.second_factor === 'FINGERPRINT' ? <Fingerprint size={16} /> : <ScanFace size={16} />}
                ok={s.second_factor ? true : s.denial_reason === 'IDENTITY_MISMATCH' ? false : null}
                value={s.second_factor ? methodLabel(s.second_factor) : 'Not recorded'}
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

        <div className="mt-3 card p-5 grid md:grid-cols-2 xl:grid-cols-4 gap-4">
          <Big icon={<CalendarClock size={15} />} label="Reserved"
               value={`${fmtTime(b.start_time)}–${fmtTime(b.end_time)}`} />
          <Big icon={<LogIn size={15} />} label="First entry"
               value={s.entry_at ? fmtTimeSec(s.entry_at) : '—'}
               sub={typeof b.entry_delay_minutes === 'number'
                 ? b.entry_delay_minutes > 0 ? `${b.entry_delay_minutes} min after the booked start`
                 : b.entry_delay_minutes < 0 ? `${-b.entry_delay_minutes} min early` : 'on time'
                 : 'No entry recorded'} />
          <Big icon={<LogOut size={15} />} label="Exit"
               value={s.exit_recorded && s.exit_at ? fmtTimeSec(s.exit_at) : 'Not recorded'}
               sub={s.exit_recorded ? 'Observed exit' : s.entry_at ? endReasonText(s.session_end_reason) : undefined} />
          <Big icon={<Timer size={15} />} label="Duration inside"
               value={s.duration_minutes != null ? fmtDuration(s.duration_minutes) : '—'}
               sub={s.duration_minutes != null ? 'Entry to recorded exit'
                 : 'Only measured when an exit is recorded'} />
        </div>
      </section>

      <div className="grid xl:grid-cols-3 gap-6">
        {/* ------------------------------------------------------ timeline */}
        <section className="xl:col-span-2">
          <SectionTitle icon={<Clock size={15} />} sub="Every recorded step, in order, to the second.">
            Timeline
          </SectionTitle>
          <div className="card p-5">
            {t.events.length === 0 ? <EmptyState compact title="No events yet" /> : (
              <Timeline items={t.events.map(e => ({
                key: e.id,
                time: fmtTimeSec(e.created_at),
                title: eventLabel(e.event_type),
                tone: eventTone(e.event_type),
                icon: iconFor(e.event_type),
                detail: <>
                  {e.reason ? <span className="text-bad-soft">{denialText(e.reason)} </span> : null}
                  {e.message}
                  {e.method && <span className="text-slate-500"> · {methodLabel(e.method)}</span>}
                  {e.device_name && <span className="text-slate-500"> · {e.device_name}</span>}
                </>,
              }))} />
            )}
          </div>
        </section>

        {/* ----------------------------------------------------- side rail */}
        <aside className="space-y-6">
          <section>
            <SectionTitle icon={<UserRound size={15} />}>Identity</SectionTitle>
            <div className="card p-4"><dl>
              <KV label="Person">{t.user.full_name}</KV>
              <KV label="Auth subject" mono>{t.user.auth_subject ?? 'not enrolled'}</KV>
              <KV label="Laboratory" mono>{t.lab.code}</KV>
              <KV label="Booking" mono>#{b.id}</KV>
            </dl></div>
          </section>

          <section>
            <SectionTitle icon={<QrCode size={15} />}>Credential</SectionTitle>
            <div className="card p-4">
              {t.token ? <dl>
                <KV label="State"><Chip tone={t.token.state === 'VALID' ? 'ok' : t.token.state === 'ISSUED'
                  ? 'info' : t.token.state === 'REVOKED' ? 'bad' : 'idle'}>{t.token.state.toLowerCase()}</Chip></KV>
                <KV label="Issued">{relative(t.token.issued_at)}</KV>
                <KV label="Valid">{fmtTime(t.token.valid_from)} → {fmtTime(t.token.valid_until)}</KV>
                <KV label="Scans accepted">{t.token.use_count}</KV>
                <KV label="Last used">{t.token.last_used_at ? fmtTimeSec(t.token.last_used_at) : '—'}</KV>
                {t.token.revoked_at && <KV label="Revoked">{relative(t.token.revoked_at)}</KV>}
              </dl> : <p className="text-sm text-slate-400">No credential issued.</p>}
            </div>
          </section>

          {t.sessions.length > 0 && (
            <section>
              <SectionTitle icon={<DoorOpen size={15} />}>Occupancy sessions</SectionTitle>
              <div className="card divide-y divide-ink-700/60">
                {t.sessions.map(x => (
                  <div key={x.id} className="p-4 text-[12.5px]">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-100 tnum">Entry {fmtTimeSec(x.started_at)}</span>
                      <span className="text-slate-400">{methodLabel(x.entry_method)}
                        {x.second_factor ? ` + ${methodLabel(x.second_factor)}` : ''}</span>
                    </div>
                    <div className="mt-1 text-slate-400">
                      {x.ended_at && x.end_reason === 'EXIT_RECORDED'
                        ? <>Exit {fmtTimeSec(x.ended_at)} · {fmtDuration(x.duration_minutes ?? 0)}</>
                        : endReasonText(x.end_reason)}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
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

function iconFor(t: string) {
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
