import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, DoorOpen, Download, Filter, ListChecks, ShieldCheck, Wrench, X,
} from 'lucide-react'
import { AccessEvent, Lab, Session, User, api, fetchBlob } from '../lib/api'
import { isAdmin, useAuth } from '../lib/auth'
import { useLive, useLiveMessages } from '../lib/live'
import {
  denialShort, denialText, endReasonText, eventLabel, eventTone, methodLabel,
} from '../lib/labels'
import { fmtDate, fmtDuration, fmtTimeSec, relative } from '../lib/time'
import {
  Chip, Dot, Drawer, EmptyState, ErrorBanner, KV, PageHeader, Select, Skeleton, Tabs,
} from '../components/ui'

/** Outcome shortcuts, mapped onto the real filters the API understands. */
const OUTCOMES: { key: string; label: string; q: Record<string, string | string[]> }[] = [
  { key: 'all', label: 'All events', q: {} },
  { key: 'granted', label: 'Granted', q: { event_type: ['ACCESS_GRANTED'] } },
  { key: 'denied', label: 'Denied', q: { event_type: ['ACCESS_DENIED'] } },
  { key: 'security', label: 'All security events', q: { security_only: 'true' } },
  { key: 'mismatch', label: 'Identity mismatch', q: { reason: 'IDENTITY_MISMATCH' } },
  { key: 'expired', label: 'Expired QR', q: { reason: 'BOOKING_EXPIRED' } },
  { key: 'wronglab', label: 'Wrong lab', q: { reason: 'WRONG_LAB' } },
  { key: 'rfid', label: 'Unknown RFID', q: { reason: 'UNKNOWN_CREDENTIAL' } },
  { key: 'bio', label: 'Biometric failed', q: { reason: 'BIOMETRIC_FAILED' } },
  { key: 'door', label: 'Door', q: { event_type: ['DOOR_OPENED', 'DOOR_CLOSED', 'EXIT_RECORDED'] } },
]

const EVENT_TYPES = [
  'QR_SCAN', 'QR_VALIDATED', 'QR_REJECTED', 'RFID_ACCEPTED', 'RFID_REJECTED',
  'FINGERPRINT_ACCEPTED', 'FINGERPRINT_REJECTED', 'FACE_ACCEPTED', 'FACE_REJECTED',
  'IDENTITY_MISMATCH', 'ACCESS_GRANTED', 'ACCESS_DENIED', 'DOOR_OPENED', 'DOOR_CLOSED',
  'EXIT_RECORDED', 'BOOKING_CREATED', 'BOOKING_CONFIRMED', 'BOOKING_CANCELLED',
  'QR_GENERATED', 'DEVICE_ONLINE', 'DEVICE_OFFLINE', 'ASSET_CHECKOUT', 'ASSET_RETURN',
]

export default function AccessMonitor() {
  const { user } = useAuth()
  const [tab, setTab] = useState<'events' | 'sessions'>('events')
  return (
    <div>
      <PageHeader eyebrow="Security & traceability" title={isAdmin(user) ? 'Access & audit' : 'Access monitor'}
        sub="Every authentication attempt and door transition, with the reason it was allowed or refused - and every occupancy session." />
      <Tabs id="access" value={tab} onChange={setTab} tabs={[
        { key: 'events', label: 'Events', icon: <Activity size={14} /> },
        { key: 'sessions', label: 'Sessions', icon: <DoorOpen size={14} /> },
      ]} />
      <div className="mt-5">{tab === 'events' ? <Events /> : <Sessions />}</div>
    </div>
  )
}

function Events() {
  const { connected } = useLive()
  const [rows, setRows] = useState<AccessEvent[] | null>(null)
  const [labs, setLabs] = useState<Lab[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [outcome, setOutcome] = useState('all')
  const [f, setF] = useState({ lab_id: '', user_id: '', event_type: '', method: '', since: '', until: '' })
  const [selected, setSelected] = useState<AccessEvent | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.labs().then(setLabs).catch(() => {})
    api.users().then(setUsers).catch(() => {})
  }, [])

  const query = useMemo(() => {
    const q: Record<string, string | string[] | number | undefined> = { limit: 400,
      lab_id: f.lab_id || undefined, user_id: f.user_id || undefined, method: f.method || undefined,
      since: f.since ? new Date(`${f.since}T00:00`).toISOString() : undefined,
      until: f.until ? new Date(`${f.until}T23:59:59`).toISOString() : undefined }
    const o = OUTCOMES.find(x => x.key === outcome)!.q
    Object.assign(q, o)
    if (f.event_type) q.event_type = [f.event_type]
    return q
  }, [f, outcome])

  const load = useCallback(() => {
    api.events(query as Record<string, string>).then(setRows)
      .catch(e => { setError(e.message); setRows([]) })
  }, [query])
  useEffect(() => { setRows(null); load() }, [load])

  const unfiltered = outcome === 'all' && !Object.values(f).some(Boolean)
  useLiveMessages(m => {
    if (m.type !== 'access_event') return
    if (unfiltered) setRows(p => [m.event, ...(p ?? []).filter(x => x.id !== m.event.id)].slice(0, 400))
    else load()
  })

  async function exportCsv() {
    try {
      const blob = await fetchBlob(api.exportEventsPath(f.lab_id ? Number(f.lab_id) : undefined))
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `access-events-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) { setError(e instanceof Error ? e.message : 'Export failed') }
  }

  const set = (k: keyof typeof f) => (v: string) => setF(p => ({ ...p, [k]: v }))
  const active = Object.values(f).filter(Boolean).length + (outcome !== 'all' ? 1 : 0)

  return (
    <div>
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}
      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1 mb-3">
        {OUTCOMES.map(o => (
          <button key={o.key} onClick={() => setOutcome(o.key)} aria-pressed={outcome === o.key}
            className={`btn btn-sm border shrink-0 ${outcome === o.key
              ? 'bg-accent-500/15 text-accent-100 border-accent-500/45'
              : 'border-ink-500 text-slate-300 hover:text-white bg-ink-800/40'}`}>{o.label}</button>
        ))}
      </div>
      <div className="card p-4 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={13} className="text-slate-400" /><span className="label">Filters</span>
          {active > 0 && <button className="text-xs link inline-flex items-center gap-1"
            onClick={() => { setF({ lab_id: '', user_id: '', event_type: '', method: '', since: '', until: '' }); setOutcome('all') }}>
            <X size={12} />Clear {active}</button>}
          <span className="ml-auto flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-[12px] text-slate-400">
              <Dot tone={connected ? 'ok' : 'idle'} live={connected} />{connected ? 'Live' : 'Reconnecting'}</span>
            <button onClick={exportCsv} className="btn-ghost btn-sm"><Download size={14} />Export CSV</button>
          </span>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-6 gap-3">
          <Select value={f.lab_id} onChange={set('lab_id')}
                  options={[['', 'All labs'], ...labs.map(l => [String(l.id), l.code] as [string, string])]} />
          <Select value={f.user_id} onChange={set('user_id')}
                  options={[['', 'Anyone'], ...users.map(u => [String(u.id), u.full_name] as [string, string])]} />
          <Select value={f.event_type} onChange={set('event_type')}
                  options={[['', 'Any event'], ...EVENT_TYPES.map(t => [t, eventLabel(t)] as [string, string])]} />
          <Select value={f.method} onChange={set('method')}
                  options={[['', 'Any method'], ...['QR', 'RFID', 'FINGERPRINT', 'FACE', 'PORTAL']
                    .map(m => [m, methodLabel(m)] as [string, string])]} />
          <input type="date" className="input" value={f.since} onChange={e => set('since')(e.target.value)} aria-label="From" />
          <input type="date" className="input" value={f.until} onChange={e => set('until')(e.target.value)} aria-label="To" />
        </div>
      </div>

      <div className="card overflow-hidden">
        {rows === null ? <div className="p-4 space-y-2">{[0, 1, 2, 3, 4].map(i => <Skeleton key={i} className="h-10" />)}</div>
          : rows.length === 0 ? <EmptyState icon={<ShieldCheck size={20} />} title="No events match"
              detail="Widen the filters, or wait for activity at a door." />
          : (
            <div className="overflow-x-auto max-h-[64vh]">
              <table className="w-full min-w-[980px]">
                <thead><tr>
                  <th className="th">Time</th><th className="th">Lab</th><th className="th">Event</th>
                  <th className="th">Person</th><th className="th">Method</th><th className="th">Reason</th>
                  <th className="th">Detail</th><th className="th"></th>
                </tr></thead>
                <tbody>
                  {rows.map(e => (
                    <tr key={e.id} className="tr cursor-pointer" onClick={() => setSelected(e)}>
                      <td className="td whitespace-nowrap text-slate-300 tnum">
                        <div>{fmtTimeSec(e.created_at)}</div>
                        <div className="text-[11px] text-slate-500">{fmtDate(e.created_at)}</div>
                      </td>
                      <td className="td mono text-slate-300">{e.lab_code ?? '—'}</td>
                      <td className="td"><Chip tone={eventTone(e.event_type)}>{eventLabel(e.event_type)}</Chip></td>
                      <td className="td text-slate-100">{e.user_name ?? <span className="text-slate-500">Not identified</span>}</td>
                      <td className="td text-slate-300">{e.method ? methodLabel(e.method) : '—'}</td>
                      <td className="td">{e.reason ? <span className="text-bad-soft text-[12.5px]">{denialShort(e.reason)}</span>
                        : <span className="text-slate-600">—</span>}</td>
                      <td className="td text-slate-400 max-w-[280px] truncate">{e.message}</td>
                      <td className="td text-right">{e.booking_id && (
                        <Link to={`/bookings/${e.booking_id}`} onClick={ev => ev.stopPropagation()}
                              className="text-xs link whitespace-nowrap">Trace</Link>)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>

      <Drawer open={!!selected} onClose={() => setSelected(null)}
              title={selected ? eventLabel(selected.event_type) : ''}
              subtitle={selected ? `Access event #${selected.id} · ${relative(selected.created_at)}` : ''}>
        {selected && (
          <div className="space-y-5">
            <Chip tone={eventTone(selected.event_type)}>{selected.event_type.replace(/_/g, ' ')}</Chip>
            {selected.reason && (
              <div className="rounded-xl border border-bad/40 bg-bad/[0.08] p-4">
                <div className="label !text-bad-soft/80">Why it was refused</div>
                <div className="mt-1.5 text-sm text-red-100">{denialText(selected.reason)}</div>
                <div className="mono text-bad-soft/70 mt-1">{selected.reason}</div>
              </div>
            )}
            <dl>
              <KV label="Timestamp">{new Date(selected.created_at).toLocaleString([], { hour12: false })}</KV>
              <KV label="Laboratory" mono>{selected.lab_code ?? '—'}</KV>
              <KV label="Person">{selected.user_name ?? 'Not identified'}</KV>
              <KV label="Method">{selected.method ? methodLabel(selected.method) : '—'}</KV>
              <KV label="Result">{selected.result ?? '—'}</KV>
              <KV label="Booking" mono>{selected.booking_id ? `#${selected.booking_id}` : '—'}</KV>
              <KV label="Device">{selected.device_name ?? (selected.device_id ? `#${selected.device_id}` : '—')}</KV>
            </dl>
            <div><div className="label mb-1.5">Message</div>
              <p className="text-[13.5px] text-slate-200 leading-relaxed">{selected.message || '—'}</p></div>
            <div className="flex flex-col gap-2">
              {selected.booking_id && (
                <Link to={`/bookings/${selected.booking_id}`} className="btn-primary"><ListChecks size={15} />
                  Open the full booking trace</Link>
              )}
              {selected.lab_id && (
                <Link to={`/issues/new?lab=${selected.lab_id}&event=${selected.id}${selected.device_id ? `&device=${selected.device_id}` : ''}`}
                      className="btn-ghost"><Wrench size={15} />Report a hardware issue from this event</Link>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}

function Sessions() {
  const [rows, setRows] = useState<Session[] | null>(null)
  const [openOnly, setOpenOnly] = useState(false)
  const load = useCallback(() => api.sessions({ open_only: openOnly || undefined, limit: 300 })
    .then(setRows).catch(() => setRows([])), [openOnly])
  useEffect(() => { setRows(null); load() }, [load])
  useLiveMessages(m => {
    if (m.type === 'access_event' && /^(ACCESS_GRANTED|DOOR|EXIT)/.test(m.event.event_type)) load()
  })

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
        <p className="text-[13px] text-slate-400 max-w-2xl">
          A session opens when access is granted. The door closing behind someone does not end it;
          only a recorded exit gives an exit time and duration. Everything else says how the
          session actually stopped counting.
        </p>
        <label className="flex items-center gap-2 text-[13px] text-slate-300">
          <input type="checkbox" checked={openOnly} onChange={e => setOpenOnly(e.target.checked)}
                 className="accent-sky-500" />Inside now only</label>
      </div>
      <div className="card overflow-hidden">
        {rows === null ? <div className="p-4"><Skeleton className="h-40" /></div>
          : rows.length === 0 ? <EmptyState icon={<DoorOpen size={20} />} title="No sessions"
              detail="Sessions appear when the door grants access." />
          : (
            <div className="overflow-x-auto max-h-[64vh]">
              <table className="w-full min-w-[1000px]">
                <thead><tr>
                  <th className="th">Entry</th><th className="th">Lab</th><th className="th">Person</th>
                  <th className="th">Factors</th><th className="th">Door opened</th><th className="th">Door closed</th>
                  <th className="th">Exit / end</th><th className="th">Inside</th><th className="th"></th>
                </tr></thead>
                <tbody>
                  {rows.map(s => (
                    <tr key={s.id} className="tr">
                      <td className="td tnum text-slate-200">{fmtTimeSec(s.started_at)}
                        <div className="text-[11px] text-slate-500">{fmtDate(s.started_at)}</div></td>
                      <td className="td mono text-slate-300">{s.lab_code}</td>
                      <td className="td text-slate-100">{s.user_name}</td>
                      <td className="td text-slate-300 text-[12.5px]">{methodLabel(s.entry_method)}
                        {s.second_factor ? ` + ${methodLabel(s.second_factor)}` : ''}</td>
                      <td className="td tnum text-slate-300">{s.door_opened_at ? fmtTimeSec(s.door_opened_at) : '—'}</td>
                      <td className="td tnum text-slate-300">{s.door_closed_at ? fmtTimeSec(s.door_closed_at) : '—'}</td>
                      <td className="td text-[12.5px]">
                        {s.ended_at === null ? <span className="flex items-center gap-1.5 text-violet-300"><Dot tone="violet" live />Inside</span>
                          : s.end_reason === 'EXIT_RECORDED' ? <span className="text-slate-100 tnum">Exit {fmtTimeSec(s.ended_at)}</span>
                          : <span className="text-slate-400">{endReasonText(s.end_reason)}</span>}
                      </td>
                      <td className="td tnum text-slate-200">{s.duration_minutes != null ? fmtDuration(s.duration_minutes) : '—'}</td>
                      <td className="td text-right">{s.booking_id && <Link to={`/bookings/${s.booking_id}`} className="text-xs link">Trace</Link>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>
    </div>
  )
}
