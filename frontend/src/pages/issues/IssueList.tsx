import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Camera, Clock, Filter, ListOrdered, Plus, Search, TriangleAlert, UserCheck, Wrench, X,
} from 'lucide-react'
import { Issue, IssueSummary, Lab, User, api } from '../../lib/api'
import { isAdmin, isStaff, useAuth } from '../../lib/auth'
import { PriorityList } from '../../components/ai'
import { useLiveMessages } from '../../lib/live'
import { ISSUE_CATEGORIES, SEVERITIES, STATUS_LABEL, categoryLabel } from '../../lib/labels'
import { relative } from '../../lib/time'
import {
  EmptyState, ErrorBanner, IssueStatusChip, MetricCard, PageHeader, SectionTitle, Select, SeverityBadge,
  Skeleton, Spinner, Tabs,
} from '../../components/ui'

const IssueAnalytics = lazy(() => import('./IssueAnalytics'))

const SEV = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 } as const

export default function IssueList() {
  const { user } = useAuth()
  return isStaff(user) ? <MaintenanceQueuePage admin={isAdmin(user)} /> : <MyReports />
}

// ---------------------------------------------------------------- student
const STUDENT_TABS = [
  { key: 'open', label: 'Open', match: ['OPEN', 'ACKNOWLEDGED'] },
  { key: 'progress', label: 'In progress', match: ['IN_PROGRESS', 'WAITING_FOR_PARTS'] },
  { key: 'resolved', label: 'Resolved', match: ['RESOLVED'] },
  { key: 'closed', label: 'Closed', match: ['CLOSED', 'REJECTED'] },
] as const
type STab = typeof STUDENT_TABS[number]['key']

function MyReports() {
  const [rows, setRows] = useState<Issue[] | null>(null)
  const [tab, setTab] = useState<STab | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(() => api.issues({ limit: 200 }).then(setRows)
    .catch(e => { setError(e.message); setRows([]) }), [])
  useEffect(() => { load() }, [load])
  useLiveMessages(m => { if (m.type === 'notification' && m.notification.issue_id) load() })

  const counts = Object.fromEntries(STUDENT_TABS.map(t => [t.key,
    (rows ?? []).filter(i => (t.match as readonly string[]).includes(i.status)).length]))
  const current: STab = tab ?? (STUDENT_TABS.find(t => counts[t.key] > 0)?.key ?? 'open')
  const list = (rows ?? []).filter(i =>
    (STUDENT_TABS.find(t => t.key === current)!.match as readonly string[]).includes(i.status))

  return (
    <div>
      <PageHeader eyebrow="Maintenance" title="My reports"
        sub="Problems you reported, and exactly where each one is in the maintenance process."
        actions={<Link to="/issues/new" className="btn-primary"><Plus size={16} />Report an issue</Link>} />
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      <Tabs id="my-reports" value={current} onChange={setTab}
            tabs={STUDENT_TABS.map(t => ({ key: t.key, label: t.label, count: counts[t.key] }))} />
      {rows === null ? <div className="mt-5 grid gap-3">{[0, 1, 2].map(i => <Skeleton key={i} className="h-24" />)}</div>
        : list.length === 0 ? (
          <div className="card mt-5">
            <EmptyState icon={<Wrench size={20} />} title={rows.length ? 'Nothing here' : 'No reports yet'}
              detail={rows.length ? undefined : 'If something in a laboratory is broken, missing or unsafe, report it in under a minute.'}
              action={<Link to="/issues/new" className="btn-primary">Report an issue</Link>} />
          </div>
        ) : <div className="mt-5 grid gap-3">{list.map(i => <IssueRow key={i.id} i={i} />)}</div>}
    </div>
  )
}

// ------------------------------------------------------------- staff/admin
const QUICK = [
  { key: 'all', label: 'All active' },
  { key: 'new', label: 'New reports' },
  { key: 'high', label: 'High priority' },
  { key: 'mine', label: 'Assigned to me' },
  { key: 'unassigned', label: 'Unassigned' },
  { key: 'overdue', label: 'Overdue' },
  { key: 'finished', label: 'Resolved & closed' },
] as const
type Quick = typeof QUICK[number]['key']

function MaintenanceQueuePage({ admin }: { admin: boolean }) {
  const [params, setParams] = useSearchParams()
  const [rows, setRows] = useState<Issue[] | null>(null)
  const [summary, setSummary] = useState<IssueSummary | null>(null)
  const [labs, setLabs] = useState<Lab[]>([])
  const [staff, setStaff] = useState<User[]>([])
  const [error, setError] = useState('')

  const quick = (params.get('view') as Quick) ??
    (params.get('severity') ? 'high' : params.get('assigned') === 'unassigned' ? 'unassigned'
      : params.get('overdue') ? 'overdue' : 'all')
  const labId = params.get('lab_id') ?? ''
  const category = params.get('category') ?? ''
  const severity = params.get('sev') ?? ''
  const assignee = params.get('assignee') ?? ''
  const q = params.get('q') ?? ''

  function set(k: string, v: string) {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v); else p.delete(k)
    if (k === 'view') { p.delete('severity'); p.delete('assigned'); p.delete('overdue') }
    setParams(p, { replace: true })
  }

  const load = useCallback(() => {
    const query: Record<string, string | number | boolean | string[] | undefined> = {
      limit: 500, lab_id: labId || undefined, category: category || undefined, q: q || undefined,
    }
    if (quick === 'finished') query.active = false
    else query.active = true
    if (quick === 'new') query.status = ['OPEN']
    if (quick === 'high') query.severity = ['HIGH', 'CRITICAL']
    else if (severity) query.severity = [severity]
    if (quick === 'mine') query.assigned = 'me'
    else if (quick === 'unassigned') query.assigned = 'unassigned'
    else if (assignee) query.assigned = assignee
    if (quick === 'overdue') query.overdue = true
    api.issues(query).then(r => setRows([...r].sort((a, b) =>
      quick === 'finished' ? +new Date(b.updated_at) - +new Date(a.updated_at)
        : SEV[a.severity] - SEV[b.severity] || +new Date(a.created_at) - +new Date(b.created_at))))
      .catch(e => { setError(e.message); setRows([]) })
    api.issueSummary().then(setSummary).catch(() => {})
  }, [quick, labId, category, severity, assignee, q])

  useEffect(() => { setRows(null); load() }, [load])
  useEffect(() => {
    api.labs().then(setLabs).catch(() => {})
    api.users().then(u => setStaff(u.filter(x => x.role !== 'STUDENT' && x.is_active))).catch(() => {})
  }, [])
  useLiveMessages(m => { if (m.type === 'staff' && m.kind === 'issue') load() })

  const anyFilter = labId || category || severity || assignee || q

  return (
    <div>
      <PageHeader eyebrow="Maintenance & operations" title="Maintenance"
        sub="Every reported problem across the laboratories - triage, assign, fix and record."
        actions={<Link to="/issues/new" className="btn-primary"><Plus size={16} />New report</Link>} />
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">
        <MetricCard label="Open" value={summary?.open ?? null} icon={<Wrench size={15} />} />
        <MetricCard label="Critical" value={summary?.critical ?? null}
                    tone={summary?.critical ? 'bad' : 'idle'} icon={<TriangleAlert size={15} />} />
        <MetricCard label="High priority" value={summary?.high ?? null}
                    tone={summary?.high ? 'warn' : 'idle'} icon={<TriangleAlert size={15} />} />
        <MetricCard label="In progress" value={summary ? summary.in_progress + summary.waiting_for_parts : null}
                    icon={<Clock size={15} />} tone="violet"
                    hint={summary?.waiting_for_parts ? `${summary.waiting_for_parts} waiting for parts` : undefined} />
        <MetricCard label="Overdue" value={summary?.overdue ?? null} tone={summary?.overdue ? 'bad' : 'idle'}
                    info={summary ? `Past the service level: critical ${summary.sla_hours.CRITICAL}h, high ${summary.sla_hours.HIGH}h, medium ${summary.sla_hours.MEDIUM}h, low ${summary.sla_hours.LOW}h.` : undefined}
                    icon={<Clock size={15} />} />
        <MetricCard label="Resolved this month" value={summary?.resolved_this_month ?? null} tone="ok"
                    icon={<UserCheck size={15} />}
                    hint={summary?.avg_resolution_hours != null
                      ? `avg ${summary.avg_resolution_hours} h to resolve` : 'No resolution data yet'} />
      </div>

      <section className="card p-5 mb-6">
        <SectionTitle icon={<ListOrdered size={15} />}
          sub="Ranked by severity, SLA, safety, assignment and upcoming bookings. AI summary optional.">
          What to fix first</SectionTitle>
        <PriorityList limit={5} />
      </section>

      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1 mb-3">
        {QUICK.map(t => (
          <button key={t.key} onClick={() => set('view', t.key === 'all' ? '' : t.key)}
            aria-pressed={quick === t.key}
            className={`btn btn-sm border shrink-0 ${quick === t.key
              ? 'bg-accent-500/15 text-accent-100 border-accent-500/45'
              : 'border-ink-500 text-slate-300 hover:text-white bg-ink-800/40'}`}>{t.label}</button>
        ))}
      </div>

      <div className="card p-4 mb-5">
        <div className="flex items-center gap-2 mb-3"><Filter size={13} className="text-slate-400" />
          <span className="label">Filters</span>
          {anyFilter && <button className="ml-auto text-xs link inline-flex items-center gap-1"
            onClick={() => setParams(quick !== 'all' ? { view: quick } : {}, { replace: true })}>
            <X size={12} />Clear</button>}
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="relative lg:col-span-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input className="input pl-9" placeholder="Ticket or text" value={q}
                   onChange={e => set('q', e.target.value)} aria-label="Search issues" />
          </div>
          <Select value={labId} onChange={v => set('lab_id', v)}
                  options={[['', 'All laboratories'], ...labs.map(l => [String(l.id), l.code] as [string, string])]} />
          <Select value={category} onChange={v => set('category', v)}
                  options={[['', 'All categories'], ...ISSUE_CATEGORIES.map(c => [c.value, c.label] as [string, string])]} />
          <Select value={severity} onChange={v => set('sev', v)}
                  options={[['', 'Any severity'], ...SEVERITIES.map(c => [c.value, c.label] as [string, string])]} />
          <Select value={assignee} onChange={v => set('assignee', v)}
                  options={[['', 'Anyone assigned'], ...staff.map(u => [String(u.id), u.full_name] as [string, string])]} />
        </div>
      </div>

      {rows === null ? <div className="grid gap-3">{[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-24" />)}</div>
        : rows.length === 0 ? (
          <div className="card"><EmptyState icon={<Wrench size={20} />} title="No issues match"
            detail={quick === 'all' && !anyFilter ? 'No open maintenance issues right now.' : 'Try another view or filter.'} /></div>
        ) : <div className="grid gap-3">{rows.map(i => <IssueRow key={i.id} i={i} staffView />)}</div>}

      {admin && (
        <div className="mt-10">
          <Suspense fallback={<Spinner label="Loading analytics" />}>
            <IssueAnalytics summary={summary} />
          </Suspense>
        </div>
      )}
    </div>
  )
}

export function IssueRow({ i, staffView = false }: { i: Issue; staffView?: boolean }) {
  const edge = i.severity === 'CRITICAL' ? 'before:bg-bad' : i.severity === 'HIGH' ? 'before:bg-warn'
    : i.severity === 'MEDIUM' ? 'before:bg-accent-500' : 'before:bg-slate-500'
  return (
    <Link to={`/issues/${i.id}`}
      className={`card card-hover block p-4 pl-5 relative overflow-hidden before:absolute before:left-0
                  before:inset-y-0 before:w-1 ${edge}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="mono text-slate-400">{i.ticket_number}</span>
            <SeverityBadge severity={i.severity} />
            <span className="text-[11.5px] text-slate-400">{categoryLabel(i.category)}</span>
            {i.is_overdue && <span className="chip bg-bad/10 text-bad-soft border border-bad/35">overdue</span>}
          </div>
          <div className="mt-1.5 text-[15px] text-white font-medium">{i.title}</div>
          <div className="mt-1 text-[12.5px] text-slate-400 flex flex-wrap gap-x-3 gap-y-0.5">
            <span className="mono !text-[12px] text-accent-200">{i.lab_code}</span>
            {i.asset_name && <span>{i.asset_name}</span>}
            {i.device_name && <span>{i.device_name}</span>}
            {staffView && <span>by {i.reporter_name}</span>}
            <span>{relative(i.created_at)}</span>
            {i.photo_count > 0 && <span className="inline-flex items-center gap-1"><Camera size={12} />{i.photo_count}</span>}
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <IssueStatusChip status={i.status} />
          <span className="text-[11.5px] text-slate-400">
            {i.assignee_name ? `→ ${i.assignee_name}` : staffView ? 'Unassigned' : STATUS_LABEL[i.status]}
          </span>
        </div>
      </div>
    </Link>
  )
}
