/**
 * The door at a glance, in the sidebar's spare space.
 *
 * Only what the door hardware actually reported, from the same endpoint the
 * laboratory page uses: controller heartbeat, door sensor, next booking. A
 * value the controller never sent reads "Not reported"; a value from a
 * controller that has since gone offline is marked as the last report.
 * Nothing is shown at all when no laboratory has door hardware.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { DoorClosed } from 'lucide-react'
import { LabStatus, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { fmtTime, relative } from '../lib/time'
import { Dot } from './ui'

export default function DoorStatus({ onNavigate }: { onNavigate?: () => void }) {
  const [labId, setLabId] = useState<number | null>(null)
  const [s, setS] = useState<LabStatus | null>(null)

  useEffect(() => {
    api.labs()
      .then(labs => setLabId(labs.find(l => l.has_controller && l.is_active)?.id ?? null))
      .catch(() => setLabId(null))
  }, [])

  const load = useCallback(() => {
    if (labId !== null) api.lab(labId).then(setS).catch(() => {})
  }, [labId])

  useEffect(() => {
    load()
    const t = window.setInterval(load, 30000)
    return () => window.clearInterval(t)
  }, [load])

  // Door and access events for this laboratory refresh it immediately.
  useLiveMessages(m => {
    if (m.type === 'access_event' && m.event.lab_id === labId) load()
  })

  if (labId === null || !s) return null

  const online = s.controller_online
  const stale = online === false
  const door = s.door_closed

  return (
    <Link to={`/labs/${s.lab.id}`} onClick={onNavigate}
      className="block mx-3 mb-3 rounded-xl border border-ink-600/70 bg-ink-800/60
                 px-3.5 py-3 hover:border-ink-500 transition-colors"
      aria-label={`${s.lab.code} door status`}>
      <div className="flex items-center gap-2 text-[10.5px] uppercase tracking-[0.12em] text-slate-400">
        <DoorClosed size={13} className="text-accent-300" />
        <span className="mono !text-[10.5px] text-slate-300">{s.lab.code}</span>
        <span>door</span>
      </div>
      <dl className="mt-2 space-y-1.5 text-[12.5px]">
        <Row label="Controller">
          <Dot tone={online === null ? 'idle' : online ? 'ok' : 'bad'} live={online === true} />
          <span className={online === null ? 'text-slate-400' : online ? 'text-slate-100' : 'text-bad-soft'}>
            {online === null ? 'No data' : online ? 'Online' : 'Offline'}</span>
        </Row>
        <Row label="Door">
          {door === null ? <span className="text-slate-400">Not reported</span> : (
            <span className={stale ? 'text-slate-400' : 'text-slate-100'}>
              {door ? 'Closed' : 'Open'}
              {stale && <span className="text-[10.5px] text-slate-500"> (last reported)</span>}
            </span>
          )}
        </Row>
        <Row label="Next booking">
          {s.next_booking_at
            ? <span className="text-slate-100 tnum" title={relative(s.next_booking_at)}>
                {isToday(s.next_booking_at) ? fmtTime(s.next_booking_at)
                  : new Date(s.next_booking_at).toLocaleDateString([], { day: 'numeric', month: 'short' })
                    + ' · ' + fmtTime(s.next_booking_at)}
              </span>
            : <span className="text-slate-400">None</span>}
        </Row>
      </dl>
    </Link>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-slate-400">{label}</dt>
      <dd className="flex items-center gap-1.5 min-w-0 truncate">{children}</dd>
    </div>
  )
}

function isToday(iso: string) {
  return new Date(iso).toDateString() === new Date().toDateString()
}
