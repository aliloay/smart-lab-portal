import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, Filter, Hourglass, Search, UserPlus, X } from 'lucide-react'
import { Booking, Lab, api } from '../lib/api'
import { isAdmin, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { fmtTime } from '../lib/time'
import {
  EmptyState, ErrorBanner, Modal, PageHeader, SectionTitle, Select, Skeleton, Tabs,
} from '../components/ui'
import BookingCard from '../components/BookingCard'
import { bucket } from './MyBookings'

const TABS = ['Upcoming', 'Active', 'Completed', 'Cancelled'] as const
type Tab = typeof TABS[number]

export default function Reservations() {
  const { user } = useAuth()
  const [rows, setRows] = useState<Booking[] | null>(null)
  const [labs, setLabs] = useState<Lab[]>([])
  const [tab, setTab] = useState<Tab>('Upcoming')
  const [labId, setLabId] = useState('')
  const [q, setQ] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [error, setError] = useState('')
  const [rejecting, setRejecting] = useState<Booking | null>(null)
  const [note, setNote] = useState('')

  const load = useCallback(() => {
    api.bookings({
      lab_id: labId ? Number(labId) : undefined,
      from: from ? new Date(`${from}T00:00`).toISOString() : undefined,
      to: to ? new Date(`${to}T23:59`).toISOString() : undefined,
    }).then(setRows).catch(e => { setError(e.message); setRows([]) })
  }, [labId, from, to])
  useEffect(() => { load() }, [load])
  useEffect(() => { api.labs().then(setLabs).catch(() => {}) }, [])
  useLiveMessages(m => {
    if (m.type === 'access_event' && /^(BOOKING|ACCESS_GRANTED|EXIT)/.test(m.event.event_type)) load()
  })

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    return (rows ?? []).filter(b => !s || `${b.user_name} ${b.user_email} ${b.lab_code} ${b.lab_name} ${b.reason}`
      .toLowerCase().includes(s))
  }, [rows, q])
  const pending = filtered.filter(b => b.status === 'PENDING' && new Date(b.end_time).getTime() > Date.now())
  const buckets = useMemo(() => bucket(filtered.filter(b => b.status !== 'PENDING')), [filtered])

  async function act(fn: () => Promise<unknown>) {
    setError('')
    try { await fn(); load() } catch (e) { setError(e instanceof Error ? e.message : 'Action failed') }
  }

  return (
    <div>
      <PageHeader eyebrow="Operations" title={isAdmin(user) ? 'Bookings' : 'Reservations'}
        sub="Every reservation across all laboratories, with its real entry record."
        actions={<Link to="/book" className="btn-primary"><UserPlus size={16} />Create booking for user</Link>} />

      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}

      <div className="card p-4 mb-5">
        <div className="flex items-center gap-2 mb-3"><Filter size={13} className="text-slate-400" />
          <span className="label">Filters</span></div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input className="input pl-9" placeholder="Person, lab or purpose" value={q}
                   onChange={e => setQ(e.target.value)} aria-label="Search bookings" />
          </div>
          <Select value={labId} onChange={setLabId} label=""
                  options={[['', 'All laboratories'], ...labs.map(l => [String(l.id), `${l.code} · ${l.name}`] as [string, string])]} />
          <input type="date" className="input" value={from} onChange={e => setFrom(e.target.value)}
                 aria-label="From date" />
          <input type="date" className="input" value={to} onChange={e => setTo(e.target.value)}
                 aria-label="To date" />
        </div>
      </div>

      {pending.length > 0 && (
        <section className="mb-6">
          <SectionTitle icon={<Hourglass size={15} />} sub="Requests waiting for a decision">
            Pending approval ({pending.length})
          </SectionTitle>
          <div className="grid gap-3">
            {pending.map(b => (
              <BookingCard key={b.id} b={b} showUser actions={<>
                <button className="btn-primary btn-sm" onClick={() => act(() => api.confirmBooking(b.id))}>
                  <Check size={14} />Approve</button>
                <button className="btn-danger btn-sm" onClick={() => { setRejecting(b); setNote('') }}>
                  <X size={14} />Reject</button>
              </>} />
            ))}
          </div>
        </section>
      )}

      <Tabs id="reservations" value={tab} onChange={setTab}
            tabs={TABS.map(t => ({ key: t, label: t, count: buckets[t].length }))} />
      {rows === null ? (
        <div className="grid gap-3 mt-5">{[0, 1, 2].map(i => <Skeleton key={i} className="h-40" />)}</div>
      ) : buckets[tab].length === 0 ? (
        <div className="card mt-5"><EmptyState title={`No ${tab.toLowerCase()} reservations`}
          detail="Adjust the filters or create a booking for a user." /></div>
      ) : (
        <div className="mt-5 grid gap-3">
          {buckets[tab].map(b => <BookingCard key={b.id} b={b} showUser />)}
        </div>
      )}

      <Modal open={!!rejecting} onClose={() => setRejecting(null)} title="Reject booking request"
        footer={<>
          <button className="btn-quiet" onClick={() => setRejecting(null)}>Back</button>
          <button className="btn-danger" onClick={() => {
            const b = rejecting!; setRejecting(null); act(() => api.rejectBooking(b.id, note))
          }}>Reject request</button>
        </>}>
        <p className="text-sm text-slate-300">
          {rejecting?.user_name} · {rejecting?.lab_code} · {rejecting && `${fmtTime(rejecting.start_time)}–${fmtTime(rejecting.end_time)}`}
        </p>
        <label className="label block mt-4 mb-1.5" htmlFor="reason">Reason (sent to the student)</label>
        <textarea id="reason" className="input min-h-[90px]" value={note} maxLength={500}
                  onChange={e => setNote(e.target.value)} placeholder="e.g. Laboratory reserved for examinations" />
      </Modal>
    </div>
  )
}
