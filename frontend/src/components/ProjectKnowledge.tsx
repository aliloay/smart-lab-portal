/**
 * Project knowledge (admins and lab staff): questions about the Smart Lab project itself,
 * answered by the local knowledge agent on this laptop from the project's documents, code,
 * history and approved conversations - with sources. Streams the answer as it is written.
 * The agent is read-only; it never changes the portal, devices or n8n.
 */
import { FormEvent, useEffect, useRef, useState } from 'react'
import { BookOpen, Send, Square } from 'lucide-react'
import { getToken } from '../lib/api'
import MicButton from './MicButton'

interface Cite { n: number; source: string; heading?: string; label: string; snippet?: string }
interface Turn {
  q: string; route?: string; why?: string; steps: string[]; text: string; cites: Cite[]
  status: 'running' | 'completed' | 'failed' | 'cancelled'; error?: string; ms?: number; firstMs?: number; note?: string
}

const EXAMPLES = [
  'Why will the Smart Lab not use a PLC?',
  'How does the consumables bin count resistors?',
  'Where is the Master ESP32 IP documented?',
  'Investigate why names could swap when two people cross',
]

const ROUTE_TEXT: Record<string, string> = {
  lookup: 'Lookup - sources only, no AI', answer: 'Answer - local AI with sources',
  investigate: 'Investigation - read code, history and tests',
}

export default function ProjectKnowledge() {
  const [q, setQ] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [now, setNow] = useState(Date.now())
  const abort = useRef<AbortController | null>(null)
  const started = useRef(0)
  const end = useRef<HTMLDivElement>(null)
  const running = turns.some(t => t.status === 'running')

  useEffect(() => { if (!running) return; const t = setInterval(() => setNow(Date.now()), 250); return () => clearInterval(t) }, [running])
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [turns])

  const patch = (fn: (t: Turn) => Turn) => setTurns(ts => ts.map((t, i) => i === ts.length - 1 ? fn(t) : t))

  async function ask(question: string) {
    if (!question.trim() || running) return
    setQ('')
    started.current = Date.now()
    setTurns(ts => [...ts, { q: question, steps: [], text: '', cites: [], status: 'running' }])
    const ac = new AbortController()
    abort.current = ac
    try {
      const res = await fetch('/api/knowledge/ask', {
        method: 'POST', signal: ac.signal,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken() ?? ''}` },
        body: JSON.stringify({ question }),
      })
      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        patch(t => ({ ...t, status: 'failed', error: err.detail ?? 'Request failed' }))
        return
      }
      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        let nl
        while ((nl = buf.indexOf('\n')) >= 0) {
          const line = buf.slice(0, nl).trim()
          buf = buf.slice(nl + 1)
          if (!line) continue
          const e = JSON.parse(line)
          if (e.type === 'meta') patch(t => ({ ...t, route: e.route, why: e.why, cites: e.citations ?? [] }))
          else if (e.type === 'step') patch(t => ({ ...t, steps: [...t.steps, String(e.text).replace(/^step: /, '')] }))
          else if (e.type === 'sources') patch(t => ({ ...t, cites: e.sources }))
          else if (e.type === 'token') patch(t => ({ ...t, text: t.text + e.text, firstMs: t.firstMs ?? Date.now() - started.current }))
          else if (e.type === 'done') patch(t => ({
            ...t, status: e.status === 'completed' ? 'completed' : e.status === 'cancelled' ? 'cancelled' : 'failed',
            error: e.error, note: e.note, ms: Date.now() - started.current,
            text: t.text || (e.answer && e.route !== 'lookup' ? e.answer : t.text),
          }))
        }
      }
      patch(t => t.status === 'running' ? { ...t, status: 'completed', ms: Date.now() - started.current } : t)
    } catch (err) {
      patch(t => ({ ...t, status: ac.signal.aborted ? 'cancelled' : 'failed',
                    error: ac.signal.aborted ? undefined : (err as Error).message, ms: Date.now() - started.current }))
    } finally {
      abort.current = null
    }
  }

  function submit(e: FormEvent) { e.preventDefault(); ask(q) }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-1">
        {!turns.length && (
          <div className="text-[13px] text-slate-400 space-y-3">
            <p>Ask about the Smart Lab project itself - how it works, why it was built this way, what changed and what
              is still open. Answers come from the project's documents, code, git history and your approved
              conversations, on this laptop only, with sources.</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map(x => (
                <button key={x} onClick={() => ask(x)} className="btn-ghost btn-sm text-left">{x}</button>))}
            </div>
          </div>)}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2">
            <div className="text-[13.5px] text-white font-medium">{t.q}</div>
            {t.route && (
              <div className="text-[11.5px] text-slate-400" title={t.why}>
                <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-200 mr-1.5">{ROUTE_TEXT[t.route] ?? t.route}</span>
                {t.status === 'running'
                  ? `working… ${((now - started.current) / 1000).toFixed(1)} s`
                  : `${t.status} · ${((t.ms ?? 0) / 1000).toFixed(1)} s${t.firstMs ? ` · first word ${(t.firstMs / 1000).toFixed(1)} s` : ''}`}
              </div>)}
            {t.steps.length > 0 && (
              <ul className="text-[11.5px] text-slate-400 list-disc pl-5">{t.steps.map((s, j) => <li key={j}>{s}</li>)}</ul>)}
            {t.text && <div className="text-[13.5px] text-slate-100 whitespace-pre-wrap leading-relaxed">{t.text}</div>}
            {t.route === 'lookup' && t.status !== 'running' && (
              <div className="text-[11.5px] text-slate-400">Sources only - no AI answer was generated.</div>)}
            {t.error && <div className="text-[12.5px] text-warn-soft">{t.error}</div>}
            {t.cites.length > 0 && (
              <details open={t.route === 'lookup'} className="text-[12px]">
                <summary className="cursor-pointer text-slate-300 inline-flex items-center gap-1.5"><BookOpen size={13} /> Sources ({t.cites.length})</summary>
                <ol className="mt-1.5 space-y-1.5">
                  {t.cites.map(c => (
                    <li key={c.n} className="text-slate-300">
                      <span className="mono text-slate-200">[{c.n}] {c.source}</span>
                      {c.heading && <span className="text-slate-400"> — {c.heading}</span>}
                      <span className="ml-1.5 text-[10.5px] px-1.5 py-0.5 rounded bg-ink-700/70 text-slate-300">{c.label}</span>
                      {c.snippet && t.route === 'lookup' && <div className="text-slate-400 mt-0.5">{c.snippet}</div>}
                    </li>))}
                </ol>
              </details>)}
          </div>))}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input className="input flex-1" value={q} onChange={e => setQ(e.target.value)} maxLength={600}
               placeholder="Ask about the project…" disabled={running} />
        <MicButton onText={t => void ask(t)} disabled={running} />
        {running
          ? <button type="button" className="btn-ghost" onClick={() => abort.current?.abort()}><Square size={15} /> Stop</button>
          : <button className="btn-primary" disabled={!q.trim()}><Send size={15} /></button>}
      </form>
      <p className="mt-1.5 text-[10.5px] text-slate-500">Local only · admins and staff · labels: DOCUMENTED, VERIFIED_CURRENT,
        TESTED (recorded, not live), HISTORICAL, REPORTED (owner said), PROPOSAL (assistant, unverified).</p>
    </div>
  )
}
