/**
 * Global search / command palette (Ctrl+K or Cmd+K, or the search button in the sidebar).
 * Pages come from the user's OWN menu (so a student never sees staff pages); devices, incidents,
 * equipment and labs come from /api/search (staff only, bounded, debounced, stale requests
 * cancelled). It only navigates - nothing here starts an action on any device.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CornerDownLeft, Search } from 'lucide-react'
import { getToken } from '../lib/api'

export interface PaletteItem { to: string; label: string; section?: string }
interface Hit { type: string; title: string; subtitle: string; to: string }

export function openPalette() { window.dispatchEvent(new Event('smartlab:palette')) }

export default function CommandPalette({ pages, staff }: { pages: PaletteItem[]; staff: boolean }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<Hit[]>([])
  const [sel, setSel] = useState(0)
  const [loading, setLoading] = useState(false)
  const nav = useNavigate()
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen(o => !o) }
      if (e.key === 'Escape') setOpen(false)
    }
    const onOpen = () => setOpen(true)
    window.addEventListener('keydown', onKey)
    window.addEventListener('smartlab:palette', onOpen)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('smartlab:palette', onOpen) }
  }, [])
  useEffect(() => { if (open) { setQ(''); setHits([]); setSel(0); window.setTimeout(() => input.current?.focus(), 0) } }, [open])

  useEffect(() => {
    if (!open || !staff || q.trim().length < 2) { setHits([]); return }
    const ctl = new AbortController()
    const t = window.setTimeout(async () => {
      setLoading(true)
      try {
        const r = await fetch(`/api/search?q=${encodeURIComponent(q.trim())}`, {
          headers: { Authorization: `Bearer ${getToken() ?? ''}` }, signal: ctl.signal })
        if (r.ok) setHits((await r.json()).results)
      } catch { /* aborted or offline: pages still work */ } finally { setLoading(false) }
    }, 120)   // server answers in ~60-80 ms; 220 ms of typing pause made results feel slow
    return () => { window.clearTimeout(t); ctl.abort() }
  }, [q, open, staff])

  const pageHits = useMemo(() => {
    const s = q.trim().toLowerCase()
    return (s ? pages.filter(p => p.label.toLowerCase().includes(s) || (p.section ?? '').toLowerCase().includes(s)) : pages).slice(0, 8)
  }, [q, pages])
  const all = [...pageHits.map(p => ({ type: 'page', title: p.label, subtitle: p.section ?? 'page', to: p.to })), ...hits]
  useEffect(() => { setSel(0) }, [q, hits.length])
  const go = (to: string) => { setOpen(false); nav(to) }

  if (!open) return null
  return (
    <div className="fixed inset-0 z-[70] bg-black/50 flex items-start justify-center pt-[12vh] px-4" onClick={() => setOpen(false)}>
      <div className="w-full max-w-xl card p-0 overflow-hidden" onClick={e => e.stopPropagation()} role="dialog" aria-label="Search">
        <div className="flex items-center gap-2 px-3 border-b border-ink-600">
          <Search size={16} className="text-slate-400" />
          <input ref={input} value={q} onChange={e => setQ(e.target.value)} placeholder={staff ? 'Search pages, devices, incidents, equipment, labs…' : 'Search pages…'}
            className="flex-1 bg-transparent py-3 text-[14px] text-white outline-none"
            onKeyDown={e => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setSel(s => Math.min(all.length - 1, s + 1)) }
              if (e.key === 'ArrowUp') { e.preventDefault(); setSel(s => Math.max(0, s - 1)) }
              if (e.key === 'Enter' && all[sel]) go(all[sel].to)
            }} />
          <kbd className="text-[10px] text-slate-500 border border-ink-600 rounded px-1">Esc</kbd>
        </div>
        <ul className="max-h-[50vh] overflow-auto py-1">
          {all.length === 0 && <li className="px-3 py-3 text-[13px] text-slate-500">{loading ? 'Searching…' : 'Nothing found.'}</li>}
          {all.map((h, i) => (
            <li key={h.type + h.to + h.title}>
              <button onMouseEnter={() => setSel(i)} onClick={() => go(h.to)}
                className={`w-full text-left px-3 py-2 flex items-center gap-2 text-[13px] ${i === sel ? 'bg-accent-500/15 text-white' : 'text-slate-300'}`}>
                <span className="text-[10.5px] uppercase tracking-wide text-slate-500 w-20 shrink-0">{h.type}</span>
                <span className="truncate">{h.title}</span>
                <span className="ml-auto text-[11px] text-slate-500 truncate">{h.subtitle}</span>
                {i === sel && <CornerDownLeft size={12} className="text-slate-500 shrink-0" />}
              </button>
            </li>))}
        </ul>
        <div className="px-3 py-1.5 border-t border-ink-600 text-[11px] text-slate-500">↑ ↓ to choose · Enter to open · navigation only - no action is started from here</div>
      </div>
    </div>
  )
}
