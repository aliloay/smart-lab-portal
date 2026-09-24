import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, CheckCircle2 } from 'lucide-react'
import { Alert, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { fmtDateTime, relative } from '../lib/time'
import { Chip, EmptyState, ErrorBanner, PageHeader, Skeleton, Tabs } from '../components/ui'

export default function Alerts() {
  const [rows, setRows] = useState<Alert[] | null>(null)
  const [tab, setTab] = useState<'open' | 'all'>('open')
  const [error, setError] = useState('')
  const load = useCallback(() => api.alerts().then(setRows)
    .catch(e => { setError(e.message); setRows([]) }), [])
  useEffect(() => { load() }, [load])
  useLiveMessages(m => { if (m.type === 'access_event' && m.event.event_type.startsWith('DEVICE')) load() })

  async function resolve(id: number) {
    try { await api.resolveAlert(id); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not resolve') }
  }

  const open = (rows ?? []).filter(a => !a.is_resolved)
  const list = tab === 'open' ? open : rows ?? []

  return (
    <div>
      <PageHeader eyebrow="Operations" title="Alerts"
        sub="Operational warnings raised by the system itself - for example a controller that stopped sending heartbeats. Equipment problems reported by people live under Maintenance." />
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}
      <Tabs id="alerts" value={tab} onChange={setTab}
            tabs={[{ key: 'open', label: 'Open', count: open.length }, { key: 'all', label: 'All', count: rows?.length ?? 0 }]} />
      <div className="mt-5">
        {rows === null ? <Skeleton className="h-48" /> : list.length === 0 ? (
          <div className="card"><EmptyState icon={<Bell size={20} />}
            title={tab === 'open' ? 'No open alerts' : 'No alerts recorded'}
            detail="Nothing requires attention." /></div>
        ) : (
          <div className="grid gap-3">
            {list.map(a => (
              <div key={a.id} className={`card p-4 flex items-start gap-4 ${a.is_resolved ? 'opacity-70' : ''}`}>
                <Chip tone={a.severity === 'CRITICAL' ? 'bad' : a.severity === 'WARNING' ? 'warn' : 'info'} dot>
                  {a.severity.toLowerCase()}</Chip>
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] text-white">{a.title}</div>
                  <div className="text-[12.5px] text-slate-400 mt-0.5">{a.detail}</div>
                  <div className="text-[11.5px] text-slate-500 mt-1.5">
                    {a.lab_code ? <Link to={`/labs/${a.lab_id}`} className="link">{a.lab_code}</Link> : 'System'}
                    {' · raised '}{relative(a.created_at)}
                    {a.resolved_at && ` · resolved ${fmtDateTime(a.resolved_at)}`}
                  </div>
                </div>
                {!a.is_resolved ? (
                  <button className="btn-ghost btn-sm shrink-0" onClick={() => resolve(a.id)}>
                    <CheckCircle2 size={14} />Resolve</button>
                ) : <Chip tone="ok">resolved</Chip>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
