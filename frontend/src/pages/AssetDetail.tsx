import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Boxes, History, MapPin, Wrench } from 'lucide-react'
import { AssetDetail as TAsset, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { assetStatusLabel, assetTone, categoryLabel } from '../lib/labels'
import { fmtDate, fmtDateTime } from '../lib/time'
import {
  Chip, EmptyState, ErrorBanner, IssueStatusChip, SectionTitle, SeverityBadge, Skeleton,
} from '../components/ui'
import { LabArt } from '../components/labArt'

export default function AssetDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const staff = isStaff(user)
  const [d, setD] = useState<TAsset | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(() => api.asset(Number(id)).then(setD).catch(e => setError(e.message)), [id])
  useEffect(() => { setD(null); load() }, [load])

  async function setStatus(status: string) {
    setError('')
    try { await api.updateAsset(Number(id), { status }); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Update failed') }
  }

  if (error && !d) return <div className="max-w-lg space-y-4"><ErrorBanner message={error} />
    <Link to="/labs" className="btn-ghost"><ArrowLeft size={15} />Laboratories</Link></div>
  if (!d) return <Skeleton className="h-64" />
  const a = d.asset

  return (
    <div className="space-y-6">
      <Link to={`/labs/${d.lab.id}`} className="inline-flex items-center gap-1.5 text-[13px] text-slate-400 hover:text-white">
        <ArrowLeft size={14} />{d.lab.name}</Link>
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <section className="relative card overflow-hidden">
        <div className="absolute inset-y-0 right-0 w-1/2 hidden md:block">
          <LabArt category={d.lab.category} className="w-full h-full" />
          <div className="absolute inset-0 bg-gradient-to-r from-ink-800 to-ink-800/30" />
        </div>
        <div className="relative p-6 sm:p-7 max-w-xl">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="mono text-accent-200">{a.asset_tag}</span>
            <Chip tone={assetTone(a.status)} dot>{assetStatusLabel(a.status)}</Chip>
            {a.open_issues > 0 && <Chip tone="warn">{a.open_issues} open issue{a.open_issues > 1 ? 's' : ''}</Chip>}
          </div>
          <h1 className="mt-2 page-title">{a.name}</h1>
          <div className="mt-2 flex flex-wrap gap-4 text-[13px] text-slate-300">
            <span className="flex items-center gap-1.5"><Boxes size={14} className="text-slate-400" />{a.category || 'Uncategorised'}</span>
            <Link to={`/labs/${d.lab.id}`} className="flex items-center gap-1.5 hover:text-white">
              <MapPin size={14} className="text-slate-400" />{d.lab.code} · {d.lab.location}</Link>
          </div>
          {a.notes && <p className="mt-3 text-[13.5px] text-slate-300">{a.notes}</p>}
          <div className="mt-5 flex gap-2 flex-wrap">
            <Link to={`/issues/new?lab=${d.lab.id}&asset=${a.id}`} className="btn-primary">
              <Wrench size={16} />Report a problem</Link>
            {staff && a.status !== 'MAINTENANCE' && a.status !== 'RETIRED' && (
              <button className="btn-ghost" onClick={() => setStatus('MAINTENANCE')}>Take out of service</button>
            )}
            {staff && a.status === 'MAINTENANCE' && (
              <button className="btn-ghost" onClick={() => setStatus('AVAILABLE')}>Return to service</button>
            )}
          </div>
        </div>
      </section>

      <section>
        <SectionTitle icon={<History size={15} />}
          sub="Every problem reported against this item and how it was resolved.">
          Maintenance history
        </SectionTitle>
        <div className="card overflow-hidden">
          {d.maintenance.length === 0 ? (
            <EmptyState icon={<Wrench size={20} />} title="No problems reported"
              detail="Nothing has been reported against this equipment." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px]">
                <thead><tr>
                  <th className="th">Issue</th><th className="th">Reported</th><th className="th">Severity</th>
                  <th className="th">Status</th><th className="th">Resolved</th><th className="th">Technician</th>
                  <th className="th">Resolution</th>
                </tr></thead>
                <tbody>
                  {d.maintenance.map(m => {
                    const canOpen = staff || m.is_mine
                    return (
                      <tr key={m.id} className="tr">
                        <td className="td">
                          <div className="mono !text-[11px] text-slate-400">{m.ticket_number}</div>
                          {canOpen ? <Link to={`/issues/${m.id}`} className="text-slate-100 hover:text-accent-200">{m.title}</Link>
                            : <span className="text-slate-100">{m.title}</span>}
                          <div className="text-[11.5px] text-slate-500">{categoryLabel(m.category)}</div>
                        </td>
                        <td className="td text-slate-300 whitespace-nowrap">{fmtDate(m.created_at)}</td>
                        <td className="td"><SeverityBadge severity={m.severity} /></td>
                        <td className="td"><IssueStatusChip status={m.status} /></td>
                        <td className="td text-slate-300 whitespace-nowrap">{m.resolved_at ? fmtDateTime(m.resolved_at) : '—'}</td>
                        <td className="td text-slate-300">{m.technician ?? '—'}</td>
                        <td className="td text-slate-300 max-w-[260px]">{m.resolution_notes || '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {staff && (
        <section>
          <SectionTitle icon={<History size={15} />}>Usage record</SectionTitle>
          <div className="card divide-y divide-ink-700/60">
            {d.transactions.length === 0 ? <EmptyState compact title="No check-outs or status changes yet" />
              : d.transactions.map(t => (
                <div key={t.id} className="px-4 py-3 flex items-center gap-3 text-[13px]">
                  <Chip tone={t.action === 'CHECKOUT' ? 'info' : t.action === 'RETURN' ? 'ok' : 'idle'}>
                    {t.action.replace('STATUS_', '→ ').replace('_', ' ').toLowerCase()}</Chip>
                  <span className="text-slate-200">{t.user_name}</span>
                  {t.note && <span className="text-slate-400">{t.note}</span>}
                  <span className="ml-auto text-slate-400 whitespace-nowrap">{fmtDateTime(t.created_at)}</span>
                </div>
              ))}
          </div>
        </section>
      )}
    </div>
  )
}
