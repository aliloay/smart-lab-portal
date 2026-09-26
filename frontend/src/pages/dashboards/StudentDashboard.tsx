import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight, BarChart3, CalendarCheck, CalendarPlus, Clock, DoorOpen, FlaskConical, History,
  QrCode, ShieldCheck, Wrench,
} from 'lucide-react'
import { AccessEvent, Booking, Issue, LabOverview, MyStats, api } from '../../lib/api'
import { firstName, useAuth } from '../../lib/auth'
import { useLiveMessages } from '../../lib/live'
import { eventLabel, eventTone, denialShort, ACTIVE_ISSUE } from '../../lib/labels'
import {
  countdown, fmtDateLong, fmtTime, greeting, relative, todayStr, dateStr,
} from '../../lib/time'
import {
  Chip, Dot, EmptyState, IssueStatusChip, MetricCard, SectionTitle, CardsSkeleton,
  Skeleton,
} from '../../components/ui'
import { LabArt, categoryMeta } from '../../components/labArt'
import { Bloom, GridField, RoboticArm } from '../../components/visual'
import LabCard from '../../components/LabCard'

export default function StudentDashboard() {
  const { user } = useAuth()
  const [bookings, setBookings] = useState<Booking[] | null>(null)
  const [labs, setLabs] = useState<LabOverview[]>([])
  const [events, setEvents] = useState<AccessEvent[]>([])
  const [issues, setIssues] = useState<Issue[]>([])
  const [, tick] = useState(0)

  const load = useCallback(() => {
    api.bookings().then(setBookings).catch(() => setBookings([]))
    api.labsOverview().then(setLabs).catch(() => {})
    api.events({ limit: 8 }).then(setEvents).catch(() => {})
    api.issues({ limit: 20 }).then(setIssues).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])
  // A door event or a notification about me: refetch rather than guess.
  useLiveMessages(m => { if (m.type === 'access_event' || m.type === 'notification') load() })
  useEffect(() => {
    const t = window.setInterval(() => tick(n => n + 1), 30000)
    return () => window.clearInterval(t)
  }, [])

  const now = Date.now()
  const confirmed = (bookings ?? []).filter(b => b.status === 'CONFIRMED')
  const active = confirmed.find(b =>
    new Date(b.start_time).getTime() <= now && now <= new Date(b.end_time).getTime())
  const upcoming = confirmed
    .filter(b => new Date(b.start_time).getTime() > now)
    .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time))
  const next = upcoming[0]
  const visits = (bookings ?? []).filter(b => b.first_entry_at).length
  const openReports = issues.filter(i => ACTIVE_ISSUE.includes(i.status))
  const availableNow = labs.filter(l => l.available_now && l.lab.is_active)

  return (
    <div className="space-y-7">
      {/* ------------------------------------------------------------ hero */}
      <section className="relative card overflow-hidden">
        <GridField />
        <Bloom />
        <RoboticArm className="absolute right-4 -top-10 w-[210px] h-auto opacity-75
                               hidden md:block" />
        <div className="relative p-6 sm:p-7 flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-xl">
            <div className="eyebrow">Your laboratory activity</div>
            <h1 className="mt-2 page-title">
              {greeting()}, {firstName(user?.full_name)}
            </h1>
            <p className="page-sub">{fmtDateLong(new Date().toISOString())}</p>
          </div>
          <div className="flex gap-2 flex-wrap md:mr-52">
            <Link to="/book" className="btn-primary"><CalendarPlus size={16} />Book a laboratory</Link>
            <Link to="/issues/new" className="btn-ghost"><Wrench size={16} />Report an issue</Link>
          </div>
        </div>
      </section>

      {/* ------------------------------------------- active access / next */}
      {bookings === null ? <Skeleton className="h-40" /> : active ? (
        <ActiveAccess b={active} />
      ) : next ? (
        <NextBooking b={next} />
      ) : (
        <section className="card">
          <EmptyState icon={<CalendarPlus size={20} />}
            title="No upcoming bookings"
            detail="Reserve a laboratory to receive a time-bound access credential for its door."
            action={<Link to="/book" className="btn-primary">Book a laboratory<ArrowRight size={15} /></Link>} />
        </section>
      )}

      {/* --------------------------------------------------------- metrics */}
      {bookings === null ? <CardsSkeleton /> : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="Upcoming bookings" value={upcoming.length}
                      icon={<CalendarCheck size={16} />} tone={upcoming.length ? 'info' : 'idle'}
                      to="/bookings" hint={next ? `Next ${countdown(next.start_time, next.end_time)}` : 'Nothing scheduled'} />
          <MetricCard label="Labs available now" value={availableNow.length}
                      icon={<FlaskConical size={16} />} to="/labs"
                      hint={`of ${labs.length} laboratories`} />
          <MetricCard label="Laboratory visits" value={visits}
                      icon={<DoorOpen size={16} />}
                      info="Bookings where the door recorded you actually entering."
                      hint="Recorded entries at the door" />
          <MetricCard label="Open reports" value={openReports.length}
                      icon={<Wrench size={16} />} to="/issues"
                      tone={openReports.length ? 'warn' : 'idle'}
                      hint={issues.length ? `${issues.length} reported in total` : 'None reported'} />
        </div>
      )}

      <div className="grid lg:grid-cols-5 gap-6">
        {/* ------------------------------------------------ recent activity */}
        <section className="lg:col-span-3">
          <SectionTitle icon={<History size={15} />}
            sub="Your own entries, refusals and bookings - live."
            action={<Link to="/bookings" className="text-xs link">All bookings</Link>}>
            Recent activity
          </SectionTitle>
          <div className="card overflow-hidden">
            {events.length === 0 ? (
              <EmptyState icon={<ShieldCheck size={20} />} title="No activity yet"
                detail="Bookings, door entries and refusals will appear here as they happen." />
            ) : (
              <ul className="divide-y divide-ink-700/60">
                {events.map(e => (
                  <li key={e.id} className="flex items-center gap-3 px-5 py-3">
                    <Dot tone={eventTone(e.event_type)} />
                    <div className="min-w-0 flex-1">
                      <div className="text-[13.5px] text-slate-100">
                        {eventLabel(e.event_type)}
                        {e.reason && <span className="text-bad-soft"> · {denialShort(e.reason)}</span>}
                      </div>
                      <div className="text-[12px] text-slate-400 truncate">
                        {e.lab_code ? `${e.lab_code} · ` : ''}{e.message}
                      </div>
                    </div>
                    <span className="shrink-0 text-[12px] text-slate-400">{relative(e.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* ----------------------------------------------------- my reports */}
        <section className="lg:col-span-2 space-y-6">
          <MyUsage />
          <div>
            <SectionTitle icon={<Wrench size={15} />}
              action={<Link to="/issues" className="text-xs link">My reports</Link>}>
              My reports
            </SectionTitle>
            <div className="card p-4">
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  ['Open', issues.filter(i => i.status === 'OPEN' || i.status === 'ACKNOWLEDGED').length],
                  ['In progress', issues.filter(i => i.status === 'IN_PROGRESS' || i.status === 'WAITING_FOR_PARTS').length],
                  ['Resolved', issues.filter(i => i.status === 'RESOLVED' || i.status === 'CLOSED').length],
                ].map(([k, v]) => (
                  <div key={k} className="well py-3">
                    <div className="font-display text-2xl text-white tnum">{v}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">{k}</div>
                  </div>
                ))}
              </div>
              {issues.length === 0 ? (
                <p className="mt-4 text-[13px] text-slate-400">
                  Something broken, missing or unsafe? Reporting it takes under a minute.
                </p>
              ) : (
                <ul className="mt-3 divide-y divide-ink-700/60">
                  {issues.slice(0, 3).map(i => (
                    <li key={i.id}>
                      <Link to={`/issues/${i.id}`} className="flex items-center gap-3 py-2.5 group">
                        <div className="min-w-0 flex-1">
                          <div className="text-[13px] text-slate-100 truncate group-hover:text-white">{i.title}</div>
                          <div className="mono !text-[11px] text-slate-400">{i.ticket_number} · {i.lab_code}</div>
                        </div>
                        <IssueStatusChip status={i.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <Link to="/issues/new" className="btn-ghost btn-sm w-full mt-3">
                <Wrench size={14} /> Report an issue
              </Link>
            </div>
          </div>

          <QuickBooking labs={labs} />
        </section>
      </div>

      {/* ------------------------------------------------ available labs */}
      <section>
        <SectionTitle icon={<FlaskConical size={15} />}
          sub="Free right now - no confirmed booking running."
          action={<Link to="/labs" className="text-xs link">All {labs.length} laboratories</Link>}>
          Available laboratories
        </SectionTitle>
        {labs.length === 0 ? (
          <div className="grid md:grid-cols-3 gap-4">
            {[0, 1, 2].map(i => <Skeleton key={i} className="h-80" />)}
          </div>
        ) : availableNow.length === 0 ? (
          <div className="card"><EmptyState title="Every laboratory is in use right now"
            detail="Check the catalogue for later availability." /></div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[...availableNow]
              .sort((a, b) => Number(b.lab.has_controller) - Number(a.lab.has_controller))
              .slice(0, 3).map(o => <LabCard key={o.lab.id} o={o} />)}
          </div>
        )}
      </section>
    </div>
  )
}

function ActiveAccess({ b }: { b: Booking }) {
  const now = Date.now()
  const s = new Date(b.start_time).getTime(), e = new Date(b.end_time).getTime()
  const pct = Math.min(100, Math.max(0, (100 * (now - s)) / (e - s)))
  return (
    <section className="relative card overflow-hidden border-ok/40 shadow-glow-ok">
      <div className="absolute inset-0 bg-gradient-to-r from-ok/[.10] via-transparent to-transparent" />
      <div className="relative p-6 flex flex-wrap items-center justify-between gap-6">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <Dot tone="ok" live />
            <span className="eyebrow !text-ok-soft">Access window open</span>
          </div>
          <h2 className="mt-2 font-display text-2xl font-semibold text-white">{b.lab_name}</h2>
          <p className="text-sm text-slate-300 mt-1 tnum">
            {fmtTime(b.start_time)} → {fmtTime(b.end_time)}
            <span className="text-slate-500"> · </span>{countdown(b.start_time, b.end_time)}
          </p>
          <div className="mt-3 w-72 max-w-full h-1.5 rounded-full bg-ink-700 overflow-hidden">
            <div className="h-full bg-ok rounded-full" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-2 text-[12.5px] text-slate-400">
            {b.first_entry_at ? `Entered at ${fmtTime(b.first_entry_at)}`
              : 'Not entered yet - show the code at the door, then your fingerprint or face.'}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={`/bookings/${b.id}`} className="btn-ghost">Details</Link>
          <Link to={`/bookings/${b.id}/qr`} className="btn-primary !px-5 !py-3">
            <QrCode size={17} />Show access code
          </Link>
        </div>
      </div>
    </section>
  )
}

function NextBooking({ b }: { b: Booking }) {
  const meta = categoryMeta(b.lab_category)
  return (
    <section className="card overflow-hidden grid sm:grid-cols-[220px_1fr]">
      <div className="relative h-32 sm:h-auto">
        <LabArt category={b.lab_category} className="absolute inset-0 w-full h-full" />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-ink-800/90 hidden sm:block" />
      </div>
      <div className="p-6 flex flex-wrap items-center justify-between gap-5">
        <div>
          <Chip tone="info"><span style={{ color: meta.hue }}>{meta.icon}</span>Next booking</Chip>
          <h2 className="mt-2.5 font-display text-xl font-semibold text-white">{b.lab_name}</h2>
          <p className="text-sm text-slate-300 mt-1 flex items-center gap-2 flex-wrap tnum">
            <Clock size={14} className="text-accent-300" />
            {new Date(b.start_time).toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })}
            , {fmtTime(b.start_time)} → {fmtTime(b.end_time)}
          </p>
          <p className="text-[12.5px] text-accent-200 mt-1.5">{countdown(b.start_time, b.end_time)}</p>
        </div>
        <div className="flex gap-2">
          <Link to={`/bookings/${b.id}`} className="btn-ghost">Details</Link>
          <Link to={`/bookings/${b.id}/qr`} className="btn-ghost"><QrCode size={15} />Access code</Link>
        </div>
      </div>
    </section>
  )
}

/** Choose a lab and a day, land in the booking flow with both filled in. */
function QuickBooking({ labs }: { labs: LabOverview[] }) {
  const nav = useNavigate()
  const bookable = useMemo(() => labs.filter(l => l.lab.is_active), [labs])
  const [lab, setLab] = useState('')
  const [date, setDate] = useState(todayStr())
  useEffect(() => { if (!lab && bookable[0]) setLab(String(bookable[0].lab.id)) }, [bookable, lab])
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1)
  return (
    <div>
      <SectionTitle icon={<CalendarPlus size={15} />}>Quick booking</SectionTitle>
      <div className="card p-4 space-y-3">
        <select className="input" value={lab} onChange={e => setLab(e.target.value)}
                aria-label="Laboratory">
          {bookable.map(o => <option key={o.lab.id} value={o.lab.id}>
            {o.lab.code} · {o.lab.name}</option>)}
        </select>
        <div className="flex gap-2">
          {[['Today', todayStr()], ['Tomorrow', dateStr(tomorrow)]].map(([t, v]) => (
            <button key={v} onClick={() => setDate(v)}
              className={`flex-1 btn-sm btn ${date === v
                ? 'bg-accent-500/20 text-accent-200 border border-accent-500/40'
                : 'btn-ghost'}`}>{t}</button>
          ))}
          <input type="date" className="input !py-1.5 !w-auto" value={date} min={todayStr()}
                 onChange={e => setDate(e.target.value)} aria-label="Date" />
        </div>
        <button disabled={!lab} onClick={() => nav(`/book?lab=${lab}&date=${date}`)}
                className="btn-primary w-full">
          Choose a time <ArrowRight size={15} />
        </button>
      </div>
    </div>
  )
}

/**
 * The student's own usage over 90 days - their bookings only, never other
 * people's and never lab-wide analytics.
 */
function MyUsage() {
  const [s, setS] = useState<MyStats | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => { api.myStats(90).then(setS).catch(() => setFailed(true)) }, [])
  const max = Math.max(1, ...(s?.weekly_hours ?? []).map(w => w.hours))
  return (
    <div>
      <SectionTitle icon={<BarChart3 size={15} />} sub="Your own bookings over the last 90 days.">
        My lab time</SectionTitle>
      <div className="card p-4">
        {failed ? <p className="text-[13px] text-slate-400">Usage could not be loaded right now.</p>
          : !s ? <Skeleton className="h-28" />
          : !s.sessions_finished ? (
            <EmptyState compact icon={<BarChart3 size={18} />} title="No finished sessions yet"
              detail="Your weekly lab time and attendance appear after your first booking ends." />
          ) : <>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="well py-2.5"><div className="font-display text-xl text-white tnum">{s.booked_hours}h</div>
                <div className="text-[11px] text-slate-400">booked</div></div>
              <div className="well py-2.5"><div className="font-display text-xl text-white tnum">
                {s.attendance_rate === null ? '–' : `${Math.round(s.attendance_rate * 100)}%`}</div>
                <div className="text-[11px] text-slate-400">attended</div></div>
              <div className="well py-2.5"><div className="font-display text-xl text-white tnum">{s.upcoming}</div>
                <div className="text-[11px] text-slate-400">upcoming</div></div>
            </div>
            <div className="mt-4 flex items-end gap-1 h-16" role="img"
                 aria-label="Booked hours per week, last 12 weeks">
              {s.weekly_hours.map(w => (
                <div key={w.week} className="flex-1 flex flex-col justify-end h-full"
                     title={`Week of ${w.week}: ${w.hours} h`}>
                  <div className="rounded-t-[3px] bg-gradient-to-t from-accent-500/70 to-teal-400/80"
                       style={{ height: `${w.hours ? Math.max((w.hours / max) * 100, 6) : 0}%` }} />
                  <div className="h-[2px] bg-ink-600/60 mt-0.5" />
                </div>))}
            </div>
            <div className="mt-1 text-[10.5px] text-slate-500 flex justify-between">
              <span>12 weeks ago</span><span>this week</span></div>
            {s.by_lab.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {s.by_lab.map(l => <Chip key={l.lab_code}>{l.lab_code} · {l.count}</Chip>)}
              </div>)}
            <p className="mt-2 text-[11.5px] text-slate-500">
              Attended = the door recorded your entry during the booking.</p>
          </>}
      </div>
    </div>
  )
}
