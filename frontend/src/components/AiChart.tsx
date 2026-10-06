/**
 * A chart the assistant answered with (data from the records, drawn here with
 * the portal's own chart styling), and "Save image" for a PNG of it.
 * Loaded lazily by the chat, so Recharts stays out of the main bundle.
 */
import { useRef } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Download } from 'lucide-react'
import type { AiChartData } from '../lib/api'
import { C, axisProps, tooltipProps } from './charts'

/** light: on the white printable report (dark text, light grid, no Save button in print). */
export default function AiChart({ chart, light = false }: { chart: AiChartData; light?: boolean }) {
  const axis = light ? { ...axisProps, stroke: '#475569' } : axisProps
  const grid = light ? '#e2e8f0' : C.grid
  const box = useRef<HTMLDivElement>(null)
  const total = chart.series.reduce((n, s) => n + s.data.reduce((a, b) => a + b, 0), 0)
  const rows = chart.x.map((x, i) =>
    Object.fromEntries([['x', x], ...chart.series.map(s => [s.name, s.data[i] ?? 0])]))
  const pie = chart.x.map((name, i) => ({ name, value: chart.series[0]?.data[i] ?? 0 }))
  return (
    <div className={light ? 'report-section border border-slate-200 rounded-lg p-3'
                          : 'mt-3 rounded-xl border border-ink-600/70 bg-ink-900/50 p-3'}>
      <div className="flex items-center gap-2 mb-2">
        <div className={`text-[13px] font-semibold ${light ? 'text-slate-900' : 'text-slate-100'}`}>{chart.title}</div>
        {total > 0 && (
          <button onClick={() => savePng(box.current, chart.title)}
                  className="no-print ml-auto inline-flex items-center gap-1 text-[11.5px] text-accent-300 hover:text-accent-200">
            <Download size={12} /> Save image</button>)}
      </div>
      <div ref={box} style={{ height: 230 }}>
        {total === 0 ? (
          <div className="h-full grid place-items-center text-[12.5px] text-slate-500">Nothing recorded in this period.</div>
        ) : (
          <ResponsiveContainer>
            {chart.kind === 'pie' ? (
              <PieChart>
                <Pie data={pie} dataKey="value" nameKey="name" innerRadius={45} outerRadius={85} paddingAngle={2}
                     isAnimationActive={!light}>
                  {pie.map((_, i) => <Cell key={i} fill={chart.series[0].colors?.[i] ?? chart.series[0].color} />)}
                </Pie>
                <Tooltip {...tooltipProps} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            ) : (
              <BarChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={grid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="x" {...axis} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} width={28} {...axis} />
                <Tooltip {...tooltipProps} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {chart.series.map(s => (
                  <Bar key={s.name} dataKey={s.name} fill={s.color} radius={[3, 3, 0, 0]} isAnimationActive={!light}
                       stackId={chart.stacked ? 'all' : undefined} />))}
              </BarChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

/** The chart's SVG drawn on a canvas with its title, downloaded as a PNG. */
function savePng(el: HTMLDivElement | null, title: string) {
  const svg = el?.querySelector('svg.recharts-surface') as SVGSVGElement | null
  if (!svg) return
  const copy = svg.cloneNode(true) as SVGSVGElement
  copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  const { width, height } = svg.getBoundingClientRect()
  const img = new Image()
  img.onload = () => {
    const k = 2, head = 36
    const c = document.createElement('canvas')
    c.width = width * k
    c.height = (height + head) * k
    const g = c.getContext('2d')!
    g.fillStyle = '#0f1b2d'
    g.fillRect(0, 0, c.width, c.height)
    g.fillStyle = '#e2e8f0'
    g.font = `600 ${14 * k}px system-ui, sans-serif`
    g.fillText(title, 12 * k, 24 * k)
    g.drawImage(img, 0, head * k, width * k, height * k)
    c.toBlob(b => {
      if (!b) return
      const a = document.createElement('a')
      a.href = URL.createObjectURL(b)
      a.download = `${title.replace(/[^\w-]+/g, '_')}.png`
      a.click()
      window.setTimeout(() => URL.revokeObjectURL(a.href), 2000)
    })
  }
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(copy))
}
