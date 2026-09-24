/**
 * One booking, with the thing a calendar cannot show: what actually
 * happened. Reserved 10:00-12:00 is the plan; first entry 10:14 is the
 * record. Exit and time inside appear only when an exit was observed.
 */
import { Link } from 'react-router-dom'
import { ChevronRight, Clock, DoorOpen, LogIn, LogOut, QrCode, UserRound } from 'lucide-react'
import type { Booking } from '../lib/api'
import { countdown, fmtDuration, fmtTime } from '../lib/time'
import { BookingStatusChip, Chip, Dot } from './ui'
import { LabArt } from './labArt'

export default function BookingCard({ b, showUser = false, actions }: {
  b: Booking; showUser?: boolean; actions?: React.ReactNode
}) {
  const now = Date.now()
  const s = new Date(b.start_time).getTime(), e = new Date(b.end_time).getTime()
  const live = b.status === 'CONFIRMED'
  const active = live && s <= now && now <= e
  const future = s > now
  const pct = active ? Math.min(100, (100 * (now - s)) / (e - s)) : future ? 0 : 100

  return (
    <article className={`card overflow-hidden flex ${active ? 'border-ok/40 shadow-glow-ok' : ''}`}>
      <div className="relative w-2 sm:w-28 shrink-0">
        <LabArt category={b.lab_category} className="absolute inset-0 w-full h-full" />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-ink-800/90" />
      </div>
      <div className="flex-1 min-w-0 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="mono text-accent-200">{b.lab_code}</span>
              <BookingStatusChip status={b.status} />
              {active && <Chip tone="ok" dot>In progress</Chip>}
              {b.currently_inside && <Chip tone="violet" dot>Inside</Chip>}
            </div>
            <h3 className="mt-1.5 font-display text-[16px] font-semibold text-white truncate">
              <Link to={`/bookings/${b.id}`} className="hover:text-accent-200">{b.lab_name}</Link>
            </h3>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-slate-300">
              <span className="tnum">
                {new Date(b.start_time).toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })}
                {' · '}{fmtTime(b.start_time)} → {fmtTime(b.end_time)}
              </span>
              {showUser && b.user_name && (
                <span className="flex items-center gap-1.5 text-slate-200"><UserRound size={13} />{b.user_name}</span>
              )}
              {live && (future || active) && (
                <span className="flex items-center gap-1.5 text-accent-200"><Clock size={13} />
                  {countdown(b.start_time, b.end_time)}</span>
              )}
            </div>
            {b.reason && <p className="mt-1.5 text-[12.5px] text-slate-400 line-clamp-1">{b.reason}</p>}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {actions}
            {b.qr_active && (
              <Link to={`/bookings/${b.id}/qr`} className="btn-ghost btn-sm"><QrCode size={14} />QR</Link>
            )}
            <Link to={`/bookings/${b.id}`} className="btn-quiet btn-sm" aria-label="Booking details">
              Details<ChevronRight size={14} />
            </Link>
          </div>
        </div>

        {/* reservation vs reality */}
        {live && (
          <div className="mt-3.5">
            <div className="h-1 rounded-full bg-ink-700 overflow-hidden">
              <div className={`h-full rounded-full ${active ? 'bg-ok' : future ? 'bg-accent-500' : 'bg-slate-500'}`}
                   style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[12px]">
          <Fact icon={<Clock size={12} />} label="Booked" value={fmtTime(b.start_time)} />
          <Fact icon={<LogIn size={12} />} label="Actual entry"
                value={b.first_entry_at ? fmtTime(b.first_entry_at) : future ? 'Not yet' : 'No entry'}
                tone={b.first_entry_at ? 'ok' : undefined}
                extra={typeof b.entry_delay_minutes === 'number'
                  ? b.entry_delay_minutes > 0 ? `${b.entry_delay_minutes} min late`
                  : b.entry_delay_minutes < 0 ? `${-b.entry_delay_minutes} min early` : 'on time'
                  : undefined} />
          <Fact icon={<LogOut size={12} />} label="Exit"
                value={b.last_exit_at ? fmtTime(b.last_exit_at)
                  : b.first_entry_at ? (b.currently_inside ? 'Inside' : 'Not recorded') : '—'} />
          <Fact icon={<DoorOpen size={12} />} label="Time inside"
                value={b.time_inside_minutes != null ? fmtDuration(b.time_inside_minutes)
                  : b.entry_count ? `${b.entry_count} entr${b.entry_count === 1 ? 'y' : 'ies'}` : '—'} />
        </div>
      </div>
    </article>
  )
}

function Fact({ icon, label, value, tone, extra }: {
  icon: React.ReactNode; label: string; value: string; tone?: 'ok'; extra?: string
}) {
  return (
    <div className="well px-2.5 py-2">
      <div className="flex items-center gap-1.5 text-[10.5px] uppercase tracking-wide text-slate-400">
        {icon}{label}</div>
      <div className={`mt-0.5 tnum ${tone === 'ok' ? 'text-ok-soft' : 'text-slate-100'}`}>
        {tone === 'ok' && <Dot tone="ok" className="mr-1.5 !w-1.5 !h-1.5" />}{value}
        {extra && <span className="text-slate-400 text-[11px]"> · {extra}</span>}
      </div>
    </div>
  )
}
