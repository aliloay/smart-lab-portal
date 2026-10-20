/**
 * System analytics - the whole lab, not only the door: one page with every subsystem's history
 * (door, environment, robots, consumables, cameras, PCs, automation, alerts) and the freshness of
 * each data source. Data: GET /analytics/system (server-side aggregation of real tables).
 * A source with no rows says so; simulated robots (…_SIM) are labelled; nothing is invented.
 */
import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity, Bot, Boxes, Camera, DoorOpen, Monitor, Thermometer, TriangleAlert, Workflow } from 'lucide-react'
import { api } from '../lib/api'
import { PageHeader, Spinner, ErrorBanner } from '../components/ui'
import SystemHealthBoard from '../components/SystemHealthBoard'
import AnomalyPanel from '../components/AnomalyPanel'
import { ChartCard, PALETTE, axisProps, tooltipProps, xTitle, yTitle } from '../components/charts'

type Pivot = { keys: string[]; series: Record<string, number | string>[]; available: boolean }
type Fresh = { source: string; last: string | null; age_s: number | null; records: number; state: 'live' | 'stale' | 'offline' | 'never' }
type Sys = {
  days: number; generated_at: string; freshness: Record<string, Fresh>
  totals: Record<string, number>
  door: Pivot; robots: Pivot; robot_movements: Pivot; inventory_tx: Pivot; cameras: Pivot; pcs: Pivot; automation: Pivot; alerts: Pivot
  environment: { series: Record<string, number | string>[]; available: boolean }
  bins: { rows: { day: string; bin_id: number; min: number; max: number; avg: number }[]; available: boolean }
  kpis: { id: string; name: string; unit: string; source: string; rule: string; kind: string }[]
}

const STATE = {
  live: 'bg-ok/15 text-ok-soft border-ok/40', stale: 'bg-warn/15 text-warn-soft border-warn/40',
  offline: 'bg-bad/15 text-bad-soft border-bad/40', never: 'bg-ink-800 text-slate-400 border-ink-600',
}
const SOURCES: [string, string, JSX.Element][] = [
  ['environment', 'Environment node', <Thermometer size={15} />], ['door', 'Door access', <DoorOpen size={15} />],
  ['robots', 'Robots', <Bot size={15} />], ['consumables', 'Consumables scale', <Boxes size={15} />],
  ['inventory', 'Inventory transactions', <Boxes size={15} />], ['cameras', 'Security cameras', <Camera size={15} />],
  ['pcs', 'Lab PCs', <Monitor size={15} />], ['automation', 'n8n automations', <Workflow size={15} />],
  ['alerts', 'Alerts', <TriangleAlert size={15} />],
]
const ago = (s: number | null) => s == null ? 'never' : s < 120 ? `${s}s ago` : s < 7200 ? `${Math.round(s / 60)} min ago`
  : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`
const short = (d: string) => d.slice(5)
const label = (k: string) => k.endsWith('_SIM') ? `${k} (simulated)` : k.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase())

function Stacked({ title, sub, p, y, height = 240 }: { title: string; sub: string; p: Pivot; y: string; height?: number }) {
  return (
    <ChartCard title={title} sub={sub} empty={!p.available} height={height}>
      <ResponsiveContainer>
        <BarChart data={p.series} margin={{ left: 4, right: 8, bottom: 4 }}>
          <CartesianGrid stroke="#1e3350" vertical={false} />
          <XAxis dataKey="day" tickFormatter={short} {...axisProps} {...xTitle('Day')} />
          <YAxis {...axisProps} {...yTitle(y)} allowDecimals={false} />
          <Tooltip {...tooltipProps} />
          <Legend wrapperStyle={{ fontSize: 11 }} formatter={label} />
          {p.keys.map((k, i) => <Bar isAnimationActive={false} key={k} dataKey={k} name={k} stackId="a" fill={k.endsWith('_SIM') ? '#64748b' : PALETTE[i % PALETTE.length]} />)}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>)
}

export default function SystemAnalytics() {
  const [days, setDays] = useState(30)
  const [d, setD] = useState<Sys | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { setD(null); api.systemAnalytics<Sys>(days).then(setD).catch(e => setError(e.message)) }, [days])

  return (
    <div className="space-y-5">
      <PageHeader eyebrow="Analytics" title="System analytics"
        sub="Every subsystem of the lab from its own records - door, environment, robots, consumables, cameras, PCs and automations." />
      <SystemHealthBoard />
      <AnomalyPanel />
      <div className="flex flex-wrap items-center gap-2">
        {[7, 30, 90].map(n => <button key={n} onClick={() => setDays(n)}
          className={`px-3 py-1.5 rounded-lg text-[13px] border ${days === n ? 'bg-accent-500/20 border-accent-400/60 text-white' : 'border-ink-600 text-slate-300'}`}>Last {n} days</button>)}
        {d && <span className="ml-auto text-[12px] text-slate-500">Generated {new Date(d.generated_at).toLocaleString()} · days in UTC</span>}
      </div>
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {!d ? <Spinner label="Aggregating all subsystems" /> : <>
        {/* data sources */}
        <div className="card p-4">
          <div className="text-[13px] font-semibold text-slate-200 mb-3 flex items-center gap-2"><Activity size={15} /> Data sources - how fresh each one is</div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-2">
            {SOURCES.map(([k, name, ic]) => { const f = d.freshness[k]; return f && (
              <div key={k} className="rounded-xl border border-ink-600/70 bg-ink-900/40 p-3">
                <div className="flex items-center gap-2 text-[13px] text-slate-200">{ic}{name}
                  <span className={`ml-auto text-[10.5px] font-semibold uppercase px-1.5 py-0.5 rounded border ${STATE[f.state]}`}>{f.state}</span></div>
                <div className="text-[11.5px] text-slate-400 mt-1">last record {ago(f.age_s)} · {f.records.toLocaleString()} total</div>
              </div>) })}
          </div>
          <p className="text-[11.5px] text-slate-500 mt-2">Live = recent for that source's normal reporting rate; stale = older but within 7 days; offline = older. Devices at the university report only while powered and on the lab network.</p>
        </div>

        {/* totals */}
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
          {[['Door events', d.totals.door_events], ['Environment readings', d.totals.env_readings], ['Robot events', d.totals.robot_events],
            ['Camera events', d.totals.camera_events], ['PC hours', d.totals.pc_hours], ['Alerts', d.totals.alerts]].map(([l, v]) => (
            <div key={l as string} className="card p-3"><div className="text-xl font-semibold text-white">{Number(v).toLocaleString()}</div>
              <div className="text-[12px] text-slate-400">{l} · last {d.days} days</div></div>))}
        </div>

        <div className="grid xl:grid-cols-2 gap-4">
          <Stacked title="Door access" sub="Door decisions per day, by result (access_events)" p={d.door} y="Events" />

          <ChartCard title="Temperature & humidity" sub="Daily average from the environment node (sensor_readings)" empty={!d.environment.available} height={240}>
            <ResponsiveContainer>
              <LineChart data={d.environment.series} margin={{ left: 4, right: 8, bottom: 4 }}>
                <CartesianGrid stroke="#1e3350" vertical={false} />
                <XAxis dataKey="day" tickFormatter={short} {...axisProps} {...xTitle('Day')} />
                <YAxis {...axisProps} {...yTitle('°C  /  %')} />
                <Tooltip {...tooltipProps} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line isAnimationActive={false} dataKey="temperature_avg" name="Temperature °C" stroke="#f59e0b" dot={false} connectNulls={false} strokeWidth={2} />
                <Line isAnimationActive={false} dataKey="humidity_avg" name="Humidity %" stroke="#38bdf8" dot={false} connectNulls={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Safety sensors" sub="Readings above zero per day - smoke, flame, motion (sensor_readings)" empty={!d.environment.available} height={240}>
            <ResponsiveContainer>
              <BarChart data={d.environment.series} margin={{ left: 4, right: 8, bottom: 4 }}>
                <CartesianGrid stroke="#1e3350" vertical={false} />
                <XAxis dataKey="day" tickFormatter={short} {...axisProps} {...xTitle('Day')} />
                <YAxis {...axisProps} {...yTitle('Readings')} allowDecimals={false} />
                <Tooltip {...tooltipProps} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar isAnimationActive={false} dataKey="smoke_pos" name="Smoke" fill="#94a3b8" />
                <Bar isAnimationActive={false} dataKey="flame_pos" name="Flame" fill="#ef4444" />
                <Bar isAnimationActive={false} dataKey="motion_pos" name="Motion" fill="#2dd4bf" />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <Stacked title="Robot activity" sub="Robot events per day per robot (robot_events) - grey = simulator" p={d.robots} y="Events" />
          <Stacked title="Robot movements completed" sub="Recorded movements with a path, per day (replayable on the robot pages)" p={d.robot_movements} y="Movements" />

          <ChartCard title="Consumables bin weight" sub="Daily lowest and highest weight on the scale (inventory_measurements)" empty={!d.bins.available} height={240}>
            <ResponsiveContainer>
              <LineChart data={d.bins.rows} margin={{ left: 4, right: 8, bottom: 4 }}>
                <CartesianGrid stroke="#1e3350" vertical={false} />
                <XAxis dataKey="day" tickFormatter={short} {...axisProps} {...xTitle('Day')} />
                <YAxis {...axisProps} {...yTitle('Grams', 52)} />
                <Tooltip {...tooltipProps} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line isAnimationActive={false} dataKey="max" name="Highest g" stroke="#2dd4bf" dot />
                <Line isAnimationActive={false} dataKey="min" name="Lowest g" stroke="#f59e0b" dot />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <Stacked title="Inventory transactions" sub="Withdrawals and refills recorded per day (inventory_transactions)" p={d.inventory_tx} y="Transactions" />
          <Stacked title="Security camera events" sub="Events per day by kind (security_events) - detections, not confirmed identities" p={d.cameras} y="Events" height={280} />
          <Stacked title="Lab PC usage" sub="Hours of PC sessions started each day (equipment_sessions)" p={d.pcs} y="Hours" />
          <Stacked title="Automation deliveries" sub="Events sent to n8n per day, by outcome (integration_events)" p={d.automation} y="Events" />
          <Stacked title="Alerts" sub="Alerts raised per day by severity (alerts)" p={d.alerts} y="Alerts" />
        </div>

        <details className="card p-4">
          <summary className="cursor-pointer text-[13px] font-semibold text-slate-200">How every number is calculated ({d.kpis.length} definitions)</summary>
          <table className="w-full mt-3 text-[12px]">
            <thead className="text-slate-400 text-left"><tr><th className="py-1">Metric</th><th>Rule</th><th>Unit</th><th>Source</th><th>Kind</th></tr></thead>
            <tbody>{d.kpis.map(k => <tr key={k.id} className="border-t border-ink-700/60 text-slate-300">
              <td className="py-1.5 pr-2 text-slate-100">{k.name}</td><td className="pr-2">{k.rule}</td><td className="pr-2">{k.unit}</td>
              <td className="pr-2 font-mono text-[11px]">{k.source}</td><td>{k.kind}</td></tr>)}</tbody>
          </table>
        </details>
      </>}
    </div>)
}
