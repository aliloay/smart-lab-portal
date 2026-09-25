/**
 * Reports. Every series is a real aggregate from /reports/overview; a
 * section with nothing behind it says "Not enough data yet" instead of
 * drawing an empty or invented chart. Hours arrive in UTC and are shifted to
 * the viewer's local time here.
 */
import { useEffect, useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { BarChart3, CalendarRange, DoorOpen, ShieldX, Timer } from 'lucide-react'
import { IssueSummary, ReportsOverview, api } from '../lib/api'
import { denialShort } from '../lib/labels'
import { ErrorBanner, MetricCard, PageHeader, SectionTitle, Skeleton } from '../components/ui'
import { C, ChartCard, PALETTE, axisProps, tooltipProps } from '../components/charts'

const PERIODS = [7, 30, 90, 365]
const DELAY_LABEL: Record<string, string> = {
  early: 'Early (>5 min)', on_time: 'On time (±5 min)', late_5_15: '5–15 min late',
  late_15_30: '15–30 min late', late_30_plus: '30+ min late',
}

export default function Reports() {
  const [days, setDays] = useState(30)
  const [r, setR] = useState<ReportsOverview | null>(null)
  const [issues, setIssues] = useState<IssueSummary | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setR(null)
    api.reports(days).then(setR).catch(e => setError(e.message))
    api.issueSummary().then(setIssues).catch(() => {})
  }, [days])

  // UTC hour -> local hour, whole hours (the offset for Cairo and most zones).
  const shift = -new Date().getTimezoneOffset() / 60
  const local = (rows: { hour: number; count: number }[]) => {
    const m = new Map<number, number>()
    rows.forEach(x => m.set(((x.hour + shift) % 24 + 24) % 24, x.count))
    return Array.from({ length: 24 }, (_, h) => ({ hour: `${String(h).padStart(2, '0')}`, count: m.get(h) ?? 0 }))
  }
  const bookingHours = useMemo(() => r ? local(r.booking_hours_utc) : [], [r])   // eslint-disable-line react-hooks/exhaustive-deps
  const entryHours = useMemo(() => r ? local(r.entry_hours_utc) : [], [r])   // eslint-disable-line react-hooks/exhaustive-deps

  const delays = r ? Object.entries(r.entry_delays).map(([k, v]) => ({ label: DELAY_LABEL[k] ?? k, count: v ?? 0 })) : []
  const outcomes = r?.access_outcomes ?? []
  const totals = outcomes.reduce((a, d) => ({ g: a.g + d.granted, d: a.d + d.denied }), { g: 0, d: 0 })

  return (
    <div>
      <PageHeader eyebrow="Analytics" title="Reports"
        sub="Laboratory usage, access outcomes and traceability - aggregated from recorded rows only."
        actions={<div className="flex gap-1 p-1 rounded-xl border border-ink-600 bg-ink-800/60">
          {PERIODS.map(p => (
            <button key={p} onClick={() => setDays(p)} aria-pressed={days === p}
              className={`px-3 py-1.5 rounded-lg text-[13px] ${days === p ? 'bg-accent-500/20 text-white'
                : 'text-slate-400 hover:text-white'}`}>{p === 365 ? '1 year' : `${p} days`}</button>
          ))}
        </div>} />
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {!r ? <Skeleton className="h-96" /> : (
        <div className="space-y-8">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="Bookings" value={r.utilisation.bookings} icon={<CalendarRange size={16} />}
                        hint={`in the last ${days} days`} />
            <MetricCard label="Used" value={r.utilisation.used_rate === null ? null
                          : `${Math.round(r.utilisation.used_rate * 100)}%`} animate={false}
                        icon={<DoorOpen size={16} />} tone="ok"
                        info="Share of finished bookings where the door recorded an actual entry."
                        hint={`${r.utilisation.used} of ${r.utilisation.finished} finished bookings`} />
            <MetricCard label="No-shows" value={r.utilisation.no_show} icon={<Timer size={16} />}
                        tone={r.utilisation.no_show ? 'warn' : 'idle'}
                        hint="Finished bookings with no entry" />
            <MetricCard label="Access denied" value={totals.d} icon={<ShieldX size={16} />}
                        tone={totals.d ? 'bad' : 'idle'} hint={`${totals.g} granted`} />
          </div>

          <section>
            <SectionTitle icon={<CalendarRange size={15} />}>Laboratory usage</SectionTitle>
            <div className="grid lg:grid-cols-2 gap-4">
              <ChartCard title="Bookings by laboratory" sub="Booked vs actually entered"
                         empty={!r.bookings_by_lab.length}>
                <ResponsiveContainer>
                  <BarChart data={r.bookings_by_lab}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="label" {...axisProps} />
                    <YAxis {...axisProps} allowDecimals={false} width={28} />
                    <Tooltip {...tooltipProps} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="count" name="Booked" fill={C.accent} radius={[6, 6, 0, 0]} />
                    <Bar dataKey="used" name="Entered" fill={C.teal} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard title="Booking volume" sub="Bookings starting each day"
                         empty={!r.booking_volume.length}>
                <ResponsiveContainer>
                  <LineChart data={r.booking_volume}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="day" {...axisProps} tickFormatter={d => d.slice(5)} minTickGap={20} />
                    <YAxis {...axisProps} allowDecimals={false} width={28} />
                    <Tooltip {...tooltipProps} />
                    <Line type="monotone" dataKey="count" name="Bookings" stroke={C.accent} strokeWidth={2.5} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard title="Busiest hours" sub="Booking start times vs actual door entries (local time)"
                         empty={!r.booking_hours_utc.length && !r.entry_hours_utc.length}>
                <ResponsiveContainer>
                  <BarChart data={bookingHours.map((b, i) => ({ ...b, entries: entryHours[i].count }))}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="hour" {...axisProps} interval={1} />
                    <YAxis {...axisProps} allowDecimals={false} width={28} />
                    <Tooltip {...tooltipProps} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="count" name="Bookings starting" fill={C.violet} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="entries" name="Door entries" fill={C.teal} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard title="Actual entry vs booked start" sub="How punctual people are - from real first entries"
                         empty={!delays.length}>
                <ResponsiveContainer>
                  <BarChart data={delays} layout="vertical" margin={{ left: 30 }}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" horizontal={false} />
                    <XAxis type="number" {...axisProps} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" {...axisProps} width={120} />
                    <Tooltip {...tooltipProps} />
                    <Bar dataKey="count" name="Bookings" radius={[0, 6, 6, 0]}>
                      {delays.map((_, i) => <Cell key={i} fill={[C.accent, C.ok, C.warn, C.warn, C.bad][i] ?? C.accent} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
          </section>

          <section>
            <SectionTitle icon={<ShieldX size={15} />}>Access outcomes</SectionTitle>
            <div className="grid lg:grid-cols-2 gap-4">
              <ChartCard title="Granted vs denied" sub="Per day" empty={!outcomes.length}>
                <ResponsiveContainer>
                  <BarChart data={outcomes}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="day" {...axisProps} tickFormatter={d => d.slice(5)} />
                    <YAxis {...axisProps} allowDecimals={false} width={28} />
                    <Tooltip {...tooltipProps} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="granted" name="Granted" stackId="a" fill={C.ok} />
                    <Bar dataKey="denied" name="Denied" stackId="a" fill={C.bad} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard title="Why access was refused" sub="Security events by reason"
                         empty={!r.denial_reasons.length}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={r.denial_reasons.map(d => ({ name: denialShort(d.reason), value: d.count }))}
                         dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={2}
                         stroke="#172841">
                      {r.denial_reasons.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                    </Pie>
                    <Tooltip {...tooltipProps} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
          </section>

          <section>
            <SectionTitle icon={<BarChart3 size={15} />}>Equipment & maintenance</SectionTitle>
            <div className="grid lg:grid-cols-2 gap-4">
              <ChartCard title="Equipment checked out" sub="Most used items" empty={!r.asset_checkouts.length}>
                <ResponsiveContainer>
                  <BarChart data={r.asset_checkouts} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" horizontal={false} />
                    <XAxis type="number" {...axisProps} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" {...axisProps} width={160} />
                    <Tooltip {...tooltipProps} />
                    <Bar dataKey="count" name="Check-outs" fill={C.teal} radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard title="Issues by status" sub={issues?.avg_resolution_hours != null
                ? `Average resolution ${issues.avg_resolution_hours} h` : 'All time'}
                         empty={!issues?.by_status.length}>
                <ResponsiveContainer>
                  <BarChart data={issues?.by_status ?? []}>
                    <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="label" {...axisProps} />
                    <YAxis {...axisProps} allowDecimals={false} width={28} />
                    <Tooltip {...tooltipProps} />
                    <Bar dataKey="count" name="Issues" radius={[6, 6, 0, 0]}>
                      {(issues?.by_status ?? []).map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
          </section>

          <p className="text-[12px] text-slate-500">
            Generated {new Date(r.generated_at).toLocaleString()}. Device availability history is not
            charted: the portal stores each device's latest heartbeat, not a history of them.
          </p>
        </div>
      )}
    </div>
  )
}
