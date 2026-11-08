/**
 * Management report, printable: weekly (7 days) or monthly (30 days).
 *
 * Its own window, outside the portal frame, on white, laid out for A4:
 * "Save as PDF" is the browser's print dialog (Destination: Save as PDF),
 * so the PDF is exactly this page, charts included, with no PDF library.
 * Every figure comes from GET /ai/report (app.services.agent), counted from
 * the portal's records - the AI model is not involved.
 */
import { ReactNode, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Printer } from 'lucide-react'
import { ManagementReport, api } from '../lib/api'
import AiChart from '../components/AiChart'

const BAR = '#2a6fdb'      // one sequential hue; validated against the white surface

function pct(v: number | null | undefined) {
  if (v == null) return null
  return <span className={v >= 0 ? 'text-emerald-700' : 'text-rose-700'}>{v >= 0 ? '+' : ''}{v}%</span>
}

function Kpi({ label, value, change, sub }: { label: string; value: ReactNode; change?: number | null; sub?: ReactNode }) {
  return (
    <div className="border border-slate-200 rounded-lg px-3 py-2.5">
      <div className="text-[10.5px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="text-[22px] font-bold text-slate-900 tnum leading-tight">{value}</div>
      <div className="text-[11px] text-slate-500">{change !== undefined && pct(change)}
        {change !== undefined && change != null && ' vs previous'}{sub}</div>
    </div>
  )
}

/** Horizontal bars, one series: the title names it, values labelled at the bar end. */
function Bars({ rows, unit }: { rows: { label: string; value: number; note?: string }[]; unit: string }) {
  const max = Math.max(...rows.map(r => r.value), 0)
  if (!rows.length || max <= 0) return <p className="text-[12px] text-slate-500">Nothing recorded in this period.</p>
  return (
    <div className="space-y-1.5">
      {rows.map(r => (
        <div key={r.label} className="grid grid-cols-[110px_1fr] items-center gap-2 text-[12px]"
             title={`${r.label}: ${r.value} ${unit}${r.note ? ` - ${r.note}` : ''}`}>
          <span className="truncate text-slate-700">{r.label}</span>
          <div className="flex items-center gap-1.5 min-w-0">
            <div className="h-[10px] rounded-r" style={{ width: `${Math.max(1, (r.value / max) * 85)}%`, background: BAR }} />
            <span className="text-slate-800 tnum shrink-0">{r.value} {unit}</span>
          </div>
        </div>))}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="report-section mt-5">
      <h2 className="text-[13px] font-bold uppercase tracking-wider text-slate-700 border-b border-slate-200 pb-1 mb-2.5">
        {title}</h2>
      {children}
    </section>
  )
}

export default function ReportPrint() {
  const [params, setParams] = useSearchParams()
  const period = params.get('period') === 'monthly' ? 'monthly' : 'weekly'
  const [r, setR] = useState<ManagementReport | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    setR(null)
    api.managementReport(period).then(setR).catch(e => setError(e.message))
  }, [period])
  useEffect(() => { document.title = r ? `${r.title} ${r.period_label}` : 'Lab report' }, [r])
  // The portal's dark page background must not show around or below the sheet.
  useEffect(() => {
    const before = document.body.style.background
    document.body.style.background = '#f1f5f9'
    return () => { document.body.style.background = before }
  }, [])

  return (
    <div className="min-h-screen bg-slate-100 print:bg-white text-slate-900">
      <style>{`
        @page { size: A4; margin: 14mm; }
        @media print { .no-print { display: none !important; } .sheet { box-shadow: none !important; margin: 0 !important; padding: 0 !important; max-width: none !important; }
          .report-section { break-inside: avoid; } body { background: white !important; } }
      `}</style>
      <div className="no-print sticky top-0 z-10 bg-white border-b border-slate-200 px-4 py-2.5 flex items-center gap-2">
        <div className="flex rounded-lg border border-slate-300 overflow-hidden text-[13px]">
          {(['weekly', 'monthly'] as const).map(p => (
            <button key={p} onClick={() => setParams({ period: p })}
              className={`px-3 py-1.5 ${p === period ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'}`}>
              {p === 'weekly' ? 'Weekly' : 'Monthly'}</button>))}
        </div>
        <button onClick={() => window.print()} disabled={!r}
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-slate-900 text-white px-3 py-1.5 text-[13px] disabled:opacity-40">
          <Printer size={14} /> Save as PDF</button>
      </div>

      <main className="sheet max-w-[820px] mx-auto my-6 bg-white shadow-sm px-10 py-8">
        {error && <p className="text-rose-700">{error}</p>}
        {!r ? !error && <p className="text-slate-500">Preparing the report…</p> : (<>
          <header className="flex items-end justify-between border-b-2 border-slate-900 pb-2">
            <div>
              <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">GIU Smart Lab · Management</div>
              <h1 className="text-[24px] font-extrabold leading-tight">{r.title}</h1>
            </div>
            <div className="text-right text-[12px] text-slate-600">
              <div className="font-semibold text-slate-900">{r.period_label}</div>
              <div>{r.span}, compared with the {r.span} before</div>
            </div>
          </header>

          <Section title="Summary">
            <ul className="text-[12.5px] text-slate-800 space-y-0.5 list-disc pl-4">
              {r.lines.map(l => <li key={l}>{l}</li>)}
            </ul>
          </Section>

          <div className="report-section grid grid-cols-4 gap-2 mt-4">
            <Kpi label="Bookings" value={r.bookings.confirmed} change={r.change_pct.bookings} />
            <Kpi label="Booked hours" value={r.bookings.booked_hours} change={r.change_pct.hours} />
            <Kpi label="Attendance" value={r.bookings.attendance_rate == null ? 'No data' : `${Math.round(r.bookings.attendance_rate * 100)}%`}
                 sub={`${r.bookings.no_show} no-show`} />
            <Kpi label="Door entries" value={r.access.granted} change={r.change_pct.entries}
                 sub={`${r.change_pct.entries != null ? ' · ' : ''}${r.access.denied} refused`} />
            <Kpi label="Issues opened" value={r.maintenance.opened} sub={`${r.maintenance.resolved} resolved`} />
            <Kpi label="Open now" value={r.maintenance.open_now} sub={`${r.maintenance.critical_open} critical · ${r.maintenance.overdue_now} overdue`} />
            <Kpi label="Alerts" value={r.alerts.opened} />
            <Kpi label="Security" value={r.access.identity_mismatch + r.access.forced_entry + r.access.door_held_open}
                 sub={`${r.access.forced_entry} forced · ${r.access.door_held_open} held open`} />
          </div>

          {!!r.charts?.length && (
            <Section title="Charts">
              <div className="grid grid-cols-2 gap-3">
                {r.charts.map((c, i) => <AiChart key={i} chart={c} light />)}
              </div>
            </Section>)}

          <div className="grid grid-cols-2 gap-6">
            <Section title="Booked hours by lab">
              <Bars unit="h" rows={r.labs.filter(l => l.hours > 0).slice(0, 10)
                .map(l => ({ label: l.lab_code, value: l.hours, note: `${l.bookings} bookings, ${l.attended} attended` }))} />
            </Section>
            <Section title="Equipment running time">
              <Bars unit="h" rows={r.equipment.filter(e => e.running_h > 0).slice(0, 10)
                .map(e => ({ label: e.name, value: e.running_h, note: `${e.lab_code ?? ''}, ${e.faults} faults` }))} />
            </Section>
          </div>

          {r.equipment.length > 0 && (
            <Section title="Robots and PCs">
              <table className="w-full text-[12px]">
                <thead><tr className="text-left text-slate-500 border-b border-slate-200">
                  <th className="py-1 font-medium">Equipment</th><th className="font-medium">Lab</th>
                  <th className="font-medium text-right">Running</th><th className="font-medium text-right">Idle</th>
                  <th className="font-medium text-right">Faults</th><th className="font-medium text-right">Users</th></tr></thead>
                <tbody>{r.equipment.map(e => (
                  <tr key={e.device_uid} className="border-b border-slate-100">
                    <td className="py-1">{e.name}{e.master_pc && <span className="text-slate-500"> (master PC)</span>}</td>
                    <td>{e.lab_code}</td><td className="text-right tnum">{e.running_h} h</td>
                    <td className="text-right tnum">{e.idle_h} h</td>
                    <td className={`text-right tnum ${e.faults ? 'text-rose-700 font-semibold' : ''}`}>{e.faults}</td>
                    <td className="text-right tnum">{e.users}</td></tr>))}</tbody>
              </table>
            </Section>)}

          <Section title="Needs attention - repeated problems and what to do">
            {!r.insights.length ? <p className="text-[12.5px] text-slate-600">Nothing repeated enough to flag in this period.</p> : (
              <ol className="space-y-2 text-[12.5px] list-decimal pl-4">
                {r.insights.map((i, n) => (
                  <li key={n}>
                    <span className="font-semibold text-slate-900">{i.title}</span>
                    {i.lab_code && <span className="text-slate-500"> · {i.lab_code}</span>}
                    <span className="text-slate-500"> · {i.count}x</span>
                    {i.last && <span className="text-slate-500"> · {i.ongoing ? 'still happening' : 'not seen since'} {i.last}</span>}
                    {!!i.unresolved && <span className="text-slate-500"> · {i.unresolved} still open</span>}
                    {i.steps ? (<>
                      <div className="text-slate-700"><span className="font-semibold">Likely cause:</span> {i.cause}</div>
                      <ol className="list-[lower-alpha] pl-5 text-slate-700">
                        {i.steps.map((st, k) => <li key={k}>{st}</li>)}</ol>
                      <div className="text-slate-700"><span className="font-semibold">Done when:</span> {i.done_when}</div>
                    </>) : <div className="text-slate-700">→ {i.recommendation}</div>}
                  </li>))}
              </ol>)}
          </Section>

          {r.top_denials.length > 0 && (
            <Section title="Why the door refused">
              <table className="w-full text-[12px]"><tbody>
                {r.top_denials.map(d => (
                  <tr key={d.reason} className="border-b border-slate-100">
                    <td className="py-1 tnum w-10 font-semibold">{d.count}</td>
                    <td className="text-slate-800">{d.meaning}</td></tr>))}
              </tbody></table>
            </Section>)}

          {r.devices.offline_now.length > 0 && (
            <Section title="Offline at the time of this report">
              <p className="text-[12.5px] text-slate-800">{r.devices.offline_now.join(', ')}</p>
            </Section>)}

          <footer className="mt-6 pt-2 border-t border-slate-200 text-[10.5px] text-slate-500 flex justify-between">
            <span>Counted from the portal's records; nothing estimated.</span>
            <span>Generated {new Date(r.generated_at).toLocaleString()}</span>
          </footer>
        </>)}
      </main>
    </div>
  )
}
