/**
 * The welcome after sign-in: ~2.4 s, CSS only, drawn OVER the portal, which is
 * already loaded and working underneath (nothing waits for it).
 *
 * When: once, right after a successful sign-in in this tab (Login.tsx sets a
 * sessionStorage flag; a reload or navigation never replays it).
 * Preview again: add ?intro to any portal URL (e.g. http://localhost/?intro).
 * Skip: the Skip button (focused), Esc, Enter or a click. Reduced motion: not shown.
 * Holds no user data beyond the first name already on screen.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { SmartLabMark } from './Brand'

const FLAG = 'smartlab.intro'
const DURATION_MS = 2400

/** Called by the sign-in page after a successful login. */
export function requestIntro() {
  try { sessionStorage.setItem(FLAG, 'pending') } catch { /* private mode: no intro */ }
}

function wanted(): boolean {
  const url = new URL(window.location.href)
  if (url.searchParams.has('intro')) {
    url.searchParams.delete('intro')
    window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash)
    return true
  }
  try {
    if (sessionStorage.getItem(FLAG) !== 'pending') return false
    sessionStorage.setItem(FLAG, 'shown')
    return true
  } catch { return false }
}

export default function WelcomeIntro({ name }: { name?: string }) {
  const [phase, setPhase] = useState<'off' | 'on' | 'leaving'>('off')
  const skipRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!wanted()) return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    setPhase('on')
  }, [])

  const finish = useCallback(() => setPhase(p => (p === 'on' ? 'leaving' : p)), [])

  useEffect(() => {
    if (phase === 'on') {
      skipRef.current?.focus()
      const t = window.setTimeout(finish, DURATION_MS)
      const k = (e: KeyboardEvent) => { if (e.key === 'Escape' || e.key === 'Enter') finish() }
      window.addEventListener('keydown', k)
      return () => { window.clearTimeout(t); window.removeEventListener('keydown', k) }
    }
    if (phase === 'leaving') {
      const t = window.setTimeout(() => setPhase('off'), 520)
      return () => window.clearTimeout(t)
    }
  }, [phase, finish])

  if (phase === 'off') return null
  return (
    <div className={`intro ${phase === 'leaving' ? 'intro-out' : ''}`} onClick={finish}
         role="dialog" aria-modal="false" aria-label="Welcome to Smart Lab">
      <div className="intro-grid" aria-hidden />
      <div className="intro-content">
        <div className="intro-mark"><SmartLabMark size={64} /></div>
        <h1 className="intro-title">SMART LAB</h1>
        <p className="intro-sub">Intelligent Research Environment</p>
        {name && <p className="intro-hello">Welcome, {name}</p>}
        <div className="intro-line" aria-hidden />
      </div>
      <button ref={skipRef} type="button" className="intro-skip btn-ghost btn-sm" onClick={e => { e.stopPropagation(); finish() }}>
        Skip
      </button>
    </div>
  )
}
