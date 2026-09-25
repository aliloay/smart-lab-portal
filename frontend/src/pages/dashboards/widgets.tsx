/**
 * Operational panels shared by the staff and admin dashboards. Each loads its
 * own data over REST and stays fresh from the live stream.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, CalendarClock, Cpu, DoorOpen, ShieldAlert, Wrench,
} from 'lucide-react'
import { AccessEvent, Booking, Device, Issue, IssueSummary, api } from '../../lib/api'
import { useLive, useLiveMessages } from '../../lib/live'
import { denialShort, eventLabel, eventTone } from '../../lib/labels'
import { fmtClock, fmtTime, relative } from '../../lib/time'
import {
  Chip, Dot, EmptyState, IssueStatusChip, SectionTitle, SeverityBadge, Skeleton,
} from '../../components/ui'

// ---------------------------------------------------------------------------
export function LiveActivity({ limit = 40, securityOnly = false, title = 'Live access activity',
                               height = 'max-h-[520px]' }: {
  limit?: number; securityOnly?: boolean; title?: string; height?: string
}) {
  const { connected } = useLive()
  const [events, setEvents] = useState<AccessEvent[] | null>(null)
  const [fresh, setFresh] = useState<Set<number>>(new Set())

  useEffect(() => {
    api.events({ limit, security_only: securityOnly || undefined })
      .then(setEvents).catch(() => setEvents([]))
  }, [limit, securityOnly])

  useLiveMessages(m => {
    if (m.type !== 'access_event') return
    const ev = m.event
    if (securityOnly && eventTone(ev.event_type) !== 'bad') return
    setEvents(p => [ev, ...(p ?? []).filter(x => x.id !== ev.id)].slice(0, limit))
    setFresh(s => new Set(s).add(ev.id))
    window.setTimeout(() => setFresh(s => { const n = new Set(s); n.delete(ev.id); return n }), 2500)
  })

  return (
    <section>
      <SectionTitle icon={securityOnly ? <ShieldAlert size={15} /> : <Activity size={15} />}
        action={<span className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-[12px] text-slate-400">
            <Dot tone={connected ? 'ok' : 'idle'} live={connected} />
            {connected ? 'Live' : 'Reconnecting'}
          </span>
          <Link to="/admin/access" className="text-xs link">Access monitor</Link>
        </span>}>
        {title}
      </SectionTitle>
      <div className={`card overflow-y-auto ${height}`}>
        {events === null ? (
          <div className="p-4 space-y-2">{[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-10" />)}</div>
        ) : events.length === 0 ? (
          <EmptyState icon={<Activity size={20} />}
            title={securityOnly ? 'No security events' : 'No events recorded yet'}
            detail={securityOnly ? 'Refused scans, mismatches and unknown cards appear here.'
              : 'Bookings, scans and door activity stream in here as they happen.'} />
        ) : (
          <ol className="divide-y divide-ink-700/60">
            {events.map(e => (
              <li key={e.id}
                  className={`px-4 py-2.5 flex items-center gap-3 transition-colors duration-700
                              ${fresh.has(e.id) ? 'bg-accent-500/10' : ''}`}>
                <span className="mono text-slate-400 shrink-0 tnum w-[62px]">{fmtClock(e.created_at)}</span>
                <span className="mono text-slate-400 shrink-0 w-14 hidden sm:block">{e.lab_code ?? '—'}</span>
                <Chip tone={eventTone(e.event_type)}>{eventLabel(e.event_type)}</Chip>
                <span className="flex-1 min-w-0 truncate text-[12.5px] text-slate-300">
                  {e.user_name && <span className="text-slate-100">{e.user_name}</span>}
                  {e.reason && <span className="text-bad-soft"> · {denialShort(e.reason)}</span>}
                  {!e.user_name && !e.reason && e.message}
                </span>
                {e.booking_id && (
                  <Link to={`/bookings/${e.booking_id}`} className="text-[11px] link shrink-0 hidden md:block">
                    trace
                  </Link>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
export function DeviceHealth() {
  const [devices, setDevices] = useState<Device[] | null>(null)
  const load = useCallback(() => api.devices().then(setDevices).catch(() => setDevices([])), [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 20000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => {
    if (m.type === 'access_event' && m.event.event_type.startsWith('DEVICE')) load()
  })

  return (
    <section>
      <SectionTitle icon={<Cpu size={15} />}
        action={<Link to="/admin/devices" className="text-xs link">All devices</Link>}>
        Device health
      </SectionTitle>
      <div className="card divide-y divide-ink-700/60">
        {devices === null ? <div className="p-4"><Skeleton className="h-24" /></div>
          : devices.length === 0 ? <EmptyState icon={<Cpu size={18} />} title="No devices registered" compact />
          : devices.slice(0, 6).map(d => (
            <div key={d.id} className="px-4 py-3 flex items-center gap-3">
              <Dot tone={d.state === 'ONLINE' ? 'ok' : d.state === 'OFFLINE' ? 'bad' : 'idle'}
                   live={d.state === 'ONLINE'} />
              <div className="min-w-0 flex-1">
                <div className="text-[13px] text-slate-100 truncate">{d.name}</div>
                <div className="mono !text-[11px] text-slate-400">{d.lab_code} · {d.device_uid}</div>
              </div>
              <div className="text-right text-[12px]">
                <div className={d.state === 'ONLINE' ? 'text-ok-soft' : d.state === 'OFFLINE'
                  ? 'text-bad-soft' : 'text-slate-400'}>
                  {d.state === 'NO_DATA' ? 'No data' : d.state === 'ONLINE' ? 'Online' : 'Offline'}
                </div>
                <div className="text-slate-500 text-[11px]">
                  {d.last_seen_at ? relative(d.last_seen_at) : 'never reported'}
                </div>
              </div>
            </div>
          ))}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
const SEV_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 } as const

export function MaintenanceQueue({ title = 'Maintenance queue', stats = false }: {
  title?: string
  /** Administrators also get the statistics row. */
  stats?: boolean
}) {
  const [summary, setSummary] = useState<IssueSummary | null>(null)
  const [queue, setQueue] = useState<Issue[] | null>(null)
  const load = useCallback(() => {
    api.issueSummary().then(setSummary).catch(() => {})
    api.issues({ active: true, limit: 50 }).then(r => setQueue(
      [...r].sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]
        || +new Date(a.created_at) - +new Date(b.created_at)))).catch(() => setQueue([]))
  }, [])
  useEffect(() => { load() }, [load])
  useLiveMessages(m => { if (m.type === 'staff' && m.kind === 'issue') load() })

  const tiles: [string, number | undefined, string, string][] = [
    ['Critical', summary?.critical, 'text-bad-soft', '/issues?severity=CRITICAL'],
    ['High', summary?.high, 'text-warn-soft', '/issues?severity=HIGH'],
    ['Unassigned', summary?.unassigned, 'text-accent-200', '/issues?assigned=unassigned'],
    ['In progress', summary?.in_progress, 'text-violet-300', '/issues'],
    ['Waiting parts', summary?.waiting_for_parts, 'text-warn-soft', '/issues'],
    ['Overdue', summary?.overdue, summary?.overdue ? 'text-bad-soft' : 'text-slate-200', '/issues?overdue=1'],
  ]
  return (
    <section>
      <SectionTitle icon={<Wrench size={15} />}
        sub={summary ? `${summary.open} open · ${summary.resolved_this_month} resolved this month` : undefined}
        action={<Link to="/issues" className="text-xs link">Open queue</Link>}>
        {title}
      </SectionTitle>
      <div className="card p-4">
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {tiles.map(([k, v, c, to]) => (
            <Link key={k} to={to} className="well py-2.5 text-center hover:border-ink-500 transition-colors">
              <div className={`font-display text-xl tnum ${c}`}>{v ?? '–'}</div>
              <div className="text-[10.5px] text-slate-400 mt-0.5">{k}</div>
            </Link>
          ))}
        </div>
        {stats && summary && (
          <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-2 text-[12px]">
            {[
              ['Resolved this month', String(summary.resolved_this_month)],
              ['Avg resolution', summary.avg_resolution_hours != null ? `${summary.avg_resolution_hours} h` : 'No data yet'],
              ['Most issues (lab)', summary.by_lab[0] ? `${summary.by_lab[0].label} · ${summary.by_lab[0].count}` : '—'],
              ['Top category', summary.by_category[0] ? `${summary.by_category[0].label} · ${summary.by_category[0].count}` : '—'],
              ['Most reported item', summary.by_asset[0] ? `${summary.by_asset[0].label} · ${summary.by_asset[0].count}` : '—'],
            ].map(([k, v]) => (
              <div key={k} className="well px-3 py-2 min-w-0">
                <div className="text-slate-400 text-[10.5px] uppercase tracking-wide">{k}</div>
                <div className="text-slate-100 truncate" title={v}>{v}</div>
              </div>
            ))}
          </div>
        )}
        {queue === null ? <Skeleton className="h-28 mt-3" /> : queue.length === 0 ? (
          <p className="mt-4 text-[13px] text-slate-400 text-center py-3">
            No open maintenance issues.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-ink-700/60">
            {queue.slice(0, 5).map(i => (
              <li key={i.id}>
                <Link to={`/issues/${i.id}`} className="flex items-center gap-3 py-2.5 group">
                  <SeverityBadge severity={i.severity} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-slate-100 truncate group-hover:text-white">{i.title}</div>
                    <div className="text-[11.5px] text-slate-400 truncate">
                      <span className="mono !text-[11px]">{i.ticket_number}</span> · {i.lab_code}
                      {i.asset_name && ` · ${i.asset_name}`}
                      {i.is_overdue && <span className="text-bad-soft"> · overdue</span>}
                    </div>
                  </div>
                  <IssueStatusChip status={i.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
export function TodaySchedule() {
  const [rows, setRows] = useState<Booking[] | null>(null)
  const load = useCallback(() => {
    const s = new Date(); s.setHours(0, 0, 0, 0)
    const e = new Date(s); e.setDate(e.getDate() + 1)
    api.bookings({ from: s.toISOString(), to: e.toISOString() })
      .then(r => setRows(r.filter(b => b.status === 'CONFIRMED' || b.status === 'PENDING')
        .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time))))
      .catch(() => setRows([]))
  }, [])
  useEffect(() => { load() }, [load])
  useLiveMessages(m => {
    if (m.type === 'access_event' && (m.event.event_type.startsWith('BOOKING')
        || m.event.event_type === 'ACCESS_GRANTED')) load()
  })
  const now = Date.now()

  return (
    <section>
      <SectionTitle icon={<CalendarClock size={15} />}
        sub={rows ? `${rows.length} reservation${rows.length === 1 ? '' : 's'} today` : undefined}
        action={<Link to="/admin/bookings" className="text-xs link">Reservations</Link>}>
        Today's schedule
      </SectionTitle>
      <div className="card overflow-hidden">
        {rows === null ? <div className="p-4"><Skeleton className="h-24" /></div>
          : rows.length === 0 ? <EmptyState icon={<CalendarClock size={18} />} compact
              title="Nothing booked today" />
          : (
            <ul className="divide-y divide-ink-700/60 max-h-[360px] overflow-y-auto">
              {rows.map(b => {
                const s = new Date(b.start_time).getTime(), e = new Date(b.end_time).getTime()
                const phase = now > e ? 'done' : now >= s ? 'now' : 'later'
                return (
                  <li key={b.id}>
                    <Link to={`/bookings/${b.id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-ink-700/30">
                      <div className="w-[92px] shrink-0 mono text-slate-300 tnum">
                        {fmtTime(b.start_time)}–{fmtTime(b.end_time)}
                      </div>
                      <Dot tone={phase === 'now' ? 'ok' : phase === 'later' ? 'info' : 'idle'}
                           live={phase === 'now'} />
                      <div className="min-w-0 flex-1">
                        <div className="text-[13px] text-slate-100 truncate">{b.user_name}</div>
                        <div className="text-[11.5px] text-slate-400 truncate">{b.lab_code} · {b.lab_name}</div>
                      </div>
                      {b.status === 'PENDING' ? <Chip tone="warn">pending</Chip>
                        : b.first_entry_at ? (
                          <span className="flex items-center gap-1 text-[11.5px] text-ok-soft">
                            <DoorOpen size={12} />{fmtTime(b.first_entry_at)}
                          </span>
                        ) : phase === 'done' ? <span className="text-[11.5px] text-slate-500">no entry</span>
                        : null}
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
      </div>
    </section>
  )
}
