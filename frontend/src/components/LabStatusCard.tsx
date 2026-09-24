/**
 * A laboratory as a network node.
 *
 * Every field here is either real or explicitly absent. `status` is fetched
 * per lab and may be null while loading; a lab with no controller shows
 * "No access hardware" rather than pretending a door exists.
 */
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, CircuitBoard, DoorClosed, MapPin, Users } from 'lucide-react'
import { Lab, LabStatus } from '../lib/api'
import { Chip, Dot } from './ui'
import { CircuitTrace } from './visual'

export default function LabStatusCard({ lab, status, index = 0 }: {
  lab: Lab
  status?: LabStatus | null
  index?: number
}) {
  const occupied = status?.occupied ?? false
  const online = status?.controller_online ?? null

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: .3, delay: Math.min(index * .04, .3) }}
    >
      <Link to={`/labs/${lab.id}`}
            className="group card card-hover block p-5 overflow-hidden">
        <CircuitTrace className="absolute -top-1 right-4 w-28 opacity-40
                                 group-hover:opacity-70 transition-opacity" />

        <div className="relative flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mono text-accent-400">{lab.code}</div>
            <h3 className="mt-1.5 text-[15px] font-semibold text-white leading-snug
                           group-hover:text-accent-300 transition-colors">
              {lab.name}
            </h3>
            <div className="mt-1 text-[11px] text-slate-500">{lab.category}</div>
          </div>

          {lab.has_controller ? (
            <Chip tone={occupied ? 'warn' : 'ok'}>
              {occupied ? 'In use' : 'Available'}
            </Chip>
          ) : (
            <Chip tone="idle">Bookable</Chip>
          )}
        </div>

        <p className="relative mt-3 text-[13px] text-slate-500 leading-relaxed
                      line-clamp-2 min-h-[2.6rem]">
          {lab.description || 'No description provided.'}
        </p>

        <div className="relative mt-4 pt-3.5 border-t border-ink-700/70
                        grid grid-cols-2 gap-3 text-[12px]">
          <div className="flex items-center gap-2 text-slate-500 min-w-0">
            <MapPin size={13} className="shrink-0" />
            <span className="truncate">{lab.location || 'Location not set'}</span>
          </div>
          <div className="flex items-center gap-2 text-slate-500">
            <Users size={13} className="shrink-0" />
            <span>
              {status
                ? `${status.current_users.length} / ${lab.capacity}`
                : `Capacity ${lab.capacity}`}
            </span>
          </div>

          {lab.has_controller ? (
            <>
              <div className="flex items-center gap-2 text-slate-500">
                <DoorClosed size={13} className="shrink-0" />
                {status?.door_closed === null || status === undefined ? (
                  <span className="text-slate-600">No data</span>
                ) : (
                  <span className={status?.door_closed ? 'text-ok' : 'text-warn'}>
                    {status?.door_closed ? 'Locked' : 'Open'}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-slate-500">
                <Dot tone={online === null ? 'idle' : online ? 'ok' : 'bad'}
                     live={!!online} />
                <span>
                  {online === null ? 'No data' : online ? 'Controller online'
                                                        : 'Controller offline'}
                </span>
              </div>
            </>
          ) : (
            <div className="col-span-2 flex items-center gap-2 text-slate-600">
              <CircuitBoard size={13} className="shrink-0" />
              <span>No access hardware installed</span>
            </div>
          )}
        </div>

        <div className="relative mt-4 flex items-center gap-1.5 text-[12px]
                        text-accent-400 opacity-0 group-hover:opacity-100
                        transition-opacity">
          View laboratory <ArrowRight size={13} />
        </div>
      </Link>
    </motion.div>
  )
}
