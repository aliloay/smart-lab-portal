/**
 * Operations Center - the staff command view.
 *
 * One request (/analytics/operations) feeds every panel; live access events
 * trigger a debounced refresh, so the page tracks the door without polling
 * hard. Every panel has an explicit empty state: a lab with no sensor says
 * "Awaiting sensor data", a session with no observed exit contributes no
 * duration, a device that never reported has no availability figure.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  Activity, Bot, CalendarRange, Cpu, DoorOpen, Gauge, RefreshCw, ShieldCheck, Thermometer,
  Timer, Workflow, Wrench,
} from 'lucide-react'
import { Lab, Operations as Ops, api } from '../lib/api'
import { useLive, useLiveMessages } from '../lib/live'
import { denialShort, methodLabel } from '../lib/labels'
import { fmtDateTime, fmtDuration, relative } from '../lib/time'
import {
  Chip, Dot, EmptyState, ErrorBanner, MetricCard, PageHeader, SectionTitle, Skeleton,
} from '../components/ui'
import { C, ChartCard, PALETTE, axisProps, tooltipProps } from '../components/charts'
import { EnvironmentPanel, Funnel, Heatmap, OutageStrip } from '../components/analytics'

const PERIODS = [7, 30, 90]
const END_REASON: Record<string, string> = {
  EXIT_RECORDED: 'Exit recorded', BOOKING_ENDED: 'Session ended (booking closed)',
  DOOR_NOT_OPENED: 'Door never opened', SUPERSEDED: 'Re-entered',
  NO_EXIT_TIMEOUT: 'Exit not recorded (timeout)', OPEN: 'Still inside',
}
const SEV_COLOR: Record<string, string> = {
  CRITICAL: C.bad, HIGH: C.warn, MEDIUM: C.accent, LOW: '#64748b',
}

export default function Operations() {
  const { connected } = useLive()
  const [days, setDays] = useState(30)
  const [labId, setLabId] = useState<number | undefined>()
  const [labs, setLabs] = useState<Lab[]>([])
  const [d, setD] = useState<Ops | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const timer = useRef<number>()

  const load = useCallback(() => {
    setLoading(true)
    api.operations(days, labId)
      .then(r => { setD(r); setError('') })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [days, labId])

  useEffect(() => { setD(null); load() }, [load])
  useEffect(() => { api.labs().then(setLabs).catch(() => {}) }, [])
  useEffect(() => {
    const t = window.setInterval(load, 60000)
    return () => window.clearInterval(t)
  }, [load])
  // Door events refresh the view, at most every few seconds.
  useLiveMessages(m => {
    if (m.type !== 'access_event' && m.type !== 'staff') return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(load, 2500)
  })

  const kpi = useMemo(() => {
    if (!d) return null
    const g = d.access_outcomes.reduce((a, r) => a + r.granted, 0)
    const n = d.access_outcomes.reduce((a, r) => a + r.denied, 0)
    const booked = d.utilisation.reduce((a, r) => a + r.booked_hours, 0)
    const avail = d.utilisation.length ? d.utilisation[0].available_hours * d.utilisation.length : 0
    const online = d.devices.filter(x => x.state === 'ONLINE').length
    const reporting = d.devices.filter(x => x.state !== 'NO_DATA').length
    return { g, n, rate: g + n ? g / (g + n) : null, booked,
             util: avail ? booked / avail : null, online, reporting }
  }, [d])

  return (
    <div>
      <PageHeader eyebrow="Command view" title="Operations Center"
        sub="Utilisation, access, sessions, devices, maintenance and automation - counted from recorded rows only."
        actions={<div className="flex flex-wrap items-center gap-2">
          <select aria-label="Laboratory" value={labId ?? ''}
            onChange={e => setLabId(e.target.value ? Number(e.target.value) : undefined)}
            className="input !py-1.5 !w-auto text-[13px]">
            <option value="">All laboratories</option>
            {labs.map(l => <option key={l.id} value={l.id}>{l.code} · {l.name}</option>)}
          </select>
          <div className="flex gap-1 p-1 rounded-xl border border-ink-600 bg-ink-800/60">
            {PERIODS.map(p => (
              <button key={p} onClick={() => setDays(p)} aria-pressed={days === p}
                className={`px-3 py-1.5 rounded-lg text-[13px] ${days === p
                  ? 'bg-accent-500/20 text-white' : 'text-slate-400 hover:text-white'}`}>{p} days</button>
            ))}
          </div>
          <button onClick={load} className="btn-ghost !px-2.5" aria-label="Refresh">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>} />

      <div className="flex items-center gap-2 text-[12px] text-slate-400 mb-5">
        <Dot tone={connected ? 'ok' : 'idle'} live={connected} />
        {connected ? 'Live - refreshes on door activity' : 'Live stream disconnected - refreshing every minute'}
        {d && <span className="text-slate-500">· updated {relative(d.generated_at)} · heatmaps in {d.timezone}</span>}
      </div>

      {error && <div className="mb-4"><ErrorBanner title="Could not load operations data" message={error}
        action={<button className="btn-ghost" onClick={load}>Retry</button>} /></div>}

      {!d || !kpi ? <Skeleton className="h-[640px]" /> : (
        <div className="space-y-8">
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <MetricCard label="Utilisation" icon={<Gauge size={16} />}
              value={kpi.util === null ? null : `${Math.round(kpi.util * 100)}%`} animate={false}
              info={`Booked hours ÷ (${d.open_hours_per_day} opening hours × ${days} days × labs with bookings).`}
              hint={`${kpi.booked.toFixed(1)} h booked`} />
            <MetricCard label="Access success" icon={<ShieldCheck size={16} />}
              value={kpi.rate === null ? null : `${Math.round(kpi.rate * 100)}%`} animate={false}
              tone={kpi.rate !== null && kpi.rate < 0.7 ? 'warn' : 'ok'}
              hint={`${kpi.g} granted · ${kpi.n} denied`} />
            <MetricCard label="Median stay" icon={<Timer size={16} />}
              value={d.sessions.median_minutes === null ? null : fmtDuration(d.sessions.median_minutes)}
              animate={false}
              info="Only sessions with an observed exit have a duration. Without an exit reader, most sessions say 'Exit not recorded'."
              hint={`${d.sessions.exit_recorded} of ${d.sessions.started} with an exit`} />
            <MetricCard label="People inside" icon={<DoorOpen size={16} />} value={d.sessions.open_now}
              hint="Open sessions now" />
            <MetricCard label="Open issues" icon={<Wrench size={16} />} value={d.maintenance.open}
              tone={d.maintenance.overdue ? 'bad' : d.maintenance.open ? 'warn' : 'idle'} to="/issues"
              hint={`${d.maintenance.overdue} overdue · ${d.maintenance.unassigned} unassigned`} />
            <MetricCard label="Devices online" icon={<Cpu size={16} />}
              value={kpi.reporting ? `${kpi.online}/${kpi.reporting}` : null} animate={false}
              tone={kpi.reporting && kpi.online < kpi.reporting ? 'bad' : 'ok'} to="/admin/devices"
              hint={`${d.devices.length - kpi.reporting} never reported`} />
          </div>

          {/* ------------------------------------------------ utilisation */}
          <section>
            <SectionTitle icon={<CalendarRange size={15} />}
              sub="When the laboratories are booked, and when people actually walk in.">Utilisation</SectionTitle>
            <div className="grid xl:grid-cols-3 gap-4">
              <ChartCard title="Booked hours by laboratory"
                sub={`Share of a ${d.open_hours_per_day} h/day opening window`} empty={!d.utilisation.length}>
                <ResponsiveContainer>
                  <BarChart data={d.utilisation.map(u => ({ ...u, pct: Math.round((u.utilisation ?? 0) * 1000) / 10 }))}
                    layout="vertical" margin={{ left: 8 }}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" horizontal={false} />
                    <XAxis type="number" {...axisProps} unit="%" />
                    <YAxis type="category" dataKey="lab_code" {...axisProps} width={80} />
                    <Tooltip {...tooltipProps} formatter={(v: number, _n, p) =>
                      [`${v}% (${p.payload.booked_hours} h, ${p.payload.used}/${p.payload.bookings} entered)`, 'Utilisation']} />
                    <Bar dataKey="pct" fill={C.accent} radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <div className="card p-5 xl:col-span-2">
                <div className="text-[14px] font-semibold text-slate-100">Booked hours · weekday × hour</div>
                <div className="text-[12px] text-slate-400 mb-4">Fractional hours per slot over the period</div>
                <Heatmap data={d.booked_heatmap} unit="h booked" />
              </div>
              <div className="card p-5 xl:col-span-3">
                <div className="text-[14px] font-semibold text-slate-100">Door entries · weekday × hour</div>
                <div className="text-[12px] text-slate-400 mb-4">Access sessions started (granted entries)</div>
                <Heatmap data={d.entry_heatmap} unit="entries" tone="teal" />
              </div>
            </div>
          </section>

          {/* ------------------------------------------------ access */}
          <section>
            <SectionTitle icon={<ShieldCheck size={15} />}
              sub="Two-factor path: credential → identity → grant → door.">Access analytics</SectionTitle>
            <div className="grid lg:grid-cols-2 gap-4">
              <div className="card p-5">
                <div className="text-[14px] font-semibold text-slate-100 mb-4">Access funnel</div>
                <Funnel steps={d.funnel} />
              </div>
              <ChartCard title="Granted vs denied" sub="Per day" empty={!d.access_outcomes.length}>
                <ResponsiveContainer>
                  <BarChart data={d.access_outcomes}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="day" {...axisProps} tickFormatter={x => x.slice(5)} minTickGap={16} />
                    <YAxis {...axisProps} allowDecimals={false} width={28} />
                    <Tooltip {...tooltipProps} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="granted" name="Granted" stackId="a" fill={C.ok} />
                    <Bar dataKey="denied" name="Denied" stackId="a" fill={C.bad} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard title="Refusal reasons" sub="Final door decisions (ACCESS_DENIED)"
                empty={!d.denial_reasons.length} height={220}>
                <ResponsiveContainer>
                  <BarChart data={d.denial_reasons.map(r => ({ label: denialShort(r.reason), count: r.count }))}
                    layout="vertical" margin={{ left: 12 }}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" horizontal={false} />
                    <XAxis type="number" {...axisProps} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" {...axisProps} width={130} />
                    <Tooltip {...tooltipProps} />
                    <Bar dataKey="count" name="Refusals" radius={[0, 6, 6, 0]}>
                      {d.denial_reasons.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <div className="card p-5">
                <div className="text-[14px] font-semibold text-slate-100">Methods and second factor</div>
                <div className="text-[12px] text-slate-400 mb-4">Grants by step-1 method · sessions by biometric</div>
                {!d.granted_by_method.length && !d.sessions.second_factor.length
                  ? <EmptyState compact title="No grants in this period" />
                  : <div className="grid sm:grid-cols-2 gap-5">
                    <ul className="space-y-2">
                      {d.granted_by_method.map(m => (
                        <li key={m.method} className="flex justify-between text-[13px]">
                          <span className="text-slate-300">{methodLabel(m.method)}</span>
                          <span className="tnum text-white">{m.count}</span></li>))}
                    </ul>
                    <ul className="space-y-2">
                      {d.sessions.second_factor.map(m => (
                        <li key={`${m.entry}-${m.second}`} className="flex justify-between text-[13px]">
                          <span className="text-slate-300">{methodLabel(m.entry)} + {m.second === 'NOT_RECORDED'
                            ? <span className="text-slate-500">not reported</span> : methodLabel(m.second)}</span>
                          <span className="tnum text-white">{m.count}</span></li>))}
                    </ul>
                  </div>}
                <div className="mt-4 flex gap-3 text-[12.5px]">
                  <Chip tone={d.security.identity_mismatch ? 'bad' : 'idle'} dot>
                    {d.security.identity_mismatch} identity mismatch</Chip>
                  <Chip tone={d.security.alarms ? 'warn' : 'idle'} dot>{d.security.alarms} door alarms</Chip>
                </div>
              </div>
            </div>
          </section>

          {/* ------------------------------------------------ sessions */}
          <section>
            <SectionTitle icon={<DoorOpen size={15} />}
              sub="Duration exists only where an exit was observed.">Sessions</SectionTitle>
            <div className="grid lg:grid-cols-2 gap-4">
              <ChartCard title="Time inside" sub="Sessions with a recorded exit"
                empty={!d.sessions.duration_buckets.length} height={220}>
                <ResponsiveContainer>
                  <BarChart data={d.sessions.duration_buckets}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="label" {...axisProps} />
                    <YAxis {...axisProps} allowDecimals={false} width={28} />
                    <Tooltip {...tooltipProps} />
                    <Bar dataKey="count" name="Sessions" fill={C.teal} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <div className="card p-5">
                <div className="text-[14px] font-semibold text-slate-100 mb-4">How sessions ended</div>
                {!d.sessions.started ? <EmptyState compact title="No sessions in this period" /> : (
                  <ul className="space-y-2.5">
                    {Object.entries(d.sessions.end_reasons).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                      <li key={k}>
                        <div className="flex justify-between text-[13px]">
                          <span className="text-slate-300">{END_REASON[k] ?? k}</span>
                          <span className="tnum text-white">{v}</span>
                        </div>
                        <div className="mt-1 h-1.5 rounded-full bg-ink-700/60">
                          <div className="h-full rounded-full bg-violet-400/70"
                               style={{ width: `${(v / d.sessions.started) * 100}%` }} />
                        </div>
                      </li>))}
                  </ul>)}
              </div>
            </div>
          </section>

          {/* ------------------------------------------------ devices */}
          <section>
            <SectionTitle icon={<Cpu size={15} />}
              sub="Observed outages: from a recorded offline transition to the next heartbeat.">Device health</SectionTitle>
            <div className="card p-5">
              {!d.devices.length ? <EmptyState compact title="No devices registered" /> : (
                <div className="space-y-3.5">
                  {d.devices.map(x => (
                    <div key={x.device_id} className="grid sm:grid-cols-[220px_1fr_150px] gap-2 sm:gap-4 items-center">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-[13px] text-slate-100 truncate">
                          <Dot tone={x.state === 'ONLINE' ? 'ok' : x.state === 'OFFLINE' ? 'bad' : 'idle'}
                               live={x.state === 'ONLINE'} />{x.name}
                        </div>
                        <div className="text-[11.5px] text-slate-500">{x.lab_code} · {x.type.replace('_', ' ').toLowerCase()}
                          {x.components && Object.entries(x.components).filter(([k, v]) => v === false && k !== 'relay_locked')
                            .map(([k]) => <span key={k} className="ml-1.5 text-bad-soft">{k} fault</span>)}
                        </div>
                      </div>
                      <OutageStrip outages={x.outages} days={days} state={x.state} />
                      <div className="text-[12px] text-slate-400 sm:text-right">
                        {x.state === 'NO_DATA' ? 'Never reported'
                          : `${x.offline_events} outage${x.offline_events === 1 ? '' : 's'} · ${fmtDuration(x.offline_minutes ?? 0)}`}
                        <div className="text-[11px] text-slate-500">
                          {x.last_seen_at ? `seen ${relative(x.last_seen_at)}` : 'Not reported'}</div>
                      </div>
                    </div>))}
                </div>)}
            </div>
          </section>

          {/* ------------------------------------------------ maintenance */}
          <section>
            <SectionTitle icon={<Wrench size={15} />}
              sub="Backlog, flow and time to resolve against the published SLA.">Maintenance</SectionTitle>
            <div className="grid lg:grid-cols-3 gap-4">
              <ChartCard title="Open by severity" empty={!d.maintenance.open} height={200}>
                <ResponsiveContainer>
                  <BarChart data={d.maintenance.by_severity}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="severity" {...axisProps} tickFormatter={s => s.slice(0, 4)} />
                    <YAxis {...axisProps} allowDecimals={false} width={24} />
                    <Tooltip {...tooltipProps} />
                    <Bar dataKey="count" name="Open" radius={[6, 6, 0, 0]}>
                      {d.maintenance.by_severity.map(s => <Cell key={s.severity} fill={SEV_COLOR[s.severity]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard title="Opened vs resolved" sub="Per day" empty={!d.maintenance.flow.length} height={200}>
                <ResponsiveContainer>
                  <BarChart data={d.maintenance.flow}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="day" {...axisProps} tickFormatter={x => x.slice(5)} minTickGap={16} />
                    <YAxis {...axisProps} allowDecimals={false} width={24} />
                    <Tooltip {...tooltipProps} />
                    <Bar dataKey="opened" name="Opened" fill={C.warn} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="resolved" name="Resolved" fill={C.ok} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <div className="card p-5">
                <div className="text-[14px] font-semibold text-slate-100 mb-4">Median time to resolve</div>
                {!d.maintenance.median_hours_to_resolve.length
                  ? <EmptyState compact title="Nothing resolved in this period" /> : (
                  <ul className="space-y-3">
                    {d.maintenance.median_hours_to_resolve.map(m => {
                      const sla = d.maintenance.sla_hours[m.severity]
                      const over = sla && m.hours > sla
                      return (
                        <li key={m.severity}>
                          <div className="flex justify-between text-[13px]">
                            <span className="text-slate-300">{m.severity.toLowerCase()} · {m.resolved} resolved</span>
                            <span className={`tnum ${over ? 'text-bad-soft' : 'text-white'}`}>{m.hours} h</span>
                          </div>
                          <div className="mt-1 h-1.5 rounded-full bg-ink-700/60">
                            <div className={`h-full rounded-full ${over ? 'bg-bad' : 'bg-ok'}`}
                                 style={{ width: `${Math.min(m.hours / (sla || m.hours), 1) * 100}%` }} />
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">SLA {sla} h</div>
                        </li>)
                    })}
                  </ul>)}
              </div>
            </div>
          </section>

          {/* ------------------------------------------------ environment */}
          <section>
            <SectionTitle icon={<Thermometer size={15} />} sub="Last 24 hours, against configured thresholds.">
              Environment</SectionTitle>
            <div className="card p-5"><EnvironmentPanel env={d.environment} /></div>
          </section>

          {/* ------------------------------------------------ automation */}
          <AutomationPanel a={d.automation} />

          <p className="text-[12px] text-slate-500">
            Generated {fmtDateTime(d.generated_at)}. Past device availability is shown only as the outages the
            portal observed; before the first recorded transition there is no history to draw.
            {' '}<Link to="/admin/reports" className="text-accent-300 hover:underline">Classic reports</Link>
          </p>
        </div>
      )}
    </div>
  )
}

function AutomationPanel({ a }: { a: Ops['automation'] }) {
  const state = !a.api_enabled && !a.push_enabled ? 'off'
    : a.outbox.FAILED ? 'degraded' : 'ok'
  return (
    <section>
      <SectionTitle icon={<Workflow size={15} />}
        sub="n8n orchestrates notifications and reports. It never decides access.">Automation (n8n)</SectionTitle>
      <div className="card p-5 grid lg:grid-cols-[1fr_1.4fr] gap-6">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Bot size={16} className="text-accent-300" />
            <span className="text-[14px] text-slate-100 font-semibold">
              {state === 'off' ? 'Not configured' : state === 'degraded' ? 'Delivering with failures' : 'Connected'}
            </span>
            <Chip tone={state === 'ok' ? 'ok' : state === 'degraded' ? 'warn' : 'idle'} dot>
              {state === 'off' ? 'portal only' : state}</Chip>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[12.5px]">
            <Flag on={a.api_enabled} label="Automation API" />
            <Flag on={a.push_enabled} label="Event push" />
            <Flag on={a.dispatcher_running} label="Dispatcher" />
            <Flag on={!!a.last_delivered_at} label={a.last_delivered_at
              ? `Delivered ${relative(a.last_delivered_at)}` : 'Nothing delivered'} />
          </div>
          <div className="grid grid-cols-4 gap-2">
            {(['PENDING', 'DELIVERED', 'FAILED', 'SKIPPED'] as const).map(k => (
              <div key={k} className="rounded-lg border border-ink-600/70 bg-ink-800/40 p-2.5 text-center">
                <div className={`font-display text-lg ${k === 'FAILED' && a.outbox[k] ? 'text-bad-soft' : 'text-white'}`}>
                  {a.outbox[k]}</div>
                <div className="text-[10.5px] text-slate-500">{k.toLowerCase()}</div>
              </div>))}
          </div>
          <div className="text-[11.5px] text-slate-500">
            Pushed types: {a.push_types.join(', ') || 'none'}. Skipped = recorded for the pull feed only.
          </div>
          {a.last_error && (
            <div className="text-[12px] rounded-lg border border-bad/30 bg-bad/5 p-2.5 text-bad-soft">
              Last failure ({a.last_error.event_type}): {a.last_error.error}
            </div>)}
        </div>
        <div>
          <div className="label mb-2 flex items-center gap-1.5"><Activity size={13} /> Recent workflow runs</div>
          {!a.recent_runs.length ? (
            <EmptyState compact title="No workflow has reported a run"
              detail="Each n8n workflow posts to /api/automation/runs when it finishes." />
          ) : (
            <ul className="divide-y divide-ink-600/50">
              {a.recent_runs.map((r, i) => (
                <li key={i} className="py-2 flex items-start gap-3 text-[12.5px]">
                  <Dot tone={r.status === 'success' ? 'ok' : r.status === 'error' ? 'bad' : 'idle'} />
                  <div className="min-w-0 flex-1">
                    <div className="text-slate-200 mono">{r.workflow}</div>
                    {r.summary && <div className="text-slate-500 truncate">{r.summary}</div>}
                  </div>
                  <span className="text-slate-500 shrink-0">{relative(r.at)}</span>
                </li>))}
            </ul>)}
        </div>
      </div>
    </section>
  )
}

function Flag({ on, label }: { on: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-300">
      <Dot tone={on ? 'ok' : 'idle'} />{label}
    </div>
  )
}
