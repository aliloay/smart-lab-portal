import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity, Bell, CalendarRange, CheckCircle2, Cpu, FlaskConical, ShieldX,
  Users,
} from 'lucide-react'
import { AccessEvent, Device, Lab, Summary, api } from '../lib/api'
import { fmtClock, relative } from '../lib/time'
import {
  Chip, Dot, EmptyState, MetricCard, SectionTitle, SkeletonCards, StateDot,
  eventTone,
} from '../components/ui'
import { Bloom, GridField, NodeField } from '../components/visual'

export default function AdminOverview() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [events, setEvents] = useState<AccessEvent[]>([])
  const [devices, setDevices] = useState<Device[]>([])
  const [labs, setLabs] = useState<Lab[]>([])
  const [live, setLive] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const load = () => {
      api.summary().then(setSummary).catch(() => {})
      api.devices().then(setDevices).catch(() => {})
    }
    load()
    api.events({ limit: 60 }).then(setEvents).catch(() => {})
    api.labs().then(setLabs).catch(() => {})
    // Counters are recomputed from the database rather than incremented in
    // the browser, so a dropped socket frame can never skew them.
    const t = setInterval(load, 20000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/activity`)
    wsRef.current = ws
    ws.onopen = () => setLive(true)
    ws.onclose = () => setLive(false)
    ws.onerror = () => setLive(false)
    ws.onmessage = m => {
      try { setEvents(p => [JSON.parse(m.data) as AccessEvent, ...p].slice(0, 140)) }
      catch { /* ignore */ }
    }
    const ka = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)
    return () => { clearInterval(ka); ws.close() }
  }, [])

  const labCode = (id: number | null) => labs.find(l => l.id === id)?.code ?? '—'

  return (
    <div className="space-y-7">
      <section className="relative card overflow-hidden">
        <GridField />
        <Bloom />
        <NodeField className="absolute inset-0 w-full h-full opacity-40" />
        <div className="relative p-6 flex items-end justify-between gap-6 flex-wrap">
          <div>
            <div className="label">Operations</div>
            <h1 className="mt-1.5 text-[24px] font-semibold text-white tracking-tight">
              System overview
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Live state across every laboratory.
            </p>
          </div>
          <span className="flex items-center gap-2 px-3 py-1.5 rounded-lg
                           bg-ink-800/80 border border-ink-600 text-[11px] text-slate-400">
            <Dot tone={live ? 'ok' : 'idle'} live={live} />
            {live ? 'Live stream connected' : 'Reconnecting'}
          </span>
        </div>
      </section>

      {!summary ? <SkeletonCards /> : (
        <>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="Laboratories" value={summary.total_labs}
                        icon={<FlaskConical size={15} />}
                        hint={`${summary.occupied_labs} occupied now`} />
            <MetricCard label="Active bookings" value={summary.active_bookings}
                        icon={<CalendarRange size={15} />}
                        tone={summary.active_bookings ? 'info' : 'idle'}
                        hint={`${summary.upcoming_bookings} upcoming`} />
            <MetricCard label="Granted today" value={summary.granted_today}
                        icon={<CheckCircle2 size={15} />} tone="ok" />
            <MetricCard label="Denied today" value={summary.denied_today}
                        icon={<ShieldX size={15} />}
                        tone={summary.denied_today > 0 ? 'bad' : 'idle'}
                        hint={summary.denied_today > 0
                          ? 'Review the access events' : 'No refusals'} />
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="Devices online" animate={false}
                        value={`${summary.devices_online}/${summary.devices_total}`}
                        icon={<Cpu size={15} />}
                        tone={summary.devices_total === 0 ? 'idle'
                          : summary.devices_online === summary.devices_total
                            ? 'ok' : 'warn'} />
            <MetricCard label="Open alerts" value={summary.open_alerts}
                        icon={<Bell size={15} />}
                        tone={summary.open_alerts > 0 ? 'warn' : 'idle'} />
          </div>
        </>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <SectionTitle icon={<Activity size={14} />}
            action={<Link to="/admin/access-events"
              className="text-xs text-accent-400 hover:text-accent-300">
              All events
            </Link>}>
            Live access activity
          </SectionTitle>

          <div className="card max-h-[580px] overflow-y-auto">
            {events.length === 0 ? (
              <EmptyState icon={<Activity size={20} />}
                title="No events recorded yet"
                detail="Bookings, scans and door activity stream in here as they happen." />
            ) : (
              <ol className="divide-y divide-ink-700/60">
                {events.map((e, i) => (
                  <motion.li key={`${e.id}-${i}`}
                    initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: .22 }}
                    className="px-5 py-3 flex items-start gap-3">
                    <span className="mono text-slate-600 pt-0.5 shrink-0 tnum">
                      {fmtClock(e.created_at)}
                    </span>
                    <span className="mono text-slate-600 pt-0.5 shrink-0 w-14">
                      {e.lab_code ?? labCode(e.lab_id)}
                    </span>
                    <Chip tone={eventTone(e.event_type)}>
                      {e.event_type.replace(/_/g, ' ')}
                    </Chip>
                    <span className="flex-1 min-w-0 truncate text-xs text-slate-400">
                      {e.message}
                    </span>
                  </motion.li>
                ))}
              </ol>
            )}
          </div>
        </div>

        <div>
          <SectionTitle icon={<Cpu size={14} />}
            action={<Link to="/admin/devices"
              className="text-xs text-accent-400 hover:text-accent-300">All</Link>}>
            Devices
          </SectionTitle>
          <div className="card divide-y divide-ink-700/60">
            {devices.length === 0 ? (
              <EmptyState icon={<Cpu size={18} />} title="No devices registered" />
            ) : devices.slice(0, 8).map(d => (
              <div key={d.id} className="px-5 py-3.5">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[13px] text-slate-200 truncate">{d.name}</div>
                    <div className="mono text-slate-600">{d.device_uid}</div>
                  </div>
                  <StateDot state={d.last_seen_at === null ? null : d.is_online}
                            labels={['Online', 'Offline']} />
                </div>
                <div className="mt-1.5 mono text-slate-600">
                  {d.ip_address ?? 'no address'}
                  {d.last_seen_at ? ` · seen ${relative(d.last_seen_at)}`
                                  : ' · never reported'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
