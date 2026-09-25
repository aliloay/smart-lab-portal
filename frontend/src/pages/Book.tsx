/**
 * Guided booking: laboratory, date, time, purpose, review, confirmed.
 *
 * Availability comes from /labs/{id}/availability, which returns every
 * reserved interval - everyone's, without identities - so a taken hour looks
 * taken before anyone tries to book it. It refreshes while the page is open
 * and after any conflict. The server still re-validates every booking: the
 * picker is a convenience, not the authority.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft, ArrowRight, Calendar, Check, CircuitBoard, Clock, FileText, FlaskConical,
  MapPin, QrCode, Search, ShieldCheck, UserRound,
} from 'lucide-react'
import { Booking, BookingSlot, Lab, User, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { dateStr, localDayBounds, pad2, todayStr } from '../lib/time'
import { Chip, ErrorBanner, Notice, PageHeader, Skeleton, SuccessMark } from '../components/ui'
import { LabArt, categoryMeta } from '../components/labArt'
import { GridField } from '../components/visual'

const STEPS = ['Laboratory', 'Date', 'Time', 'Purpose', 'Review', 'Confirmed'] as const
const DAY_START = 8
const DAY_END = 22
const MAX_HOURS = 8
// "Test QR now": a short booking that starts immediately, so the door can
// be tested at any hour - including outside DAY_START..DAY_END, when the
// grid has nothing left to pick.
const TEST_MINUTES = 30
const PURPOSES = ['Thesis experiment', 'Course lab session', 'Project prototyping',
                  'Equipment training', 'Measurement / testing']

export default function Book() {
  const { user } = useAuth()
  const staff = isStaff(user)
  const nav = useNavigate()
  const [params] = useSearchParams()

  const [labs, setLabs] = useState<Lab[] | null>(null)
  const [people, setPeople] = useState<User[]>([])
  const [step, setStep] = useState(0)
  const [labId, setLabId] = useState<number | null>(null)
  const [date, setDate] = useState(params.get('date') ?? todayStr())
  const [startHour, setStartHour] = useState<number | null>(null)
  const [endHour, setEndHour] = useState<number | null>(null)
  // 'grid' = whole hours from the availability grid; 'exact' = any time,
  // to the minute, with AM/PM - e.g. 12:10 AM, outside the grid's hours.
  const [mode, setMode] = useState<'grid' | 'exact'>('grid')
  const [exStart, setExStart] = useState<Clock12>(() => nowClock12(0))
  const [exEnd, setExEnd] = useState<Clock12>(() => nowClock12(60))
  const [reason, setReason] = useState('')
  const [forUser, setForUser] = useState<string>('')
  const [slots, setSlots] = useState<BookingSlot[] | null>(null)
  const [fortnight, setFortnight] = useState<BookingSlot[]>([])
  const [q, setQ] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<Booking | null>(null)

  useEffect(() => {
    api.labs().then(l => {
      const active = l.filter(x => x.is_active)
      setLabs(active)
      const pre = Number(params.get('lab'))
      if (pre && active.some(x => x.id === pre)) {
        setLabId(pre)
        setStep(params.get('date') ? 2 : 1)
      }
    }).catch(e => { setError(e.message); setLabs([]) })
    if (staff) api.users().then(u => setPeople(u.filter(x => x.is_active))).catch(() => {})
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  const lab = labs?.find(l => l.id === labId) ?? null

  // --- availability -------------------------------------------------------
  const loadDay = useCallback(() => {
    if (!labId) return
    const [s, e] = localDayBounds(date)
    api.availability(labId, s, e).then(setSlots).catch(() => setSlots([]))
  }, [labId, date])

  useEffect(() => { setSlots(null); loadDay() }, [loadDay])
  useEffect(() => {
    if (!labId) return
    const [s] = localDayBounds(todayStr())
    const e = new Date(s); e.setDate(e.getDate() + 14)
    api.availability(labId, s, e.toISOString()).then(setFortnight).catch(() => setFortnight([]))
  }, [labId])
  // Fresh without a manual refresh: poll while picking, and on any booking event.
  useEffect(() => {
    if (step !== 2) return
    const t = window.setInterval(loadDay, 30000)
    return () => window.clearInterval(t)
  }, [step, loadDay])
  useLiveMessages(m => {
    if (m.type === 'access_event' && m.event.event_type.startsWith('BOOKING')) loadDay()
  })

  /** hour -> 'taken' | 'mine' */
  const hourState = useMemo(() => {
    const m = new Map<number, 'taken' | 'mine'>()
    for (const s of slots ?? []) {
      const a = new Date(s.start_time), b = new Date(s.end_time)
      for (let h = DAY_START; h < DAY_END; h++) {
        const hs = new Date(`${date}T${pad2(h)}:00`), he = new Date(hs.getTime() + 3600e3)
        if (hs < b && he > a) m.set(h, s.is_mine ? 'mine' : 'taken')
      }
    }
    return m
  }, [slots, date])

  const pastHours = useMemo(() => {
    const p = new Set<number>()
    if (date === todayStr()) {
      const nowH = new Date().getHours()
      // The current hour stays bookable: the server only requires the
      // window to end in the future, and "book it now" is a real need.
      for (let h = DAY_START; h < nowH; h++) p.add(h)
    }
    return p
  }, [date, step])   // eslint-disable-line react-hooks/exhaustive-deps

  // A selection that has since become taken is dropped, not silently kept.
  useEffect(() => {
    if (startHour === null) return
    const end = endHour ?? startHour + 1
    for (let h = startHour; h < end; h++) {
      if (hourState.has(h) || pastHours.has(h)) { setStartHour(null); setEndHour(null); return }
    }
  }, [hourState, pastHours])   // eslint-disable-line react-hooks/exhaustive-deps

  function pickHour(h: number) {
    setError('')
    if (startHour === null || endHour !== null) { setStartHour(h); setEndHour(null); return }
    if (h === startHour) { setEndHour(h + 1); return }
    if (h < startHour) { setStartHour(h); return }
    for (let x = startHour; x <= h; x++) {
      if (hourState.has(x)) { setStartHour(h); setEndHour(null); return }
    }
    if (h + 1 - startHour > MAX_HOURS) {
      setError(`A booking can be at most ${MAX_HOURS} hours.`); return
    }
    setEndHour(h + 1)
  }

  const inRange = (h: number) => startHour !== null && (
    endHour === null ? h === startHour : h >= startHour && h < endHour)

  /** The chosen window as local Date objects, whichever tab picked it. */
  const win = useMemo<{ start: Date; end: Date } | null>(() => {
    if (mode === 'grid') {
      if (startHour === null || endHour === null) return null
      return { start: new Date(`${date}T${pad2(startHour)}:00`),
               end: new Date(`${date}T${pad2(endHour % 24)}:00`) }
    }
    const start = new Date(`${date}T${to24(exStart)}`)
    const end = new Date(`${date}T${to24(exEnd)}`)
    // An end at or before the start means it runs past midnight.
    if (end <= start) end.setDate(end.getDate() + 1)
    return { start, end }
  }, [mode, date, startHour, endHour, exStart, exEnd])

  const exactProblem = mode !== 'exact' || !win ? ''
    : win.end.getTime() - win.start.getTime() > MAX_HOURS * 3600e3
      ? `A booking can be at most ${MAX_HOURS} hours.`
    : win.end <= new Date() ? 'That time has already passed.' : ''

  const canNext = [labId !== null, !!date, win !== null && !exactProblem,
                   true, true][step] ?? false

  async function submit() {
    if (!win || !labId) return
    setError(''); setBusy(true)
    try {
      const b = await api.createBooking({
        lab_id: labId,
        start_time: win.start.toISOString(),
        end_time: win.end.toISOString(),
        reason: reason.trim(),
        user_id: forUser ? Number(forUser) : undefined,
      })
      setDone(b)
      setStep(5)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Booking failed')
      // Most likely someone else just took the slot: show the fresh picture.
      loadDay()
      setStep(2)
    } finally {
      setBusy(false)
    }
  }

  /** Book from right now for TEST_MINUTES and go straight to the QR. */
  async function testQrNow() {
    if (!labId) return
    setError(''); setBusy(true)
    try {
      // Start a minute back so a browser clock slightly ahead of the server
      // does not produce a credential that is "not valid yet".
      const start = new Date(Date.now() - 60e3)
      const end = new Date(Date.now() + TEST_MINUTES * 60e3)
      const b = await api.createBooking({
        lab_id: labId,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        reason: 'QR door test',
        user_id: forUser ? Number(forUser) : undefined,
      })
      nav(`/bookings/${b.id}/qr`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Test booking failed')
      loadDay()
    } finally {
      setBusy(false)
    }
  }

  // ------------------------------------------------------------ confirmed
  if (done) return <Confirmed b={done} onAnother={() => {
    setDone(null); setStep(0); setStartHour(null); setEndHour(null); setReason('')
  }} onQr={() => nav(`/bookings/${done.id}/qr`)} />

  return (
    <div className="max-w-5xl mx-auto">
      <PageHeader eyebrow="Reservation" title={staff && forUser ? 'Create booking for user' : 'Book a laboratory'}
        sub="A confirmed booking issues an access credential that is valid only for that laboratory, only inside your window." />

      <Stepper step={step} />

      <div className="mt-5 grid lg:grid-cols-[1fr_300px] gap-5">
        <div className="card p-5 sm:p-6 min-h-[380px]">
          {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div key={step} initial={{ opacity: 0, x: 14 }} animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -14 }} transition={{ duration: .16 }}>

              {step === 0 && (
                <div>
                  <StepTitle icon={<FlaskConical size={16} />} title="Which laboratory?" />
                  <div className="relative mb-3">
                    <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input className="input pl-9" placeholder="Filter laboratories" value={q}
                           onChange={e => setQ(e.target.value)} aria-label="Filter laboratories" />
                  </div>
                  {labs === null ? <Skeleton className="h-72" /> : (
                    <div className="grid sm:grid-cols-2 gap-2.5 max-h-[440px] overflow-y-auto pr-1">
                      {labs.filter(l => !q || `${l.code} ${l.name} ${l.category}`.toLowerCase()
                        .includes(q.toLowerCase())).map(l => {
                        const m = categoryMeta(l.category)
                        const sel = labId === l.id
                        return (
                          <button key={l.id} onClick={() => { setLabId(l.id); setStartHour(null); setEndHour(null) }}
                            aria-pressed={sel}
                            className={`text-left rounded-xl border overflow-hidden transition-all ${sel
                              ? 'border-accent-400 ring-2 ring-accent-500/30 bg-accent-500/10'
                              : 'border-ink-600 bg-ink-900/40 hover:border-ink-400'}`}>
                            <div className="relative h-16">
                              <LabArt category={l.category} className="absolute inset-0 w-full h-full" />
                              <span className="absolute bottom-1.5 left-2.5 mono text-accent-100 drop-shadow">{l.code}</span>
                              {sel && <span className="absolute top-2 right-2 grid place-items-center w-6 h-6 rounded-full bg-accent-500 text-white"><Check size={14} /></span>}
                            </div>
                            <div className="p-3">
                              <div className="text-[13.5px] text-white leading-snug">{l.name}</div>
                              <div className="mt-1 flex items-center gap-2 text-[11.5px] text-slate-400">
                                <span style={{ color: m.hue }}>{m.icon}</span>{l.category}
                                <span className="text-slate-600">·</span>
                                {l.has_controller ? <span className="text-ok-soft">Door access</span>
                                  : <span>No door hardware</span>}
                              </div>
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {step === 1 && (
                <div>
                  <StepTitle icon={<Calendar size={16} />} title="Which day?"
                    sub="The bar under each day shows how much of it is already reserved." />
                  <div className="grid grid-cols-4 sm:grid-cols-7 gap-2 mb-5">
                    {nextDays(14).map(d => {
                      const load = dayLoad(fortnight, d.value)
                      return (
                        <button key={d.value} onClick={() => setDate(d.value)} aria-pressed={date === d.value}
                          className={`rounded-xl border px-2 py-2.5 text-center transition-all ${date === d.value
                            ? 'border-accent-400 bg-accent-500/15 text-white'
                            : 'border-ink-600 bg-ink-900/40 text-slate-300 hover:border-ink-400'}`}>
                          <div className="text-[10.5px] uppercase tracking-wide text-slate-400">{d.weekday}</div>
                          <div className="font-display text-lg font-semibold">{d.day}</div>
                          <div className="text-[10.5px] text-slate-400">{d.month}</div>
                          <div className="mt-1.5 h-1 rounded-full bg-ink-700 overflow-hidden">
                            <div className={`h-full ${load > .75 ? 'bg-warn' : 'bg-accent-400'}`}
                                 style={{ width: `${load * 100}%` }} />
                          </div>
                        </button>
                      )
                    })}
                  </div>
                  <label className="label block mb-1.5" htmlFor="date">Or pick a date</label>
                  <input id="date" className="input max-w-xs" type="date" value={date} min={todayStr()}
                         onChange={e => { setDate(e.target.value); setStartHour(null); setEndHour(null) }} />
                </div>
              )}

              {step === 2 && (
                <div>
                  <StepTitle icon={<Clock size={16} />} title="Which hours?"
                    sub={mode === 'grid'
                      ? 'Tap a start hour, then an end hour. Availability updates live.'
                      : 'Pick any start and end time, to the minute.'} />
                  <div className="mb-4 inline-flex rounded-xl border border-ink-500 p-1 bg-ink-900/40" role="tablist">
                    {([['grid', 'Hour grid'], ['exact', 'Exact time (AM/PM)']] as const).map(([m, label]) => (
                      <button key={m} role="tab" aria-selected={mode === m}
                        onClick={() => { setError(''); setMode(m) }}
                        className={`px-3 py-1.5 rounded-lg text-[13px] transition-colors ${
                          mode === m ? 'bg-accent-500/25 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>
                        {label}
                      </button>
                    ))}
                  </div>
                  {mode === 'exact' ? (
                    <div className="space-y-4">
                      <div className="flex flex-wrap gap-6">
                        <ClockPicker label="Start" value={exStart} onChange={setExStart} />
                        <ClockPicker label="End" value={exEnd} onChange={setExEnd} />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button className="btn-quiet" onClick={() => { setExStart(nowClock12(0)); setExEnd(nowClock12(60)) }}>
                          Now → +1 h
                        </button>
                        <button className="btn-quiet" onClick={() => { setExStart(nowClock12(0)); setExEnd(nowClock12(30)) }}>
                          Now → +30 min
                        </button>
                      </div>
                      {win && (
                        <div className="text-sm text-slate-200 flex items-center gap-2">
                          <Clock size={14} className="text-accent-300" />
                          <b className="tnum">{fmtWin(win)}</b>
                          {win.end.getDate() !== win.start.getDate() &&
                            <span className="text-slate-400">(ends the next day)</span>}
                        </div>
                      )}
                      {exactProblem && <Notice tone="warn" icon={<Clock size={15} />}>{exactProblem}</Notice>}
                    </div>
                  ) : <>
                  <Legend />
                  {slots === null ? <Skeleton className="h-40 mt-4" /> : (
                    <div className="mt-4 grid grid-cols-4 sm:grid-cols-7 gap-2">
                      {Array.from({ length: DAY_END - DAY_START }, (_, i) => DAY_START + i).map(h => {
                        const st = hourState.get(h)
                        const past = pastHours.has(h)
                        const disabled = !!st || past
                        const sel = inRange(h)
                        return (
                          <button key={h} disabled={disabled} onClick={() => pickHour(h)}
                            aria-pressed={sel}
                            title={st === 'mine' ? 'Your existing booking' : st ? 'Already reserved'
                              : past ? 'In the past' : `${pad2(h)}:00 – ${pad2(h + 1)}:00`}
                            className={`relative py-3 rounded-xl text-[13px] border transition-all tnum ${
                              sel ? 'border-accent-400 bg-accent-500/25 text-white font-semibold shadow-glow'
                              : st === 'mine' ? 'border-accent-600/50 bg-accent-700/15 text-accent-300 cursor-not-allowed'
                              : st ? 'border-ink-600 text-slate-500 cursor-not-allowed bg-[repeating-linear-gradient(135deg,rgba(148,163,184,.08)_0_6px,transparent_6px_12px)]'
                              : past ? 'border-ink-700 text-slate-600 cursor-not-allowed bg-ink-900/60'
                              : 'border-ink-500 bg-ink-800/60 text-slate-100 hover:border-accent-400/70 hover:bg-ink-700'}`}>
                            {pad2(h)}:00
                            {st === 'taken' && <span className="block text-[9.5px] text-slate-500">reserved</span>}
                            {st === 'mine' && <span className="block text-[9.5px]">yours</span>}
                          </button>
                        )
                      })}
                    </div>
                  )}
                  <div className="mt-4 min-h-[24px] flex items-center gap-2 text-sm text-slate-200">
                    {startHour !== null && (
                      <>
                        <Clock size={14} className="text-accent-300" />
                        {endHour === null
                          ? <>Starting {pad2(startHour)}:00 · now choose an end hour (or tap it again for one hour)</>
                          : <><b className="tnum">{pad2(startHour)}:00 → {pad2(endHour)}:00</b>
                              <span className="text-slate-400">({endHour - startHour} h)</span></>}
                      </>
                    )}
                  </div>
                  </>}
                  <div className="mt-5 pt-4 border-t border-ink-600/60 flex flex-wrap items-center justify-between gap-3">
                    <div className="text-[13px] text-slate-400">
                      Testing the door? Book this laboratory from now for {TEST_MINUTES} minutes
                      and open the QR immediately.
                    </div>
                    <button className="btn-quiet" disabled={busy || !labId} onClick={testQrNow}>
                      <QrCode size={15} /> Test QR now
                    </button>
                  </div>
                </div>
              )}

              {step === 3 && (
                <div>
                  <StepTitle icon={<FileText size={16} />} title="What is it for?"
                    sub="Optional, but it helps staff plan the laboratory." />
                  <div className="flex gap-2 flex-wrap mb-3">
                    {PURPOSES.map(p => (
                      <button key={p} onClick={() => setReason(p)}
                        className={`btn btn-sm border ${reason === p
                          ? 'border-accent-400 bg-accent-500/15 text-accent-100'
                          : 'border-ink-500 text-slate-300 hover:text-white'}`}>{p}</button>
                    ))}
                  </div>
                  <textarea className="input min-h-[120px] resize-y" value={reason} maxLength={500}
                            placeholder="e.g. Thesis experiment - manipulator calibration"
                            onChange={e => setReason(e.target.value)} aria-label="Purpose" />
                  <div className="mt-1 text-right text-[11px] text-slate-500">{reason.length}/500</div>
                  {staff && (
                    <div className="mt-4">
                      <label className="label block mb-1.5" htmlFor="for">
                        <UserRound size={12} className="inline mr-1" />Book on behalf of
                      </label>
                      <select id="for" className="input" value={forUser} onChange={e => setForUser(e.target.value)}>
                        <option value="">Myself ({user?.full_name})</option>
                        {people.filter(p => p.id !== user?.id).map(p => (
                          <option key={p.id} value={p.id}>{p.full_name} · {p.email}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}

              {step === 4 && lab && win && (
                <div>
                  <StepTitle icon={<ShieldCheck size={16} />} title="Review and confirm" />
                  <dl className="well p-4 space-y-3 text-[13.5px]">
                    <Row k="Laboratory" v={<>{lab.name} <span className="mono text-slate-400">· {lab.code}</span></>} />
                    <Row k="Location" v={lab.location || '—'} />
                    <Row k="Date" v={new Date(`${date}T00:00`).toLocaleDateString([], {
                      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })} />
                    <Row k="Time" v={<span className="tnum">{fmtWin(win)}</span>} />
                    <Row k="Purpose" v={reason || '—'} />
                    {forUser && <Row k="Booked for" v={people.find(p => String(p.id) === forUser)?.full_name} />}
                    <Row k="Door access" v={<span className="inline-flex items-center gap-2">
                      <QrCode size={14} className="text-accent-300" />QR code, then fingerprint or face</span>} />
                  </dl>
                  {!lab.has_controller && (
                    <div className="mt-4"><Notice tone="warn" icon={<CircuitBoard size={15} />}>
                      This laboratory has no access-control hardware yet. The booking and its
                      credential are recorded normally, but no door will respond to it.
                    </Notice></div>
                  )}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* summary rail */}
        <aside className="card overflow-hidden h-fit">
          <div className="relative h-28">
            {lab ? <LabArt category={lab.category} className="absolute inset-0 w-full h-full" />
                 : <div className="absolute inset-0 grid place-items-center bg-ink-900/40">
                     <GridField />
                     <span className="relative text-[12px] text-slate-500">Choose a laboratory</span>
                   </div>}
            <div className="absolute inset-0 bg-gradient-to-t from-ink-800 to-transparent" />
          </div>
          <div className="p-4 space-y-3 text-[13px]">
            <SumRow icon={<FlaskConical size={14} />} label="Laboratory" value={lab ? `${lab.code} · ${lab.name}` : 'Not chosen'} />
            <SumRow icon={<MapPin size={14} />} label="Location" value={lab?.location || '—'} />
            <SumRow icon={<Calendar size={14} />} label="Date" value={new Date(`${date}T00:00`)
              .toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })} />
            <SumRow icon={<Clock size={14} />} label="Time" value={win ? fmtWin(win) : 'Not chosen'} />
          </div>
        </aside>
      </div>

      <div className="mt-5 flex items-center justify-between">
        <button className="btn-quiet" disabled={step === 0} onClick={() => { setError(''); setStep(s => Math.max(0, s - 1)) }}>
          <ArrowLeft size={15} />Back
        </button>
        {step < 4 ? (
          <button className="btn-primary" disabled={!canNext} onClick={() => { setError(''); setStep(s => s + 1) }}>
            Continue<ArrowRight size={15} />
          </button>
        ) : (
          <button className="btn-primary !px-6" disabled={busy} onClick={submit}>
            {busy ? 'Confirming…' : 'Confirm booking'}{!busy && <Check size={16} />}
          </button>
        )}
      </div>
    </div>
  )
}

function Stepper({ step }: { step: number }) {
  return (
    <ol className="flex items-center gap-2" aria-label="Booking steps">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-2 flex-1 last:flex-none"
            aria-current={i === step ? 'step' : undefined}>
          <div className={`flex items-center gap-2 ${i > step ? 'opacity-50' : ''}`}>
            <span className={`w-7 h-7 rounded-full grid place-items-center text-[12px] font-semibold
              transition-colors ${i < step ? 'bg-ok/20 text-ok-soft border border-ok/45'
                : i === step ? 'bg-accent-500/25 text-accent-100 border border-accent-400 shadow-glow'
                : 'bg-ink-800 text-slate-400 border border-ink-500'}`}>
              {i < step ? <Check size={13} strokeWidth={3} /> : i + 1}
            </span>
            <span className={`hidden md:block text-[12.5px] ${i === step ? 'text-white font-medium' : 'text-slate-400'}`}>{s}</span>
          </div>
          {i < STEPS.length - 1 && (
            <span className={`flex-1 h-px ${i < step ? 'bg-ok/50' : 'bg-ink-600'}`} />
          )}
        </li>
      ))}
    </ol>
  )
}

/** A 12-hour clock reading: hour 1-12, minute 0-59, AM/PM. */
interface Clock12 { h: number; m: number; ap: 'AM' | 'PM' }

function nowClock12(plusMinutes: number): Clock12 {
  const d = new Date(Date.now() + plusMinutes * 60e3)
  const h24 = d.getHours()
  return { h: h24 % 12 || 12, m: d.getMinutes(), ap: h24 < 12 ? 'AM' : 'PM' }
}

/** Clock12 -> "HH:MM" (24-hour) for building a local Date. */
function to24(c: Clock12): string {
  const h = (c.h % 12) + (c.ap === 'PM' ? 12 : 0)
  return `${pad2(h)}:${pad2(c.m)}`
}

const fmt12 = (d: Date) =>
  d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true })

function fmtWin(w: { start: Date; end: Date }): string {
  const mins = Math.round((w.end.getTime() - w.start.getTime()) / 60e3)
  const dur = mins % 60 ? `${Math.floor(mins / 60) ? `${Math.floor(mins / 60)} h ` : ''}${mins % 60} min`
                        : `${mins / 60} h`
  return `${fmt12(w.start)} → ${fmt12(w.end)} (${dur})`
}

function ClockPicker({ label, value, onChange }:
  { label: string; value: Clock12; onChange: (c: Clock12) => void }) {
  return (
    <div>
      <div className="label mb-1.5">{label}</div>
      <div className="flex items-center gap-2">
        <select className="input w-[88px] tnum" aria-label={`${label} hour`} value={value.h}
          onChange={e => onChange({ ...value, h: Number(e.target.value) })}>
          {Array.from({ length: 12 }, (_, i) => i + 1).map(h => <option key={h} value={h}>{h}</option>)}
        </select>
        <span className="text-slate-400">:</span>
        <select className="input w-[88px] tnum" aria-label={`${label} minute`} value={value.m}
          onChange={e => onChange({ ...value, m: Number(e.target.value) })}>
          {Array.from({ length: 60 }, (_, i) => i).map(m => <option key={m} value={m}>{pad2(m)}</option>)}
        </select>
        <div className="inline-flex rounded-lg border border-ink-500 overflow-hidden">
          {(['AM', 'PM'] as const).map(ap => (
            <button key={ap} aria-pressed={value.ap === ap} onClick={() => onChange({ ...value, ap })}
              className={`px-3 py-2 text-[13px] ${value.ap === ap
                ? 'bg-accent-500/25 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>
              {ap}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function StepTitle({ icon, title, sub }: { icon: React.ReactNode; title: string; sub?: string }) {
  return (
    <div className="mb-4">
      <h2 className="flex items-center gap-2 text-[16px] font-semibold text-white">
        <span className="text-accent-300">{icon}</span>{title}
      </h2>
      {sub && <p className="text-[13px] text-slate-400 mt-1">{sub}</p>}
    </div>
  )
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-4 text-[11.5px] text-slate-400">
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border border-ink-500 bg-ink-800" />Free</span>
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border border-accent-400 bg-accent-500/30" />Selected</span>
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border border-ink-600 bg-[repeating-linear-gradient(135deg,rgba(148,163,184,.25)_0_2px,transparent_2px_4px)]" />Reserved</span>
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border border-accent-600/50 bg-accent-700/20" />Your booking</span>
    </div>
  )
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex items-start justify-between gap-4"><dt className="label pt-0.5">{k}</dt>
    <dd className="text-slate-100 text-right">{v}</dd></div>
}

function SumRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="text-accent-300 mt-0.5">{icon}</span>
      <div className="min-w-0"><div className="text-[11px] text-slate-400">{label}</div>
        <div className="text-slate-100 leading-snug">{value}</div></div>
    </div>
  )
}

function Confirmed({ b, onAnother, onQr }: { b: Booking; onAnother: () => void; onQr: () => void }) {
  const pending = b.status === 'PENDING'
  return (
    <div className="max-w-xl mx-auto">
      <Stepper step={5} />
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  className="mt-6 card overflow-hidden text-center">
        <div className="relative h-28">
          <LabArt category={b.lab_category} className="absolute inset-0 w-full h-full" />
          <div className="absolute inset-0 bg-gradient-to-t from-ink-800 to-ink-800/30" />
        </div>
        <div className="px-7 pb-7 -mt-8 relative">
          <div className="inline-grid place-items-center w-16 h-16 rounded-full bg-ink-800 border border-ok/40">
            <SuccessMark size={48} />
          </div>
          <div className="mt-3 eyebrow !text-ok-soft">{pending ? 'Request submitted' : 'Booking confirmed'}</div>
          <h1 className="mt-1 font-display text-2xl font-semibold text-white">{b.lab_name}</h1>
          <div className="mt-6 well p-4 text-left space-y-2.5 text-[13.5px]">
            <Row k="Laboratory" v={<span className="mono">{b.lab_code}</span>} />
            <Row k="Date" v={new Date(b.start_time).toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })} />
            <Row k="Time" v={<span className="tnum">{new Date(b.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              {' → '}{new Date(b.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>} />
            {b.reason && <Row k="Purpose" v={b.reason} />}
            {b.user_name && <Row k="Booked for" v={b.user_name} />}
          </div>
          <div className={`mt-4 rounded-xl border px-4 py-3 flex items-center gap-3 text-left ${pending
            ? 'border-warn/35 bg-warn/[0.07]' : 'border-ok/35 bg-ok/[0.08]'}`}>
            <QrCode size={20} className={pending ? 'text-warn-soft' : 'text-ok-soft'} />
            <div>
              <div className={`text-[13px] font-semibold ${pending ? 'text-warn-soft' : 'text-ok-soft'}`}>
                {pending ? 'Awaiting approval' : 'Access credential ready'}</div>
              <div className="text-[12px] text-slate-300">
                {pending ? 'Staff will review the request; you will be notified.'
                  : 'Valid only for this laboratory, only during this window.'}</div>
            </div>
          </div>
          <div className="mt-6 flex flex-col sm:flex-row gap-2.5 justify-center">
            {!pending && <button onClick={onQr} className="btn-primary"><QrCode size={16} />Open QR</button>}
            <Link to={`/bookings/${b.id}`} className="btn-ghost">View booking</Link>
            <button onClick={onAnother} className="btn-quiet">Book another</button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

function nextDays(n: number) {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() + i)
    return {
      value: dateStr(d),
      weekday: i === 0 ? 'Today' : d.toLocaleDateString([], { weekday: 'short' }),
      day: d.getDate(),
      month: d.toLocaleDateString([], { month: 'short' }),
    }
  })
}

/** Fraction of the bookable day already reserved, from real slots. */
function dayLoad(slots: BookingSlot[], date: string): number {
  const ds = new Date(`${date}T${pad2(DAY_START)}:00`).getTime()
  const de = new Date(`${date}T${pad2(DAY_END)}:00`).getTime()
  let busy = 0
  for (const s of slots) {
    const a = Math.max(ds, new Date(s.start_time).getTime())
    const b = Math.min(de, new Date(s.end_time).getTime())
    if (b > a) busy += b - a
  }
  return Math.min(1, busy / (de - ds))
}
