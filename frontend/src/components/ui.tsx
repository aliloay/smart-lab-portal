/**
 * The shared vocabulary of the interface.
 *
 * The rule that runs through all of it: a value that has not been reported is
 * shown as "No data", never as a zero, a dash that could be mistaken for a
 * reading, or a plausible default. A dashboard that invents numbers is worse
 * than one that admits what it does not know.
 */
import { ReactNode, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion, useInView } from 'framer-motion'
import { AlertTriangle, Inbox, Info, X } from 'lucide-react'
import {
  STATUS_LABEL, Tone, bookingTone, issueStatusTone, severityTone,
} from '../lib/labels'
import type { IssueSeverity, IssueStatus } from '../lib/api'

export type { Tone }

const TONE_CHIP: Record<Tone, string> = {
  ok:     'bg-ok/10 text-ok-soft border border-ok/30',
  warn:   'bg-warn/10 text-warn-soft border border-warn/30',
  bad:    'bg-bad/10 text-bad-soft border border-bad/35',
  info:   'bg-accent-500/10 text-accent-300 border border-accent-500/30',
  violet: 'bg-violet-500/10 text-violet-300 border border-violet-500/30',
  idle:   'bg-ink-600/45 text-slate-300 border border-ink-500',
}

export const TONE_DOT: Record<Tone, string> = {
  ok: 'bg-ok', warn: 'bg-warn', bad: 'bg-bad', info: 'bg-accent-400',
  violet: 'bg-violet-400', idle: 'bg-slate-500',
}

export const TONE_TEXT: Record<Tone, string> = {
  ok: 'text-ok-soft', warn: 'text-warn-soft', bad: 'text-bad-soft',
  info: 'text-accent-300', violet: 'text-violet-300', idle: 'text-slate-300',
}

export function Chip({ tone = 'idle', kind, children, dot = false, className = '' }: {
  tone?: Tone; kind?: Tone; children: ReactNode; dot?: boolean; className?: string
}) {
  const t = kind ?? tone
  return (
    <span className={`chip ${TONE_CHIP[t]} ${className}`}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${TONE_DOT[t]}`} />}
      {children}
    </span>
  )
}

/** Status dot. `live` adds a slow pulse and a ring that means "updating". */
export function Dot({ tone = 'idle', live = false, className = '' }: {
  tone?: Tone; live?: boolean; className?: string
}) {
  return (
    <span className={`relative inline-flex w-2 h-2 shrink-0 ${className}`}>
      {live && (
        <span className={`absolute inset-0 rounded-full ${TONE_DOT[tone]}
                          animate-ping-slow`} />
      )}
      <span className={`relative inline-block w-2 h-2 rounded-full ${TONE_DOT[tone]}`} />
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
      <span className={`inline-flex items-center gap-2 ${text} text-slate-400`}>
        <Dot tone="idle" />{unknown}
      </span>
    )
  }
  return (
    <span className={`inline-flex items-center gap-2 ${text}`}>
      <Dot tone={state ? 'ok' : 'bad'} live={state} />
      <span className={state ? 'text-ok-soft' : 'text-bad-soft'}>
        {state ? labels[0] : labels[1]}
      </span>
    </span>
  )
}

/** Counts up to a real value once it scrolls into view. */
export function AnimatedCounter({ value, duration = 700 }: {
  value: number; duration?: number
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '-20px' })
  const [shown, setShown] = useState(value)
  const first = useRef(true)

  useEffect(() => {
    if (!inView) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || value === 0 || !first.current) { setShown(value); return }
    first.current = false
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration)
      setShown(Math.round(value * (1 - Math.pow(1 - p, 3))))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    setShown(0)
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [inView, value, duration])

  return <span ref={ref} className="tnum">{shown}</span>
}

export function InfoTip({ text }: { text: string }) {
  return (
    <span tabIndex={0} title={text} aria-label={text}
          className="inline-grid place-items-center w-4 h-4 rounded-full
                     text-slate-400 hover:text-slate-200 cursor-help">
      <Info size={12} />
    </span>
  )
}

export function MetricCard({ label, value, hint, tone = 'idle', icon, suffix,
                            animate = true, info, to, emphasis = false }: {
  label: string
  value: number | string | null
  hint?: ReactNode
  tone?: Tone
  icon?: ReactNode
  suffix?: string
  animate?: boolean
  /** Plain-language explanation, shown on hover and focus. */
  info?: string
  to?: string
  emphasis?: boolean
}) {
  const valueTone = tone === 'idle' ? 'text-white' : TONE_TEXT[tone]
  const body = (
    <>
      <div className="absolute inset-x-5 top-0 h-px bg-gradient-to-r
                      from-transparent via-accent-400/45 to-transparent" />
      <div className="flex items-start justify-between gap-3">
        <span className="label flex items-center gap-1">
          {label}{info && <InfoTip text={info} />}
        </span>
        {icon && (
          <span className={`grid place-items-center w-8 h-8 rounded-lg border
                            ${tone === 'idle'
                              ? 'border-ink-500/70 bg-ink-700/50 text-slate-300'
                              : `${TONE_CHIP[tone]}`}`}>
            {icon}
          </span>
        )}
      </div>
      <div className={`mt-2 font-display text-[30px] leading-none font-semibold
                       ${valueTone}`}>
        {value === null
          ? <span className="text-base font-sans font-normal text-slate-400">No data</span>
          : typeof value === 'number' && animate
            ? <><AnimatedCounter value={value} />{suffix}</>
            : <>{value}{suffix}</>}
      </div>
      {hint && <div className="mt-2 text-[12.5px] text-slate-400">{hint}</div>}
    </>
  )
  const cls = `card p-5 overflow-hidden block ${emphasis ? 'ring-1 ring-accent-500/25' : ''}`
  return to
    ? <Link to={to} className={`${cls} card-hover`}>{body}</Link>
    : <div className={cls}>{body}</div>
}

export function SectionTitle({ children, action, sub, icon }: {
  children: ReactNode; action?: ReactNode; sub?: ReactNode; icon?: ReactNode
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-3">
      <div className="min-w-0">
        <h2 className="text-[14px] font-semibold text-slate-100 tracking-wide
                       flex items-center gap-2">
          {icon && <span className="text-accent-300">{icon}</span>}
          {children}
        </h2>
        {sub && <p className="text-[12.5px] text-slate-400 mt-0.5">{sub}</p>}
      </div>
      {action}
    </div>
  )
}

export function PageHeader({ eyebrow, title, sub, actions, children }: {
  eyebrow?: ReactNode; title: ReactNode; sub?: ReactNode; actions?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-6 flex-wrap mb-6">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1 className="page-title text-balance">{title}</h1>
        {sub && <p className="page-sub text-balance">{sub}</p>}
        {children}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
    </div>
  )
}

export function EmptyState({ title, detail, action, icon, compact = false }: {
  title: string; detail?: ReactNode; action?: ReactNode; icon?: ReactNode
  compact?: boolean
}) {
  return (
    <div className={`${compact ? 'py-8' : 'py-14'} px-6 text-center`}>
      <div className="inline-flex items-center justify-center w-11 h-11 rounded-xl
                      bg-ink-700/60 border border-ink-500/70 text-slate-400 mb-3.5">
        {icon ?? <Inbox size={18} />}
      </div>
      <div className="text-sm font-medium text-slate-200">{title}</div>
      {detail && (
        <div className="mt-1.5 text-[13px] text-slate-400 max-w-sm mx-auto
                        leading-relaxed">{detail}</div>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/** Shimmer placeholder, shaped like the content it replaces. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} />
}

export function CardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card p-5 space-y-3">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-14" />
          <Skeleton className="h-3 w-24" />
        </div>
      ))}
    </div>
  )
}

export function Spinner({ label, inline = false }: { label?: string; inline?: boolean }) {
  return (
    <div className={`flex items-center justify-center gap-3 text-slate-400
                     ${inline ? '' : 'py-16'}`}>
      <span className="w-4 h-4 border-2 border-ink-500 border-t-accent-400
                       rounded-full animate-spin" />
      {label !== '' && <span className="text-sm">{label ?? 'Loading'}</span>}
    </div>
  )
}

export function ErrorBanner({ message, title, onDismiss, action }: {
  message: string; title?: string; onDismiss?: () => void; action?: ReactNode
}) {
  return (
    <div role="alert"
         className="rounded-xl border border-bad/40 bg-bad/[0.08] px-4 py-3
                    flex gap-3 items-start">
      <AlertTriangle size={16} className="text-bad-soft shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        {title && <div className="text-sm font-medium text-bad-soft">{title}</div>}
        <div className="text-sm text-red-200/90 leading-relaxed">{message}</div>
        {action && <div className="mt-2">{action}</div>}
      </div>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss"
                className="text-bad-soft/70 hover:text-bad-soft shrink-0 -mt-0.5 px-1">
          <X size={15} />
        </button>
      )}
    </div>
  )
}

export function Notice({ tone = 'info', icon, children }: {
  tone?: 'info' | 'warn' | 'ok'; icon?: ReactNode; children: ReactNode
}) {
  const cls = tone === 'warn' ? 'border-warn/35 bg-warn/[0.07] text-amber-100/90'
    : tone === 'ok' ? 'border-ok/35 bg-ok/[0.07] text-emerald-100/90'
    : 'border-accent-500/30 bg-accent-500/[0.06] text-sky-100/90'
  const ic = tone === 'warn' ? 'text-warn-soft' : tone === 'ok' ? 'text-ok-soft'
    : 'text-accent-300'
  return (
    <div className={`rounded-xl border px-4 py-3 flex gap-3 items-start text-[13px]
                     leading-relaxed ${cls}`}>
      <span className={`shrink-0 mt-0.5 ${ic}`}>{icon ?? <Info size={15} />}</span>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

// --- tabs --------------------------------------------------------------------
export function Tabs<T extends string>({ tabs, value, onChange, id }: {
  tabs: { key: T; label: string; count?: number; icon?: ReactNode }[]
  value: T
  onChange: (k: T) => void
  id: string
}) {
  return (
    <div role="tablist"
         className="flex gap-1 border-b border-ink-600 overflow-x-auto no-scrollbar">
      {tabs.map(t => (
        <button key={t.key} role="tab" aria-selected={value === t.key}
          onClick={() => onChange(t.key)}
          className={`relative flex items-center gap-2 px-4 py-2.5 text-sm
                      whitespace-nowrap transition-colors ${value === t.key
                        ? 'text-white' : 'text-slate-400 hover:text-slate-200'}`}>
          {t.icon}
          {t.label}
          {t.count !== undefined && (
            <span className={`text-[11px] px-1.5 rounded-md tnum ${value === t.key
              ? 'bg-accent-500/20 text-accent-200' : 'bg-ink-700 text-slate-400'}`}>
              {t.count}
            </span>
          )}
          {value === t.key && (
            <motion.span layoutId={`tab-${id}`}
              className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent-400" />
          )}
        </button>
      ))}
    </div>
  )
}

// --- overlays ----------------------------------------------------------------
export function Drawer({ open, onClose, title, subtitle, children, width = 'sm:w-[460px]' }: {
  open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode
  children: ReactNode; width?: string
}) {
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            exit={{ opacity: 0 }} onClick={onClose}
            className="fixed inset-0 z-50 bg-ink-950/70 backdrop-blur-sm" />
          <motion.aside role="dialog" aria-modal="true"
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 340, damping: 36 }}
            className={`fixed right-0 inset-y-0 z-50 w-full ${width} bg-ink-850
                        border-l border-ink-600 overflow-y-auto shadow-lift`}>
            <div className="sticky top-0 z-10 bg-ink-850/95 backdrop-blur px-5 py-4
                            border-b border-ink-600 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="text-[15px] font-semibold text-white">{title}</div>
                {subtitle && <div className="text-xs text-slate-400 mt-0.5">{subtitle}</div>}
              </div>
              <button onClick={onClose} aria-label="Close" className="btn-quiet !p-2">
                <X size={16} />
              </button>
            </div>
            <div className="p-5">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

export function Modal({ open, onClose, title, children, footer }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode
  footer?: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            exit={{ opacity: 0 }} onClick={onClose}
            className="absolute inset-0 bg-ink-950/75 backdrop-blur-sm" />
          <motion.div role="dialog" aria-modal="true"
            initial={{ opacity: 0, y: 12, scale: .98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8 }} transition={{ duration: .18 }}
            className="relative w-full max-w-lg card p-0 overflow-hidden">
            <div className="px-5 py-4 border-b border-ink-600 flex items-center
                            justify-between">
              <div className="text-[15px] font-semibold text-white">{title}</div>
              <button onClick={onClose} aria-label="Close" className="btn-quiet !p-2">
                <X size={16} />
              </button>
            </div>
            <div className="p-5">{children}</div>
            {footer && (
              <div className="px-5 py-4 border-t border-ink-600 flex justify-end gap-2
                              bg-ink-900/40">{footer}</div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

// --- forms -------------------------------------------------------------------
export function Field({ label, hint, error, children, htmlFor }: {
  label: ReactNode; hint?: ReactNode; error?: string | null; children: ReactNode
  htmlFor?: string
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="label block mb-1.5">{label}</label>
      {children}
      {error ? <p className="mt-1.5 text-xs text-bad-soft">{error}</p>
        : hint ? <p className="mt-1.5 text-xs text-slate-400">{hint}</p> : null}
    </div>
  )
}

export function Select({ label, value, onChange, options, className = '' }: {
  label?: string; value: string; onChange: (v: string) => void
  options: [string, string][]; className?: string
}) {
  const sel = (
    <select className={`input ${className}`} value={value} aria-label={label}
            onChange={e => onChange(e.target.value)}>
      {options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
    </select>
  )
  return label ? <div><label className="label block mb-1.5">{label}</label>{sel}</div> : sel
}

// --- data display ------------------------------------------------------------
export function KV({ label, children, mono = false }: {
  label: ReactNode; children: ReactNode; mono?: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b
                    border-ink-700/60 last:border-0">
      <dt className="label pt-0.5 shrink-0">{label}</dt>
      <dd className={`text-[13.5px] text-slate-200 text-right min-w-0 ${mono ? 'mono' : ''}`}>
        {children}
      </dd>
    </div>
  )
}

export interface TimelineItem {
  key: string | number
  time: ReactNode
  title: ReactNode
  detail?: ReactNode
  tone?: Tone
  icon?: ReactNode
  meta?: ReactNode
}

/** Vertical timeline: the shape of a sequence that actually happened. */
export function Timeline({ items, dense = false }: { items: TimelineItem[]; dense?: boolean }) {
  return (
    <ol className="relative">
      {items.map((it, i) => (
        <li key={it.key} className={`relative flex gap-4 ${dense ? 'pb-4' : 'pb-6'}
                                     last:pb-0`}>
          {i < items.length - 1 && (
            <span className="absolute left-[15px] top-8 bottom-0 w-px
                             bg-gradient-to-b from-ink-500 to-ink-600/30" />
          )}
          <span className={`relative z-[1] grid place-items-center w-8 h-8 rounded-lg
                            border shrink-0 ${TONE_CHIP[it.tone ?? 'idle']}`}>
            {it.icon ?? <span className={`w-1.5 h-1.5 rounded-full
                                          ${TONE_DOT[it.tone ?? 'idle']}`} />}
          </span>
          <div className="min-w-0 flex-1 pt-1">
            <div className="flex items-baseline justify-between gap-3 flex-wrap">
              <div className={`text-[13.5px] font-medium ${
                it.tone && it.tone !== 'idle' ? TONE_TEXT[it.tone] : 'text-slate-100'}`}>
                {it.title}
              </div>
              <div className="mono text-slate-400 tnum">{it.time}</div>
            </div>
            {it.detail && (
              <div className="mt-0.5 text-[12.5px] text-slate-400 leading-relaxed">
                {it.detail}
              </div>
            )}
            {it.meta && <div className="mt-1.5">{it.meta}</div>}
          </div>
        </li>
      ))}
    </ol>
  )
}

export function ProgressBar({ value, tone = 'info' }: { value: number; tone?: Tone }) {
  return (
    <div className="h-1.5 rounded-full bg-ink-700 overflow-hidden">
      <div className={`h-full rounded-full transition-[width] duration-500 ${TONE_DOT[tone]}`}
           style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} />
    </div>
  )
}

export function Avatar({ name, size = 32 }: { name?: string | null; size?: number }) {
  const initials = (name ?? '?').split(/\s+/).filter(Boolean).slice(0, 2)
    .map(w => w[0]?.toUpperCase()).join('')
  return (
    <span style={{ width: size, height: size, fontSize: size * 0.36 }}
          className="inline-grid place-items-center rounded-full shrink-0 font-semibold
                     text-accent-100 bg-gradient-to-br from-accent-600/70 to-teal-500/50
                     border border-accent-400/30">
      {initials || '?'}
    </span>
  )
}

// --- domain badges -----------------------------------------------------------
export function SeverityBadge({ severity }: { severity: IssueSeverity | string }) {
  const bars = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 }[severity] ?? 1
  const tone = severityTone(severity)
  return (
    <span className={`chip ${TONE_CHIP[tone]}`}>
      <span className="flex items-end gap-[2px] h-2.5" aria-hidden>
        {[1, 2, 3, 4].map(b => (
          <span key={b} style={{ height: `${25 + b * 18}%` }}
                className={`w-[3px] rounded-sm ${b <= bars ? TONE_DOT[tone] : 'bg-ink-500'}`} />
        ))}
      </span>
      {severity.toLowerCase()}
    </span>
  )
}

export function IssueStatusChip({ status }: { status: IssueStatus }) {
  return <Chip tone={issueStatusTone(status)} dot>{STATUS_LABEL[status] ?? status}</Chip>
}

export function BookingStatusChip({ status }: { status: string }) {
  return <Chip tone={bookingTone(status)}>{status.toLowerCase()}</Chip>
}

/** Draws a tick once, on mount. Confirmation should feel like completion. */
export function SuccessMark({ size = 56 }: { size?: number }) {
  return (
    <motion.svg width={size} height={size} viewBox="0 0 52 52" fill="none"
      initial="hidden" animate="visible" aria-hidden>
      <motion.circle cx="26" cy="26" r="24" stroke="currentColor" strokeWidth="2"
        className="text-ok/40"
        variants={{ hidden: { pathLength: 0, opacity: 0 },
                    visible: { pathLength: 1, opacity: 1 } }}
        transition={{ duration: 0.5, ease: 'easeOut' }} />
      <motion.path d="M15 27l8 8 15-16" stroke="currentColor" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" className="text-ok"
        variants={{ hidden: { pathLength: 0 }, visible: { pathLength: 1 } }}
        transition={{ duration: 0.38, delay: 0.32, ease: 'easeOut' }} />
    </motion.svg>
  )
}

// Aliases kept for older call sites.
export const Empty = EmptyState
export const SkeletonCards = CardsSkeleton
