/**
 * Sensor and asset analytics: every stored measurement with its age and quality, a history that shows gaps as gaps, the
 * same period before it, and the sensors that do not exist yet (named, never charted). Reads /api/metrics only.
 */
import { useEffect, useMemo, useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Download } from 'lucide-react'
import { MetricDef, MetricHistory, MetricLatest, api } from '../lib/api'
import { C, ChartCard, axisProps, tooltipProps, xTitle, yTitle } from '../components/charts'
import { fmtDateTime, relative } from '../lib/time'
import { csv } from '../lib/metricCsv'
import { visibleInterval } from '../lib/visibleInterval'
import { Chip, EmptyState, ErrorBanner, MetricCard, PageHeader, SectionTitle, Select, Spinner } from '../components/ui'

const Q: Record<string, ['ok' | 'warn' | 'bad' | 'idle', string]> = {
  VALID: ['ok', 'valid'], STALE: ['warn', 'stale'], DEVICE_OFFLINE: ['bad', 'device offline'],
  OUT_OF_RANGE: ['bad', 'out of range'], UNREGISTERED: ['idle', 'not registered'] }
const PERIODS: [string, string][] = [['24h', '24 hours'], ['7d', '7 days'], ['30d', '30 days'], ['90d', '90 days']]
const num = (v: number | null | undefined, unit = '') => v == null ? null : `${Math.round(v * 100) / 100}${unit ? ' ' + unit : ''}`
const shown = (r: MetricLatest) => r.kind === 'state' ? (r.value ? 'yes' : 'no') : num(r.value, r.unit)

export default function SensorAnalytics() {
  const [rows, setRows] = useState<MetricLatest[] | null>(null)
  const [defs, setDefs] = useState<MetricDef[]>([])
  const [error, setError] = useState('')
  const [group, setGroup] = useState('all')
  const [sel, setSel] = useState<string | null>(null)
  const [period, setPeriod] = useState('7d')
  const [h, setH] = useState<MetricHistory | null>(null)
  const [hErr, setHErr] = useState('')

  useEffect(() => {
    const load = () => { api.metricLatest().then(r => { setRows(r); setError('') }).catch(e => setError(e.message)) }
    load(); api.metricRegistry().then(setDefs).catch(() => {})
    const t = visibleInterval(load, 30000)
    return () => window.clearInterval(t)
  }, [])
  const list = useMemo(() => (rows ?? []).filter(r => group === 'all' || r.group === group), [rows, group])
  const cur = list.find(r => r.sensor_id === sel) ?? list.find(r => r.metric_name === 'temperature' && !r.metadata.simulated) ?? list.find(r => r.metric_name === 'temperature') ?? list[0] ?? null
  const registered = cur ? cur.quality !== 'UNREGISTERED' : false
  const devId = cur?.device_id, metric = cur?.metric_name
  useEffect(() => {
    setH(null); setHErr('')
    if (devId == null || !metric || !registered) return
    let on = true
    api.metricHistory(devId, metric, period).then(r => on && setH(r)).catch(e => on && setHErr(e.message))
    return () => { on = false }
  }, [devId, metric, period, registered])

  const groups: [string, string][] = [['all', 'All groups'], ...[...new Set((rows ?? []).map(r => r.group))].sort().map(g => [g, g] as [string, string])]
  const data = useMemo(() => h?.series.map(s => ({ ...s, range: s.min == null ? null : [s.min, s.max] })) ?? [], [h])
  const planned = defs.filter(d => d.status === 'PLANNED' && !rows?.some(r => r.metric_name === d.name))
  const save = () => {
    if (!h || !cur) return
    const url = URL.createObjectURL(new Blob([csv(h, cur)], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url; a.download = `${cur.device_uid}_${cur.metric_name}_${h.period}.csv`; a.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const day = period === '24h'
  const tick = (t: string) => { const d = new Date(t); return day ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : d.toLocaleDateString([], { day: '2-digit', month: 'short' }) }
  const unit = cur?.unit ?? ''
  const valid = list.filter(r => r.quality === 'VALID').length

  return (
    <>
      <PageHeader eyebrow="Intelligence" title="Sensor analytics"
        sub="Stored measurements with their age, quality and calibration state. Indicators here are not certified safety instruments." />
      {error && <div className="mb-4"><ErrorBanner title={rows ? 'Update failed: showing the last good values' : 'Could not read the measurements'} message={error} /></div>}
      {!rows && !error && <Spinner label="Reading the measurements" />}
      {rows?.length === 0 && <EmptyState title="No measurements stored" detail="No device has stored a reading in the last 90 days." />}
      {rows && rows.length > 0 && <>
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="w-full sm:w-44"><Select label="Group" value={group} onChange={setGroup} options={groups} /></div>
          <div className="w-full sm:w-80"><Select label="Measurement" value={cur?.sensor_id ?? ''} onChange={setSel}
            options={list.map(r => [r.sensor_id, `${r.label} · ${r.device_uid}`])} /></div>
          <div className="w-full sm:w-36"><Select label="Period" value={period} onChange={setPeriod} options={PERIODS} /></div>
          <button className="btn-ghost btn-sm self-end" disabled={!h?.stats.n} onClick={save}><Download size={13} /> CSV</button>
        </div>
        {cur && <div className="flex flex-wrap items-center gap-2 mb-4 text-[12.5px] text-slate-400">
          <Chip tone={Q[cur.quality]?.[0] ?? 'idle'} dot>{Q[cur.quality]?.[1] ?? cur.quality}</Chip>
          {cur.metadata.simulated && <Chip tone="violet">simulated</Chip>}
          <span>{relative(cur.timestamp)} · source {cur.source || 'unknown'} · {cur.calibration_status} · provenance {cur.metadata.provenance ?? 'not recorded'}</span></div>}
        {hErr && <ErrorBanner message={hErr} />}
        {cur && !registered && <p className="text-[13px] text-slate-400">This metric is not in the registry, so it has no unit or range and is not charted.</p>}
        {registered && !h && !hErr && <Spinner label="Reading the history" />}
        {h && cur && <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5 mb-4">
            <MetricCard label="Last value" animate={false} value={shown(cur)} hint={cur.quality === 'VALID' ? 'current' : `${relative(cur.timestamp)}, not current`} tone={cur.quality === 'VALID' ? 'idle' : 'warn'} />
            <MetricCard label={cur.kind === 'state' ? 'Share of readings "yes"' : 'Average'} animate={false}
              value={cur.kind === 'state' ? (h.stats.avg == null ? null : `${Math.round(h.stats.avg * 1000) / 10} %`) : num(h.stats.avg, unit)}
              hint={h.previous.avg == null ? 'no data in the period before' : `before: ${cur.kind === 'state' ? Math.round(h.previous.avg * 1000) / 10 + ' %' : num(h.previous.avg, unit)}`} />
            <MetricCard label="Lowest / highest" animate={false} value={h.stats.n && cur.kind !== 'state' ? `${num(h.stats.min)} / ${num(h.stats.max)}` : null} hint={unit || undefined} />
            <MetricCard label="Coverage" animate={false} value={`${h.coverage_pct} %`} hint={`${h.gap_count} gap${h.gap_count === 1 ? '' : 's'} of at least ${h.bucket_s / 60} min`} tone={h.coverage_pct < 50 ? 'warn' : 'idle'} />
            <MetricCard label="Change per hour" animate={false} value={num(h.change_per_hour, unit)} hint="last two neighbouring buckets; not a forecast" />
          </div>
          <ChartCard title={`${cur.label}${unit ? ` (${unit})` : ''} - ${cur.device_name}`} height={300} empty={!h.stats.n}
            sub={`Average per ${h.bucket_s / 60} min${cur.kind === 'state' ? '' : ' with lowest-highest band'}. An empty stretch means no stored reading; nothing is filled in.${h.stats.rejected ? ` ${h.stats.rejected} impossible value(s) left out.` : ''}`}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
                <CartesianGrid stroke={C.grid} strokeOpacity={0.35} vertical={false} />
                <XAxis dataKey="t" {...axisProps} tickFormatter={tick} minTickGap={40} {...xTitle('Time')} />
                <YAxis {...axisProps} domain={cur.kind === 'state' ? [0, 1] : ['auto', 'auto']} {...yTitle(unit || 'value', 54)} />
                <Tooltip {...tooltipProps} labelFormatter={t => fmtDateTime(String(t))}
                  formatter={(v: unknown, n: unknown) => [Array.isArray(v) ? `${num(v[0])} to ${num(v[1])} ${unit}` : `${num(v as number)} ${unit}`, n === 'range' ? 'lowest to highest' : 'average']} />
                {cur.kind !== 'state' && <Area dataKey="range" stroke="none" fill={C.accent} fillOpacity={0.16} isAnimationActive={false} connectNulls={false} />}
                <Line dataKey="avg" stroke={C.accent} strokeWidth={2} dot={data.length < 60 ? { r: 2 } : false} isAnimationActive={false} connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </ChartCard>
        </>}

        <div className="mt-6"><SectionTitle sub={`${valid} of ${list.length} are valid now. Choose a row to chart it.`}>All measurements</SectionTitle>
          <div className="card overflow-x-auto"><table className="w-full text-[12.5px] min-w-[640px]">
            <thead className="text-left text-slate-400"><tr>{['Measurement', 'Device', 'Last value', 'Quality', 'Age', 'Calibration'].map(x => <th key={x} className="px-4 py-2 font-medium">{x}</th>)}</tr></thead>
            <tbody>{list.map(r => (
              <tr key={r.sensor_id} className={`border-t border-ink-600/50 ${r.sensor_id === cur?.sensor_id ? 'bg-accent-400/[0.07]' : ''}`}>
                <td className="px-4 py-1.5"><button className="text-left text-slate-100 hover:text-accent-300 min-h-[32px]" onClick={() => { setSel(r.sensor_id); window.scrollTo({ top: 0 }) }}>{r.label}</button></td>
                <td className="px-4 mono text-slate-400">{r.device_uid}{r.metadata.simulated ? ' (simulated)' : ''}</td><td className="px-4 tnum text-slate-200">{shown(r)}</td>
                <td className="px-4"><Chip tone={Q[r.quality]?.[0] ?? 'idle'}>{Q[r.quality]?.[1] ?? r.quality}</Chip></td>
                <td className="px-4 text-slate-400">{relative(r.timestamp)}</td><td className="px-4 text-slate-400">{r.calibration_status}</td></tr>))}</tbody></table></div></div>
      </>}
      {planned.length > 0 && <div className="mt-6"><SectionTitle sub="Described so the format is fixed. No sensor is installed, so there is no value and no chart.">Planned measurements</SectionTitle>
        <div className="flex flex-wrap gap-2">{planned.map(d => <Chip key={d.name} tone="idle">{d.label} ({d.unit}) · {d.source}</Chip>)}</div></div>}
    </>
  )
}
