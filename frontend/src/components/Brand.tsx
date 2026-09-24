/**
 * The Smart Lab identity.
 *
 * The mark is original: a hexagonal laboratory cell containing an articulated
 * arm whose joints are network nodes - robotics and IoT in one glyph. It is
 * deliberately not styled after the university's logo.
 *
 * The official GIU logo is never redrawn here. InstitutionLogo shows the
 * real file when VITE_INSTITUTION_LOGO points at it (see
 * public/brand/README.md), and a plain text label otherwise.
 */
import { useId, useState } from 'react'

export function SmartLabMark({ size = 36, animated = false, className = '' }: {
  size?: number; animated?: boolean; className?: string
}) {
  // Unique ids per instance: a gradient defined inside a hidden copy (the
  // phone header on a desktop) cannot be painted by the visible ones.
  const uid = useId().replace(/:/g, '')
  const g = `slm-g-${uid}`, bg = `slm-bg-${uid}`
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden
         className={className}>
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#38bdf8" />
          <stop offset="1" stopColor="#2dd4bf" />
        </linearGradient>
        <radialGradient id={bg} cx="35%" cy="25%" r="80%">
          <stop offset="0" stopColor="#1c2e4a" />
          <stop offset="1" stopColor="#0b1322" />
        </radialGradient>
      </defs>
      <path d="M32 4 56.2 18v28L32 60 7.8 46V18Z" fill={`url(#${bg})`}
            stroke={`url(#${g})`} strokeWidth="3" strokeLinejoin="round" />
      {/* inner cell, a fainter echo of the outline */}
      <path d="M32 12 49.3 22v20L32 52 14.7 42V22Z" fill="none"
            stroke="#38bdf8" strokeOpacity=".18" strokeWidth="1" />
      <g fill="none" stroke="#e0f2fe" strokeWidth="3.4" strokeLinecap="round"
         strokeLinejoin="round">
        <path d="M18 47h14" />
        <path d="M25 44 29 29 43 23" />
        <path d="M43 23l4-4M43 23l5 2" />
      </g>
      <g fill="#38bdf8">
        <circle cx="25" cy="44" r="3.2" />
        <circle cx="29" cy="29" r="3.2" />
        <circle cx="43" cy="23" r="2.6" />
      </g>
      {/* the signal from the tool: the arm is connected, not just moving */}
      <g fill="none" stroke="#2dd4bf" strokeWidth="1.8" strokeLinecap="round"
         className={animated ? 'art-blink' : ''}>
        <path d="M49 14.5a7 7 0 0 1 4 4" />
        <path d="M50.5 10.5a11 11 0 0 1 6.5 6.5" strokeOpacity=".55" />
      </g>
    </svg>
  )
}

export function Wordmark({ compact = false, tight = false }: { compact?: boolean; tight?: boolean }) {
  return (
    <div className="leading-none">
      <div className="font-display font-semibold tracking-[0.18em] text-white
                      text-[15px]">
        SMART<span className="text-accent-300"> LAB</span>
      </div>
      {!compact && (
        <div className={`mt-1.5 uppercase text-slate-400 whitespace-nowrap ${tight
          ? 'text-[8.5px] tracking-[0.12em]' : 'text-[10px] tracking-[0.2em]'}`}>
          Intelligent Research Laboratory
        </div>
      )}
    </div>
  )
}

/** Set VITE_INSTITUTION_LOGO to the official file (see public/brand/README). */
const LOGO_URL = (import.meta.env.VITE_INSTITUTION_LOGO as string | undefined) || ''

/**
 * The official university logo when one has been configured, the
 * university's name as text otherwise. Never a lookalike.
 */
export function InstitutionLogo({ className = '', textClass = '' }: {
  className?: string; textClass?: string
}) {
  const [failed, setFailed] = useState(false)
  if (LOGO_URL && !failed) {
    return (
      <img src={LOGO_URL} alt="German International University"
           className={`h-8 w-auto object-contain ${className}`}
           onError={() => setFailed(true)} />
    )
  }
  return (
    <span className={`text-[11px] uppercase tracking-[0.16em] text-slate-400
                      ${textClass}`}>
      German International University
    </span>
  )
}
