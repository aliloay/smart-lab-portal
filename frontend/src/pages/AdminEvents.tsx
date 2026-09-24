import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Download, Filter, ShieldCheck, X } from 'lucide-react'
import { AccessEvent, Lab, User, api, getToken } from '../lib/api'
import { fmtDateTime } from '../lib/time'
import {
  Chip, EmptyState, Skeleton, denialReason, eventTone,
} from '../components/ui'

const EVENT_TYPES = [
  'QR_SCAN', 'QR_VALIDATED', 'QR_REJECTED', 'RFID_ACCEPTED', 'RFID_REJECTED',
  'FINGERPRINT_ACCEPTED', 'FINGERPRINT_REJECTED', 'FACE_ACCEPTED',
  'FACE_REJECTED', 'IDENTITY_MISMATCH', 'ACCESS_GRANTED', 'ACCESS_DENIED',
  'DOOR_OPENED', 'DOOR_CLOSED', 'BOOKING_CREATED', 'BOOKING_CONFIRMED',
  'BOOKING_CANCELLED', 'QR_GENERATED', 'DEVICE_ONLINE', 'DEVICE_OFFLINE',
]

export default function AdminEvents() {
  const [rows, setRows] = useState<AccessEvent[]>([])
  const [labs, setLabs] = useState<Lab[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<AccessEvent | null>(null)
  const [f, setF] = useState({
    lab_id: '', user_id: '', event_type: '', method: '', result: '' })

  useEffect(() => {
    api.labs().then(setLabs).catch(() => {})
    api.users().then(setUsers).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    api.events({ ...f, limit: 300 })
      .then(setRows).finally(() => setLoading(false))
  }, [f])

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLSelectElement>) =>
    setF(p => ({ ...p, [k]: e.target.value }))

  /**
   * CSV export. Fetched with the auth header and handed to the browser as a
   * blob rather than opening the URL directly — a plain link carries no
   * Authorization header and would be rejected.
   */
  async function exportCsv() {
    const res = await fetch(api.exportEventsUrl(f.lab_id ? Number(f.lab_id) : undefined),
                            { headers: { Authorization: `Bearer ${getToken()}` } })
    if (!res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `access-events-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const active = Object.values(f).filter(Boolean).length

  return (
    <div>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="page-title">Access events</h1>
          <p className="page-sub">
            Every authentication attempt and door transition, with the reason
            it was allowed or refused.
          </p>
        </div>
        <button onClick={exportCsv} className="btn-ghost">
          <Download size={15} />Export CSV
        </button>
      </div>

      <div className="card-pad mt-5">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={13} className="text-slate-500" />
          <span className="label">Filters</span>
          {active > 0 && (
            <button onClick={() => setF({ lab_id: '', user_id: '', event_type: '',
                                          method: '', result: '' })}
                    className="ml-auto text-[11px] text-accent-400 hover:text-accent-300">
              Clear {active}
            </button>
          )}
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <Select label="Laboratory" value={f.lab_id} onChange={set('lab_id')}
                  options={[['', 'All'], ...labs.map(l => [String(l.id), l.code] as [string, string])]} />
          <Select label="Person" value={f.user_id} onChange={set('user_id')}
                  options={[['', 'Anyone'], ...users.map(u => [String(u.id), u.full_name] as [string, string])]} />
          <Select label="Event" value={f.event_type} onChange={set('event_type')}
                  options={[['', 'All'], ...EVENT_TYPES.map(t => [t, t.replace(/_/g, ' ')] as [string, string])]} />
          <Select label="Method" value={f.method} onChange={set('method')}
                  options={[['', 'All'], ...['RFID', 'QR', 'FINGERPRINT', 'FACE', 'PORTAL']
                    .map(m => [m, m] as [string, string])]} />
          <Select label="Result" value={f.result} onChange={set('result')}
                  options={[['', 'All'], ...['GRANTED', 'DENIED', 'PENDING']
                    .map(r => [r, r] as [string, string])]} />
        </div>
      </div>

      <div className="card mt-5 overflow-hidden">
        {loading ? (
          <div className="p-5 space-y-2">
            {[0, 1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-9" />)}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState icon={<ShieldCheck size={20} />}
                      title="No events match these filters"
                      detail="Widen the filters, or wait for activity at a door." />
        ) : (
          <div className="overflow-x-auto max-h-[62vh]">
            <table className="w-full min-w-[920px]">
              <thead><tr>
                <th className="th">Time</th><th className="th">Lab</th>
                <th className="th">Event</th><th className="th">Person</th>
                <th className="th">Method</th><th className="th">Reason</th>
                <th className="th">Detail</th>
              </tr></thead>
              <tbody>
                {rows.map(e => (
                  <tr key={e.id} onClick={() => setSelected(e)}
                      className="tr cursor-pointer">
                    <td className="td text-slate-500 whitespace-nowrap tnum">
                      {fmtDateTime(e.created_at)}
                    </td>
                    <td className="td mono text-slate-500">{e.lab_code ?? '—'}</td>
                    <td className="td">
                      <Chip tone={eventTone(e.event_type)}>
                        {e.event_type.replace(/_/g, ' ')}
                      </Chip>
                    </td>
                    <td className="td text-slate-300">{e.user_name ?? '—'}</td>
                    <td className="td text-slate-500">{e.method ?? '—'}</td>
                    <td className="td">
                      {e.reason
                        ? <span className="text-bad text-xs">{denialReason(e.reason)}</span>
                        : <span className="text-slate-700">—</span>}
                    </td>
                    <td className="td text-slate-500 max-w-md truncate">{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ------------------------------------------------- detail drawer */}
      <AnimatePresence>
        {selected && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setSelected(null)}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" />
            <motion.aside
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 34 }}
              className="fixed right-0 inset-y-0 z-50 w-full sm:w-[420px]
                         bg-ink-900 border-l border-ink-600 overflow-y-auto"
              role="dialog" aria-label="Event detail"
            >
              <div className="sticky top-0 bg-ink-900/95 backdrop-blur px-5 py-4
                              border-b border-ink-700 flex items-center justify-between">
                <div>
                  <div className="label">Access event</div>
                  <div className="mono text-slate-500 mt-0.5">#{selected.id}</div>
                </div>
                <button onClick={() => setSelected(null)} aria-label="Close"
                        className="btn-quiet !px-2 !py-2"><X size={16} /></button>
              </div>

              <div className="p-5 space-y-4">
                <Chip tone={eventTone(selected.event_type)}>
                  {selected.event_type.replace(/_/g, ' ')}
                </Chip>

                {selected.reason && (
                  <div className="rounded-lg border border-bad/40 bg-bad/10 p-4">
                    <div className="label text-bad/80">Why it was refused</div>
                    <div className="mt-1.5 text-sm text-bad">
                      {denialReason(selected.reason)}
                    </div>
                    <div className="mono text-bad/60 mt-1">{selected.reason}</div>
                  </div>
                )}

                <dl className="space-y-3">
                  <Field label="Timestamp" value={fmtDateTime(selected.created_at)} />
                  <Field label="Laboratory" value={selected.lab_code ?? '—'} mono />
                  <Field label="Person" value={selected.user_name ?? 'Not identified'} />
                  <Field label="Method" value={selected.method ?? '—'} />
                  <Field label="Result" value={selected.result ?? '—'} />
                  <Field label="Booking"
                         value={selected.booking_id ? `#${selected.booking_id}` : '—'} />
                  <Field label="Device"
                         value={selected.device_id ? `#${selected.device_id}` : '—'} />
                </dl>

                <div>
                  <div className="label mb-1.5">Message</div>
                  <p className="text-[13px] text-slate-300 leading-relaxed">
                    {selected.message || '—'}
                  </p>
                </div>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

function Select({ label, value, onChange, options }: {
  label: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void
  options: [string, string][]
}) {
  return (
    <div>
      <label className="label block mb-1.5">{label}</label>
      <select className="input" value={value} onChange={onChange} aria-label={label}>
        {options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
    </div>
  )
}

function Field({ label, value, mono }: {
  label: string; value: string; mono?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="label">{label}</dt>
      <dd className={`text-[13px] text-slate-300 text-right ${mono ? 'mono' : ''}`}>
        {value}
      </dd>
    </div>
  )
}
