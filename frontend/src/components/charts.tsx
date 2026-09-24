/**
 * Chart styling shared by the reports and maintenance analytics. Loaded only
 * with those pages (they are lazy), so Recharts stays out of the main bundle.
 */
import { ReactNode } from 'react'
import { BarChart3 } from 'lucide-react'
import { EmptyState } from './ui'

export const C = {
  grid: '#253a5a',
  axis: '#94a3b8',
  ok: '#10b981',
  bad: '#ef4444',
  warn: '#f59e0b',
  accent: '#38bdf8',
  teal: '#2dd4bf',
  violet: '#a78bfa',
}

export const PALETTE = ['#38bdf8', '#2dd4bf', '#a78bfa', '#818cf8', '#f0abfc', '#7dd3fc', '#5eead4', '#c4b5fd']

export const axisProps = {
  stroke: C.axis, fontSize: 11, tickLine: false, axisLine: false,
} as const

export const tooltipProps = {
  contentStyle: { background: '#0f1a2c', border: '1px solid #314a70', borderRadius: 10,
                  fontSize: 12, color: '#e2e8f0' },
  labelStyle: { color: '#cbd5e1' },
  cursor: { fill: 'rgba(56,189,248,0.06)' },
} as const

export function ChartCard({ title, sub, children, empty, height = 260, action }: {
  title: string; sub?: string; children: ReactNode; empty?: boolean; height?: number
  action?: ReactNode
}) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <div className="text-[14px] font-semibold text-slate-100">{title}</div>
          {sub && <div className="text-[12px] text-slate-400 mt-0.5">{sub}</div>}
        </div>
        {action}
      </div>
      {empty ? (
        <div style={{ minHeight: height }} className="grid place-items-center">
          <EmptyState compact icon={<BarChart3 size={18} />} title="Not enough data yet"
            detail="This chart fills in from real records as they accumulate." />
        </div>
      ) : <div style={{ height }}>{children}</div>}
    </div>
  )
}
