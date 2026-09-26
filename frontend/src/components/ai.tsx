/**
 * AI assistant UI.
 *
 * staff:   answers from the portal's own analytics through read-only tools.
 * student: answers from the student's own bookings/reports and the lab list.
 * See backend app/services/ai.py. The model is either free and local
 * (Ollama) or Claude. When neither is set up the staff panel says how; the
 * student panel just stays hidden. The priority list is deterministic and
 * always works.
 */
import { FormEvent, ReactNode, useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Bot, ListOrdered, MessageCircle, Send, Sparkles, TriangleAlert, X } from 'lucide-react'
import { AiAnswer, AiStatus, Priority, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { Chip, EmptyState, SeverityBadge, Skeleton, Spinner } from './ui'

type Turn = { role: 'user' | 'assistant'; content: string; tools?: string[] }

const STUDENT_SUGGESTED = [
  'When is my next booking?',
  'Which labs are free tomorrow afternoon?',
  'What happened to the issue I reported?',
  'How do I get into the lab with my booking?',
]

const SUGGESTED = [
  'How busy were the labs this week compared with last week?',
  'Which lab has the most no-shows, and when?',
  'Were there any security concerns in the last 24 hours?',
  'What should the technicians fix first today?',
]

/** Minimal rendering: paragraphs, "- " bullets and **bold** - no HTML from the model. */
export function AiText({ text }: { text: string }) {
  const bold = (line: string): ReactNode[] =>
    line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith('**') && part.endsWith('**')
        ? <strong key={i} className="text-white">{part.slice(2, -2)}</strong> : part)
  const blocks = text.split(/\n{2,}/)
  return (
    <div className="space-y-2 text-[13.5px] leading-relaxed text-slate-200">
      {blocks.map((b, i) => {
        const lines = b.split('\n').filter(Boolean)
        if (lines.length && lines.every(l => /^\s*([-*•]|\d+[.)])\s+/.test(l))) {
          return <ul key={i} className="list-disc pl-5 space-y-1">
            {lines.map((l, j) => <li key={j}>{bold(l.replace(/^\s*([-*•]|\d+[.)])\s+/, ''))}</li>)}
          </ul>
        }
        return <p key={i}>{lines.map((l, j) => <span key={j}>{bold(l.replace(/^#+\s*/, ''))}{j < lines.length - 1 && <br />}</span>)}</p>
      })}
    </div>
  )
}

/** What to tell staff when the model is configured but cannot answer yet. */
function SetupHint({ s }: { s: AiStatus }) {
  if (!s.configured) {
    return <EmptyState compact icon={<Bot size={18} />} title="AI assistant not set up"
      detail="Free option: install Ollama (ollama.com) on this computer, run the two 'ollama pull' commands from docs/AI_ASSISTANT.md, and restart the portal. Everything else, including the priority list, works without it." />
  }
  if (!s.reachable) {
    return <EmptyState compact icon={<Bot size={18} />} title="Local AI (Ollama) is not running"
      detail="Start the Ollama app on the computer running the portal (install it from ollama.com if needed), then reload this page." />
  }
  return <EmptyState compact icon={<Bot size={18} />} title="AI model not downloaded yet"
    detail={`In a terminal on that computer run: ${s.missing_models.map(m => `ollama pull ${m}`).join('  and  ')}`} />
}

export function AskTheLab({ mode = 'staff' }: { mode?: 'staff' | 'student' }) {
  const student = mode === 'student'
  const [status, setStatus] = useState<AiStatus | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    (student ? api.studentAiStatus() : api.aiStatus()).then(setStatus)
      .catch(() => setStatus({ configured: false, provider: null, model: null, reachable: false,
                               missing_models: [], questions_per_hour: 0 }))
  }, [student])
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [turns, busy])

  const ask = async (question: string) => {
    const text = question.trim()
    if (!text || busy) return
    setError('')
    const history = turns.map(t => ({ role: t.role, content: t.content }))
    setTurns(t => [...t, { role: 'user', content: text }])
    setQ('')
    setBusy(true)
    try {
      const r: AiAnswer = await (student ? api.studentAiAsk : api.aiAsk)(text, history)
      setTurns(t => [...t, { role: 'assistant', content: r.answer, tools: r.tools_used }])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The assistant could not answer.')
      setTurns(t => t.slice(0, -1))
      setQ(text)
    } finally { setBusy(false) }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); ask(q) }

  if (status === null) return <Skeleton className="h-40" />
  const ready = status.configured && status.reachable && status.missing_models.length === 0
  if (!ready) {
    if (!student) return <SetupHint s={status} />
    return status.configured
      ? <p className="text-[12.5px] text-slate-400">The helper is offline right now. Try again later.</p>
      : null
  }
  return (
    <div className="flex flex-col">
      <div className="max-h-[420px] overflow-y-auto space-y-3 pr-1">
        {turns.length === 0 && (
          <div className="space-y-2">
            <p className="text-[12.5px] text-slate-400">{student
              ? 'Ask about your bookings, your reports, or which labs are free.'
              : "Ask about usage, access, devices or maintenance. Answers are computed from the portal's own records."}</p>
            <div className="flex flex-wrap gap-2">
              {(student ? STUDENT_SUGGESTED : SUGGESTED).map(s => (
                <button key={s} onClick={() => ask(s)} disabled={busy}
                  className="text-left text-[12.5px] px-3 py-1.5 rounded-lg border border-ink-600 bg-ink-800/50
                             text-slate-300 hover:text-white hover:border-accent-400/50">{s}</button>))}
            </div>
          </div>)}
        {turns.map((t, i) => t.role === 'user' ? (
          <div key={i} className="flex justify-end">
            <div className="max-w-[85%] rounded-xl rounded-br-sm bg-accent-500/15 border border-accent-400/25
                            px-3.5 py-2 text-[13.5px] text-slate-100">{t.content}</div>
          </div>
        ) : (
          <div key={i} className="flex gap-2.5">
            <span className="mt-0.5 grid place-items-center w-7 h-7 rounded-lg bg-violet-500/15 text-violet-300 shrink-0">
              <Sparkles size={14} /></span>
            <div className="min-w-0 flex-1 rounded-xl rounded-tl-sm border border-ink-600/70 bg-ink-800/40 px-3.5 py-2.5">
              <AiText text={t.content} />
              {!!t.tools?.length && (
                <div className="mt-2 text-[11px] text-slate-500">
                  Checked: {Array.from(new Set(t.tools)).map(x => x.replace(/^get_|^list_/, '').replace(/_/g, ' ')).join(', ')}
                </div>)}
            </div>
          </div>))}
        {busy && <div className="flex items-center gap-2 text-[12.5px] text-slate-400">
          <Spinner inline /> Looking at the records…</div>}
        <div ref={end} />
      </div>
      {error && <div className="mt-2 text-[12.5px] text-bad-soft flex items-center gap-1.5">
        <TriangleAlert size={13} />{error}</div>}
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input value={q} onChange={e => setQ(e.target.value)} maxLength={1000} disabled={busy}
          placeholder={student ? 'Ask about your bookings…' : 'Ask the lab…'}
          aria-label="Question for the AI assistant" className="input flex-1" />
        <button type="submit" className="btn-primary" disabled={busy || q.trim().length < 2}>
          <Send size={15} /><span className="hidden sm:inline">Ask</span></button>
      </form>
      <p className="mt-2 text-[11px] text-slate-500">
        {student
          ? 'It only sees your own bookings and reports. It cannot book, cancel or open doors.'
          : 'Read-only: the assistant cannot change bookings, issues or doors. Check important figures on the charts.'}
        {status.provider === 'ollama' && ` Runs on a free local model (${status.model}).`}
      </p>
    </div>
  )
}

/** Official maintenance order (deterministic) + optional AI summary. */
export function PriorityList({ limit = 5, withSummary = true }: { limit?: number; withSummary?: boolean }) {
  const [rows, setRows] = useState<Priority[] | null>(null)
  const [scoring, setScoring] = useState<string[]>([])
  const [ai, setAi] = useState<{ on: boolean; busy: boolean; text: string; error: string }>(
    { on: false, busy: false, text: '', error: '' })

  useEffect(() => {
    api.priorities(limit).then(r => { setRows(r.priorities); setScoring(r.scoring) }).catch(() => setRows([]))
    api.aiStatus().then(s => setAi(a => ({ ...a, on: s.configured && s.reachable && !s.missing_models.length })))
      .catch(() => {})
  }, [limit])

  const summarise = () => {
    setAi(a => ({ ...a, busy: true, error: '' }))
    api.aiSummary('issues')
      .then(r => setAi(a => ({ ...a, busy: false, text: r.answer })))
      .catch(e => setAi(a => ({ ...a, busy: false, error: e.message })))
  }

  if (!rows) return <Skeleton className="h-40" />
  return (
    <div className="space-y-3">
      {rows.length === 0 ? <EmptyState compact icon={<ListOrdered size={18} />} title="No open issues" /> : (
        <ol className="space-y-2">
          {rows.map((p, i) => (
            <li key={p.issue_id}>
              <Link to={p.link} className="flex gap-3 rounded-xl border border-ink-600/70 bg-ink-800/40 p-3 hover:border-accent-400/40">
                <span className="font-display text-lg text-slate-400 w-5 text-center">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[13.5px] text-slate-100 truncate">{p.title}</span>
                    <SeverityBadge severity={p.severity} />
                    {p.overdue && <Chip tone="bad">overdue</Chip>}
                  </div>
                  <div className="text-[11.5px] text-slate-500 mt-0.5 mono">{p.ticket} · {p.lab_code} · open {p.age_hours} h</div>
                  <div className="text-[11.5px] text-slate-400 mt-1">{p.reasons.join(' · ')}</div>
                </div>
                <span className="text-right shrink-0">
                  <span className="block font-display text-lg text-white tnum">{p.score}</span>
                  <span className="text-[10.5px] text-slate-500">score</span>
                </span>
              </Link>
            </li>))}
        </ol>)}
      <details className="text-[11.5px] text-slate-500">
        <summary className="cursor-pointer">How the score works</summary>
        <ul className="list-disc pl-5 mt-1 space-y-0.5">{scoring.map(s => <li key={s}>{s}</li>)}</ul>
      </details>
      {withSummary && ai.on && rows.length > 0 && (
        <div className="rounded-xl border border-violet-400/25 bg-violet-500/5 p-3.5">
          {!ai.text && !ai.busy && (
            <button onClick={summarise} className="btn-ghost btn-sm"><Sparkles size={14} />Summarise with AI</button>)}
          {ai.busy && <div className="flex items-center gap-2 text-[12.5px] text-slate-400"><Spinner inline />Reading the open issues…</div>}
          {ai.text && <AiText text={ai.text} />}
          {ai.error && <div className="text-[12.5px] text-bad-soft">{ai.error}</div>}
        </div>)}
    </div>
  )
}

/**
 * Chat bubble on every page. Staff get the lab assistant (with setup hints
 * if the model is not ready); students get their helper, and see no bubble
 * at all while no AI is set up. The panel stays mounted when closed so the
 * conversation survives navigation.
 */
const OPEN_CHAT = 'smartlab:open-chat'
/** Open the chat panel from anywhere (e.g. the sidebar button). */
export const openChat = () => window.dispatchEvent(new Event(OPEN_CHAT))

/** Whether this user has a chat at all: staff always, students once AI is set up. */
export function useChatAvailable(): boolean {
  const { user } = useAuth()
  const staff = isStaff(user)
  const [available, setAvailable] = useState(false)
  useEffect(() => {
    if (!user) { setAvailable(false); return }
    if (staff) { setAvailable(true); return }
    api.studentAiStatus().then(s => setAvailable(s.configured)).catch(() => setAvailable(false))
  }, [user, staff])
  return available
}

export function ChatBubble() {
  const { user } = useAuth()
  const loc = useLocation()
  const staff = isStaff(user)
  const [open, setOpen] = useState(false)
  const available = useChatAvailable()

  useEffect(() => {
    const show = () => setOpen(true)
    window.addEventListener(OPEN_CHAT, show)
    return () => window.removeEventListener(OPEN_CHAT, show)
  }, [])

  if (!user || !available) return null
  // The Operations Center already shows the full panel; the bubble appears
  // there only when opened from the sidebar.
  if (loc.pathname === '/admin/operations' && !open) return null
  return (
    <>
      <div className={`fixed z-40 bottom-24 right-4 sm:right-6 w-[calc(100vw-2rem)] sm:w-[410px]
                       card p-4 shadow-2xl ${open ? '' : 'hidden'}`}
           role="dialog" aria-label="AI assistant">
        <div className="flex items-center gap-2 mb-3">
          <span className="grid place-items-center w-7 h-7 rounded-lg bg-violet-500/15 text-violet-300">
            <Sparkles size={14} /></span>
          <div className="flex-1 text-sm font-medium text-white">
            {staff ? 'Ask the lab' : 'Ask Smart Lab'}</div>
          <button onClick={() => setOpen(false)} aria-label="Close" className="p-1 text-slate-400 hover:text-white">
            <X size={16} /></button>
        </div>
        <AskTheLab mode={staff ? 'staff' : 'student'} />
      </div>
      <button onClick={() => setOpen(o => !o)} aria-label={open ? 'Close assistant' : 'Open AI assistant'}
        className="fixed z-40 bottom-5 right-4 sm:right-6 w-14 h-14 rounded-full grid place-items-center
                   bg-gradient-to-br from-accent-500 to-violet-500 text-white shadow-lg
                   hover:scale-105 transition-transform">
        {open ? <X size={22} /> : <MessageCircle size={22} />}
      </button>
    </>
  )
}
