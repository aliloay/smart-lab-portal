/**
 * Anomalies on the real measurements: rules, sensor-fault checks and statistical baselines (no ML -
 * the panel says why). Each finding shows signal, expected, observed, window, confidence and source,
 * and can be raised as an incident once per day.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp } from 'lucide-react'
import { api } from '../lib/api'
import { relative } from '../lib/time'
import { Chip, SectionTitle } from './ui'

type Scan = Awaited<ReturnType<typeof api.anomalies>>
const LAYER_TONE: Record<string, 'bad' | 'warn' | 'violet'> = { RULE: 'bad', SENSOR: 'warn', BASELINE: 'violet' }

export default function AnomalyPanel() {
  const [s, setS] = useState<Scan | null>(null)
  const [raised, setRaised] = useState<Record<number, number>>({})
  const [error, setError] = useState('')
  useEffect(() => { api.anomalies().then(setS).catch(e => setError(e.message)) }, [])
  const raise = async (i: number) => {
    try { const r = await api.raiseAnomaly(i); setRaised(x => ({ ...x, [i]: r.incident_id })) }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
  }
  return (
    <section className="mb-8">
      <SectionTitle icon={<TrendingUp size={15} />} sub="Thresholds, sensor-fault checks and each node's own 7-day baseline - on measurements that exist.">
        Anomalies and maintenance signals</SectionTitle>
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}
      {s && <div className="space-y-3">
        {s.findings.length === 0 && <p className="text-[13px] text-slate-400">No findings in the latest data.</p>}
        {s.findings.map((f, i) => (
          <div key={i} className="card p-3 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone={LAYER_TONE[f.layer] ?? 'idle'}>{f.layer.toLowerCase()}</Chip>
              <Chip tone={f.severity === 'WARNING' ? 'warn' : 'idle'}>{f.kind.replaceAll('_', ' ').toLowerCase()}</Chip>
              <b className="text-slate-100 text-[13px]">{f.signal}</b>
              <span className="text-[12px] text-slate-400">{f.device} · {f.lab}</span>
              {f.stale && <Chip tone="warn">stale data · {relative(f.evaluated_at)}</Chip>}
              {raised[i] ? <Link to="/admin/incidents" className="ml-auto text-[12px] text-accent-300">Incident #{raised[i]} →</Link>
                : <button className="btn-ghost btn-sm ml-auto" onClick={() => raise(i)}>Raise as incident</button>}
            </div>
            <div className="text-[12.5px] text-slate-300">Observed <b>{f.observed}</b> · expected {f.expected} · window {f.window}</div>
            <div className="text-[12px] text-slate-400">{f.explanation} <span className="text-slate-500">Confidence: {f.confidence}. Source: {f.source}.</span></div>
          </div>))}
        <div className="card p-3 text-[12px] text-slate-400 space-y-1">
          <div><b className="text-slate-200">Machine learning:</b> {s.ml_status}</div>
          <div><b className="text-slate-200">Not covered:</b> {s.not_covered}</div>
          <div><b className="text-slate-200">Evaluated:</b> {s.evaluated.map(e => `${e.device}/${e.metric} (${e.readings} readings)`).join(' · ')}</div>
        </div>
      </div>}
    </section>
  )
}
