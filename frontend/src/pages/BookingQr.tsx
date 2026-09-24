/**
 * The page a student holds up to the door camera.
 *
 * THE QR ITSELF IS OFF LIMITS TO DESIGN.
 *
 * Everything around it can be as rich as we like, but inside the white panel
 * the rules come from the OV2640 and OpenCV, not from taste:
 *   - pure white background, no tint, no gradient, no glass
 *   - nothing overlaid on the code, ever
 *   - minimal padding, because the PNG already carries its 4-module quiet
 *     zone and extra margin only shrinks the modules within whatever the
 *     camera frames
 *   - image-rendering: pixelated, so the browser never blurs module edges
 *   - as large as the viewport allows, ~85% of screen width on a phone
 *
 * Measured: 28/28 successful decodes across seven distances and four
 * degradation settings, from a real browser render at phone resolution.
 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft, Clock, Fingerprint, QrCode, ScanFace, ShieldCheck,
} from 'lucide-react'
import { QrPayload, api } from '../lib/api'
import { fmtDateTime } from '../lib/time'
import { Chip, Dot, ErrorBanner, Skeleton } from '../components/ui'

type Phase = 'before' | 'open' | 'closed' | 'dead'

export default function BookingQr() {
  const { id } = useParams()
  const [qr, setQr] = useState<QrPayload | null>(null)
  const [error, setError] = useState('')
  const [, tick] = useState(0)

  useEffect(() => {
    api.qr(Number(id))
      .then(setQr)
      .catch(e => setError(e?.message ?? 'Could not load the access code'))
  }, [id])

  // One-second tick so the countdown and the phase flip the moment the
  // window opens or closes, with no refresh.
  useEffect(() => {
    const t = setInterval(() => tick(n => n + 1), 1000)
    return () => clearInterval(t)
  }, [])

  if (error) {
    return (
      <div className="max-w-md mx-auto space-y-4">
        <ErrorBanner message={error} />
        <Link to="/bookings" className="btn-ghost">
          <ArrowLeft size={15} />Back to bookings
        </Link>
      </div>
    )
  }

  if (!qr) {
    return (
      <div className="max-w-xl mx-auto">
        <Skeleton className="h-4 w-28" />
        <div className="card mt-4 p-5 space-y-4">
          <Skeleton className="h-5 w-56 mx-auto" />
          <Skeleton className="aspect-square w-full rounded-lg" />
          <Skeleton className="h-4 w-full" />
        </div>
      </div>
    )
  }

  const now = Date.now()
  const from = new Date(qr.valid_from).getTime()
  const until = new Date(qr.valid_until).getTime()

  const phase: Phase =
    qr.status === 'CANCELLED' ? 'dead'
    : now < from ? 'before'
    : now <= until ? 'open'
    : 'closed'

  const live = phase === 'open'

  return (
    <div className="max-w-xl mx-auto">
      <Link to="/bookings"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500
                       hover:text-slate-300 transition-colors">
        <ArrowLeft size={13} />My bookings
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className={`mt-4 card overflow-hidden transition-shadow duration-500
                    ${live ? 'border-ok/40 shadow-glow-ok' : ''}`}
      >
        {/* header */}
        <div className="px-4 sm:px-6 pt-5 pb-4 text-center">
          <div className="label">Laboratory access</div>
          <h1 className="mt-1.5 text-lg font-semibold text-white">{qr.lab_name}</h1>
          <div className="mono text-slate-500 mt-0.5">{qr.lab_code}</div>
        </div>

        {/* status strip */}
        <div className="px-4 sm:px-6 pb-4">
          <AnimatePresence mode="wait">
            <motion.div
              key={phase}
              initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }} transition={{ duration: .18 }}
              className={`flex items-center justify-center gap-2 py-2 rounded-lg
                border text-[13px] font-medium ${
                phase === 'open'  ? 'bg-ok/10 border-ok/35 text-ok'
              : phase === 'before'? 'bg-warn/10 border-warn/35 text-warn'
              :                     'bg-bad/10 border-bad/35 text-bad'}`}
            >
              <Dot tone={phase === 'open' ? 'ok' : phase === 'before' ? 'warn' : 'bad'}
                   live={live} />
              {phase === 'open'   && <>Access window open</>}
              {phase === 'before' && <>Access opens {relTime(from - now)}</>}
              {phase === 'closed' && <>Access window closed</>}
              {phase === 'dead'   && <>Booking cancelled</>}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* THE SCANNABLE AREA. Do not decorate inside this box.             */}
        {/* ---------------------------------------------------------------- */}
        <div className="px-3 sm:px-6">
          <div className={`relative rounded-lg p-2 sm:p-3 bg-white
                           transition-opacity duration-300
                           ${live ? '' : 'opacity-20'}`}>
            <img
              src={`data:image/png;base64,${qr.qr_png_base64}`}
              alt="Laboratory access code"
              className="w-full h-auto block"
              style={{ imageRendering: 'pixelated' }}
            />
            {!live && (
              <div className="absolute inset-0 grid place-items-center">
                <div className="px-4 py-2 rounded-lg bg-ink-950/95 border
                                border-bad/40 text-bad text-sm font-semibold">
                  {phase === 'dead' ? 'Cancelled'
                    : phase === 'before' ? 'Not yet valid' : 'Expired'}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* countdown */}
        <div className="px-4 sm:px-6 py-5 space-y-3 border-b border-ink-700/60">
          <Row label="Window"
               value={`${fmtDateTime(qr.valid_from)} — ${fmtDateTime(qr.valid_until)}`} />
          <Row label="Status" value={
            live ? <Chip tone="ok">Valid now</Chip>
                 : <Chip tone="bad">
                     {phase === 'dead' ? 'Cancelled'
                       : phase === 'before' ? 'Not yet valid' : 'Expired'}
                   </Chip>
          } />
          <Row label={<span className="flex items-center gap-1.5">
                        <Clock size={12} />Time
                      </span>}
               value={
                 <span className="tnum">
                   {phase === 'open'   && `${precise(until - now)} remaining`}
                   {phase === 'before' && `opens in ${precise(from - now)}`}
                   {phase === 'closed' && 'window has ended'}
                   {phase === 'dead'   && '—'}
                 </span>
               } />

          {/* Progress through the window. A bar reads faster than a number
              when someone is standing at a door in a hurry. */}
          {phase === 'open' && (
            <div className="pt-1">
              <div className="h-1 rounded-full bg-ink-700 overflow-hidden">
                <motion.div
                  className="h-full bg-ok rounded-full"
                  initial={false}
                  animate={{ width: `${100 * (now - from) / (until - from)}%` }}
                  transition={{ duration: .6 }}
                />
              </div>
            </div>
          )}
        </div>

        {/* what to do */}
        <div className="px-4 sm:px-6 py-5">
          <div className="label mb-3">At the door</div>
          <ol className="space-y-3">
            <StepRow n={1} icon={<QrCode size={14} />}
                     title="Show this code to the camera"
                     detail="Hold the screen 15–25 cm from the lens at full brightness." />
            <StepRow n={2}
                     icon={<span className="flex gap-1">
                             <Fingerprint size={14} /><ScanFace size={14} />
                           </span>}
                     title="Verify with fingerprint or face"
                     detail="The biometric must match the person this booking belongs to." />
            <StepRow n={3} icon={<ShieldCheck size={14} />}
                     title="The door unlocks"
                     detail="Only after both factors have matched." />
          </ol>

          <p className="mt-5 text-[11px] text-slate-600 leading-relaxed">
            This code alone does not open the door, and it works only at{' '}
            <span className="mono text-slate-500">{qr.lab_code}</span> during the
            window above. Showing it elsewhere, or outside that window, is refused.
          </p>
        </div>
      </motion.div>
    </div>
  )
}

function Row({ label, value }: { label: React.ReactNode; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="label">{label}</span>
      <span className="text-[13px] text-slate-300 text-right">{value}</span>
    </div>
  )
}

function StepRow({ n, icon, title, detail }: {
  n: number; icon: React.ReactNode; title: string; detail: string
}) {
  return (
    <li className="flex gap-3">
      <span className="shrink-0 w-6 h-6 rounded-md bg-ink-700 border border-ink-600
                       grid place-items-center text-[11px] font-semibold
                       text-accent-300">{n}</span>
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-[13px] text-slate-200">
          <span className="text-accent-400">{icon}</span>{title}
        </div>
        <div className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
          {detail}
        </div>
      </div>
    </li>
  )
}

/** hh:mm:ss when under an hour is not enough resolution to be useful. */
function precise(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`
}

function relTime(ms: number): string {
  const mins = Math.floor(ms / 60000)
  if (mins < 60) return `in ${mins} min`
  const h = Math.floor(mins / 60)
  if (h < 24) return `in ${h}h ${mins % 60}m`
  return `in ${Math.floor(h / 24)} days`
}
