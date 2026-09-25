import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, BarChart3, Bell, Boxes, CalendarRange, CheckCircle2, Cpu, DoorOpen,
  FlaskConical, Network, PlayCircle, ShieldX, Users, Wrench,
} from 'lucide-react'
import { Alert, LabOverview, Summary, SystemStatus, api } from '../../lib/api'
import { useLive, useLiveMessages } from '../../lib/live'
import { fmtDateLong, relative } from '../../lib/time'
import {
  CardsSkeleton, Chip, Dot, EmptyState, MetricCard, ProgressBar, SectionTitle, Skeleton,
} from '../../components/ui'
import { Bloom, GridField, LabNetworkMap } from '../../components/visual'
import { DeviceHealth, LiveActivity, MaintenanceQueue } from './widgets'

type Day = { day: string; granted: number; denied: number }

export default function AdminDashboard() {
  const { connected } = useLive()
  const [s, setS] = useState<Summary | null>(null)
  const [labs, setLabs] = useState<LabOverview[] | null>(null)
  const [sys, setSys] = useState<SystemStatus | null>(null)
  const [week, setWeek] = useState<Day[] | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])

  const load = useCallback(() => {
    api.summary().then(setS).catch(() => {})
    api.labsOverview().then(setLabs).catch(() => setLabs([]))
    api.systemStatus().then(setSys).catch(() => {})
    api.alerts(true).then(setAlerts).catch(() => {})
    api.accessReport(7).then(rows => {
      const m = new Map<string, Day>()
      rows.forEach(r => {
        const d = m.get(r.day) ?? { day: r.day, granted: 0, denied: 0 }
        if (r.event === 'ACCESS_GRANTED') d.granted += r.count
        else d.denied += r.count
        m.set(r.day, d)
      })
      setWeek([...m.values()].sort((a, b) => a.day.localeCompare(b.day)))
    }).catch(() => setWeek([]))
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 30000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => { if (m.type === 'access_event' || m.type === 'staff') load() })

  const nodes = useMemo(() => (labs ?? []).map(o => ({
    id: o.lab.id, code: o.lab.code, name: o.lab.name, hasHardware: o.lab.has_controller,
    online: o.lab.has_controller ? o.controller_online : null,
    occupied: o.occupied, issues: o.open_issues,
  })), [labs])

  const healthy = sys?.database === true

  return (
    <div className="space-y-7">
      {/* ------------------------------------------------------- overview */}
      <section className="relative card overflow-hidden">
        <GridField />
        <Bloom />
        <div className="relative grid lg:grid-cols-[1fr_1.35fr] gap-2">
          <div className="p-6 sm:p-7 flex flex-col">
            <div className="eyebrow">Smart laboratory overview</div>
            <h1 className="mt-2 page-title">System overview</h1>
            <p className="page-sub">{fmtDateLong(new Date().toISOString())} · live state across
              every laboratory, device and credential.</p>

            <div className="mt-6 grid grid-cols-2 gap-2.5">
              {[
                ['System', sys ? (healthy ? 'Healthy' : 'Degraded') : 'Checking',
                  sys ? (healthy ? 'ok' : 'bad') : 'idle'],
                ['Live stream', connected ? 'Connected' : 'Reconnecting', connected ? 'ok' : 'warn'],
                ['Controllers', sys ? (sys.controllers_total
                  ? `${sys.controllers_online} / ${sys.controllers_total} online` : 'None registered') : '…',
                  !sys || sys.devices_reporting === 0 ? 'idle'
                    : sys.controllers_online === sys.controllers_total ? 'ok' : 'warn'],
                ['Last heartbeat', sys?.last_heartbeat_at ? relative(sys.last_heartbeat_at) : 'No data',
                  sys?.last_heartbeat_at ? 'info' : 'idle'],
              ].map(([k, v, t]) => (
                <div key={k} className="well px-3.5 py-3">
                  <div className="label !text-[10px]">{k}</div>
                  <div className="mt-1 flex items-center gap-2 text-[13.5px] text-slate-100">
                    <Dot tone={t as 'ok'} live={t === 'ok'} />{v}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-auto pt-5 flex gap-2 flex-wrap">
              <Link to="/admin/reports" className="btn-primary btn-sm"><BarChart3 size={15} />Reports</Link>
              <Link to="/admin/access" className="btn-ghost btn-sm"><Activity size={15} />Access & audit</Link>
              <Link to="/demo" className="btn-quiet btn-sm"><PlayCircle size={15} />Simulation</Link>
            </div>
          </div>
          <div className="relative px-4 pb-4 lg:py-4">
            <div className="flex items-center justify-between px-2 pt-2 lg:pt-0">
              <span className="label flex items-center gap-2"><Network size={13} />Laboratory network</span>
              <span className="flex gap-3 text-[11px] text-slate-400">
                <span className="flex items-center gap-1.5"><Dot tone="ok" />Controller online</span>
                <span className="flex items-center gap-1.5"><Dot tone="bad" />Offline</span>
                <span className="flex items-center gap-1.5"><Dot tone="idle" />No hardware</span>
                <span className="flex items-center gap-1.5"><Dot tone="warn" />Issues</span>
              </span>
            </div>
            {labs === null ? <Skeleton className="h-[300px] mt-3" />
              : <LabNetworkMap nodes={nodes} className="w-full h-auto" />}
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------- metrics */}
      {!s ? <CardsSkeleton count={8} /> : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="Laboratories" value={s.total_labs} icon={<FlaskConical size={16} />}
                      to="/labs" hint={`${s.labs_with_hardware} with access hardware · ${s.occupied_labs} in use`} />
          <MetricCard label="Active users" value={s.active_users} icon={<Users size={16} />}
                      to="/admin/users" hint={`${s.people_inside} inside a lab now`} />
          <MetricCard label="Bookings today" value={s.bookings_today} icon={<CalendarRange size={16} />}
                      to="/admin/bookings" tone={s.active_bookings ? 'info' : 'idle'}
                      hint={`${s.active_bookings} active · ${s.upcoming_bookings} upcoming · ${s.pending_bookings} pending`} />
          <MetricCard label="Access controllers online" animate={false}
                      value={s.devices_total ? `${s.devices_online}/${s.devices_total}` : null}
                      icon={<Cpu size={16} />} to="/admin/devices"
                      info="ESP32-based laboratory access devices currently connected to the portal."
                      tone={!s.devices_total ? 'idle' : s.devices_online === s.devices_total ? 'ok' : 'warn'} />
          <MetricCard label="Granted today" value={s.granted_today} icon={<CheckCircle2 size={16} />}
                      tone={s.granted_today ? 'ok' : 'idle'} to="/admin/access" />
          <MetricCard label="Security events today" value={s.security_events_today}
                      icon={<ShieldX size={16} />} tone={s.security_events_today ? 'bad' : 'idle'}
                      to="/admin/access"
                      info="Refused scans, identity mismatches, unknown cards and failed biometrics."
                      hint={`${s.denied_today} denied at the door`} />
          <MetricCard label="Open issues" value={s.open_issues} icon={<Wrench size={16} />} to="/issues"
                      tone={s.critical_issues ? 'bad' : s.open_issues ? 'warn' : 'idle'}
                      hint={`${s.critical_issues} critical · ${s.overdue_issues} overdue`} />
          <MetricCard label="Open alerts" value={s.open_alerts} icon={<Bell size={16} />}
                      to="/admin/alerts" tone={s.open_alerts ? 'warn' : 'idle'} />
        </div>
      )}

      {/* ------------------------------------------ access + asset status */}
      <div className="grid xl:grid-cols-3 gap-6">
        <section className="xl:col-span-2">
          <SectionTitle icon={<BarChart3 size={15} />} sub="Door outcomes over the last 7 days"
            action={<Link to="/admin/reports" className="text-xs link">Full reports</Link>}>
            Access statistics
          </SectionTitle>
          <div className="card p-5">
            {week === null ? <Skeleton className="h-40" />
              : week.length === 0 ? (
                <EmptyState compact icon={<BarChart3 size={18} />} title="Not enough data yet"
                  detail="The chart fills in as the door records granted and denied entries." />
              ) : <WeekBars days={week} />}
          </div>
        </section>
        <section>
          <SectionTitle icon={<Boxes size={15} />}
            action={<Link to="/admin/equipment" className="text-xs link">Equipment</Link>}>
            Asset status
          </SectionTitle>
          <div className="card p-5 space-y-4">
            {!s ? <Skeleton className="h-32" /> : s.assets_total === 0 ? (
              <EmptyState compact title="No equipment registered" />
            ) : (
              <>
                {[
                  ['Available', s.assets_total - s.assets_checked_out - s.assets_in_maintenance, 'ok'],
                  ['Checked out', s.assets_checked_out, 'info'],
                  ['In maintenance', s.assets_in_maintenance, 'warn'],
                ].map(([k, v, t]) => (
                  <div key={k as string}>
                    <div className="flex justify-between text-[13px] mb-1.5">
                      <span className="text-slate-300">{k}</span>
                      <span className="text-white tnum">{v} <span className="text-slate-500">/ {s.assets_total}</span></span>
                    </div>
                    <ProgressBar value={(v as number) / s.assets_total} tone={t as 'ok'} />
                  </div>
                ))}
              </>
            )}
          </div>
        </section>
      </div>

      <div className="grid xl:grid-cols-2 gap-6">
        <LiveActivity securityOnly title="Security events" height="max-h-[380px]" limit={30} />
        <MaintenanceQueue title="Laboratory maintenance" stats />
      </div>

      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2"><LiveActivity title="Live activity" limit={40} /></div>
        <div className="space-y-6">
          <section>
            <SectionTitle icon={<Bell size={15} />}
              action={<Link to="/admin/alerts" className="text-xs link">All alerts</Link>}>
              Open alerts
            </SectionTitle>
            <div className="card divide-y divide-ink-700/60">
              {alerts.length === 0 ? (
                <EmptyState compact icon={<Bell size={18} />} title="No open alerts"
                            detail="Device outages and other operational warnings appear here." />
              ) : alerts.slice(0, 5).map(a => (
                <div key={a.id} className="px-4 py-3 flex items-start gap-3">
                  <Chip tone={a.severity === 'CRITICAL' ? 'bad' : a.severity === 'WARNING' ? 'warn' : 'info'}>
                    {a.severity.toLowerCase()}</Chip>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-slate-100">{a.title}</div>
                    <div className="text-[11.5px] text-slate-400">{a.lab_code ?? 'System'} · {relative(a.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>
          <DeviceHealth />
          <Link to="/admin/reports" className="card card-hover p-5 flex items-center gap-4">
            <span className="grid place-items-center w-11 h-11 rounded-xl bg-violet-500/15
                             border border-violet-500/30 text-violet-300"><DoorOpen size={18} /></span>
            <div className="flex-1">
              <div className="text-[14px] text-white font-medium">Utilisation & traceability reports</div>
              <div className="text-[12.5px] text-slate-400">Bookings vs actual entries, busiest hours, denials</div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  )
}

/** Tiny dependency-free bar chart; the full charts live on the reports page. */
function WeekBars({ days }: { days: Day[] }) {
  const max = Math.max(1, ...days.map(d => d.granted + d.denied))
  const totals = days.reduce((a, d) => ({ g: a.g + d.granted, d: a.d + d.denied }), { g: 0, d: 0 })
  return (
    <div>
      <div className="flex gap-6 mb-4 text-[13px]">
        <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-sm bg-ok" />
          Granted <b className="text-white tnum">{totals.g}</b></span>
        <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-sm bg-bad" />
          Denied <b className="text-white tnum">{totals.d}</b></span>
      </div>
      <div className="flex gap-3 h-44">
        {days.map(d => (
          <div key={d.day} className="flex-1 h-full flex flex-col items-center justify-end
                                      gap-1.5 min-w-0">
            <div className="w-full max-w-[46px] flex flex-col-reverse rounded-md overflow-hidden
                            bg-ink-700/40"
                 style={{ height: `calc((100% - 22px) * ${(d.granted + d.denied) / max})` }}
                 title={`${d.day}: ${d.granted} granted, ${d.denied} denied`}>
              <div className="bg-ok/80" style={{ flexGrow: d.granted }} />
              <div className="bg-bad/80" style={{ flexGrow: d.denied }} />
            </div>
            <span className="text-[10.5px] text-slate-400 tnum">
              {new Date(`${d.day}T00:00`).toLocaleDateString([], { day: 'numeric', month: 'short' })}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
