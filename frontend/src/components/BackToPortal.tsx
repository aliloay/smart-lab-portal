/**
 * The way back from a full-screen page outside the portal frame (IoT Dashboard wall, Live monitor) - owner
 * 2026-10-27: "an Esc button ... so I could get back through the portal, not the browser".
 * A visible "Portal" button, and the Esc key: in browser full screen the first Esc only leaves full screen
 * (the browser's own rule); the next Esc - or the first one when not in full screen - goes back to the portal.
 * Esc is ignored while typing in a field or while a dialog is open.
 */
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function BackToPortal({ to = '/command', className = '' }: { to?: string; className?: string }) {
  const nav = useNavigate()
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented || document.fullscreenElement) return
      const t = e.target as HTMLElement | null
      if (t && (t.closest('input, textarea, select, [contenteditable="true"]') || document.querySelector('[role="dialog"]:not([aria-hidden="true"])'))) return
      nav(to)
    }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [nav, to])
  return (
    <button type="button" onClick={() => nav(to)} title="Back to the portal (Esc)"
            className={`inline-flex items-center gap-1.5 rounded-lg border border-white/[.12] bg-white/[.04] px-2.5 py-1.5 text-[12px] font-medium text-slate-200 hover:border-cyan-400/50 hover:text-white ${className}`}>
      <ArrowLeft size={14} /> Portal <kbd className="ml-0.5 rounded border border-white/15 px-1 text-[10px] text-slate-400">Esc</kbd>
    </button>)
}
