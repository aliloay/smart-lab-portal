import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  CalendarPlus, CalendarRange, Clock, DoorOpen, LogIn, MapPin, QrCode, X,
} from 'lucide-react'
import { Booking, api } from '../lib/api'
import { fmtDate, fmtTime } from '../lib/time'
import { Chip, EmptyState, SectionTitle, bookingTone } from '../components/ui'

const TABS = ['Upcoming', 'Active', 'Completed', 'Cancelled'] as const
type Tab = typeof TABS[number]

export default function Bookings({ all = false }: { all?: boolean }) {
  const [rows, setRows] = useState<Booking[]>([])
  const [tab, setTab] = useState<Tab>('Upcoming')
  const [loading, setLoading] = useState(true)

  const load = () => api.bookings().then(setRows).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const now = Date.now()
  const buckets = useMemo(() => {
    const b: Record<Tab, Booking[]> = {
      Upcoming: [], Active: [], Completed: [], Cancelled: [] }
    for (const r of rows) {
      const s = new Date(r.start_time).getTime()
      const e = new Date(r.end_time).getTime()
      const dead = r.status === 'CANCELLED' || r.status === 'REJECTED'
      if (dead) b.Cancelled.push(r)
      else if (s <= now && now <= e) b.Active.push(r)
      else if (s > now) b.Upcoming.push(r)
      else b.Completed.push(r)
    }
    return b
  }, [rows, now])

  // Land on a tab that has something in it rather than an empty Upcoming.
  useEffect(() => {
    if (loading) return
    if (buckets.Upcoming.length === 0) {
      const first = TABS.find(t => buckets[t].length > 0)
      if (first) setTab(first)
    }
  }, [loading])   // eslint-disable-line react-hooks/exhaustive-deps

  async function cancel(id: number) {
    await api.cancelBooking(id)
    load()
  }

  const list = buckets[tab]

  return (
    <div>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="page-title">{all ? 'All bookings' : 'My bookings'}</h1>
          <p className="page-sub">
            {all ? 'Every reservation across all laboratories.'
                 : 'Your laboratory reservations and access credentials.'}
          </p>
        </div>
        {!all && (
          <Link to="/book" className="btn-primary">
            <CalendarPlus size={15} />New booking
          </Link>
        )}
      </div>

      <div className="mt-6 flex gap-1 border-b border-ink-600 overflow-x-auto">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`relative px-4 py-2.5 text-sm whitespace-nowrap transition-colors
              ${tab === t ? 'text-accent-300' : 'text-slate-500 hover:text-slate-300'}`}>
            {t}
            <span className="ml-1.5 text-[11px] text-slate-600">
              {buckets[t].length}
            </span>
            {tab === t && (
              <motion.span layoutId="booking-tab"
                className="absolute inset-x-0 -bottom-px h-0.5 bg-accent-400" />
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-3 mt-6">
          {[0, 1, 2].map(i => <div key={i} className="card-pad h-28 skeleton" />)}
        </div>
      ) : list.length === 0 ? (
        <div className="card mt-6">
          <EmptyState icon={<CalendarRange size={20} />}
            title={`No ${tab.toLowerCase()} bookings`}
            detail={tab === 'Upcoming' && !all
              ? 'Book a laboratory to get started.' : undefined}
            action={tab === 'Upcoming' && !all
              ? <Link to="/book" className="btn-primary">Book a laboratory</Link>
              : undefined} />
        </div>
      ) : (
        <div className="mt-6 grid gap-3">
          {list.map((b, i) => (
            <BookingRow key={b.id} b={b} index={i} showUser={all}
                        onCancel={() => cancel(b.id)} />
          ))}
        </div>
      )}
    </div>
  )
}

function BookingRow({ b, index, showUser, onCancel }: {
  b: Booking; index: number; showUser: boolean; onCancel: () => void
}) {
  const now = Date.now()
  const live = b.status === 'CONFIRMED' && new Date(b.end_time).getTime() > now
  const active = b.status === 'CONFIRMED' &&
    new Date(b.start_time).getTime() <= now && now <= new Date(b.end_time).getTime()

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * .04, .3) }}
      className={`card p-5 ${active ? 'border-ok/35' : ''}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="mono text-accent-400">{b.lab_code}</span>
            <Chip tone={bookingTone(b.status)}>{b.status}</Chip>
            {active && <Chip tone="ok">In progress</Chip>}
          </div>

          <h3 className="mt-1.5 text-[15px] font-semibold text-white">
            {b.lab_name}
          </h3>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5
                          text-[12px] text-slate-500">
            <span className="flex items-center gap-1.5">
              <MapPin size={12} />{fmtDate(b.start_time)}
            </span>
            <span className="flex items-center gap-1.5 tnum">
              <Clock size={12} />{fmtTime(b.start_time)} – {fmtTime(b.end_time)}
            </span>
            {showUser && b.user_name && (
              <span className="text-slate-400">{b.user_name}</span>
            )}
          </div>

          {b.reason && (
            <p className="mt-2 text-[12px] text-slate-500 max-w-xl">{b.reason}</p>
          )}

          {/* ------------------------------------------------------------ */}
          {/* Actual use. This is the difference between "the room was      */}
          {/* booked" and "the room was used" — and the punctuality figure  */}
          {/* is the thing a utilisation study actually needs.              */}
          {/* ------------------------------------------------------------ */}
          <div className="mt-3 pt-3 border-t border-ink-700/60 flex flex-wrap
                          items-center gap-x-5 gap-y-1.5 text-[12px]">
            {b.first_entry_at ? (
              <>
                <span className="flex items-center gap-1.5 text-slate-400">
                  <LogIn size={12} className="text-ok" />
                  Entered {fmtTime(b.first_entry_at)}
                </span>
                {typeof b.entry_delay_minutes === 'number' && (
                  <span className={
                    b.entry_delay_minutes > 5 ? 'text-warn'
                    : b.entry_delay_minutes < -5 ? 'text-accent-300'
                    : 'text-ok'}>
                    {b.entry_delay_minutes > 0
                      ? `${b.entry_delay_minutes} min after start`
                      : b.entry_delay_minutes < 0
                        ? `${Math.abs(b.entry_delay_minutes)} min early`
                        : 'on time'}
                  </span>
                )}
                {b.entry_count > 1 && (
                  <span className="flex items-center gap-1.5 text-slate-500">
                    <DoorOpen size={12} />{b.entry_count} entries
                  </span>
                )}
              </>
            ) : (
              <span className="text-slate-600">
                {new Date(b.start_time).getTime() > now
                  ? 'Not yet used'
                  : 'No entry recorded'}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {live && (
            <>
              <Link to={`/bookings/${b.id}/qr`} className="btn-ghost !py-2 !px-3">
                <QrCode size={14} />Access code
              </Link>
              <button onClick={onCancel} title="Cancel booking"
                      aria-label="Cancel booking"
                      className="btn-quiet !px-2.5 !py-2 hover:!text-bad">
                <X size={15} />
              </button>
            </>
          )}
        </div>
      </div>
    </motion.div>
  )
}
