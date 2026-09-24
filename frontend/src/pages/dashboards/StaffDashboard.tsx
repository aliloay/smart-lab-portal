import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell, CalendarClock, Cpu, DoorOpen, FlaskConical, ShieldCheck, ShieldX, Wrench,
} from 'lucide-react'
import { LabOverview, Summary, api } from '../../lib/api'
import { firstName, useAuth } from '../../lib/auth'
import { useLiveMessages } from '../../lib/live'
import { fmtDateLong, greeting } from '../../lib/time'
import { CardsSkeleton, Dot, EmptyState, MetricCard, SectionTitle } from '../../components/ui'
import { Bloom, GridField, NodeField } from '../../components/visual'
import { DeviceHealth, LiveActivity, MaintenanceQueue, TodaySchedule } from './widgets'

/** Staff: "what is happening, what needs me, what next" - for today. */
export default function StaffDashboard() {
  const { user } = useAuth()
  const [s, setS] = useState<Summary | null>(null)
  const [labs, setLabs] = useState<LabOverview[]>([])

  const load = useCallback(() => {
    api.summary().then(setS).catch(() => {})
    api.labsOverview().then(setLabs).catch(() => {})
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 30000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => { if (m.type === 'access_event' || m.type === 'staff') load() })

  const active = labs.filter(l => l.occupied)

  return (
    <div className="space-y-7">
      <section className="relative card overflow-hidden">
        <GridField />
        <Bloom tone="teal" />
        <NodeField className="absolute right-0 top-0 h-full w-1/2 opacity-50 fade-l" />
        <div className="relative p-6 sm:p-7 flex flex-wrap items-end justify-between gap-6">
          <div>
            <div className="eyebrow">Laboratory operations</div>
            <h1 className="mt-2 page-title">{greeting()}, {firstName(user?.full_name)}</h1>
            <p className="page-sub">{fmtDateLong(new Date().toISOString())}</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Link to="/admin/bookings" className="btn-ghost"><CalendarClock size={16} />Reservations</Link>
            <Link to="/admin/access" className="btn-ghost"><ShieldCheck size={16} />Access monitor</Link>
            <Link to="/issues" className="btn-primary"><Wrench size={16} />Maintenance</Link>
          </div>
        </div>
      </section>

      {!s ? <CardsSkeleton count={6} /> : (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
          <MetricCard label="Pending bookings" value={s.pending_bookings} to="/admin/bookings"
                      icon={<CalendarClock size={16} />} tone={s.pending_bookings ? 'warn' : 'idle'}
                      hint={s.pending_bookings ? 'Awaiting a decision' : 'Nothing to approve'} />
          <MetricCard label="People inside" value={s.people_inside} icon={<DoorOpen size={16} />}
                      info="Open occupancy sessions: granted entry, no exit or window end yet."
                      hint={`${s.occupied_labs} lab${s.occupied_labs === 1 ? '' : 's'} in use`} />
          <MetricCard label="Denied today" value={s.denied_today} to="/admin/access"
                      icon={<ShieldX size={16} />} tone={s.denied_today ? 'bad' : 'idle'}
                      hint={`${s.granted_today} granted`} />
          <MetricCard label="Open issues" value={s.open_issues} to="/issues"
                      icon={<Wrench size={16} />}
                      tone={s.critical_issues ? 'bad' : s.open_issues ? 'warn' : 'idle'}
                      hint={s.critical_issues ? `${s.critical_issues} critical` : `${s.unassigned_issues} unassigned`} />
          <MetricCard label="Open alerts" value={s.open_alerts} to="/admin/alerts"
                      icon={<Bell size={16} />} tone={s.open_alerts ? 'warn' : 'idle'} />
          <MetricCard label="Access controllers online" animate={false}
                      value={s.devices_total ? `${s.devices_online}/${s.devices_total}` : null}
                      icon={<Cpu size={16} />} to="/admin/devices"
                      info="ESP32-based laboratory access devices currently connected to the portal."
                      tone={!s.devices_total ? 'idle' : s.devices_online === s.devices_total ? 'ok' : 'warn'} />
        </div>
      )}

      <div className="grid xl:grid-cols-2 gap-6">
        <TodaySchedule />
        <MaintenanceQueue />
      </div>

      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2"><LiveActivity /></div>
        <div className="space-y-6">
          <section>
            <SectionTitle icon={<FlaskConical size={15} />}
              action={<Link to="/labs" className="text-xs link">All labs</Link>}>
              Active laboratories
            </SectionTitle>
            <div className="card divide-y divide-ink-700/60">
              {active.length === 0 ? (
                <EmptyState compact icon={<FlaskConical size={18} />} title="No laboratory in use"
                            detail="Labs appear here while a booking runs or someone is inside." />
              ) : active.map(o => (
                <Link key={o.lab.id} to={`/labs/${o.lab.id}`}
                      className="flex items-center gap-3 px-4 py-3 hover:bg-ink-700/30">
                  <Dot tone="warn" live />
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-slate-100 truncate">{o.lab.name}</div>
                    <div className="mono !text-[11px] text-slate-400">{o.lab.code}</div>
                  </div>
                  <span className="text-[12px] text-slate-300">
                    {o.occupants ? `${o.occupants} inside` : 'Booked now'}
                  </span>
                </Link>
              ))}
            </div>
          </section>
          <DeviceHealth />
        </div>
      </div>
    </div>
  )
}
