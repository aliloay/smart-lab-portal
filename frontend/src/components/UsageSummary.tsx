/**
 * Lab usage in plain words (replaces the day strip + hour heat map on the lab page, 2026-10-15:
 * owner found them hard to read). Same data (labs twin endpoint): three key numbers and one
 * labelled bar chart - average hours booked on each weekday, value written on every bar.
 */
const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const fmtH = (h: number) => (h >= 10 ? h.toFixed(0) : h.toFixed(1)) + ' h'

export default function UsageSummary({ heatmap, daysStrip, days }: {
  heatmap: number[][]; daysStrip: { day: string; booked_hours: number }[]; days: number
}) {
  const perDay = DAYS.map((_, d) => (heatmap[d] ?? []).reduce((a, b) => a + b, 0))
  const perHour = Array.from({ length: 24 }, (_, h) => DAYS.reduce((a, _d, d) => a + (heatmap[d]?.[h] ?? 0), 0))
  const max = Math.max(...perDay, 0.01)
  const busiestDay = perDay.indexOf(Math.max(...perDay))
  const busiestHour = perHour.indexOf(Math.max(...perHour))
  const today = new Date().toISOString().slice(0, 10)
  const total = daysStrip.filter(d => d.day <= today).reduce((a, d) => a + d.booked_hours, 0)
  const ahead = daysStrip.filter(d => d.day > today).reduce((a, d) => a + d.booked_hours, 0)
  const none = perDay.every(v => v === 0)
  return (
    <div className="space-y-5">
      <div className="grid sm:grid-cols-3 gap-3">
        {[[fmtH(total), 'booked in the last weeks shown'], [fmtH(ahead), 'already booked ahead'],
          [none ? '-' : `${DAYS[busiestDay]} · ${String(busiestHour).padStart(2, '0')}:00`, 'busiest day and hour']].map(([v, l]) => (
          <div key={l} className="rounded-xl border border-ink-600/70 bg-ink-900/40 p-3">
            <div className="text-xl font-semibold text-white">{v}</div>
            <div className="text-[12px] text-slate-400">{l}</div>
          </div>))}
      </div>
      <div>
        <div className="text-[13px] font-medium text-slate-200">Average hours booked per weekday</div>
        <div className="text-[11.5px] text-slate-500 mb-3">last {days} days · longer bar = busier day</div>
        {none ? <p className="text-[12.5px] text-slate-400">No bookings in this period yet.</p> : (
          <div className="space-y-1.5">
            {DAYS.map((d, i) => (
              <div key={d} className="grid grid-cols-[86px_1fr_52px] items-center gap-2 text-[12.5px]">
                <span className="text-slate-300">{d}</span>
                <div className="h-5 rounded-md bg-ink-800/70 overflow-hidden">
                  <div className={`h-full rounded-md ${i === busiestDay ? 'bg-cyan-400' : 'bg-cyan-600/70'}`}
                       style={{ width: `${(perDay[i] / max) * 100}%` }} />
                </div>
                <span className="text-right tabular-nums text-slate-200">{fmtH(perDay[i])}</span>
              </div>))}
          </div>)}
      </div>
    </div>)
}
