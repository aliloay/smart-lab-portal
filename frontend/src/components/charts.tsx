/**
 * Chart styling shared by the reports and maintenance analytics. Loaded only
 * with those pages (they are lazy), so Recharts stays out of the main bundle.
 */
import { ReactNode, useEffect, useRef, useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { EmptyState } from './ui'

export const C = {
  grid: '#33507a',
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
  contentStyle: { background: '#172841', border: '1px solid #41618f', borderRadius: 10,
                  fontSize: 12, color: '#e2e8f0' },
  labelStyle: { color: '#cbd5e1' },
  cursor: { fill: 'rgba(56,189,248,0.06)' },
} as const

export function ChartCard({ title, sub, children, empty, height = 260, action }: {
  title: string; sub?: string; children: ReactNode; empty?: boolean; height?: number
  action?: ReactNode
}) {
  // A chart is built only when its card comes near the screen (2026-10-20: System analytics built 12 charts at
  // once - a 643 ms main-thread block on opening the tab). Same height before and after: nothing jumps.
  const box = useRef<HTMLDivElement>(null)
  const [near, setNear] = useState(false)
  useEffect(() => {
    const el = box.current
    if (!el || near) return
    if (typeof IntersectionObserver === 'undefined') { setNear(true); return }
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { setNear(true); io.disconnect() } },
                                        { rootMargin: '300px 0px' })
    io.observe(el)
    return () => io.disconnect()
  }, [near])
  return (
    <div className="card p-5" ref={box}>
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
      ) : <div style={{ height }}>{near ? children : null}</div>}
    </div>
  )
}

// Axis titles (owner: every chart needs labelled X and Y axes).
export const xTitle = (value: string) => ({
  height: 38, label: { value, position: 'insideBottom' as const, offset: 0, fill: '#94a3b8', fontSize: 11 },
})
export const yTitle = (value: string, width = 44) => ({
  width, label: { value, angle: -90, position: 'insideLeft' as const, fill: '#94a3b8', fontSize: 11, style: { textAnchor: 'middle' as const } },
})
