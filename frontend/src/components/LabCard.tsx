/**
 * A laboratory in the catalogue.
 *
 * Every field is real or explicitly absent: a lab without a door controller
 * says so rather than implying a lock exists, and "available" means no
 * confirmed booking is running right now - not a guess.
 */
import { Link } from 'react-router-dom'
import { ArrowRight, CalendarPlus, CircuitBoard, MapPin, TriangleAlert, Users } from 'lucide-react'
import type { LabOverview } from '../lib/api'
import { fmtTime } from '../lib/time'
import { Chip, Dot } from './ui'
import { LabArt, categoryMeta } from './labArt'

export default function LabCard({ o, canBook = true }: { o: LabOverview; canBook?: boolean }) {
  const { lab } = o
  const meta = categoryMeta(lab.category)
  const hw = lab.has_controller
  const status = !lab.is_active
    ? { tone: 'idle' as const, text: 'Not bookable' }
    : o.occupied ? { tone: 'warn' as const, text: 'In use' }
    : { tone: 'ok' as const, text: 'Available' }

  return (
    <article className="group card card-hover overflow-hidden flex flex-col">
      <Link to={`/labs/${lab.id}`} className="relative block h-36 overflow-hidden"
            aria-label={`${lab.name} (${lab.code})`}>
        <LabArt category={lab.category}
                className="absolute inset-0 w-full h-full transition-transform
                           duration-500 group-hover:scale-[1.03]" />
        <div className="absolute inset-0 bg-gradient-to-t from-ink-800 via-ink-800/20
                        to-transparent" />
        <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1
                        rounded-md bg-ink-900/75 backdrop-blur border border-white/10
                        text-[11px] font-medium text-slate-100">
          <span style={{ color: meta.hue }}>{meta.icon}</span>
          {lab.category}
        </div>
        <div className="absolute top-3 right-3">
          <Chip tone={status.tone} dot className="!bg-ink-900/80 backdrop-blur">
            {status.text}
          </Chip>
        </div>
        <div className="absolute bottom-2.5 left-4 mono text-accent-200 font-medium
                        drop-shadow">{lab.code}</div>
      </Link>

      <div className="px-4 pt-3 pb-4 flex flex-col flex-1">
        <h3 className="font-display text-[16px] font-semibold text-white leading-snug">
          <Link to={`/labs/${lab.id}`} className="hover:text-accent-200 transition-colors">
            {lab.name}
          </Link>
        </h3>
        <p className="mt-1.5 text-[13px] text-slate-400 leading-relaxed line-clamp-2
                      min-h-[2.5rem]">
          {lab.description || 'No description provided.'}
        </p>

        <dl className="mt-3.5 grid grid-cols-2 gap-x-3 gap-y-2 text-[12.5px]">
          <div className="flex items-center gap-2 text-slate-300 min-w-0">
            <MapPin size={13} className="text-slate-400 shrink-0" />
            <span className="truncate">{lab.location || 'Location not set'}</span>
          </div>
          <div className="flex items-center gap-2 text-slate-300">
            <Users size={13} className="text-slate-400 shrink-0" />
            Capacity {lab.capacity}
          </div>
          <div className="col-span-2 flex items-center gap-2 min-w-0">
            {hw ? (
              <>
                <Dot tone={o.controller_online === null ? 'idle'
                          : o.controller_online ? 'ok' : 'bad'}
                     live={!!o.controller_online} />
                <span className={o.controller_online === null ? 'text-slate-400'
                  : o.controller_online ? 'text-ok-soft' : 'text-bad-soft'}>
                  {o.controller_online === null ? 'Door controller · no data yet'
                    : o.controller_online ? 'Door controller online'
                    : 'Door controller offline'}
                </span>
              </>
            ) : (
              <>
                <CircuitBoard size={13} className="text-slate-500 shrink-0" />
                <span className="text-slate-400">No access hardware installed</span>
              </>
            )}
          </div>
          {(o.open_issues > 0 || o.next_booking_at) && (
            <div className="col-span-2 flex items-center gap-3 flex-wrap text-[12px]">
              {o.open_issues > 0 && (
                <span className={`inline-flex items-center gap-1.5 ${
                  o.high_priority_issues ? 'text-warn-soft' : 'text-slate-300'}`}>
                  <TriangleAlert size={12} />
                  {o.open_issues} open issue{o.open_issues > 1 ? 's' : ''}
                </span>
              )}
              {o.next_booking_at && (
                <span className="text-slate-400">
                  Next booking {fmtTime(o.next_booking_at)}
                  {new Date(o.next_booking_at).toDateString() !== new Date().toDateString()
                    && ` · ${new Date(o.next_booking_at).toLocaleDateString([], {
                      day: 'numeric', month: 'short' })}`}
                </span>
              )}
            </div>
          )}
        </dl>

        <div className="mt-auto pt-4 flex items-center gap-2">
          <Link to={`/labs/${lab.id}`} className="btn-ghost btn-sm flex-1">
            View laboratory <ArrowRight size={14} />
          </Link>
          {canBook && lab.is_active && (
            <Link to={`/book?lab=${lab.id}`} className="btn-primary btn-sm">
              <CalendarPlus size={14} /> Book
            </Link>
          )}
        </div>
      </div>
    </article>
  )
}
