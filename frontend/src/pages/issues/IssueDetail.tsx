import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, Boxes, Camera, CheckCircle2, ClipboardCheck, Cpu, Eye, Lock, MessageSquare,
  RotateCcw, Send, ShieldCheck, UserPlus, Wrench,
} from 'lucide-react'
import { IssueDetail as TIssue, IssueStatus, PhotoStage, User, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useLiveMessages } from '../../lib/live'
import {
  SEVERITIES, STATUS_LABEL, categoryLabel, issueStatusTone,
} from '../../lib/labels'
import { fmtDateTime, fmtTimeSec, relative } from '../../lib/time'
import {
  Avatar, Chip, EmptyState, ErrorBanner, IssueStatusChip, KV, Notice, ProgressBar, SectionTitle,
  SeverityBadge, Skeleton, Timeline,
} from '../../components/ui'
import { AuthImage, GalleryPhoto, Lightbox, PhotoPicker, PickedFile } from '../../components/media'

const STAGE_LABEL: Record<PhotoStage, string> = {
  REPORT: 'Reported', BEFORE: 'Before maintenance', AFTER: 'After maintenance',
}

export default function IssueDetail() {
  const { id } = useParams()
  const iid = Number(id)
  const { user } = useAuth()
  const [issue, setIssue] = useState<TIssue | null>(null)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const [staff, setStaff] = useState<User[]>([])
  const [lightbox, setLightbox] = useState<number | null>(null)

  const load = useCallback(() => api.issue(iid).then(setIssue).catch(e => setError(e.message)), [iid])
  useEffect(() => { setIssue(null); setError(''); load() }, [load])
  useEffect(() => {
    if (issue?.can_manage && staff.length === 0) {
      api.users().then(u => setStaff(u.filter(x => x.role !== 'STUDENT' && x.is_active))).catch(() => {})
    }
  }, [issue?.can_manage])   // eslint-disable-line react-hooks/exhaustive-deps
  useLiveMessages(m => {
    if ((m.type === 'staff' && m.issue_id === iid) ||
        (m.type === 'notification' && m.notification.issue_id === iid)) load()
  })

  async function act(fn: () => Promise<TIssue | unknown>) {
    setActionError(''); setBusy(true)
    try {
      const r = await fn()
      if (r && typeof r === 'object' && 'history' in (r as object)) setIssue(r as TIssue)
      else await load()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Action failed')
    } finally { setBusy(false) }
  }

  const photos: GalleryPhoto[] = useMemo(() => (issue?.photos ?? []).map(p => ({
    id: p.id,
    thumbPath: api.issuePhotoPath(iid, p.id, 'thumb'),
    fullPath: api.issuePhotoPath(iid, p.id, 'full'),
    downloadPath: api.issuePhotoPath(iid, p.id, 'full', true),
    caption: `${issue?.ticket_number} · ${STAGE_LABEL[p.stage]} · ${p.original_filename || `photo ${p.id}`}`,
  })), [issue, iid])

  if (error) return <div className="max-w-lg space-y-4"><ErrorBanner message={error} />
    <Link to="/issues" className="btn-ghost"><ArrowLeft size={15} />Back to issues</Link></div>
  if (!issue) return <div className="space-y-4"><Skeleton className="h-36" /><Skeleton className="h-80" /></div>

  const i = issue
  const back = i.can_manage ? 'Maintenance' : 'My reports'

  return (
    <div className="space-y-6">
      <Link to="/issues" className="inline-flex items-center gap-1.5 text-[13px] text-slate-400 hover:text-white">
        <ArrowLeft size={14} />{back}</Link>

      {/* ---------------------------------------------------------- header */}
      <section className="card p-6 relative overflow-hidden">
        <div className={`absolute inset-x-0 top-0 h-1 ${i.severity === 'CRITICAL' ? 'bg-bad'
          : i.severity === 'HIGH' ? 'bg-warn' : i.severity === 'MEDIUM' ? 'bg-accent-500' : 'bg-slate-500'}`} />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="mono text-[13px] text-accent-200">{i.ticket_number}</span>
              <SeverityBadge severity={i.severity} />
              <IssueStatusChip status={i.status} />
              {i.is_overdue && <Chip tone="bad">overdue</Chip>}
            </div>
            <h1 className="mt-2.5 page-title !text-[26px]">{i.title}</h1>
            <div className="mt-3 flex flex-wrap gap-2 text-[12.5px]">
              <Link to={`/labs/${i.lab_id}`} className="chip bg-ink-700/70 border border-ink-500 text-slate-200 !normal-case !tracking-normal !text-[12px]">
                <span className="mono text-accent-200">{i.lab_code}</span> {i.lab_name}</Link>
              {i.asset_id && (
                <Link to={`/equipment/${i.asset_id}`} className="chip bg-ink-700/70 border border-ink-500 text-slate-200 !normal-case !tracking-normal !text-[12px]">
                  <Boxes size={12} />{i.asset_name} <span className="mono text-slate-400">{i.asset_tag}</span></Link>
              )}
              {i.device_name && (
                <span className="chip bg-ink-700/70 border border-ink-500 text-slate-200 !normal-case !tracking-normal !text-[12px]">
                  <Cpu size={12} />{i.device_name}</span>
              )}
              <span className="chip bg-ink-700/70 border border-ink-500 text-slate-300 !normal-case !tracking-normal !text-[12px]">
                {categoryLabel(i.category)}</span>
            </div>
          </div>
          <div className="text-right text-[12.5px] text-slate-400 space-y-1">
            <div>Reported by <span className="text-slate-200">{i.reporter_name}</span></div>
            <div>{fmtDateTime(i.created_at)}</div>
            <div>{i.assignee_name ? <>Assigned to <span className="text-slate-200">{i.assignee_name}</span></> : 'Not assigned yet'}</div>
          </div>
        </div>
      </section>

      <div className="grid xl:grid-cols-[1fr_380px] gap-6">
        <div className="space-y-6 min-w-0">
          <section className="card p-5">
            <div className="label mb-2">Description</div>
            <p className="text-[14px] text-slate-200 leading-relaxed whitespace-pre-wrap">{i.description}</p>
            {i.additional_comments && (
              <><div className="label mt-5 mb-2">Additional comments</div>
                <p className="text-[13.5px] text-slate-300 whitespace-pre-wrap">{i.additional_comments}</p></>
            )}
          </section>

          {(i.resolution_notes || i.status === 'RESOLVED' || i.status === 'CLOSED') && (
            <section className="card p-5 border-ok/35 bg-ok/[0.05]">
              <div className="flex items-center gap-2 text-ok-soft font-semibold text-[14px]">
                <CheckCircle2 size={16} />Resolution</div>
              <p className="mt-2 text-[14px] text-slate-200 whitespace-pre-wrap">
                {i.resolution_notes || 'No resolution notes recorded.'}</p>
              <div className="mt-3 text-[12px] text-slate-400">
                {i.assignee_name && <>Technician {i.assignee_name} · </>}
                {i.resolved_at && <>Resolved {fmtDateTime(i.resolved_at)}</>}
              </div>
            </section>
          )}

          {/* ------------------------------------------------------ photos */}
          <section>
            <SectionTitle icon={<Camera size={15} />} sub="Originals are kept for the investigation; tap to enlarge.">
              Photos <span className="text-slate-500 font-normal">({i.photos.length})</span>
            </SectionTitle>
            <div className="card p-5">
              {i.photos.length === 0 ? <p className="text-[13px] text-slate-400">No photos attached.</p> : (
                (['REPORT', 'BEFORE', 'AFTER'] as PhotoStage[]).map(stage => {
                  const list = i.photos.map((p, idx) => ({ p, idx })).filter(x => x.p.stage === stage)
                  if (!list.length) return null
                  return (
                    <div key={stage} className="mb-4 last:mb-0">
                      <div className="label mb-2">{STAGE_LABEL[stage]}</div>
                      <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-2.5">
                        {list.map(({ p, idx }) => (
                          <button key={p.id} onClick={() => setLightbox(idx)}
                                  className="group relative aspect-square rounded-lg overflow-hidden border border-ink-600 hover:border-accent-400"
                                  aria-label={`Open photo ${idx + 1}`}>
                            <AuthImage path={photos[idx].thumbPath} alt={photos[idx].caption}
                                       className="w-full h-full transition-transform group-hover:scale-105" />
                            <span className="absolute inset-x-0 bottom-0 px-1.5 py-1 bg-ink-950/80 text-[10px]
                                             text-slate-300 truncate text-left">{p.uploaded_by_name}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )
                })
              )}
              {i.can_add_photos && <AddPhotos issue={i} onDone={load} />}
            </div>
          </section>

          {/* ---------------------------------------------------- comments */}
          <Conversation issue={i} onPosted={load} />
        </div>

        {/* ----------------------------------------------------- side rail */}
        <aside className="space-y-6">
          {i.can_manage && (
            <StaffPanel issue={i} staff={staff} me={user!} busy={busy} error={actionError}
                        act={act} />
          )}

          <section>
            <SectionTitle icon={<ClipboardCheck size={15} />}>Timeline</SectionTitle>
            <div className="card p-5">
              <Timeline dense items={i.history.map(h => ({
                key: h.id,
                time: `${new Date(h.created_at).toLocaleDateString([], { day: 'numeric', month: 'short' })} ${fmtTimeSec(h.created_at)}`,
                title: h.new_status && h.event_type !== 'ISSUE_COMMENT_ADDED'
                  ? (h.event_type === 'ISSUE_CREATED' ? 'Issue reported' : STATUS_LABEL[h.new_status])
                  : h.event_type.replace('ISSUE_', '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase()),
                tone: h.new_status ? issueStatusTone(h.new_status) : 'idle',
                detail: <>{h.message}{h.actor_name && h.event_type !== 'ISSUE_CREATED' &&
                  !h.message.includes(h.actor_name) && <span className="text-slate-500"> · {h.actor_name}</span>}</>,
              }))} />
            </div>
          </section>

          <section>
            <SectionTitle icon={<Eye size={15} />}>Details</SectionTitle>
            <div className="card p-4"><dl>
              <KV label="Ticket" mono>{i.ticket_number}</KV>
              <KV label="Laboratory">{i.lab_code}</KV>
              <KV label="Equipment">{i.asset_name ?? (i.device_name ?? 'General laboratory issue')}</KV>
              <KV label="Category">{categoryLabel(i.category)}</KV>
              <KV label="Created">{fmtDateTime(i.created_at)}</KV>
              <KV label="Acknowledged">{i.acknowledged_at ? relative(i.acknowledged_at) : '—'}</KV>
              <KV label="Resolved">{i.resolved_at ? fmtDateTime(i.resolved_at) : '—'}</KV>
              {i.closed_at && <KV label="Closed">{fmtDateTime(i.closed_at)}</KV>}
              {i.access_event_id && <KV label="Access event" mono>#{i.access_event_id}</KV>}
            </dl></div>
          </section>
        </aside>
      </div>

      <Lightbox photos={photos} index={lightbox} onClose={() => setLightbox(null)} onIndex={setLightbox} />
    </div>
  )
}

// ---------------------------------------------------------------------------
function StaffPanel({ issue: i, staff, me, busy, error, act }: {
  issue: TIssue; staff: User[]; me: User; busy: boolean; error: string
  act: (fn: () => Promise<unknown>) => Promise<void>
}) {
  const [assignee, setAssignee] = useState(String(i.assigned_to_id ?? ''))
  const [notes, setNotes] = useState(i.resolution_notes ?? '')
  const [note, setNote] = useState('')
  useEffect(() => { setAssignee(String(i.assigned_to_id ?? '')) }, [i.assigned_to_id])

  const moves = i.allowed_statuses.filter(s => s !== 'RESOLVED' && s !== 'CLOSED')
  const finished = ['RESOLVED', 'CLOSED', 'REJECTED'].includes(i.status)

  return (
    <section>
      <SectionTitle icon={<Wrench size={15} />}>Manage</SectionTitle>
      <div className="card p-4 space-y-4">
        {error && <ErrorBanner message={error} />}

        {i.status === 'OPEN' && (
          <button disabled={busy} onClick={() => act(() => api.acknowledgeIssue(i.id))}
                  className="btn-primary w-full"><ShieldCheck size={15} />Acknowledge</button>
        )}

        {!finished && (
          <div>
            <div className="label mb-1.5">Assigned technician</div>
            <div className="flex gap-2">
              <select className="input" value={assignee} onChange={e => setAssignee(e.target.value)}
                      aria-label="Assign to">
                <option value="">Unassigned</option>
                {staff.map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}
              </select>
              <button className="btn-ghost btn-sm shrink-0" disabled={busy || assignee === String(i.assigned_to_id ?? '')}
                      onClick={() => act(() => api.assignIssue(i.id, assignee ? Number(assignee) : null))}>
                Save</button>
            </div>
            {i.assigned_to_id !== me.id && (
              <button className="mt-2 text-xs link inline-flex items-center gap-1" disabled={busy}
                      onClick={() => act(() => api.assignIssue(i.id, me.id))}>
                <UserPlus size={12} />Assign to me</button>
            )}
          </div>
        )}

        {moves.length > 0 && (
          <div>
            <div className="label mb-1.5">Move to</div>
            <input className="input mb-2" placeholder="Optional note (sent to the reporter)" value={note}
                   onChange={e => setNote(e.target.value)} maxLength={2000} />
            <div className="flex gap-2 flex-wrap">
              {moves.map(s => (
                <button key={s} disabled={busy}
                        onClick={() => act(() => api.setIssueStatus(i.id, s as IssueStatus, note)).then(() => setNote(''))}
                        className={`btn btn-sm border ${s === 'REJECTED' ? 'border-bad/45 text-bad-soft hover:bg-bad/10'
                          : 'border-ink-500 text-slate-200 hover:border-accent-400 bg-ink-800/40'}`}>
                  {STATUS_LABEL[s as IssueStatus]}</button>
              ))}
            </div>
          </div>
        )}

        {!finished && (
          <div>
            <div className="label mb-1.5">Severity</div>
            <select className="input" value={i.severity} aria-label="Severity" disabled={busy}
                    onChange={e => act(() => api.updateIssue(i.id, { severity: e.target.value as TIssue['severity'] }))}>
              {SEVERITIES.map(s => <option key={s.value} value={s.value}>{s.label} - {s.hint}</option>)}
            </select>
          </div>
        )}

        {i.allowed_statuses.includes('RESOLVED') && (
          <div className="pt-3 divider">
            <div className="label mb-1.5 mt-3">Resolve</div>
            <textarea className="input min-h-[80px]" value={notes} onChange={e => setNotes(e.target.value)}
                      placeholder="What was done - parts replaced, settings changed, tests passed." maxLength={4000} />
            <button className="btn-primary w-full mt-2" disabled={busy || notes.trim().length < 5}
                    onClick={() => act(() => api.resolveIssue(i.id, notes))}>
              <CheckCircle2 size={15} />Mark resolved</button>
          </div>
        )}

        {i.can_close && (i.status === 'RESOLVED' || i.status === 'REJECTED') && (
          <button className="btn-ghost w-full" disabled={busy}
                  onClick={() => act(() => api.closeIssue(i.id))}><Lock size={15} />Close issue</button>
        )}
        {i.can_close && finished && (
          <button className="btn-quiet w-full" disabled={busy}
                  onClick={() => act(() => api.reopenIssue(i.id))}><RotateCcw size={15} />Reopen</button>
        )}

        {i.asset_id && <AssetMaintenanceToggle assetId={i.asset_id} busy={busy} act={act} />}
      </div>
    </section>
  )
}

function AssetMaintenanceToggle({ assetId, busy, act }: {
  assetId: number; busy: boolean; act: (fn: () => Promise<unknown>) => Promise<void>
}) {
  const [status, setStatus] = useState<string | null>(null)
  useEffect(() => { api.asset(assetId).then(d => setStatus(d.asset.status)).catch(() => {}) }, [assetId])
  if (!status) return null
  const inMaint = status === 'MAINTENANCE'
  return (
    <div className="pt-3 divider">
      <div className="mt-3 text-[12.5px] text-slate-300 flex items-center justify-between gap-2">
        <span>Equipment is <b className={inMaint ? 'text-warn-soft' : 'text-slate-100'}>
          {status.replace('_', ' ').toLowerCase()}</b></span>
        {(inMaint || status === 'AVAILABLE') && (
          <button className="btn-ghost btn-sm" disabled={busy}
            onClick={() => act(async () => {
              const r = await api.updateAsset(assetId, { status: inMaint ? 'AVAILABLE' : 'MAINTENANCE' })
              setStatus(r.status)
            })}>
            {inMaint ? 'Return to service' : 'Take out of service'}</button>
        )}
      </div>
    </div>
  )
}

function AddPhotos({ issue, onDone }: { issue: TIssue; onDone: () => void }) {
  const [files, setFiles] = useState<PickedFile[]>([])
  const [stage, setStage] = useState<PhotoStage>(issue.can_manage ? 'BEFORE' : 'REPORT')
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  async function upload() {
    setError(''); setProgress(0)
    try {
      await api.uploadIssuePhotos(issue.id, files.map(f => f.file), stage, setProgress)
      files.forEach(f => URL.revokeObjectURL(f.url))
      setFiles([]); setOpen(false); onDone()
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed') }
    finally { setProgress(null) }
  }

  if (!open) return (
    <button className="btn-ghost btn-sm mt-4" onClick={() => setOpen(true)}>
      <Camera size={14} />{issue.can_manage ? 'Add maintenance photos' : 'Add more photos'}</button>
  )
  return (
    <div className="mt-4 pt-4 divider space-y-3">
      {issue.can_manage && (
        <div className="flex gap-2">
          {(['BEFORE', 'AFTER', 'REPORT'] as PhotoStage[]).map(s => (
            <button key={s} onClick={() => setStage(s)} aria-pressed={stage === s}
              className={`btn btn-sm border ${stage === s ? 'bg-accent-500/15 border-accent-500/45 text-accent-100'
                : 'border-ink-500 text-slate-300'}`}>{STAGE_LABEL[s]}</button>
          ))}
        </div>
      )}
      <PhotoPicker files={files} onChange={setFiles} disabled={progress !== null} />
      {error && <ErrorBanner message={error} />}
      {progress !== null && <ProgressBar value={progress} />}
      <div className="flex gap-2">
        <button className="btn-primary btn-sm" disabled={!files.length || progress !== null} onClick={upload}>
          Upload {files.length || ''}</button>
        <button className="btn-quiet btn-sm" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </div>
  )
}

function Conversation({ issue: i, onPosted }: { issue: TIssue; onPosted: () => void }) {
  const [body, setBody] = useState('')
  const [internal, setInternal] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function post() {
    setBusy(true); setError('')
    try { await api.commentIssue(i.id, body, internal); setBody(''); setInternal(false); onPosted() }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not post') }
    finally { setBusy(false) }
  }

  return (
    <section>
      <SectionTitle icon={<MessageSquare size={15} />}
        sub={i.can_manage ? 'Internal notes are visible to staff only.' : undefined}>
        Updates & comments
      </SectionTitle>
      <div className="card p-5">
        {i.comments.length === 0 ? <EmptyState compact icon={<MessageSquare size={18} />} title="No comments yet" /> : (
          <ul className="space-y-4">
            {i.comments.map(c => (
              <li key={c.id} className="flex gap-3">
                <Avatar name={c.author_name} size={30} />
                <div className={`flex-1 min-w-0 rounded-xl px-3.5 py-2.5 border ${c.is_internal
                  ? 'border-warn/30 bg-warn/[0.06]' : 'border-ink-600 bg-ink-900/40'}`}>
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="text-slate-100 font-medium">{c.author_name}</span>
                    {c.author_role !== 'STUDENT' && <span className="text-accent-300">staff</span>}
                    {c.is_internal && <Chip tone="warn">internal</Chip>}
                    <span className="text-slate-500 ml-auto">{relative(c.created_at)}</span>
                  </div>
                  <p className="mt-1 text-[13.5px] text-slate-200 whitespace-pre-wrap">{c.body}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
        {i.can_comment ? (
          <div className="mt-5 pt-4 divider">
            {error && <div className="mb-2"><ErrorBanner message={error} /></div>}
            <textarea className="input min-h-[80px]" value={body} onChange={e => setBody(e.target.value)}
                      maxLength={2000} placeholder={i.can_manage ? 'Update for the reporter, or an internal note'
                        : 'Add information that might help the technician'} />
            <div className="mt-2 flex items-center gap-3">
              {i.can_manage && (
                <label className="flex items-center gap-2 text-[12.5px] text-slate-300">
                  <input type="checkbox" checked={internal} onChange={e => setInternal(e.target.checked)}
                         className="accent-amber-500" />Internal note</label>
              )}
              <button className="btn-primary btn-sm ml-auto" disabled={busy || !body.trim()} onClick={post}>
                <Send size={14} />Post</button>
            </div>
          </div>
        ) : (
          <div className="mt-4"><Notice>This issue is {STATUS_LABEL[i.status].toLowerCase()}, so comments are closed.</Notice></div>
        )}
      </div>
    </section>
  )
}
