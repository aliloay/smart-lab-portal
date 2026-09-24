/**
 * Guided booking.
 *
 * Four steps rather than one form, because the choices are dependent: which
 * hours are free depends on the laboratory and the date, so asking for them
 * all at once means showing availability for something the person has not
 * chosen yet.
 *
 * The availability shown here is a CONVENIENCE. The backend re-validates
 * every booking against the live database — a browser can be stale, edited,
 * or simply lying.
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft, ArrowRight, Calendar, Check, CircuitBoard, Clock, FlaskConical,
  MapPin, QrCode,
} from 'lucide-react'
import { Booking, Lab, api } from '../lib/api'
import { localToUtcIso } from '../lib/time'
import { Chip, ErrorBanner, SuccessMark } from '../components/ui'

const STEPS = ['Laboratory', 'Date', 'Time', 'Confirm'] as const

/** The day the facility is open. Slots outside this are not offered at all. */
const DAY_START = 8
const DAY_END = 22

export default function Book() {
  const nav = useNavigate()
  const [labs, setLabs] = useState<Lab[]>([])
  const [existing, setExisting] = useState<Booking[]>([])
  const [loading, setLoading] = useState(true)

  const [step, setStep] = useState(0)
  const [labId, setLabId] = useState<number | null>(null)
  const [date, setDate] = useState(todayStr())
  const [startHour, setStartHour] = useState<number | null>(null)
  const [endHour, setEndHour] = useState<number | null>(null)
  const [reason, setReason] = useState('')

  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<Booking | null>(null)

  useEffect(() => {
    Promise.all([api.labs(), api.bookings()])
      .then(([l, b]) => { setLabs(l.filter(x => x.is_active)); setExisting(b) })
      .finally(() => setLoading(false))
  }, [])

  const lab = labs.find(l => l.id === labId) ?? null

  /** Hours already taken in this lab on this date. */
  const takenHours = useMemo(() => {
    if (!labId) return new Set<number>()
    const taken = new Set<number>()
    for (const b of existing) {
      if (b.lab_id !== labId) continue
      if (b.status !== 'CONFIRMED' && b.status !== 'PENDING') continue
      const s = new Date(b.start_time)
      const e = new Date(b.end_time)
      if (dateStr(s) !== date) continue
      for (let h = s.getHours(); h < e.getHours() + (e.getMinutes() ? 1 : 0); h++) {
        taken.add(h)
      }
    }
    return taken
  }, [existing, labId, date])

  /** Hours in the past today cannot be booked. */
  const pastHours = useMemo(() => {
    const p = new Set<number>()
    if (date === todayStr()) {
      const nowH = new Date().getHours()
      for (let h = DAY_START; h < nowH; h++) p.add(h)
    }
    return p
  }, [date])

  function pickHour(h: number) {
    if (startHour === null || endHour !== null) {
      setStartHour(h); setEndHour(null); return
    }
    if (h === startHour) { setStartHour(null); return }
    if (h < startHour) { setStartHour(h); return }
    // Reject a range that jumps over an already-booked hour.
    for (let x = startHour; x <= h; x++) {
      if (takenHours.has(x)) { setStartHour(h); setEndHour(null); return }
    }
    setEndHour(h + 1)
  }

  const inRange = (h: number) =>
    startHour !== null && endHour !== null && h >= startHour && h < endHour

  const canNext =
    (step === 0 && labId !== null) ||
    (step === 1 && !!date) ||
    (step === 2 && startHour !== null && endHour !== null) ||
    step === 3

  async function submit() {
    if (startHour === null || endHour === null || !labId) return
    setError(''); setBusy(true)
    try {
      const b = await api.createBooking({
        lab_id: labId,
        start_time: localToUtcIso(date, `${pad(startHour)}:00`),
        end_time: localToUtcIso(date, `${pad(endHour)}:00`),
        reason,
      })
      setDone(b)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Booking failed')
    } finally {
      setBusy(false)
    }
  }

  /* ------------------------------------------------------- confirmation */
  if (done) {
    return (
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  className="max-w-lg mx-auto text-center">
        <div className="card p-8">
          <SuccessMark />
          <h1 className="mt-5 text-xl font-semibold text-white">Booking confirmed</h1>
          <p className="text-sm text-slate-400 mt-1.5">
            A time-bound access credential has been issued for this laboratory.
          </p>

          <div className="mt-7 text-left space-y-3 rounded-lg bg-ink-900/60
                          border border-ink-700 p-4">
            <Line label="Laboratory" value={done.lab_name ?? ''} />
            <Line label="Code" value={<span className="mono">{done.lab_code}</span>} />
            <Line label="Date" value={new Date(done.start_time)
              .toLocaleDateString([], { day: 'numeric', month: 'long', year: 'numeric' })} />
            <Line label="Time" value={
              `${new Date(done.start_time).toLocaleTimeString([], {
                hour: '2-digit', minute: '2-digit' })} – ${
                new Date(done.end_time).toLocaleTimeString([], {
                hour: '2-digit', minute: '2-digit' })}`} />
            {done.reason && <Line label="Purpose" value={done.reason} />}
            <Line label="Access" value={<Chip tone="ok">QR credential ready</Chip>} />
          </div>

          <div className="mt-7 flex flex-col sm:flex-row gap-2.5 justify-center">
            <button onClick={() => nav(`/bookings/${done.id}/qr`)}
                    className="btn-primary"><QrCode size={15} />Show access code</button>
            <button onClick={() => nav('/bookings')} className="btn-ghost">
              My bookings
            </button>
          </div>
        </div>
      </motion.div>
    )
  }

  if (loading) {
    return <div className="max-w-3xl mx-auto card-pad h-72 skeleton" />
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="page-title">Book a laboratory</h1>
      <p className="page-sub">
        A confirmed booking issues an access code valid only for that
        laboratory, only during your window.
      </p>

      {/* stepper */}
      <ol className="mt-6 flex items-center gap-2">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-2 flex-1 last:flex-none">
            <div className={`flex items-center gap-2 ${i > step ? 'opacity-45' : ''}`}>
              <span className={`w-6 h-6 rounded-full grid place-items-center
                text-[11px] font-semibold transition-colors ${
                i < step ? 'bg-ok/20 text-ok border border-ok/40'
                : i === step ? 'bg-accent-500/20 text-accent-300 border border-accent-500/50'
                : 'bg-ink-800 text-slate-500 border border-ink-600'}`}>
                {i < step ? <Check size={12} strokeWidth={3} /> : i + 1}
              </span>
              <span className={`hidden sm:block text-xs ${
                i === step ? 'text-slate-200 font-medium' : 'text-slate-500'}`}>
                {s}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span className={`flex-1 h-px ${i < step ? 'bg-ok/40' : 'bg-ink-600'}`} />
            )}
          </li>
        ))}
      </ol>

      <div className="card-pad mt-5 min-h-[340px]">
        {error && <div className="mb-4"><ErrorBanner message={error}
                       onDismiss={() => setError('')} /></div>}

        <AnimatePresence mode="wait">
          <motion.div key={step}
            initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }} transition={{ duration: .18 }}>

            {/* ------------------------------------------------ step 1 */}
            {step === 0 && (
              <div>
                <h2 className="text-sm font-semibold text-slate-200 mb-3">
                  Which laboratory?
                </h2>
                <div className="grid sm:grid-cols-2 gap-2.5 max-h-[380px] overflow-y-auto pr-1">
                  {labs.map(l => (
                    <button key={l.id} onClick={() => setLabId(l.id)}
                      className={`text-left p-3.5 rounded-lg border transition-all ${
                        labId === l.id
                          ? 'border-accent-500/60 bg-accent-500/10'
                          : 'border-ink-600 bg-ink-900/40 hover:border-ink-400'}`}>
                      <div className="flex items-start justify-between gap-2">
                        <span className="mono text-accent-400">{l.code}</span>
                        {l.has_controller
                          ? <Chip tone="ok">Door</Chip>
                          : <Chip tone="idle">No door HW</Chip>}
                      </div>
                      <div className="mt-1.5 text-[13px] text-slate-200 leading-snug">
                        {l.name}
                      </div>
                      <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500">
                        <MapPin size={11} />{l.location || '—'}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ------------------------------------------------ step 2 */}
            {step === 1 && (
              <div>
                <h2 className="text-sm font-semibold text-slate-200 mb-3">
                  Which day?
                </h2>
                <div className="flex gap-2 flex-wrap mb-4">
                  {nextDays(7).map(d => (
                    <button key={d.value} onClick={() => setDate(d.value)}
                      className={`px-3.5 py-2.5 rounded-lg border text-center transition-all ${
                        date === d.value
                          ? 'border-accent-500/60 bg-accent-500/10 text-accent-300'
                          : 'border-ink-600 bg-ink-900/40 text-slate-400 hover:border-ink-400'}`}>
                      <div className="text-[10px] uppercase tracking-wide opacity-70">
                        {d.weekday}
                      </div>
                      <div className="text-sm font-semibold mt-0.5">{d.day}</div>
                      <div className="text-[10px] opacity-70">{d.month}</div>
                    </button>
                  ))}
                </div>
                <label className="label block mb-1.5">Or pick a date</label>
                <input className="input max-w-xs" type="date" value={date}
                       min={todayStr()} onChange={e => setDate(e.target.value)} />
              </div>
            )}

            {/* ------------------------------------------------ step 3 */}
            {step === 2 && (
              <div>
                <h2 className="text-sm font-semibold text-slate-200">
                  Which hours?
                </h2>
                <p className="text-xs text-slate-500 mt-1 mb-4">
                  Click a start hour, then an end hour. Unavailable hours are
                  already reserved by someone else.
                </p>

                <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                  {Array.from({ length: DAY_END - DAY_START }, (_, i) => DAY_START + i)
                    .map(h => {
                      const taken = takenHours.has(h)
                      const past = pastHours.has(h)
                      const disabled = taken || past
                      const selected = inRange(h) || startHour === h
                      return (
                        <button key={h} disabled={disabled}
                          onClick={() => pickHour(h)}
                          title={taken ? 'Already reserved'
                                : past ? 'In the past' : undefined}
                          className={`py-2.5 rounded-lg text-[13px] border transition-all tnum ${
                            selected
                              ? 'border-accent-500/60 bg-accent-500/20 text-accent-200 font-medium'
                            : disabled
                              ? 'border-ink-700 bg-ink-900/60 text-slate-700 cursor-not-allowed line-through'
                              : 'border-ink-600 bg-ink-900/40 text-slate-400 hover:border-ink-400 hover:text-slate-200'}`}>
                          {pad(h)}:00
                        </button>
                      )
                    })}
                </div>

                {startHour !== null && (
                  <div className="mt-4 flex items-center gap-2 text-sm text-slate-300">
                    <Clock size={14} className="text-accent-400" />
                    {endHour === null
                      ? <>Starting {pad(startHour)}:00 — now pick an end hour</>
                      : <>{pad(startHour)}:00 – {pad(endHour)}:00
                          <span className="text-slate-500">
                            ({endHour - startHour}h)
                          </span></>}
                  </div>
                )}

                <div className="mt-5">
                  <label className="label block mb-1.5">Purpose</label>
                  <textarea className="input min-h-[80px] resize-y" value={reason}
                            placeholder="Thesis experiment — manipulator calibration"
                            onChange={e => setReason(e.target.value)} />
                </div>
              </div>
            )}

            {/* ------------------------------------------------ step 4 */}
            {step === 3 && lab && startHour !== null && endHour !== null && (
              <div>
                <h2 className="text-sm font-semibold text-slate-200 mb-4">
                  Review and confirm
                </h2>
                <div className="rounded-lg bg-ink-900/60 border border-ink-700 p-4 space-y-3">
                  <Line label="Laboratory" value={
                    <span className="flex items-center gap-2">
                      <FlaskConical size={13} className="text-accent-400" />
                      {lab.name}
                    </span>} />
                  <Line label="Code" value={<span className="mono">{lab.code}</span>} />
                  <Line label="Location" value={lab.location || '—'} />
                  <Line label="Date" value={
                    new Date(`${date}T00:00`).toLocaleDateString([], {
                      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })} />
                  <Line label="Time" value={
                    <span className="tnum">{pad(startHour)}:00 – {pad(endHour)}:00</span>} />
                  <Line label="Purpose" value={reason || '—'} />
                  <Line label="Access method" value={
                    <span className="flex items-center gap-2">
                      <QrCode size={13} className="text-accent-400" />
                      QR code, then fingerprint or face
                    </span>} />
                </div>

                {!lab.has_controller && (
                  <div className="mt-4 flex items-start gap-2.5 rounded-lg border
                                  border-warn/35 bg-warn/10 px-4 py-3 text-xs text-warn">
                    <CircuitBoard size={14} className="mt-0.5 shrink-0" />
                    <span>
                      This laboratory has no access-control hardware installed
                      yet. The booking and its credential are recorded normally,
                      but no door will respond to it.
                    </span>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* navigation */}
      <div className="mt-5 flex items-center justify-between">
        <button className="btn-quiet" disabled={step === 0}
                onClick={() => setStep(s => Math.max(0, s - 1))}>
          <ArrowLeft size={15} />Back
        </button>

        {step < STEPS.length - 1 ? (
          <button className="btn-primary" disabled={!canNext}
                  onClick={() => setStep(s => s + 1)}>
            Continue<ArrowRight size={15} />
          </button>
        ) : (
          <button className="btn-primary" disabled={busy} onClick={submit}>
            {busy ? 'Confirming…' : 'Confirm booking'}
            {!busy && <Check size={15} />}
          </button>
        )}
      </div>
    </div>
  )
}

function Line({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="label pt-0.5">{label}</span>
      <span className="text-[13px] text-slate-200 text-right">{value}</span>
    </div>
  )
}

const pad = (n: number) => String(n).padStart(2, '0')

function todayStr() { return dateStr(new Date()) }

function dateStr(d: Date) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function nextDays(n: number) {
  return Array.from({ length: n }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() + i)
    return {
      value: dateStr(d),
      weekday: d.toLocaleDateString([], { weekday: 'short' }),
      day: d.getDate(),
      month: d.toLocaleDateString([], { month: 'short' }),
    }
  })
}
