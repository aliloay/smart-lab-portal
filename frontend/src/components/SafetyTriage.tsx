/**
 * Advisory safety triage strip (2026-10-27): the backend's ranked list (services/safety_triage.py) - what to look
 * at first, with its evidence and ages. Advisory only, never a safety function. Quiet when nothing is flagged.
 */
import { useEffect, useState } from 'react'
import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { getToken } from '../lib/api'

interface Item { priority: number; lab_code: string; title: string; action: string; key: string
  evidence: { source: string; value: string; age_s: number | null }[] }

const TONE: Record<number, string> = { 1: 'border-red-500/60 bg-red-500/10 text-red-200', 2: 'border-amber-400/50 bg-amber-400/10 text-amber-100',
  3: 'border-sky-400/40 bg-sky-400/5 text-sky-100' }

export default function SafetyTriage({ labId, compact = false }: { labId?: number | null; compact?: boolean }) {
  const [items, setItems] = useState<Item[] | null>(null)
  const [advisory, setAdvisory] = useState('')
  useEffect(() => {
    let live = true
    const load = () => {
      if (document.hidden) return
      const token = getToken()
      fetch(`/api/safety/triage${labId ? `?lab_id=${labId}` : ''}`, { cache: 'no-store', headers: token ? { Authorization: `Bearer ${token}` } : {} })
        .then(r => r.ok ? r.json() : null).then(d => { if (live && d) { setItems(d.items); setAdvisory(d.advisory) } }).catch(() => {})
    }
    load(); const t = window.setInterval(load, 10000)
    return () => { live = false; window.clearInterval(t) }
  }, [labId])
  if (items === null) return null
  if (!items.length) return (
    <div className={`flex items-center gap-2 rounded-xl border border-emerald-400/25 bg-emerald-400/5 px-3 ${compact ? 'py-1.5 text-[11.5px]' : 'py-2 text-[12.5px]'} text-emerald-200`}>
      <ShieldCheck size={14} /> Safety triage: nothing flagged right now <span className="text-slate-500">· advisory</span></div>)
  return (
    <section aria-label="Safety triage" className="space-y-1.5">
      <div className="flex items-center gap-2 text-[12px] text-slate-300"><ShieldAlert size={14} className="text-amber-300" />
        <b className="text-white">Safety triage</b> <span className="text-slate-500">{advisory}</span></div>
      {items.slice(0, compact ? 3 : 6).map(i => (
        <div key={i.key} className={`rounded-xl border px-3 py-2 ${TONE[i.priority] ?? TONE[3]}`}>
          <div className="flex items-center gap-2 text-[13px] font-semibold"><span className="rounded bg-black/30 px-1.5 text-[11px]">P{i.priority}</span>
            <span className="truncate">{i.lab_code} · {i.title}</span></div>
          {!compact && <div className="text-[12px] opacity-90">{i.action}</div>}
          <div className="text-[11px] opacity-70">{i.evidence.map(e => `${e.source}: ${e.value}${e.age_s != null ? ` (${e.age_s} s ago)` : ''}`).join(' · ')}</div>
        </div>))}
    </section>)
}
