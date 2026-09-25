/**
 * One booking, traced end to end: reservation, credential, both factors,
 * the door, and what is known about the exit. This is the page used to
 * demonstrate - and afterwards reconstruct - a physical access session.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, ChevronRight, Clock, DoorOpen, QrCode, ShieldCheck, UserRound, Wrench,
} from 'lucide-react'
import { BookingTrace, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { endReasonText, methodLabel } from '../lib/labels'
import { fmtDateLong, fmtDuration, fmtTime, fmtTimeSec, relative } from '../lib/time'
import {
  BookingStatusChip, Chip, ErrorBanner, KV, SectionTitle, Skeleton,
} from '../components/ui'
import { LabArt } from '../components/labArt'
import { AccessSteps, EntryFacts, EventTimeline } from '../components/Trace'

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
        <AccessSteps s={s} />
        <div className="mt-3">
          <EntryFacts s={s} reserved={{ start: b.start_time, end: b.end_time }}
                      delayMinutes={b.entry_delay_minutes} />
        </div>
      </section>

      <div className="grid xl:grid-cols-3 gap-6">
        {/* ------------------------------------------------------ timeline */}
        <section className="xl:col-span-2">
          <SectionTitle icon={<Clock size={15} />} sub="Every recorded step, in order, to the second.">
            Timeline
          </SectionTitle>
          <div className="card p-5">
            <EventTimeline events={t.events} />
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
                  <Link key={x.id} to={`/sessions/${x.id}`}
                        className="block p-4 text-[12.5px] hover:bg-ink-700/30">
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
                    <div className="mt-1.5 text-[11.5px] link inline-flex items-center gap-1">
                      Open access session<ChevronRight size={12} /></div>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  )
}
