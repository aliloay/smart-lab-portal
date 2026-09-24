import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarPlus, CalendarRange, X } from 'lucide-react'
import { Booking, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { EmptyState, ErrorBanner, Modal, PageHeader, Skeleton, Tabs } from '../components/ui'
import BookingCard from '../components/BookingCard'

const TABS = ['Upcoming', 'Active', 'Completed', 'Cancelled'] as const
type Tab = typeof TABS[number]

export function bucket(rows: Booking[], now = Date.now()) {
  const b: Record<Tab, Booking[]> = { Upcoming: [], Active: [], Completed: [], Cancelled: [] }
  for (const r of rows) {
    const s = new Date(r.start_time).getTime()
    const e = new Date(r.end_time).getTime()
    if (r.status === 'CANCELLED' || r.status === 'REJECTED') b.Cancelled.push(r)
    else if (s <= now && now <= e) b.Active.push(r)
    else if (s > now) b.Upcoming.push(r)
    else b.Completed.push(r)
  }
  b.Upcoming.sort((x, y) => +new Date(x.start_time) - +new Date(y.start_time))
  return b
}

export default function MyBookings() {
  const [rows, setRows] = useState<Booking[] | null>(null)
  const [tab, setTab] = useState<Tab | null>(null)
  const [error, setError] = useState('')
  const [cancelling, setCancelling] = useState<Booking | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => api.bookings().then(setRows)
    .catch(e => { setError(e.message); setRows([]) }), [])
  useEffect(() => { load() }, [load])
  useLiveMessages(m => { if (m.type === 'access_event' || m.type === 'notification') load() })

  const buckets = useMemo(() => bucket(rows ?? []), [rows])
  // Land on the tab that matters: an active booking beats an empty list.
  const current: Tab = tab ?? (buckets.Active.length ? 'Active'
    : buckets.Upcoming.length ? 'Upcoming' : buckets.Completed.length ? 'Completed' : 'Upcoming')

  async function confirmCancel() {
    if (!cancelling) return
    setBusy(true)
    try { await api.cancelBooking(cancelling.id); setCancelling(null); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not cancel') }
    finally { setBusy(false) }
  }

  const list = buckets[current]

  return (
    <div>
      <PageHeader eyebrow="Reservations" title="My bookings"
        sub="Your laboratory reservations, their access credentials, and when you actually entered."
        actions={<Link to="/book" className="btn-primary"><CalendarPlus size={16} />New booking</Link>} />

      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}

      <Tabs id="my-bookings" value={current} onChange={setTab}
            tabs={TABS.map(t => ({ key: t, label: t, count: buckets[t].length }))} />

      {rows === null ? (
        <div className="grid gap-3 mt-5">{[0, 1, 2].map(i => <Skeleton key={i} className="h-40" />)}</div>
      ) : list.length === 0 ? (
        <div className="card mt-5">
          <EmptyState icon={<CalendarRange size={20} />} title={`No ${current.toLowerCase()} bookings`}
            detail={current === 'Upcoming' ? 'Book a laboratory to get a time-bound access credential.' : undefined}
            action={current === 'Upcoming'
              ? <Link to="/book" className="btn-primary">Book a laboratory</Link> : undefined} />
        </div>
      ) : (
        <div className="mt-5 grid gap-3">
          {list.map(b => (
            <BookingCard key={b.id} b={b} actions={(current === 'Upcoming' || current === 'Active')
              && b.status !== 'CANCELLED' ? (
              <button onClick={() => setCancelling(b)} className="btn-quiet btn-sm hover:!text-bad-soft"
                      aria-label="Cancel booking"><X size={14} />Cancel</button>
            ) : undefined} />
          ))}
        </div>
      )}

      <Modal open={!!cancelling} onClose={() => setCancelling(null)} title="Cancel this booking?"
        footer={<>
          <button className="btn-quiet" onClick={() => setCancelling(null)}>Keep it</button>
          <button className="btn-danger" disabled={busy} onClick={confirmCancel}>
            {busy ? 'Cancelling…' : 'Cancel booking'}</button>
        </>}>
        <p className="text-sm text-slate-300 leading-relaxed">
          {cancelling?.lab_name}, {cancelling && new Date(cancelling.start_time).toLocaleString([], {
            weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}.
          The access code stops working immediately and the time becomes free for others.
        </p>
      </Modal>
    </div>
  )
}
