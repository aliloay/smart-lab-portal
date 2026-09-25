/**
 * An item's whole life in the laboratory: identity, where it is, who has
 * it, when it was last inspected, when maintenance is due, and every
 * problem reported against it and how it was fixed. Values that were never
 * recorded say so; nothing is estimated.
 */
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, Boxes, CalendarClock, ClipboardCheck, Hash, History, MapPin, Pencil,
  ShieldCheck, Tag, UserRound, Wrench,
} from 'lucide-react'
import { AssetDetail as TAsset, LifecycleEntry, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { assetStatusLabel, assetTone, categoryLabel } from '../lib/labels'
import { fmtDate, relative } from '../lib/time'
import {
  Chip, EmptyState, ErrorBanner, Field, IssueStatusChip, Modal, SectionTitle, SeverityBadge,
  Skeleton, Timeline, Tone,
} from '../components/ui'
import { LabArt } from '../components/labArt'

const LIFE: Record<LifecycleEntry['kind'], { tone: Tone; icon: JSX.Element }> = {
  ISSUE_REPORTED: { tone: 'warn', icon: <Wrench size={14} /> },
  ISSUE_RESOLVED: { tone: 'ok', icon: <ShieldCheck size={14} /> },
  INSPECTION: { tone: 'info', icon: <ClipboardCheck size={14} /> },
  CHECKOUT: { tone: 'violet', icon: <UserRound size={14} /> },
  RETURN: { tone: 'idle', icon: <UserRound size={14} /> },
  STATUS: { tone: 'idle', icon: <Tag size={14} /> },
}

export default function AssetDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const staff = isStaff(user)
  const [d, setD] = useState<TAsset | null>(null)
  const [error, setError] = useState('')
  const [inspecting, setInspecting] = useState(false)
  const [editing, setEditing] = useState(false)
  const load = useCallback(() => api.asset(Number(id)).then(setD).catch(e => setError(e.message)), [id])
  useEffect(() => { setD(null); load() }, [load])

  async function setStatus(status: string) {
    setError('')
    try { await api.updateAsset(Number(id), { status }); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Update failed') }
  }

  if (error && !d) return <div className="max-w-lg space-y-4"><ErrorBanner message={error} />
    <Link to="/labs" className="btn-ghost"><ArrowLeft size={15} />Laboratories</Link></div>
  if (!d) return <div className="space-y-4"><Skeleton className="h-56" /><Skeleton className="h-64" /></div>
  const a = d.asset

  return (
    <div className="space-y-6">
      <Link to={staff ? '/admin/equipment' : `/labs/${d.lab.id}`}
            className="inline-flex items-center gap-1.5 text-[13px] text-slate-400 hover:text-white">
        <ArrowLeft size={14} />{staff ? 'Equipment' : d.lab.name}</Link>
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {/* ---------------------------------------------------------- hero */}
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
            {a.maintenance_due && <Chip tone="bad">maintenance due</Chip>}
          </div>
          <h1 className="mt-2 page-title">{a.name}</h1>
          <div className="mt-2 flex flex-wrap gap-4 text-[13px] text-slate-300">
            <span className="flex items-center gap-1.5"><Boxes size={14} className="text-slate-400" />{a.category || 'Uncategorised'}</span>
            <Link to={`/labs/${d.lab.id}`} className="flex items-center gap-1.5 hover:text-white">
              <MapPin size={14} className="text-slate-400" />{d.lab.code} · {d.lab.location || d.lab.name}</Link>
          </div>
          {a.notes && <p className="mt-3 text-[13.5px] text-slate-300">{a.notes}</p>}
          <div className="mt-5 flex gap-2 flex-wrap">
            <Link to={`/issues/new?lab=${d.lab.id}&asset=${a.id}`} className="btn-primary">
              <Wrench size={16} />Report a problem</Link>
            {staff && <button className="btn-ghost" onClick={() => setInspecting(true)}>
              <ClipboardCheck size={16} />Record inspection</button>}
            {staff && <button className="btn-quiet" onClick={() => setEditing(true)}>
              <Pencil size={15} />Edit details</button>}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------ lifecycle */}
      <section>
        <SectionTitle icon={<Tag size={15} />}>Asset record</SectionTitle>
        <div className="card p-5 grid sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-4">
          <Fact icon={<Hash size={13} />} label="Asset ID" value={<span className="mono">{a.asset_tag}</span>} />
          <Fact icon={<Boxes size={13} />} label="Type" value={a.category || '—'} />
          <Fact icon={<MapPin size={13} />} label="Laboratory" value={`${d.lab.code} · ${d.lab.name}`} />
          <Fact icon={<MapPin size={13} />} label="Location" value={d.lab.location || '—'} />
          <Fact icon={<Hash size={13} />} label="Serial number"
                value={a.serial_number ? <span className="mono">{a.serial_number}</span> : <Muted>Not recorded</Muted>} />
          <Fact icon={<Tag size={13} />} label="Status"
                value={<span className="flex items-center gap-2">
                  <Chip tone={assetTone(a.status)}>{assetStatusLabel(a.status)}</Chip>
                  {staff && a.status !== 'MAINTENANCE' && a.status !== 'RETIRED' && (
                    <button className="text-xs link" onClick={() => setStatus('MAINTENANCE')}>take out of service</button>)}
                  {staff && a.status === 'MAINTENANCE' && (
                    <button className="text-xs link" onClick={() => setStatus('AVAILABLE')}>return to service</button>)}
                </span>} />
          <Fact icon={<UserRound size={13} />} label="Current user"
                value={a.status !== 'CHECKED_OUT' ? <Muted>Not checked out</Muted>
                  : staff ? <>{a.holder_name ?? '—'}{a.checked_out_at &&
                      <span className="text-slate-400 text-[12px]"> · since {relative(a.checked_out_at)}</span>}</>
                  : <Muted>Checked out</Muted>} />
          <Fact icon={<ClipboardCheck size={13} />} label="Last inspection"
                value={a.last_inspected_at ? fmtDate(a.last_inspected_at) : <Muted>Not recorded</Muted>} />
          <Fact icon={<CalendarClock size={13} />} label="Next maintenance"
                value={a.next_maintenance_at
                  ? <span className={a.maintenance_due ? 'text-bad-soft' : ''}>{fmtDate(a.next_maintenance_at)}
                      {a.maintenance_due && ' · overdue'}</span>
                  : <Muted>Not scheduled</Muted>} />
        </div>
      </section>

      <div className="grid xl:grid-cols-5 gap-6">
        {/* ------------------------------------------- maintenance history */}
        <section className="xl:col-span-3">
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
                <table className="w-full min-w-[560px]">
                  <thead><tr>
                    <th className="th">Issue</th><th className="th">Reported</th>
                    <th className="th">State</th><th className="th">Resolved</th>
                  </tr></thead>
                  <tbody>
                    {d.maintenance.map(m => (
                      <tr key={m.id} className="tr align-top">
                        <td className="td">
                          <div className="mono !text-[11px] text-slate-400">{m.ticket_number} · {categoryLabel(m.category)}</div>
                          {staff || m.is_mine
                            ? <Link to={`/issues/${m.id}`} className="text-slate-100 hover:text-accent-200">{m.title}</Link>
                            : <span className="text-slate-100">{m.title}</span>}
                          {m.resolution_notes && <div className="mt-1 text-[12px] text-slate-300">↳ {m.resolution_notes}</div>}
                        </td>
                        <td className="td text-slate-300 whitespace-nowrap">{fmtDate(m.created_at)}</td>
                        <td className="td"><div className="flex flex-col items-start gap-1.5">
                          <SeverityBadge severity={m.severity} /><IssueStatusChip status={m.status} /></div></td>
                        <td className="td text-slate-300 text-[13px]">
                          {m.resolved_at ? <div className="whitespace-nowrap">{fmtDate(m.resolved_at)}</div> : '—'}
                          {m.technician && <div className="text-[12px] text-slate-400">{m.technician}</div>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* ---------------------------------------------- lifecycle timeline */}
        <section className="xl:col-span-2">
          <SectionTitle icon={<History size={15} />}
            sub={staff ? 'Reports, fixes, inspections, loans and status changes.'
                       : 'Reports, fixes, inspections and status changes.'}>
            Lifecycle
          </SectionTitle>
          <div className="card p-5 max-h-[560px] overflow-y-auto">
            {d.lifecycle.length === 0 ? <EmptyState compact title="No history yet" /> : (
              <Timeline dense items={d.lifecycle.map((e, i) => ({
                key: `${e.kind}-${i}`,
                time: fmtDate(e.at),
                title: e.issue_id && (staff || d.maintenance.find(m => m.id === e.issue_id)?.is_mine)
                  ? <Link to={`/issues/${e.issue_id}`} className="hover:underline underline-offset-2">{e.title}</Link>
                  : e.title,
                tone: LIFE[e.kind].tone,
                icon: LIFE[e.kind].icon,
                detail: <>{e.detail}{e.actor && <span className="text-slate-500"> · {e.actor}</span>}</>,
              }))} />
            )}
          </div>
        </section>
      </div>

      {inspecting && <InspectModal assetId={a.id} onClose={() => setInspecting(false)}
                                   onDone={() => { setInspecting(false); load() }} />}
      {editing && <EditModal d={d} onClose={() => setEditing(false)}
                             onDone={() => { setEditing(false); load() }} />}
    </div>
  )
}

function Fact({ icon, label, value }: { icon: JSX.Element; label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 label"><span className="text-accent-300">{icon}</span>{label}</div>
      <div className="mt-1 text-[14px] text-slate-100">{value}</div>
    </div>
  )
}

const Muted = ({ children }: { children: React.ReactNode }) =>
  <span className="text-slate-400">{children}</span>

function InspectModal({ assetId, onClose, onDone }: { assetId: number; onClose: () => void; onDone: () => void }) {
  const [note, setNote] = useState('')
  const [next, setNext] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const tomorrow = new Date(Date.now() + 86400e3).toISOString().slice(0, 10)
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await api.inspectAsset(assetId, note, next ? new Date(`${next}T09:00`).toISOString() : null)
      onDone()
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed') } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title="Record inspection">
      <form onSubmit={save} className="space-y-3">
        {error && <ErrorBanner message={error} />}
        <p className="text-[13px] text-slate-300">Records that the item was inspected now, by you.</p>
        <Field label="Findings" hint="What was checked and what was found.">
          <input className="input" value={note} maxLength={255} onChange={e => setNote(e.target.value)}
                 placeholder="e.g. Joint torque and emergency stop tested - OK" /></Field>
        <Field label="Next maintenance due (optional)">
          <input className="input" type="date" min={tomorrow} value={next} onChange={e => setNext(e.target.value)} /></Field>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Record inspection'}</button>
        </div>
      </form>
    </Modal>
  )
}

function EditModal({ d, onClose, onDone }: { d: TAsset; onClose: () => void; onDone: () => void }) {
  const a = d.asset
  const [f, setF] = useState({ name: a.name, category: a.category, serial_number: a.serial_number ?? '',
    notes: a.notes, next: a.next_maintenance_at ? a.next_maintenance_at.slice(0, 10) : '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      await api.updateAsset(a.id, { name: f.name, category: f.category, notes: f.notes,
        serial_number: f.serial_number.trim() || null,
        next_maintenance_at: f.next ? new Date(`${f.next}T09:00`).toISOString() : null })
      onDone()
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed') } finally { setBusy(false) }
  }
  return (
    <Modal open onClose={onClose} title={`Edit ${a.asset_tag}`}>
      <form onSubmit={save} className="space-y-3">
        {error && <ErrorBanner message={error} />}
        <Field label="Name"><input className="input" required minLength={2} value={f.name}
          onChange={e => setF({ ...f, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Type / category"><input className="input" value={f.category}
            onChange={e => setF({ ...f, category: e.target.value })} /></Field>
          <Field label="Serial number"><input className="input mono" value={f.serial_number} maxLength={64}
            onChange={e => setF({ ...f, serial_number: e.target.value })} /></Field>
        </div>
        <Field label="Next maintenance due"><input className="input" type="date" value={f.next}
          onChange={e => setF({ ...f, next: e.target.value })} /></Field>
        <Field label="Notes"><textarea className="input" value={f.notes}
          onChange={e => setF({ ...f, notes: e.target.value })} /></Field>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </form>
    </Modal>
  )
}
