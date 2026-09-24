import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, CheckCheck } from 'lucide-react'
import { Notification, api } from '../lib/api'
import { useLive, useLiveMessages } from '../lib/live'
import { fmtTime, relative } from '../lib/time'
import { Dot, EmptyState, PageHeader, Skeleton, Tabs } from '../components/ui'
import { noteTone } from '../components/NotificationBell'

export default function Notifications() {
  const nav = useNavigate()
  const { refreshUnread } = useLive()
  const [rows, setRows] = useState<Notification[] | null>(null)
  const [tab, setTab] = useState<'all' | 'unread'>('all')
  const load = useCallback(() => api.notifications(false, 200).then(setRows).catch(() => setRows([])), [])
  useEffect(() => { load() }, [load])
  useLiveMessages(m => { if (m.type === 'notification') load() })

  const list = (rows ?? []).filter(n => tab === 'all' || !n.is_read)
  const groups = useMemo(() => {
    const m = new Map<string, Notification[]>()
    list.forEach(n => {
      const d = new Date(n.created_at)
      const today = new Date().toDateString()
      const y = new Date(Date.now() - 86400e3).toDateString()
      const k = d.toDateString() === today ? 'Today' : d.toDateString() === y ? 'Yesterday'
        : d.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })
      m.set(k, [...(m.get(k) ?? []), n])
    })
    return [...m.entries()]
  }, [list])

  async function open(n: Notification) {
    if (!n.is_read) { await api.markRead(n.id).catch(() => {}); refreshUnread(); load() }
    if (n.link) nav(n.link)
  }

  const unread = (rows ?? []).filter(n => !n.is_read).length

  return (
    <div className="max-w-3xl">
      <PageHeader eyebrow="Inbox" title="Notifications"
        sub="Booking, access and maintenance updates about you - raised only by things that actually happened."
        actions={unread > 0 ? <button className="btn-ghost" onClick={async () => {
          await api.markAllRead(); refreshUnread(); load() }}><CheckCheck size={16} />Mark all read</button> : undefined} />
      <Tabs id="notes" value={tab} onChange={setTab}
            tabs={[{ key: 'all', label: 'All', count: rows?.length ?? 0 }, { key: 'unread', label: 'Unread', count: unread }]} />
      <div className="mt-5">
        {rows === null ? <Skeleton className="h-60" /> : list.length === 0 ? (
          <div className="card"><EmptyState icon={<Bell size={20} />}
            title={tab === 'unread' ? 'All caught up' : 'No notifications yet'}
            detail="Confirmations, reminders, refusals at the door and issue updates appear here." /></div>
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
                    {n.body && <div className="text-[13px] text-slate-400 mt-0.5">{n.body}</div>}
                  </div>
                  <div className="text-right text-[12px] text-slate-400 shrink-0">
                    <div>{fmtTime(n.created_at)}</div><div className="text-slate-500">{relative(n.created_at)}</div>
                  </div>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
