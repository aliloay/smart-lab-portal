import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight, CalendarPlus, Clock, FlaskConical, QrCode, ShieldCheck, Sparkles,
} from 'lucide-react'
import { AccessEvent, Booking, Lab, LabStatus, api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { countdown, fmtDateTime, fmtTime, relative } from '../lib/time'
import {
  Chip, Dot, EmptyState, MetricCard, SectionTitle, SkeletonCards,
  bookingTone, eventTone,
} from '../components/ui'
import LabStatusCard from '../components/LabStatusCard'
import { Bloom, GridField, RoboticArm } from '../components/visual'

export default function Dashboard() {
  const { user } = useAuth()
  const [bookings, setBookings] = useState<Booking[]>([])
  const [labs, setLabs] = useState<Lab[]>([])
  const [statuses, setStatuses] = useState<Record<number, LabStatus>>({})
  const [events, setEvents] = useState<AccessEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [, tick] = useState(0)

  useEffect(() => {
    Promise.all([api.bookings(), api.labs()])
      .then(([b, l]) => {
        setBookings(b)
        setLabs(l)
        // Live status only for labs that actually have a controller — asking
        // the others would return nothing and waste a request per card.
        l.filter(x => x.has_controller).forEach(x =>
          api.lab(x.id).then(s => setStatuses(p => ({ ...p, [x.id]: s })))
            .catch(() => {}))
      })
      .finally(() => setLoading(false))
    api.events({ user_id: user?.id, limit: 8 }).then(setEvents).catch(() => {})
  }, [user?.id])

  // Keeps the countdown honest without refetching.
  useEffect(() => {
    const t = setInterval(() => tick(n => n + 1), 30000)
    return () => clearInterval(t)
  }, [])

  const now = Date.now()
  const confirmed = bookings.filter(b => b.status === 'CONFIRMED')
  const active = confirmed.find(b =>
    new Date(b.start_time).getTime() <= now && now <= new Date(b.end_time).getTime())
  const next = confirmed
    .filter(b => new Date(b.start_time).getTime() > now)
    .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time))[0]

  const withHardware = labs.filter(l => l.has_controller)
  const onlineCount = withHardware
    .filter(l => statuses[l.id]?.controller_online).length
  const occupiedCount = Object.values(statuses).filter(s => s.occupied).length

  return (
    <div className="space-y-8">
      {/* ------------------------------------------------------------- hero */}
      <section className="relative card overflow-hidden">
        <GridField />
        <Bloom />
        <RoboticArm className="absolute -right-10 -top-6 w-[290px] h-auto
                               opacity-[.35] hidden md:block" />

        <div className="relative p-6 sm:p-7">
          <div className="label flex items-center gap-2">
            <Sparkles size={12} className="text-accent-400" />
            Smart laboratory status
          </div>
          <h1 className="mt-2 text-[26px] font-semibold text-white tracking-tight">
            {greeting()}, {user?.full_name?.split(' ')[0]}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {new Date().toLocaleDateString([], {
              weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>
      </section>

      {/* ---------------------------------------------------------- metrics */}
      {loading ? <SkeletonCards /> : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="Laboratories" value={labs.length}
                      icon={<FlaskConical size={15} />}
                      hint={`${withHardware.length} with access hardware`} />
          <MetricCard label="Your bookings" value={confirmed.length}
                      icon={<CalendarPlus size={15} />}
                      tone={confirmed.length ? 'info' : 'idle'}
                      hint={active ? 'One active now' : next ? 'One upcoming' : 'None upcoming'} />
          <MetricCard label="Access controllers online"
                      info="Door controllers currently reporting to the portal. Only laboratories with access hardware installed are counted."
                      value={`${onlineCount}/${withHardware.length}`}
                      animate={false}
                      icon={<ShieldCheck size={15} />}
                      tone={withHardware.length === 0 ? 'idle'
                            : onlineCount === withHardware.length ? 'ok' : 'warn'} />
          <MetricCard label="Labs in use" value={occupiedCount}
                      icon={<Clock size={15} />}
                      tone={occupiedCount ? 'warn' : 'idle'}
                      hint="Based on live door sessions" />
        </div>
      )}

      {/* ------------------------------------------------- active / next */}
      {active ? (
        <motion.section
          initial={{ opacity: 0, scale: .99 }} animate={{ opacity: 1, scale: 1 }}
          className="relative card overflow-hidden border-ok/35 shadow-glow-ok"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-ok/[.07] to-transparent" />
          <div className="relative p-6 flex flex-wrap items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2">
                <Dot tone="ok" live />
                <span className="chip bg-ok/12 text-ok border border-ok/30">
                  Access window open
                </span>
              </div>
              <h2 className="mt-3 text-lg font-semibold text-white">
                {active.lab_name}
              </h2>
              <p className="text-sm text-slate-400 mt-1">
                {fmtTime(active.start_time)} – {fmtTime(active.end_time)}
                <span className="text-slate-600"> · </span>
                <span className="tnum">{countdown(active.start_time, active.end_time)}</span>
              </p>
              {active.reason && (
                <p className="text-xs text-slate-500 mt-1.5">{active.reason}</p>
              )}
            </div>
            <Link to={`/bookings/${active.id}/qr`} className="btn-primary">
              <QrCode size={15} />Show access code
            </Link>
          </div>
        </motion.section>
      ) : next ? (
        <section className="card p-6 flex flex-wrap items-center justify-between gap-6">
          <div>
            <Chip tone="info">Next booking</Chip>
            <h2 className="mt-3 text-lg font-semibold text-white">{next.lab_name}</h2>
            <p className="text-sm text-slate-400 mt-1">
              {fmtDateTime(next.start_time)}
              <span className="text-slate-600"> · </span>
              <span className="tnum">{countdown(next.start_time, next.end_time)}</span>
            </p>
          </div>
          <Link to={`/bookings/${next.id}/qr`} className="btn-ghost">
            <QrCode size={15} />View access code
          </Link>
        </section>
      ) : !loading && (
        <section className="card">
          <EmptyState
            icon={<CalendarPlus size={20} />}
            title="No upcoming bookings"
            detail="Reserve a laboratory to receive a time-bound access credential for its door."
            action={<Link to="/book" className="btn-primary">
              Book a laboratory<ArrowRight size={15} />
            </Link>}
          />
        </section>
      )}

      {/* ---------------------------------------------------- lab network */}
      <section>
        <SectionTitle icon={<FlaskConical size={14} />}
          action={<Link to="/labs"
            className="text-xs text-accent-400 hover:text-accent-300">
            All {labs.length} laboratories
          </Link>}>
          Laboratory network
        </SectionTitle>

        {loading ? (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[0, 1, 2].map(i => <div key={i} className="card-pad h-48 skeleton" />)}
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {/* Labs with hardware first — those are the ones with live state. */}
            {[...labs]
              .sort((a, b) => Number(b.has_controller) - Number(a.has_controller))
              .slice(0, 6)
              .map((l, i) => (
                <LabStatusCard key={l.id} lab={l} status={statuses[l.id]} index={i} />
              ))}
          </div>
        )}
      </section>

      {/* ------------------------------------------------- recent activity */}
      <section>
        <SectionTitle icon={<ShieldCheck size={14} />}>Your recent access</SectionTitle>
        <div className="card overflow-hidden">
          {events.length === 0 ? (
            <EmptyState icon={<ShieldCheck size={20} />}
                        title="No access activity yet"
                        detail="Entries and refusals at laboratory doors will appear here." />
          ) : (
            <ul className="divide-y divide-ink-700/60">
              {events.map((e, i) => (
                <motion.li key={e.id}
                  initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: Math.min(i * .03, .25) }}
                  className="flex items-center gap-3 px-5 py-3"
                >
                  <Chip tone={eventTone(e.event_type)}>
                    {e.event_type.replace(/_/g, ' ')}
                  </Chip>
                  <span className="flex-1 min-w-0 truncate text-xs text-slate-500">
                    {e.message}
                  </span>
                  <span className="shrink-0 text-xs text-slate-600">
                    {relative(e.created_at)}
                  </span>
                </motion.li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

function greeting() {
  const h = new Date().getHours()
  if (h < 5)  return 'Working late'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}
