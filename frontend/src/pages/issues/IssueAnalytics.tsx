import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import { BarChart3 } from 'lucide-react'
import type { IssueSummary } from '../../lib/api'
import { SectionTitle } from '../../components/ui'
import { C, ChartCard, PALETTE, axisProps, tooltipProps } from '../../components/charts'

/** Admin maintenance analytics. Real counts only; empty means empty. */
export default function IssueAnalytics({ summary }: { summary: IssueSummary | null }) {
  if (!summary) return null
  const hasTrend = summary.trend.some(t => t.created || t.resolved)
  return (
    <section>
      <SectionTitle icon={<BarChart3 size={15} />}
        sub={`${summary.total} issues recorded in total${summary.avg_resolution_hours != null
          ? ` · average resolution ${summary.avg_resolution_hours} h` : ''}`}>
        Laboratory maintenance analytics
      </SectionTitle>
      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="Reported vs resolved" sub="Last 30 days" empty={!hasTrend}>
          <ResponsiveContainer>
            <AreaChart data={summary.trend}>
              <defs>
                <linearGradient id="gCreated" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor={C.accent} stopOpacity={.35} />
                  <stop offset="1" stopColor={C.accent} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gResolved" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor={C.ok} stopOpacity={.35} />
                  <stop offset="1" stopColor={C.ok} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
              <XAxis dataKey="day" {...axisProps} tickFormatter={d => d.slice(5)} minTickGap={24} />
              <YAxis {...axisProps} allowDecimals={false} width={28} />
              <Tooltip {...tooltipProps} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="created" name="Reported" stroke={C.accent} fill="url(#gCreated)" strokeWidth={2} />
              <Area type="monotone" dataKey="resolved" name="Resolved" stroke={C.ok} fill="url(#gResolved)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Open issues by laboratory" empty={!summary.by_lab.length}>
          <ResponsiveContainer>
            <BarChart data={summary.by_lab}>
              <CartesianGrid stroke={C.grid} strokeDasharray="3 5" vertical={false} />
              <XAxis dataKey="label" {...axisProps} />
              <YAxis {...axisProps} allowDecimals={false} width={28} />
              <Tooltip {...tooltipProps} />
              <Bar dataKey="count" name="Open issues" radius={[6, 6, 0, 0]} fill={C.accent} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Open issues by category" empty={!summary.by_category.length}>
          <ResponsiveContainer>
            <BarChart data={summary.by_category} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid stroke={C.grid} strokeDasharray="3 5" horizontal={false} />
              <XAxis type="number" {...axisProps} allowDecimals={false} />
              <YAxis type="category" dataKey="label" {...axisProps} width={110} />
              <Tooltip {...tooltipProps} />
              <Bar dataKey="count" name="Issues" radius={[0, 6, 6, 0]}>
                {summary.by_category.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Most frequently reported equipment" sub="All time"
                   empty={!summary.by_asset.length}>
          <ResponsiveContainer>
            <BarChart data={summary.by_asset} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid stroke={C.grid} strokeDasharray="3 5" horizontal={false} />
              <XAxis type="number" {...axisProps} allowDecimals={false} />
              <YAxis type="category" dataKey="label" {...axisProps} width={150} />
              <Tooltip {...tooltipProps} />
              <Bar dataKey="count" name="Reports" radius={[0, 6, 6, 0]} fill={C.violet} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </section>
  )
}
