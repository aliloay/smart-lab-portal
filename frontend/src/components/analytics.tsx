/**
 * Small, dependency-free visualisations shared by the Operations Center, the
 * lab digital twin and the student dashboard. Plain SVG/CSS so pages that
 * only need a heatmap or a sparkline do not pull Recharts into their chunk.
 *
 * Every component draws what it is given and nothing else: an all-zero
 * matrix renders the empty state, a series with no points is not drawn.
 */
import { ReactNode } from 'react'
import { Thermometer } from 'lucide-react'
import { EnvironmentBlock, EnvSeries } from '../lib/api'
import { fmtTime, relative } from '../lib/time'
import { EmptyState } from './ui'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** Weekday x hour matrix. `unit` names what a cell counts. */
export function Heatmap({ data, unit, fromHour = 6, toHour = 23, tone = 'accent' }: {
  data: number[][]; unit: string; fromHour?: number; toHour?: number
  tone?: 'accent' | 'teal' | 'violet'
}) {
  const max = Math.max(0, ...data.flat())
  if (!max) {
    return <EmptyState compact title="No data in this period"
      detail="The heatmap fills in from recorded bookings and entries." />
  }
  const rgb = tone === 'teal' ? '45,212,191' : tone === 'violet' ? '167,139,250' : '56,189,248'
  const hours = Array.from({ length: toHour - fromHour + 1 }, (_, i) => fromHour + i)
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-[3px] min-w-full"
           style={{ gridTemplateColumns: `34px repeat(${hours.length}, minmax(16px, 1fr))` }}>
        <span />
        {hours.map(h => (
          <span key={h} className="text-[10px] text-slate-500 text-center tnum">
            {h % 3 === 0 ? String(h).padStart(2, '0') : ''}
          </span>
        ))}
        {DAYS.map((d, wd) => (
          <Row key={d} label={d}>
            {hours.map(h => {
              const v = data[wd]?.[h] ?? 0
              const a = v ? 0.12 + 0.88 * (v / max) : 0
              return (
                <span key={h} role="img"
                  aria-label={`${d} ${String(h).padStart(2, '0')}:00 - ${fmtNum(v)} ${unit}`}
                  title={`${d} ${String(h).padStart(2, '0')}:00 · ${fmtNum(v)} ${unit}`}
                  className="h-5 rounded-[4px] border border-ink-600/40 transition-transform hover:scale-110"
                  style={{ background: v ? `rgba(${rgb},${a})` : 'rgba(39,62,98,0.35)' }} />
              )
            })}
          </Row>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-500">
        <span>less</span>
        {[0.15, 0.35, 0.6, 0.85, 1].map(a => (
          <span key={a} className="w-4 h-3 rounded-sm" style={{ background: `rgba(${rgb},${a})` }} />
        ))}
        <span>more · peak {fmtNum(max)} {unit}</span>
      </div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return <>
    <span className="text-[11px] text-slate-400 self-center">{label}</span>
    {children}
  </>
}

const fmtNum = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1))

/** Stepwise funnel; each bar is relative to the first step. */
export function Funnel({ steps }: { steps: { step: string; count: number }[] }) {
  const top = steps[0]?.count ?? 0
  if (!steps.some(s => s.count)) {
    return <EmptyState compact title="No door activity in this period"
      detail="Credential scans, identity checks and door openings appear here." />
  }
  return (
    <ol className="space-y-2.5">
      {steps.map((s, i) => {
        const pct = top ? s.count / top : 0
        const prev = i ? steps[i - 1].count : null
        const drop = prev ? 1 - s.count / prev : null
        return (
          <li key={s.step}>
            <div className="flex items-baseline justify-between text-[12.5px]">
              <span className="text-slate-300">{s.step}</span>
              <span className="tnum text-slate-100 font-medium">{s.count}
                {drop !== null && drop > 0 && (
                  <span className="ml-2 text-[11px] text-slate-500">−{Math.round(drop * 100)}%</span>)}
              </span>
            </div>
            <div className="mt-1 h-2.5 rounded-full bg-ink-700/60 overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-accent-500 to-teal-400"
                   style={{ width: `${Math.max(pct * 100, s.count ? 2 : 0)}%` }} />
            </div>
          </li>
        )
      })}
      <li className="text-[11.5px] text-slate-500 pt-1">
        Step counts come from separate events and can exceed the step before them - a
        biometric retry is counted each time it is recorded.
      </li>
    </ol>
  )
}

/** One metric as a sparkline with its threshold band. */
export function Sparkline({ s, height = 46 }: { s: EnvSeries; height?: number }) {
  const pts = s.points
  if (pts.length < 2) {
    return <div className="text-[11.5px] text-slate-500">One reading so far - a trend needs two.</div>
  }
  const xs = pts.map(p => new Date(p.t).getTime())
  const ys = pts.map(p => p.v)
  const lo = Math.min(...ys, s.min ?? Infinity), hi = Math.max(...ys, s.max ?? -Infinity)
  const x0 = Math.min(...xs), x1 = Math.max(...xs)
  const W = 240
  const px = (x: number) => ((x - x0) / Math.max(x1 - x0, 1)) * W
  const py = (y: number) => height - 4 - ((y - lo) / Math.max(hi - lo, 1e-9)) * (height - 8)
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${px(xs[i]).toFixed(1)},${py(p.v).toFixed(1)}`).join('')
  return (
    <svg viewBox={`0 0 ${W} ${height}`} className="w-full" style={{ height }} aria-hidden>
      {s.max !== null && <line x1={0} x2={W} y1={py(s.max)} y2={py(s.max)}
        stroke="#f59e0b" strokeDasharray="3 4" strokeWidth={1} opacity={0.6} />}
      {s.min !== null && <line x1={0} x2={W} y1={py(s.min)} y2={py(s.min)}
        stroke="#f59e0b" strokeDasharray="3 4" strokeWidth={1} opacity={0.6} />}
      <path d={d} fill="none" stroke="#2dd4bf" strokeWidth={2} strokeLinejoin="round" />
    </svg>
  )
}

const METRIC_LABEL: Record<string, string> = {
  temperature: 'Temperature', humidity: 'Humidity', co2: 'CO₂', noise: 'Noise',
}

/** Environment readings, or an honest "Awaiting sensor data". */
export function EnvironmentPanel({ env, compact = false }: { env: EnvironmentBlock | null; compact?: boolean }) {
  if (!env || !env.has_data) {
    return (
      <EmptyState compact icon={<Thermometer size={18} />} title="Awaiting sensor data"
        detail={compact ? 'No sensor node has reported for this laboratory.'
          : 'No sensor node has reported yet. Readings posted to /api/access/telemetry appear here within seconds - nothing is simulated.'} />
    )
  }
  return (
    <div className={`grid gap-3 ${compact ? 'sm:grid-cols-2' : 'sm:grid-cols-2 xl:grid-cols-4'}`}>
      {env.series.map(s => {
        const out = (s.max !== null && s.latest > s.max) || (s.min !== null && s.latest < s.min)
        return (
          <div key={s.metric} className={`rounded-xl border p-3.5 ${out
            ? 'border-warn/40 bg-warn/5' : 'border-ink-600/70 bg-ink-800/40'}`}>
            <div className="flex items-baseline justify-between">
              <span className="label">{METRIC_LABEL[s.metric] ?? s.metric}</span>
              <span className="text-[11px] text-slate-500" title={new Date(s.latest_at).toLocaleString()}>
                {relative(s.latest_at)}
              </span>
            </div>
            <div className={`mt-1 font-display text-2xl ${out ? 'text-warn-soft' : 'text-white'}`}>
              {fmtNum(s.latest)}<span className="text-sm text-slate-400 ml-0.5">{s.unit}</span>
            </div>
            <div className="text-[11px] text-slate-500 mb-1.5">
              {s.min !== null || s.max !== null
                ? `Range ${s.min ?? '−'} – ${s.max ?? '−'} ${s.unit}` : 'No threshold configured'}
              {' · '}{s.points.length} readings / {env.hours} h
            </div>
            <Sparkline s={s} />
          </div>
        )
      })}
    </div>
  )
}

/** Horizontal bar over the period with the observed outages cut out. */
export function OutageStrip({ outages, days, state }: {
  outages: { from: string; to: string }[]; days: number
  state: 'ONLINE' | 'OFFLINE' | 'NO_DATA'
}) {
  if (state === 'NO_DATA') {
    return <div className="h-2.5 rounded-full bg-ink-700/50" title="Never reported" />
  }
  const end = Date.now(), start = end - days * 864e5
  return (
    <div className="relative h-2.5 rounded-full bg-ok/40 overflow-hidden"
         title={outages.length ? `${outages.length} observed outage(s)` : 'No outage observed'}>
      {outages.map((o, i) => {
        const a = Math.max(new Date(o.from).getTime(), start)
        const b = Math.min(new Date(o.to).getTime(), end)
        if (b <= a) return null
        return <span key={i} className="absolute inset-y-0 bg-bad"
          title={`${fmtTime(o.from)} → ${fmtTime(o.to)}`}
          style={{ left: `${((a - start) / (end - start)) * 100}%`,
                   width: `${Math.max(((b - a) / (end - start)) * 100, 0.6)}%` }} />
      })}
    </div>
  )
}
