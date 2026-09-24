/**
 * The page a student holds up to the door camera.
 *
 * THE QR ITSELF IS OFF LIMITS TO DESIGN.
 *
 * Everything around it can be as rich as we like, but inside the white panel
 * the rules come from the OV2640 and OpenCV, not from taste:
 *   - pure white background, no tint, no gradient, no glass
 *   - nothing overlaid on the code and nothing animated over it, ever
 *   - minimal padding: the PNG already carries its 4-module quiet zone
 *   - image-rendering: pixelated, so module edges are never blurred
 *   - as large as the viewport allows
 *
 * Outside its window the code is dimmed and the reason is shown ABOVE it,
 * never on top of it.
 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, Clock, Fingerprint, MonitorSmartphone, QrCode, ScanFace, ShieldCheck, Sun,
} from 'lucide-react'
import { QrPayload, api } from '../lib/api'
import { fmtDateLong, fmtTime } from '../lib/time'
import { Dot, ErrorBanner, Skeleton } from '../components/ui'
import { AccessFlow } from '../components/visual'

type Phase = 'before' | 'open' | 'closed' | 'dead'

export default function BookingQr() {
  const { id } = useParams()
  const [qr, setQr] = useState<QrPayload | null>(null)
  const [error, setError] = useState('')
  const [, tick] = useState(0)

  useEffect(() => {
    api.qr(Number(id)).then(setQr)
      .catch(e => setError(e?.message ?? 'Could not load the access code'))
  }, [id])

  // One-second tick: the countdown and the phase flip the moment the window
  // opens or closes, with no refresh.
  useEffect(() => {
    const t = window.setInterval(() => tick(n => n + 1), 1000)
    return () => window.clearInterval(t)
  }, [])

  const now = Date.now()
  const from = qr ? new Date(qr.valid_from).getTime() : 0
  const until = qr ? new Date(qr.valid_until).getTime() : 0
  const phase: Phase = !qr ? 'before'
    : qr.status === 'CANCELLED' || qr.status === 'REJECTED' ? 'dead'
    : now < from ? 'before' : now <= until ? 'open' : 'closed'
  const live = phase === 'open'

  // Keep the phone screen awake while the code is usable at the door.
  useEffect(() => {
    if (!live) return
    let lock: { release: () => Promise<void> } | null = null
    const nav = navigator as Navigator & { wakeLock?: { request: (t: 'screen') => Promise<{ release: () => Promise<void> }> } }
    nav.wakeLock?.request('screen').then(l => { lock = l }).catch(() => {})
    return () => { lock?.release().catch(() => {}) }
  }, [live])

  if (error) return (
    <div className="max-w-md mx-auto space-y-4">
      <ErrorBanner message={error} />
      <Link to="/bookings" className="btn-ghost"><ArrowLeft size={15} />Back to bookings</Link>
    </div>
  )
  if (!qr) return (
    <div className="max-w-4xl mx-auto grid md:grid-cols-[1fr_320px] gap-5">
      <Skeleton className="aspect-square" /><Skeleton className="h-80" />
    </div>
  )

  const banner = {
    open: { cls: 'bg-ok/10 border-ok/40 text-ok-soft', text: 'Access window open' },
    before: { cls: 'bg-warn/10 border-warn/35 text-warn-soft', text: `Opens in ${precise(from - now)}` },
    closed: { cls: 'bg-bad/10 border-bad/35 text-bad-soft', text: 'Access window closed' },
    dead: { cls: 'bg-bad/10 border-bad/35 text-bad-soft', text: 'Booking cancelled · code revoked' },
  }[phase]

  return (
    <div className="max-w-4xl mx-auto">
      <Link to={`/bookings/${qr.booking_id}`}
            className="inline-flex items-center gap-1.5 text-[13px] text-slate-400 hover:text-white">
        <ArrowLeft size={14} />Booking details</Link>

      <div className="mt-4 text-center md:text-left">
        <div className="eyebrow">Access credential</div>
        <h1 className="mt-1.5 font-display text-2xl sm:text-[28px] font-semibold text-white">{qr.lab_name}</h1>
        <div className="mt-1 text-[13.5px] text-slate-300">
          <span className="mono text-accent-200">{qr.lab_code}</span> · {fmtDateLong(qr.valid_from)}
          {' · '}<span className="tnum">{fmtTime(qr.valid_from)} → {fmtTime(qr.valid_until)}</span>
        </div>
      </div>

      <div className="mt-5 grid md:grid-cols-[minmax(0,1fr)_320px] gap-5 items-start">
        {/* ------------------------------------------------------ the code */}
        <section className={`card p-3 sm:p-4 ${live ? 'border-ok/45 shadow-glow-ok' : ''}`}>
          <div className={`flex items-center justify-center gap-2 py-2.5 rounded-xl border text-[14px]
                           font-semibold mb-3 ${banner.cls}`} role="status" aria-live="polite">
            <Dot tone={phase === 'open' ? 'ok' : phase === 'before' ? 'warn' : 'bad'} live={live} />
            <span className="tnum">{banner.text}</span>
          </div>
          {/* THE SCANNABLE AREA. White, square, nothing on top of it. */}
          <div className={`rounded-lg bg-white p-1.5 sm:p-2 transition-opacity duration-300
                           ${live ? '' : 'opacity-25'}`}>
            <img src={`data:image/png;base64,${qr.qr_png_base64}`}
                 alt={`Access code for ${qr.lab_code}`} className="w-full h-auto block"
                 style={{ imageRendering: 'pixelated' }} />
          </div>
          <p className="mt-3 text-center text-[12.5px] text-slate-400">
            {live ? 'Hold the screen 15–25 cm from the camera at full brightness.'
              : phase === 'before' ? 'The door will refuse this code until the window opens.'
              : 'This code no longer opens the door.'}
          </p>
        </section>

        {/* ----------------------------------------------------- the window */}
        <aside className="space-y-4">
          <div className="card p-5">
            <div className="label flex items-center gap-1.5"><Clock size={12} />
              {phase === 'open' ? 'Time remaining' : phase === 'before' ? 'Opens in' : 'Window'}</div>
            <div className={`mt-2 font-display text-[40px] leading-none tnum ${live ? 'text-ok-soft'
              : phase === 'before' ? 'text-white' : 'text-slate-400'}`}>
              {phase === 'open' ? precise(until - now) : phase === 'before' ? precise(from - now)
                : phase === 'dead' ? 'Revoked' : 'Closed'}
            </div>
            {phase === 'open' && (
              <div className="mt-4 h-1.5 rounded-full bg-ink-700 overflow-hidden">
                <div className="h-full bg-ok rounded-full transition-[width] duration-700"
                     style={{ width: `${(100 * (now - from)) / (until - from)}%` }} />
              </div>
            )}
            <div className="mt-4 text-[12.5px] text-slate-300 tnum">
              {fmtTime(qr.valid_from)} → {fmtTime(qr.valid_until)}
            </div>
          </div>

          <div className="card p-5">
            <div className="label mb-4">At the door</div>
            <AccessFlow steps={[
              { icon: <QrCode size={17} />, title: 'Scan this QR', detail: 'The camera reads it; the portal checks your booking.' },
              { icon: <span className="flex -space-x-1"><Fingerprint size={15} /><ScanFace size={15} /></span>,
                title: 'Fingerprint or face', detail: 'Must match the person this booking belongs to.' },
              { icon: <ShieldCheck size={17} />, title: 'Door unlocks', detail: 'Only after both factors have matched.' },
            ]} />
          </div>

          <div className="card p-4 text-[12px] text-slate-400 space-y-2">
            <div className="flex gap-2"><Sun size={14} className="text-accent-300 shrink-0 mt-0.5" />
              <span>Turn screen brightness up; glare is the most common reason a scan fails.</span></div>
            <div className="flex gap-2"><MonitorSmartphone size={14} className="text-accent-300 shrink-0 mt-0.5" />
              <span>Valid only at <span className="mono text-slate-300">{qr.lab_code}</span> during this
              window. Anywhere else, or at another time, it is refused.</span></div>
          </div>
        </aside>
      </div>
    </div>
  )
}

function precise(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const p = (n: number) => String(n).padStart(2, '0')
  if (d > 0) return `${d}d ${h}h ${p(m)}m`
  return h > 0 ? `${h}:${p(m)}:${p(sec)}` : `${m}:${p(sec)}`
}
