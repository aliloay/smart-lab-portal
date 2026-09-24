import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../lib/api'
import { Empty, SectionTitle, Spinner } from '../components/ui'

interface Row { lab: string; day: string; event: string; count: number }

export default function AdminReports() {
  const [rows, setRows] = useState<Row[]>([])
  const [days, setDays] = useState(7)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.accessReport(days).then(setRows).finally(() => setLoading(false))
  }, [days])

  // Pivot to one record per day. Only days that actually have events appear -
  // the series is never padded with zeros to make the chart look busier.
  const byDay = new Map<string, { day: string; granted: number; denied: number }>()
  for (const r of rows) {
    const d = byDay.get(r.day) ?? { day: r.day, granted: 0, denied: 0 }
    if (r.event === 'ACCESS_GRANTED') d.granted += r.count
    if (r.event === 'ACCESS_DENIED') d.denied += r.count
    byDay.set(r.day, d)
  }
  const chart = [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day))
  const totals = chart.reduce((a, c) => ({
    granted: a.granted + c.granted, denied: a.denied + c.denied }), { granted: 0, denied: 0 })

  return (
    <div>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Reports</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Access outcomes aggregated from recorded events.
          </p>
        </div>
        <select className="input w-auto" value={days}
                onChange={e => setDays(Number(e.target.value))}>
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
        </select>
      </div>

      {loading ? <Spinner /> : chart.length === 0 ? (
        <div className="card mt-6">
          <Empty title="No access events in this period"
                 detail="Charts appear once the door records activity." />
        </div>
      ) : (
        <>
          <div className="grid sm:grid-cols-3 gap-4 mt-6">
            <div className="card-pad">
              <div className="label">Granted</div>
              <div className="mt-2 text-3xl font-semibold text-ok tabular-nums">
                {totals.granted}
              </div>
            </div>
            <div className="card-pad">
              <div className="label">Denied</div>
              <div className="mt-2 text-3xl font-semibold text-bad tabular-nums">
                {totals.denied}
              </div>
            </div>
            <div className="card-pad">
              <div className="label">Denial rate</div>
              <div className="mt-2 text-3xl font-semibold text-slate-100 tabular-nums">
                {totals.granted + totals.denied === 0 ? '—' :
                  `${Math.round(100 * totals.denied / (totals.granted + totals.denied))}%`}
              </div>
            </div>
          </div>

          <div className="mt-7">
            <SectionTitle>Daily outcomes</SectionTitle>
            <div className="card p-5">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2a40" vertical={false} />
                  <XAxis dataKey="day" stroke="#64748b" fontSize={11} tickLine={false} />
                  <YAxis stroke="#64748b" fontSize={11} tickLine={false}
                         axisLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={{
                    background: '#0f1624', border: '1px solid #2a3852',
                    borderRadius: 6, fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="granted" name="Granted" fill="#10b981" radius={[3,3,0,0]} />
                  <Bar dataKey="denied"  name="Denied"  fill="#ef4444" radius={[3,3,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
