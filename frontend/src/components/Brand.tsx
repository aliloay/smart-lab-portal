/**
 * The Smart Lab identity.
 *
 * The mark: a camera aperture around an articulated robot arm (vision + robotics),
 * redrawn as SVG from the owner's logo. Deliberately not styled after the
 * university's logo.
 *
 * The official GIU logo is used as supplied, never redrawn: InstitutionLogo
 * shows public/brand/giu-logo.png: the university's logo with the white
 * background removed and only the lettering set white for dark surfaces.
 * The black G, the black flag stripe, the red and the gold are unchanged.
 * If the file cannot be loaded it falls back to the university's name.
 */
import { useId, useState } from 'react'

export function SmartLabMark({ size = 36, animated = false, className = '' }: {
  size?: number; animated?: boolean; className?: string
}) {
  // The Smart Lab symbol (owner's logo, 2026-10-15; reference: docs/brand/smartlab-logo-reference.png):
  // a cyan camera aperture - vision - around a robot arm with an amber joint, plus an amber light
  // wedge. Redrawn as SVG so it stays sharp and tiny; below 24 px the blade seams are left out.
  // Unique ids per instance: a gradient defined inside a hidden copy cannot paint the visible ones.
  const uid = useId().replace(/:/g, '')
  const g = `slm-g-${uid}`, am = `slm-a-${uid}`
  const detailed = size >= 24
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Smart Lab"
         className={className}>
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#67e8f9" /><stop offset="1" stopColor="#2563eb" />
        </linearGradient>
        <linearGradient id={am} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fbbf24" /><stop offset="1" stopColor="#f59e0b" stopOpacity="0" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="30" fill={`url(#${g})`} />
      {detailed && <path d="M43.3 27.9Q58.0 31.1 53.9 51.7 M41.2 39.7Q45.8 54.0 25.9 60.9 M29.9 43.8Q19.8 55.0 3.9 41.1 M20.7 36.1Q6.0 32.9 10.1 12.3 M22.8 24.3Q18.2 10.0 38.1 3.1 M34.1 20.2Q44.2 9.0 60.1 22.9" fill="none" stroke="#0b1528" strokeWidth="1.6" strokeLinecap="round" strokeOpacity=".75" />}
      <path d="M50 22A21 21 0 0 1 49 46L44 41A14 14 0 0 0 45 25Z" fill={`url(#${am})`} opacity=".85"
            className={animated ? 'art-blink' : ''} />
      <circle cx="32" cy="32" r="15" fill="#0b1528" />
      <path d="M23 43.5h10" stroke="#e0f2fe" strokeWidth="3" strokeLinecap="round" />
      <path d="M27.5 41 27 33.5 35.5 25 40 31" fill="none" stroke="#e0f2fe" strokeWidth="3.6"
            strokeLinecap="round" strokeLinejoin="round" />
      {detailed && <path d="M38 33.5l2-2.5 2 2.5" fill="none" stroke="#e0f2fe" strokeWidth="1.8"
                         strokeLinecap="round" strokeLinejoin="round" />}
      <circle cx="27" cy="33.5" r="2.6" fill="#38bdf8" stroke="#e0f2fe" strokeWidth="1.4" />
      <circle cx="35.5" cy="25" r="2.6" fill="#0b1528" stroke="#fbbf24" strokeWidth="1.8" />
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

/** VITE_INSTITUTION_LOGO can point at a different file (see public/brand/README). */
const LOGO_URL = (import.meta.env.VITE_INSTITUTION_LOGO as string | undefined)
  || '/brand/giu-logo.png'

/** The official university logo; its name as text if the file is missing. */
export function InstitutionLogo({ className = '', textClass = '', strong = false }: {
  className?: string; textClass?: string
  /** A firmer outline, for where the logo sits small on a dark bar. */
  strong?: boolean
}) {
  const [failed, setFailed] = useState(false)
  if (LOGO_URL && !failed) {
    return (
      // The G and the first flag stripe are black, as in the official logo.
      // On a dark page a thin, soft light outline keeps their shape legible
      // without recolouring them - a display effect, the file is unchanged.
      <img src={LOGO_URL} alt="German International University"
           className={`h-8 w-auto object-contain ${className}`}
           style={{ filter: strong
             ? 'drop-shadow(0 0 0.8px rgba(241,245,249,1)) drop-shadow(0 0 0.8px rgba(241,245,249,.85)) drop-shadow(0 0 3px rgba(241,245,249,.22))'
             : 'drop-shadow(0 0 0.6px rgba(241,245,249,.95)) drop-shadow(0 0 2px rgba(241,245,249,.18))' }}
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
