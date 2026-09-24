/**
 * The shared vocabulary of the interface.
 *
 * The rule that runs through all of it: a value that has not been reported is
 * shown as "No data", never as a zero, a dash that could be mistaken for a
 * reading, or a plausible default. A dashboard that invents numbers is worse
 * than one that admits what it doesn't know — and for a thesis this is the
 * difference between a measurement and a decoration.
 */
import { ReactNode, useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'
import { AlertTriangle, Inbox } from 'lucide-react'

export type Tone = 'ok' | 'warn' | 'bad' | 'info' | 'idle'

const TONE_CHIP: Record<Tone, string> = {
  ok:   'bg-ok/10 text-ok border border-ok/25',
  warn: 'bg-warn/10 text-warn border border-warn/25',
  bad:  'bg-bad/10 text-bad border border-bad/25',
  info: 'bg-accent-500/10 text-accent-300 border border-accent-500/25',
  idle: 'bg-ink-600/40 text-slate-400 border border-ink-500',
}

const TONE_DOT: Record<Tone, string> = {
  ok: 'bg-ok', warn: 'bg-warn', bad: 'bg-bad',
  info: 'bg-accent-400', idle: 'bg-slate-600',
}

export function Chip({ tone, kind, children, dot = false }: {
  tone?: Tone
  /** Synonym for `tone`. Both spellings exist across the pages; one
      implementation serves them. */
  kind?: Tone
  children: ReactNode
  dot?: boolean
}) {
  const t: Tone = tone ?? kind ?? 'idle'
  return (
    <span className={`chip ${TONE_CHIP[t]}`}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${TONE_DOT[t]}`} />}
      {children}
    </span>
  )
}

/** Live indicator. The pulse means "this is updating", not "look at me". */
export function LiveDot({ on, label }: { on: boolean; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-500">
      <span className={`w-1.5 h-1.5 rounded-full ${
        on ? 'bg-ok animate-pulse-dot' : 'bg-slate-600'}`} />
      {label ?? (on ? 'Live' : 'Reconnecting')}
    </span>
  )
}

/**
 * Tri-state hardware indicator: true / false / unknown.
 * Unknown is not a failure, and must not look like one.
 */
export function StateDot({ state, labels, unknown = 'No data', size = 'md' }: {
  state: boolean | null | undefined
  labels: [string, string]
  unknown?: string
  size?: 'sm' | 'md'
}) {
  const text = size === 'sm' ? 'text-xs' : 'text-sm'
  if (state === null || state === undefined) {
    return (
      <span className={`inline-flex items-center gap-2 ${text} text-slate-500`}>
        <span className="w-2 h-2 rounded-full bg-slate-600" />
        {unknown}
      </span>
    )
  }
  return (
    <span className={`inline-flex items-center gap-2 ${text}`}>
      <span className={`w-2 h-2 rounded-full ${
        state ? 'bg-ok animate-pulse-dot' : 'bg-bad'}`} />
      <span className={state ? 'text-ok' : 'text-bad'}>
        {state ? labels[0] : labels[1]}
      </span>
    </span>
  )
}

/**
 * Counts up to a real value when it scrolls into view.
 * Only ever animates toward data that exists; never invents an intermediate
 * reading that could be misread as live.
 */
export function AnimatedCounter({ value, duration = 700 }: {
  value: number; duration?: number
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  const [shown, setShown] = useState(0)

  useEffect(() => {
    if (!inView) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || value === 0) { setShown(value); return }

    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration)
      // ease-out cubic: fast start, settles gently on the true value
      setShown(Math.round(value * (1 - Math.pow(1 - p, 3))))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [inView, value, duration])

  return <span ref={ref} className="tabular-nums">{shown}</span>
}

export function MetricCard({ label, value, hint, tone = 'idle', icon, suffix,
                            animate = true, info }: {
  label: string
  value: number | string | null
  hint?: string
  tone?: Tone
  icon?: ReactNode
  suffix?: string
  /** Plain-language explanation, shown on hover and focus. A student should
      never have to know what an ESP32 is to read a dashboard. */
  info?: string
  /** false renders the value as-is. Used for ratios like "2/3", where
      counting up would be meaningless. */
  animate?: boolean
}) {
  const valueTone =
    tone === 'ok' ? 'text-ok' : tone === 'warn' ? 'text-warn'
    : tone === 'bad' ? 'text-bad' : 'text-slate-100'

  return (
    <motion.div layout className="surface-pad surface-hover relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r
                      from-transparent via-accent-500/40 to-transparent" />
      <div className="flex items-start justify-between gap-3">
        <span className="label flex items-center gap-1.5">
          {label}
          {info && (
            <span tabIndex={0} title={info} aria-label={info}
                  className="inline-grid place-items-center w-3.5 h-3.5 rounded-full
                             border border-ink-500 text-slate-500 text-[9px]
                             leading-none cursor-help hover:text-slate-300
                             hover:border-ink-400 transition-colors">
              i
            </span>
          )}
        </span>
        {icon && <span className="text-slate-600 shrink-0">{icon}</span>}
      </div>
      <div className={`mt-2.5 text-[28px] leading-none font-semibold ${valueTone}`}>
        {value === null
          ? <span className="text-base text-slate-600">No data</span>
          : typeof value === 'number' && animate
            ? <><AnimatedCounter value={value} />{suffix}</>
            : <>{value}{suffix}</>}
      </div>
      {hint && <div className="mt-2 text-xs text-slate-500">{hint}</div>}
    </motion.div>
  )
}

export function SectionTitle({ children, action, sub, icon }: {
  children: ReactNode; action?: ReactNode; sub?: string; icon?: ReactNode
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-3">
      <div>
        <h2 className="text-[13px] font-semibold text-slate-200 tracking-wide
                       flex items-center gap-2">
          {icon && <span className="text-accent-400">{icon}</span>}
          {children}
        </h2>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
      {action}
    </div>
  )
}

export function PageHeader({ eyebrow, title, sub, actions }: {
  eyebrow?: string; title: string; sub?: string; actions?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-6 flex-wrap mb-6">
      <div className="min-w-0">
        {eyebrow && (
          <div className="mono text-accent-400 mb-1.5">{eyebrow}</div>
        )}
        <h1 className="text-xl sm:text-2xl font-semibold text-slate-50 text-balance">
          {title}
        </h1>
        {sub && (
          <p className="text-sm text-slate-500 mt-1 max-w-2xl text-balance">{sub}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  )
}

export function EmptyState({ title, detail, action, icon }: {
  title: string; detail?: string; action?: ReactNode; icon?: ReactNode
}) {
  return (
    <div className="py-14 px-6 text-center">
      <div className="inline-flex items-center justify-center w-11 h-11 rounded-xl
                      bg-ink-700/60 border border-ink-600 text-slate-600 mb-3.5">
        {icon ?? <Inbox size={18} />}
      </div>
      <div className="text-sm font-medium text-slate-300">{title}</div>
      {detail && (
        <div className="mt-1.5 text-xs text-slate-500 max-w-sm mx-auto
                        leading-relaxed">{detail}</div>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/** Shimmer placeholder. Shaped like the content it replaces, so the layout
    does not jump when real data lands. */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-md bg-ink-700/60 ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-sweep
                      bg-gradient-to-r from-transparent via-white/[0.04]
                      to-transparent" />
    </div>
  )
}

export function CardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="surface-pad space-y-3">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-14" />
          <Skeleton className="h-3 w-24" />
        </div>
      ))}
    </div>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-slate-500">
      <span className="w-4 h-4 border-2 border-ink-500 border-t-accent-400
                       rounded-full animate-spin" />
      <span className="text-sm">{label ?? 'Loading'}</span>
    </div>
  )
}

export function ErrorBanner({ message, title, onDismiss }: {
  message: string; title?: string; onDismiss?: () => void
}) {
  return (
    <div className="rounded-lg border border-bad/35 bg-bad/[0.07] px-4 py-3
                    flex gap-3 items-start">
      <AlertTriangle size={16} className="text-bad shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        {title && <div className="text-sm font-medium text-bad">{title}</div>}
        <div className="text-sm text-bad/90 leading-relaxed">{message}</div>
      </div>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss"
                className="text-bad/60 hover:text-bad shrink-0 -mt-0.5 px-1">
          &times;
        </button>
      )}
    </div>
  )
}

/** Fades a page in on mount. Short enough not to sit between the person and
    their data. */
export function Reveal({ children, delay = 0 }: {
  children: ReactNode; delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  )
}

// --- semantic mappings -----------------------------------------------------
// Centralised so a denial is the same red everywhere in the product.

export function eventTone(t: string): Tone {
  if (t.includes('GRANTED') || t.endsWith('ACCEPTED') || t === 'QR_VALIDATED'
      || t === 'BOOKING_CONFIRMED' || t === 'DEVICE_ONLINE') return 'ok'
  if (t.includes('DENIED') || t.endsWith('REJECTED')
      || t === 'IDENTITY_MISMATCH' || t === 'ALARM') return 'bad'
  if (t.startsWith('DOOR') || t === 'DEVICE_OFFLINE'
      || t === 'BOOKING_CANCELLED') return 'warn'
  if (t.startsWith('BOOKING') || t.startsWith('QR')
      || t.startsWith('ASSET')) return 'info'
  return 'idle'
}

export function bookingTone(s: string): Tone {
  if (s === 'CONFIRMED') return 'ok'
  if (s === 'CANCELLED' || s === 'REJECTED') return 'bad'
  if (s === 'PENDING') return 'warn'
  return 'idle'
}

export function assetTone(s: string): Tone {
  if (s === 'AVAILABLE') return 'ok'
  if (s === 'MAINTENANCE') return 'warn'
  if (s === 'RETIRED') return 'bad'
  return 'idle'
}

/** Human wording for a machine denial code. The audit trail keeps the code;
    people get the sentence. */
export function denialText(reason?: string | null): string | null {
  if (!reason) return null
  const map: Record<string, string> = {
    TOKEN_UNKNOWN: 'The scanned code is not a credential this system issued.',
    TOKEN_REVOKED: 'This credential was replaced or revoked.',
    BOOKING_NOT_CONFIRMED: 'The booking behind this code is not confirmed.',
    BOOKING_CANCELLED: 'The booking was cancelled.',
    BOOKING_NOT_STARTED: 'The booking window has not opened yet.',
    BOOKING_EXPIRED: 'The booking window has closed.',
    WRONG_LAB: 'This credential belongs to a different laboratory.',
    USER_INACTIVE: 'The account is not active.',
    UNKNOWN_CREDENTIAL: 'The card or tag is not registered.',
    NO_ACTIVE_BOOKING: 'No active booking for this laboratory.',
    IDENTITY_MISMATCH: 'The biometric did not match the identity from step 1.',
    BIOMETRIC_TIMEOUT: 'No fingerprint or face was presented in time.',
    BIOMETRIC_FAILED: 'The biometric check failed.',
    DEVICE_UNKNOWN: 'The reader reported an unrecognised laboratory.',
    BACKEND_UNAVAILABLE: 'The portal could not be reached, so entry was refused.',
  }
  return map[reason] ?? reason.replace(/_/g, ' ').toLowerCase()
}


// ---------------------------------------------------------------------------
// Names the page components import. Kept as thin wrappers over the primitives
// above so there is still exactly ONE implementation of each behaviour.
// ---------------------------------------------------------------------------

/** Bare status dot. `live` adds the slow pulse that means "updating". */
export function Dot({ tone = 'idle', live = false, className = '' }: {
  tone?: Tone; live?: boolean; className?: string
}) {
  return (
    <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${
      TONE_DOT[tone]} ${live ? 'animate-pulse-dot' : ''} ${className}`} />
  )
}

/** Alias kept because several pages import the shorter name. */
export const Empty = EmptyState

export const SkeletonCards = CardsSkeleton

export const denialReason = denialText

/** Draws a tick once, on mount. Confirmation should feel like completion,
    which a static glyph does not. */
export function SuccessMark({ size = 56 }: { size?: number }) {
  return (
    <motion.svg
      width={size} height={size} viewBox="0 0 52 52" fill="none"
      initial="hidden" animate="visible" aria-hidden
    >
      <motion.circle
        cx="26" cy="26" r="24" stroke="currentColor" strokeWidth="2"
        className="text-ok/40"
        variants={{ hidden: { pathLength: 0, opacity: 0 },
                    visible: { pathLength: 1, opacity: 1 } }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      />
      <motion.path
        d="M15 27l8 8 15-16" stroke="currentColor" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" className="text-ok"
        variants={{ hidden: { pathLength: 0 }, visible: { pathLength: 1 } }}
        transition={{ duration: 0.38, delay: 0.32, ease: 'easeOut' }}
      />
    </motion.svg>
  )
}
