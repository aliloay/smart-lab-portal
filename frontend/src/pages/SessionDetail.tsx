/**
 * One access session - a single visit to a laboratory - traced end to end.
 *
 * Reachable from the access monitor (sessions tab and any event), from a
 * booking, and from the live activity streams. Works for card entries that
 * have no booking. Booking time and actual entry time are shown side by
 * side and never conflated; an exit appears only if one was recorded.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, CalendarRange, Clock, DoorOpen, FlaskConical, UserRound,
} from 'lucide-react'
import { AccessEvent, SessionTrace, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { denialText, endReasonText, eventLabel, eventTone, methodLabel } from '../lib/labels'
import { fmtDateLong, fmtTime, fmtTimeSec, relative } from '../lib/time'
import {
  BookingStatusChip, Chip, Dot, Drawer, ErrorBanner, KV, SectionTitle, Skeleton,
} from '../components/ui'
import { AccessSteps, EntryFacts, EventTimeline } from '../components/Trace'

export default function SessionDetail() {
  const { id } = useParams()
  const sid = Number(id)
  const { user } = useAuth()
  const [t, setT] = useState<SessionTrace | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<AccessEvent | null>(null)

  const load = useCallback(() => api.session(sid).then(setT).catch(e => setError(e.message)), [sid])
  useEffect(() => { setT(null); setError(''); load() }, [load])
  // A live session keeps updating: the door, an exit, a later re-entry.
  useLiveMessages(m => {
    if (m.type === 'access_event' && t && m.event.user_id === t.user.id
        && m.event.lab_id === t.lab.id) load()
  })

  if (error) return (
    <div className="max-w-lg space-y-4">
      <ErrorBanner message={error} />
      <Link to={isStaff(user) ? '/admin/access' : '/bookings'} className="btn-ghost">
        <ArrowLeft size={15} />Back</Link>
    </div>
  )
  if (!t) return <div className="space-y-4"><Skeleton className="h-36" /><Skeleton className="h-72" /></div>

  const { session: s, summary } = t
  const inside = s.ended_at === null

  return (
    <div className="space-y-6">
      <Link to={isStaff(user) ? '/admin/access' : '/bookings'}
            className="inline-flex items-center gap-1.5 text-[13px] text-slate-400 hover:text-white">
        <ArrowLeft size={14} />{isStaff(user) ? 'Access monitor' : 'My bookings'}</Link>

      <section className={`card p-6 sm:p-7 ${inside ? 'border-violet-500/40' : ''}`}>
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="mono text-slate-400">ACCESS SESSION #{s.id}</span>
              {inside ? <Chip tone="violet" dot>Inside now</Chip>
                : s.end_reason === 'EXIT_RECORDED' ? <Chip tone="ok">Exit recorded</Chip>
                : <Chip tone="idle">Ended</Chip>}
              {summary.result && <Chip tone={summary.result === 'GRANTED' ? 'ok' : 'bad'}>
                {summary.result === 'GRANTED' ? 'Access granted' : 'Access denied'}</Chip>}
            </div>
            <h1 className="mt-2 page-title">{t.user.full_name}</h1>
            <p className="page-sub">
              <span className="mono text-accent-200">{t.lab.code}</span> · {t.lab.name} ·{' '}
              {fmtDateLong(s.started_at)}
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-[13px]">
            <div><dt className="label">User</dt><dd className="text-slate-100 flex items-center gap-1.5">
              <UserRound size={13} className="text-slate-400" />{t.user.full_name}</dd></div>
            <div><dt className="label">Identity</dt><dd className="mono text-accent-200">
              {t.user.auth_subject ?? 'not enrolled'}</dd></div>
            <div><dt className="label">Laboratory</dt><dd className="text-slate-100 flex items-center gap-1.5">
              <FlaskConical size={13} className="text-slate-400" />
              <Link to={`/labs/${t.lab.id}`} className="hover:text-accent-200">{t.lab.code}</Link></dd></div>
            <div><dt className="label">Booking</dt><dd className="text-slate-100 flex items-center gap-1.5">
              <CalendarRange size={13} className="text-slate-400" />
              {t.booking ? <Link to={`/bookings/${t.booking.id}`} className="link">
                #{t.booking.id} · {fmtTime(t.booking.start_time)}–{fmtTime(t.booking.end_time)}</Link>
                : 'None (card entry)'}</dd></div>
          </dl>
        </div>
      </section>

      <section>
        <SectionTitle icon={<DoorOpen size={15} />}
          sub="Step 1 establishes who; step 2 must match it; only then does the controller unlock.">
          Live access session
        </SectionTitle>
        <AccessSteps s={summary} />
        <div className="mt-3">
          <EntryFacts s={summary}
                      reserved={t.booking ? { start: t.booking.start_time, end: t.booking.end_time } : null}
                      delayMinutes={t.booking?.entry_delay_minutes} />
        </div>
      </section>

      <div className="grid xl:grid-cols-3 gap-6">
        <section className="xl:col-span-2">
          <SectionTitle icon={<Clock size={15} />} sub="Recorded events, to the second. Select one to inspect it.">
            Timeline
          </SectionTitle>
          <div className="card p-5"><EventTimeline events={t.events} onSelect={setSelected} /></div>
        </section>
        <aside className="space-y-6">
          <section>
            <SectionTitle icon={<DoorOpen size={15} />}>Session record</SectionTitle>
            <div className="card p-4"><dl>
              <KV label="Entry method">{methodLabel(s.entry_method)}</KV>
              <KV label="Second factor">{s.second_factor ? methodLabel(s.second_factor) : 'Not reported'}</KV>
              <KV label="Access granted">{fmtTimeSec(s.started_at)}</KV>
              <KV label="Door opened">{s.door_opened_at ? fmtTimeSec(s.door_opened_at) : '—'}</KV>
              <KV label="Door closed">{s.door_closed_at ? fmtTimeSec(s.door_closed_at) : '—'}</KV>
              <KV label="Exit">{s.end_reason === 'EXIT_RECORDED' && s.ended_at ? fmtTimeSec(s.ended_at) : 'Not recorded'}</KV>
              <KV label="State">{inside
                ? <span className="inline-flex items-center gap-1.5 text-violet-300"><Dot tone="violet" live />Inside</span>
                : endReasonText(s.end_reason)}</KV>
            </dl></div>
          </section>
          {t.booking && (
            <section>
              <SectionTitle icon={<CalendarRange size={15} />}>Booking</SectionTitle>
              <Link to={`/bookings/${t.booking.id}`} className="card card-hover block p-4">
                <div className="flex items-center gap-2"><span className="mono text-slate-400">#{t.booking.id}</span>
                  <BookingStatusChip status={t.booking.status} /></div>
                <div className="mt-1.5 text-[14px] text-white">
                  {fmtTime(t.booking.start_time)} – {fmtTime(t.booking.end_time)}</div>
                {t.booking.reason && <div className="text-[12.5px] text-slate-400 mt-0.5">{t.booking.reason}</div>}
              </Link>
            </section>
          )}
        </aside>
      </div>

      <Drawer open={!!selected} onClose={() => setSelected(null)}
              title={selected ? eventLabel(selected.event_type) : ''}
              subtitle={selected ? `Access event #${selected.id} · ${relative(selected.created_at)}` : ''}>
        {selected && (
          <div className="space-y-5">
            <Chip tone={eventTone(selected.event_type)}>{selected.event_type.replace(/_/g, ' ')}</Chip>
            {selected.reason && (
              <div className="rounded-xl border border-bad/40 bg-bad/[0.08] p-4">
                <div className="label !text-bad-soft/80">Reason</div>
                <div className="mt-1.5 text-sm text-red-100">{denialText(selected.reason)}</div>
                <div className="mono text-bad-soft/70 mt-1">{selected.reason}</div>
              </div>
            )}
            <dl>
              <KV label="Time">{new Date(selected.created_at).toLocaleString([], { hour12: false })}</KV>
              <KV label="Person">{selected.user_name ?? 'Not identified'}</KV>
              <KV label="Laboratory" mono>{selected.lab_code ?? '—'}</KV>
              <KV label="Device">{selected.device_name ?? '—'}</KV>
              <KV label="Booking" mono>{selected.booking_id ? `#${selected.booking_id}` : '—'}</KV>
              <KV label="Method">{selected.method ? methodLabel(selected.method) : '—'}</KV>
              <KV label="Result">{selected.result ?? '—'}</KV>
            </dl>
            <div><div className="label mb-1.5">Message</div>
              <p className="text-[13.5px] text-slate-200">{selected.message || '—'}</p></div>
          </div>
        )}
      </Drawer>
    </div>
  )
}
