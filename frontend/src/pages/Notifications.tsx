/**
 * Every notification the signed-in person has received - from the portal
 * itself and from the n8n automations - with tabs (all, unread, n8n,
 * portal, critical), a type filter, search and "load more".
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, CheckCheck, Search, Workflow } from 'lucide-react'
import { Inbox, InboxTab, Notification, api } from '../lib/api'
import { useLive, useLiveMessages } from '../lib/live'
import { fmtTime, relative } from '../lib/time'
import { Dot, EmptyState, PageHeader, Skeleton, Tabs } from '../components/ui'
import { noteTone } from '../components/NotificationBell'

const PAGE = 50
const kindLabel = (k: string) => k.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase())

function SourceTag({ source }: { source?: string | null }) {
  if (source === 'n8n') return (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10.5px] font-semibold bg-violet-500/15 text-violet-300">
      <Workflow size={11} /> n8n</span>)
  if (source === 'portal') return (
    <span className="rounded px-1.5 py-0.5 text-[10.5px] font-semibold bg-accent-500/10 text-accent-300">portal</span>)
  return null
}

export default function Notifications() {
  const nav = useNavigate()
  const { refreshUnread } = useLive()
  const [tab, setTab] = useState<InboxTab>('all')
  const [kind, setKind] = useState('')
  const [q, setQ] = useState('')
  const [data, setData] = useState<Inbox | null>(null)
  const [rows, setRows] = useState<Notification[]>([])
  const [more, setMore] = useState(false)
  const seq = useRef(0)

  const load = useCallback((append = false) => {
    const my = ++seq.current
    if (!append) setMore(false)
    api.inbox({ tab, kind: kind || undefined, q: q.trim() || undefined,
                offset: append ? rows.length : 0, limit: PAGE })
      .then(d => {
        if (my !== seq.current) return                  // a newer filter won
        setData(d)
        setRows(r => append ? [...r, ...d.items] : d.items)
      })
      .catch(() => { if (!append) setData(d => d ?? { items: [], total: 0, kinds: [],
        counts: { all: 0, unread: 0, n8n: 0, portal: 0, critical: 0 } }) })
      .finally(() => setMore(false))
  }, [tab, kind, q, rows.length])

  useEffect(() => {
    const t = window.setTimeout(() => load(false), q ? 300 : 0)    // wait for typing to pause
    return () => window.clearTimeout(t)
  }, [tab, kind, q]) // eslint-disable-line react-hooks/exhaustive-deps
  useLiveMessages(m => { if (m.type === 'notification') load(false) })

  const groups = useMemo(() => {
    const m = new Map<string, Notification[]>()
    const today = new Date().toDateString()
    const y = new Date(Date.now() - 86400e3).toDateString()
    rows.forEach(n => {
      const d = new Date(n.created_at)
      const k = d.toDateString() === today ? 'Today' : d.toDateString() === y ? 'Yesterday'
        : d.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })
      m.set(k, [...(m.get(k) ?? []), n])
    })
    return [...m.entries()]
  }, [rows])

  async function open(n: Notification) {
    if (!n.is_read) {
      await api.markRead(n.id).catch(() => {})
      setRows(r => r.map(x => x.id === n.id ? { ...x, is_read: true } : x))
      refreshUnread()
    }
    if (n.link) nav(n.link)
  }

  const c = data?.counts
  return (
    <div className="max-w-4xl">
      <PageHeader eyebrow="Inbox" title="Notifications"
        sub="Everything sent to you: from the portal itself and from the n8n automations (device offline, hazards, emergencies, reminders)."
        actions={(c?.unread ?? 0) > 0 ? <button className="btn-ghost" onClick={async () => {
          await api.markAllRead(); refreshUnread(); load(false) }}><CheckCheck size={16} />Mark all read</button> : undefined} />
      <Tabs id="notes" value={tab} onChange={setTab} tabs={[
        { key: 'all', label: 'All', count: c?.all ?? 0 },
        { key: 'unread', label: 'Unread', count: c?.unread ?? 0 },
        { key: 'n8n', label: 'From n8n', count: c?.n8n ?? 0 },
        { key: 'portal', label: 'From the portal', count: c?.portal ?? 0 },
        { key: 'critical', label: 'Critical', count: c?.critical ?? 0 },
      ]} />
      <div className="mt-4 flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input className="input !pl-9" placeholder="Search title or text" value={q}
                 onChange={e => setQ(e.target.value)} aria-label="Search notifications" />
        </div>
        <select className="input w-auto" value={kind} onChange={e => setKind(e.target.value)} aria-label="Type">
          <option value="">All types</option>
          {(data?.kinds ?? []).map(k => <option key={k} value={k}>{kindLabel(k)}</option>)}
        </select>
      </div>
      {tab === 'all' && (c?.all ?? 0) > (c?.n8n ?? 0) + (c?.portal ?? 0) && (
        <p className="mt-2 text-[12px] text-slate-500">
          Older notifications (before 6 Oct 2026) have no source tag: which path raised them was not recorded.</p>)}
      <div className="mt-5" data-testid="notification-list">
        {data === null ? <Skeleton className="h-60" /> : rows.length === 0 ? (
          <div className="card"><EmptyState icon={<Bell size={20} />}
            title={tab === 'unread' ? 'All caught up' : 'Nothing here'}
            detail="Confirmations, reminders, refusals at the door, device and hazard alerts appear here." /></div>
        ) : groups.map(([day, items]) => (
          <section key={day} className="mb-6">
            <div className="label mb-2">{day}</div>
            <div className="card divide-y divide-ink-700/60 overflow-hidden">
              {items.map(n => (
                <button key={n.id} onClick={() => open(n)}
                  className={`w-full text-left px-5 py-4 flex gap-4 hover:bg-ink-700/35 ${n.is_read ? '' : 'bg-accent-500/[0.05]'}`}>
                  <Dot tone={noteTone(n)} className="mt-1.5" live={!n.is_read} />
                  <div className="min-w-0 flex-1">
                    <div className={`text-[14px] ${n.is_read ? 'text-slate-300' : 'text-white font-medium'}`}>{n.title}</div>
                    {n.body && <div className="text-[13px] text-slate-400 mt-0.5 break-words">{n.body}</div>}
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
                      <SourceTag source={n.source} /><span>{kindLabel(n.kind)}</span>
                    </div>
                  </div>
                  <div className="text-right text-[12px] text-slate-400 shrink-0">
                    <div>{fmtTime(n.created_at)}</div><div className="text-slate-500">{relative(n.created_at)}</div>
                  </div>
                </button>
              ))}
            </div>
          </section>
        ))}
        {data && rows.length < data.total && (
          <button className="btn-ghost w-full" disabled={more} onClick={() => { setMore(true); load(true) }}>
            {more ? 'Loading…' : `Load more (${data.total - rows.length} older)`}</button>)}
      </div>
    </div>
  )
}
