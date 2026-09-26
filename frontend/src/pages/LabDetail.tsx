import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Activity, ArrowLeft, Boxes, CalendarClock, CalendarPlus, Camera, CircuitBoard, Cpu,
  DoorClosed, Droplets, Fingerprint, Gauge, Lock, MapPin, Radio, Server, Thermometer,
  TriangleAlert, Users, Wind, Wrench, Zap,
} from 'lucide-react'
import { AccessEvent, Asset, Device, LabStatus, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { useLive, useLiveMessages } from '../lib/live'
import { assetStatusLabel, assetTone, denialShort, eventLabel, eventTone } from '../lib/labels'
import { fmtClock, fmtDateTime, fmtTime, relative } from '../lib/time'
import {
  Chip, Dot, EmptyState, ErrorBanner, IssueStatusChip, SectionTitle, SeverityBadge,
  Skeleton, StateDot,
} from '../components/ui'
import { LabArt, categoryMeta } from '../components/labArt'
import { DoorSchematic } from '../components/visual'

export default function LabDetail() {
  const { id } = useParams()
  const labId = Number(id)
  const { user } = useAuth()
  const staff = isStaff(user)
  const { connected } = useLive()
  const [status, setStatus] = useState<LabStatus | null>(null)
  const [error, setError] = useState('')
  const [events, setEvents] = useState<AccessEvent[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [sensors, setSensors] = useState<unknown[] | null>(null)

  const loadStatus = useCallback(() => {
    api.lab(labId).then(setStatus).catch(e => setError(e.message))
  }, [labId])

  useEffect(() => {
    setStatus(null); setError('')
    loadStatus()
    api.labActivity(labId, 60).then(setEvents).catch(() => {})
    api.assets(labId).then(setAssets).catch(() => {})
    api.labSensors(labId).then(setSensors).catch(() => setSensors([]))
  }, [labId, loadStatus])

  useLiveMessages(m => {
    if (m.type === 'access_event' && m.event.lab_id === labId) {
      setEvents(p => [m.event, ...p.filter(x => x.id !== m.event.id)].slice(0, 80))
      if (/^(DOOR|ACCESS|DEVICE|EXIT)/.test(m.event.event_type)) loadStatus()
    }
    if (m.type === 'staff' && m.kind === 'issue') loadStatus()
  })

  if (error) {
    return <div className="max-w-lg space-y-4">
      <ErrorBanner message={error} />
      <Link to="/labs" className="btn-ghost"><ArrowLeft size={15} />All laboratories</Link>
    </div>
  }
  if (!status) {
    return <div className="space-y-5">
      <Skeleton className="h-56" />
      <div className="grid lg:grid-cols-3 gap-4">{[0, 1, 2].map(i => <Skeleton key={i} className="h-40" />)}</div>
    </div>
  }

  const { lab } = status
  const meta = categoryMeta(lab.category)
  const dev = (t: string) => status.devices.find(d => d.device_type === t)
  const master = dev('MASTER_CONTROLLER'), camera = dev('CAMERA'), face = dev('FACE_SERVER')
  const tri = (d?: Device) => !d || d.state === 'NO_DATA' ? null : d.state === 'ONLINE'
  const comp = (k: string): boolean | null => {
    const v = master?.component_state?.[k]
    return typeof v === 'boolean' ? v : null
  }
  // With the controller silent, everything it reported is history, not state.
  const stale = !!master && master.state !== 'ONLINE' && master.last_seen_at !== null
  const staleNote = stale && master?.last_seen_at
    ? `Last reported ${relative(master.last_seen_at)} · controller offline` : undefined

  return (
    <div className="space-y-7">
      <Link to="/labs" className="inline-flex items-center gap-1.5 text-[13px] text-slate-400
                                  hover:text-white"><ArrowLeft size={14} />Laboratories</Link>

      {/* ---------------------------------------------------------- hero */}
      <section className="relative card overflow-hidden">
        <div className="absolute inset-y-0 right-0 w-full md:w-[62%]">
          <LabArt category={lab.category} className="w-full h-full" />
          <div className="absolute inset-0 bg-gradient-to-r from-ink-800 via-ink-800/80 to-ink-800/10" />
          <div className="absolute inset-0 bg-gradient-to-t from-ink-800/90 to-transparent md:hidden" />
        </div>
        <div className="relative p-6 sm:p-8 max-w-2xl">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="mono text-accent-200 text-[13px]">{lab.code}</span>
            <span className="inline-flex items-center gap-1.5 text-[12px] text-slate-300">
              <span style={{ color: meta.hue }}>{meta.icon}</span>{lab.category}
            </span>
            {lab.has_controller ? (
              <Chip tone={status.controller_online === null ? 'idle'
                : status.controller_online ? 'ok' : 'bad'} dot>
                {status.controller_online === null ? 'Controller · no data'
                  : status.controller_online ? 'Online' : 'Controller offline'}
              </Chip>
            ) : <Chip tone="idle">No access hardware</Chip>}
            <Chip tone={status.occupied ? 'warn' : 'ok'}>{status.occupied ? 'In use' : 'Available'}</Chip>
          </div>
          <h1 className="mt-3 page-title !text-[32px]">{lab.name}</h1>
          <p className="mt-2.5 text-[14.5px] text-slate-300 leading-relaxed">
            {lab.description || 'No description provided.'}
          </p>
          <div className="mt-4 flex items-center gap-5 flex-wrap text-[13px] text-slate-300">
            <span className="flex items-center gap-1.5"><MapPin size={14} className="text-slate-400" />
              {lab.location || 'Location not set'}</span>
            <span className="flex items-center gap-1.5"><Users size={14} className="text-slate-400" />
              Capacity {lab.capacity}</span>
            <span className="flex items-center gap-1.5"><Boxes size={14} className="text-slate-400" />
              {assets.length} equipment items</span>
          </div>
          <div className="mt-6 flex gap-2 flex-wrap">
            {lab.is_active && (
              <Link to={`/book?lab=${lab.id}`} className="btn-primary"><CalendarPlus size={16} />Book this laboratory</Link>
            )}
            <Link to={`/issues/new?lab=${lab.id}`} className="btn-ghost"><Wrench size={16} />Report an issue</Link>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------- live status */}
      <section>
        <SectionTitle icon={<CircuitBoard size={15} />}
          sub={lab.has_controller ? 'What the door hardware last reported. Grey means not reported - never assumed "fine".' : undefined}
          action={<span className="flex items-center gap-1.5 text-[12px] text-slate-400">
            <Dot tone={connected ? 'ok' : 'idle'} live={connected} />{connected ? 'Live' : 'Reconnecting'}
          </span>}>
          Live status
        </SectionTitle>
        {lab.has_controller ? (
          <div className="card p-5 grid lg:grid-cols-[1.1fr_1fr] gap-6 items-center">
            <DoorSchematic controller={tri(master)} camera={tri(camera) ?? comp('camera')} face={tri(face)}
                           doorClosed={status.door_closed} className="w-full h-auto" />
            <div className="grid sm:grid-cols-2 gap-2.5">
              <Node icon={<DoorClosed size={15} />} title="Door" stale={staleNote}
                    state={status.door_closed} labels={['Closed', 'Open']} />
              <Node icon={<Cpu size={15} />} title="Master controller" device={master}
                    state={tri(master)} labels={['Online', 'Offline']} />
              <Node icon={<Camera size={15} />} title="Entry camera" device={camera}
                    state={tri(camera) ?? comp('camera')} labels={['Online', 'Offline']} />
              <Node icon={<Server size={15} />} title="Face server" device={face}
                    state={tri(face)} labels={['Online', 'Offline']} />
              <Node icon={<Radio size={15} />} title="RFID reader"
                    state={comp('rfid')} labels={['Ready', 'Fault']}
                    stale={comp('rfid') !== null ? staleNote : undefined}
                    note={comp('rfid') === null ? 'The firmware does not send this yet' : undefined} />
              <Node icon={<Fingerprint size={15} />} title="Fingerprint"
                    state={comp('fingerprint')} labels={['Ready', 'Fault']}
                    stale={comp('fingerprint') !== null ? staleNote : undefined}
                    note={comp('fingerprint') === null ? 'The firmware does not send this yet' : undefined} />
              <Node icon={<Lock size={15} />} title="Relay"
                    state={comp('relay_locked')} labels={['Locked', 'Unlocked']}
                    stale={comp('relay_locked') !== null ? staleNote : undefined}
                    note={comp('relay_locked') === null ? 'The firmware does not send this yet' : undefined} />
              <Node icon={<Users size={15} />} title="Occupancy" neutral
                    state={status.occupants > 0 ? true : status.controller_online === null ? null : false}
                    labels={[`${status.occupants} inside`, 'Nobody inside']}
                    note={staff && status.current_users.length ? status.current_users.join(', ') : undefined} />
            </div>
          </div>
        ) : (
          <div className="card">
            <EmptyState icon={<CircuitBoard size={20} />} title="No access-control hardware installed"
              detail="This laboratory can be booked and credentials are issued normally, but no door
                      controller responds to them yet." />
          </div>
        )}
      </section>

      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          {/* ----------------------------------------------------- booking */}
          <section>
            <SectionTitle icon={<CalendarClock size={15} />}
              action={lab.is_active ? <Link to={`/book?lab=${lab.id}`} className="text-xs link">Book</Link> : undefined}>
              Bookings
            </SectionTitle>
            <div className="card p-5 grid md:grid-cols-2 gap-5">
              <div>
                <div className="label mb-2">Now</div>
                {status.current_booking ? (
                  <div className="well p-4 border-warn/30">
                    <div className="flex items-center gap-2"><Dot tone="warn" live />
                      <span className="text-[13.5px] text-white font-medium tnum">
                        {fmtTime(status.current_booking.start_time)} → {fmtTime(status.current_booking.end_time)}
                      </span></div>
                    <div className="mt-1 text-[12.5px] text-slate-300">
                      {status.current_booking.is_mine ? 'Your booking'
                        : status.current_booking.user_name ?? 'Reserved'}
                    </div>
                    {status.current_booking.booking_id && (
                      <Link to={`/bookings/${status.current_booking.booking_id}`}
                            className="mt-2 inline-block text-xs link">Open booking trace →</Link>
                    )}
                  </div>
                ) : <div className="well p-4 text-[13px] text-slate-300 flex items-center gap-2">
                      <Dot tone="ok" />Free right now</div>}
              </div>
              <div>
                <div className="label mb-2">Upcoming</div>
                {status.upcoming.length === 0 ? (
                  <div className="text-[13px] text-slate-400">Nothing booked ahead.</div>
                ) : (
                  <ul className="space-y-1.5">
                    {status.upcoming.map((s, i) => (
                      <li key={i} className="flex items-center gap-2 text-[13px]">
                        <span className="mono text-slate-300 shrink-0 tnum whitespace-nowrap">
                          {new Date(s.start_time).toLocaleDateString([], { day: 'numeric', month: 'short' })}
                          {' '}{fmtTime(s.start_time)}–{fmtTime(s.end_time)}
                        </span>
                        <span className="truncate text-slate-400">
                          {s.is_mine ? <span className="text-accent-300">You</span> : s.user_name ?? 'Reserved'}
                        </span>
                        {s.status === 'PENDING' && <Chip tone="warn">pending</Chip>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </section>

          {/* ----------------------------------------------------- activity */}
          <section>
            <SectionTitle icon={<Activity size={15} />}
              sub={staff ? 'Every authentication attempt and door transition at this laboratory.'
                         : 'Your own activity at this laboratory.'}>
              Access activity
            </SectionTitle>
            <div className="card max-h-[460px] overflow-y-auto">
              {events.length === 0 ? (
                <EmptyState icon={<Activity size={20} />} title="No activity recorded"
                  detail="Events appear here the moment they happen at the door." />
              ) : (
                <ol className="divide-y divide-ink-700/60">
                  {events.map(e => (
                    <li key={e.id} className="px-4 py-2.5 flex items-center gap-3">
                      <span className="mono text-slate-400 shrink-0 w-[62px] tnum">{fmtClock(e.created_at)}</span>
                      <Chip tone={eventTone(e.event_type)}>{eventLabel(e.event_type)}</Chip>
                      <span className="flex-1 min-w-0 truncate text-[12.5px] text-slate-300">
                        {e.user_name ?? e.message}
                        {e.reason && <span className="text-bad-soft"> · {denialShort(e.reason)}</span>}
                      </span>
                      <span className="text-[11px] text-slate-500 hidden sm:block">{relative(e.created_at)}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </section>
        </div>

        <div className="space-y-6">
          {/* ------------------------------------------------- maintenance */}
          <section>
            <SectionTitle icon={<Wrench size={15} />}
              action={staff ? <Link to={`/issues?lab_id=${lab.id}`} className="text-xs link">All</Link> : undefined}>
              Maintenance
            </SectionTitle>
            <div className="card p-4">
              <div className="flex items-center gap-4">
                <div><div className="font-display text-2xl text-white tnum">{status.open_issues}</div>
                  <div className="text-[11.5px] text-slate-400">open issues</div></div>
                <div><div className={`font-display text-2xl tnum ${status.high_priority_issues
                  ? 'text-warn-soft' : 'text-white'}`}>{status.high_priority_issues}</div>
                  <div className="text-[11.5px] text-slate-400">high priority</div></div>
                <Link to={`/issues/new?lab=${lab.id}`} className="ml-auto btn-ghost btn-sm">
                  <Wrench size={14} />Report</Link>
              </div>
              {status.recent_issues.length > 0 && (
                <ul className="mt-3 divide-y divide-ink-700/60">
                  {status.recent_issues.map(i => {
                    const body = (
                      <div className="py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="mono !text-[11px] text-slate-400">{i.ticket_number}</span>
                          <SeverityBadge severity={i.severity} />
                        </div>
                        <div className="mt-1 text-[13px] text-slate-100">{i.title}</div>
                        <div className="mt-1 flex items-center gap-2 text-[11.5px] text-slate-400">
                          <IssueStatusChip status={i.status} />
                          {i.asset_name && <span className="truncate">{i.asset_name}</span>}
                        </div>
                      </div>
                    )
                    // Other people's reports are visible as lab state, but only
                    // staff and the reporter can open them.
                    return <li key={i.id}>{staff || i.is_mine
                      ? <Link to={`/issues/${i.id}`} className="block hover:bg-ink-700/20 -mx-2 px-2 rounded-lg">{body}</Link>
                      : body}</li>
                  })}
                </ul>
              )}
            </div>
          </section>

          {/* --------------------------------------------------- equipment */}
          <section>
            <SectionTitle icon={<Boxes size={15} />}>Equipment <span className="text-slate-500 font-normal">({assets.length})</span></SectionTitle>
            <div className="card divide-y divide-ink-700/60 max-h-80 overflow-y-auto">
              {assets.length === 0 ? <EmptyState compact icon={<Boxes size={18} />} title="No equipment registered" />
                : assets.map(a => (
                  <Link key={a.id} to={`/equipment/${a.id}`}
                        className="px-4 py-3 flex items-center gap-3 hover:bg-ink-700/30">
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] text-slate-100 truncate">{a.name}</div>
                      <div className="mono !text-[11px] text-slate-400">{a.asset_tag} · {a.category}</div>
                    </div>
                    {a.open_issues > 0 && (
                      <span className="flex items-center gap-1 text-[11.5px] text-warn-soft">
                        <TriangleAlert size={12} />{a.open_issues}</span>
                    )}
                    <Chip tone={assetTone(a.status)}>{assetStatusLabel(a.status)}</Chip>
                  </Link>
                ))}
            </div>
          </section>

          {/* ------------------------------------------------- environment */}
          <section>
            <SectionTitle icon={<Gauge size={15} />}
              sub="Real sensor readings only - nothing is estimated.">Environment</SectionTitle>
            <div className="card p-4">
              <div className="grid grid-cols-2 gap-2">
                {[
                  [<Thermometer key="t" size={14} />, 'Temperature'], [<Droplets key="h" size={14} />, 'Humidity'],
                  [<Wind key="c" size={14} />, 'CO₂'], [<Wind key="v" size={14} />, 'TVOC'],
                  [<Zap key="e" size={14} />, 'Energy'],
                ].map(([icon, label]) => (
                  <div key={label as string} className="well px-3 py-2.5">
                    <div className="flex items-center gap-1.5 text-[11.5px] text-slate-400">{icon}{label}</div>
                    <div className="mt-1 text-[12.5px] text-slate-500">No live sensor data</div>
                  </div>
                ))}
                <div className="well px-3 py-2.5">
                  <div className="flex items-center gap-1.5 text-[11.5px] text-slate-400"><Users size={14} />Occupancy</div>
                  <div className="mt-1 text-[13px] text-white tnum">
                    {lab.has_controller ? `${status.occupants} / ${lab.capacity}` : 'No door data'}
                  </div>
                </div>
              </div>
              <p className="mt-3 text-[11.5px] text-slate-400 leading-relaxed">
                {sensors && sensors.length > 0 ? `${sensors.length} readings recorded.`
                  : 'No environmental sensor node reports for this laboratory yet. Readings appear here once one is deployed.'}
                {' '}Occupancy comes from door sessions.
              </p>
            </div>
          </section>

          {status.next_booking_at && (
            <p className="text-[12px] text-slate-400">Next confirmed booking {fmtDateTime(status.next_booking_at)}.</p>
          )}
        </div>
      </div>
    </div>
  )
}

function Node({ icon, title, state, labels, device, note, stale, neutral }: {
  icon: React.ReactNode; title: string; state: boolean | null
  labels: [string, string]; device?: Device; note?: string
  /** Both values are normal (e.g. occupancy): "false" is not a fault colour. */
  neutral?: boolean
  /** Set when the value is a last report from a controller now offline. */
  stale?: string
}) {
  return (
    <div className="well p-3.5">
      <div className="flex items-center gap-2 text-slate-300 text-[12.5px]">
        <span className="text-accent-300">{icon}</span>{title}
      </div>
      <div className="mt-2">
        {stale && state !== null ? (
          <span className="inline-flex items-center gap-2 text-sm text-slate-400">
            <Dot tone="idle" />{state ? labels[0] : labels[1]}
            <span className="text-[11px] text-slate-500">(last reported)</span>
          </span>
        ) : neutral && state === false ? (
          <span className="inline-flex items-center gap-2 text-sm text-slate-300">
            <Dot tone="idle" />{labels[1]}</span>
        ) : <StateDot state={state} labels={labels} unknown="Not reported" />}
      </div>
      {stale && state !== null && <div className="text-[11px] text-slate-500 mt-1 truncate">{stale}</div>}
      {device && (
        <div className="mono !text-[11px] text-slate-400 mt-1 truncate">
          {device.last_seen_at ? `heartbeat ${relative(device.last_seen_at)}` : 'never reported'}
        </div>
      )}
      {note && <div className="text-[11px] text-slate-500 mt-1 truncate">{note}</div>}
    </div>
  )
}
