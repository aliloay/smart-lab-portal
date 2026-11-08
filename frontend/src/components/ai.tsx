/**
 * AI assistant UI.
 *
 * staff:   answers from the portal's own analytics through read-only tools.
 * student: answers from the student's own bookings/reports and the lab list.
 * See backend app/services/ai.py. The model is either free and local
 * (Ollama) or Claude. Common questions (next booking, free labs, weekly /
 * monthly report, who is inside, equipment use, repeated problems) are
 * answered instantly by the agent from the records, with or without a
 * model. The priority list is deterministic and always works.
 */
import { FormEvent, ReactNode, Suspense, lazy, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowUpRight, BookOpen, Bot, ThumbsDown, ThumbsUp, ListOrdered, Maximize2, MessageCircle, Mic, Minimize2, ScanLine, Send, Sparkles, Square, TriangleAlert, Volume2, VolumeX, X, Zap } from 'lucide-react'
import { MAX_RECORD_MS, Recording, VoiceStatus, micSupported, speak, spokenSummary, stopSpeaking, transcribe, voiceStatus } from '../lib/voice'
import { AiAction, AiAnswer, AiChartData, AiStatus, Priority, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { Chip, EmptyState, SeverityBadge, Skeleton, Spinner } from './ui'

type Turn = {
  role: 'user' | 'assistant'; content: string; tools?: string[]
  instant?: boolean; link?: { label: string; to: string }; charts?: AiChartData[]
  actions?: AiAction[]
}
// Charts load with the first chart answer: Recharts stays out of the main bundle.
const AiChart = lazy(() => import('./AiChart'))
const ProjectKnowledge = lazy(() => import('./ProjectKnowledge'))

const STUDENT_SUGGESTED = [
  'When is my next booking?',
  'Which labs are free now?',
  'What happened to the issue I reported?',
  'How do I get into the lab with my booking?',
]

const SUGGESTED = [
  'Weekly report',
  'Monthly report',
  'Which robot was used most?',
  'What keeps repeating, and how do we fix it?',
  'Who is inside the labs?',
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

export function AskTheLab({ mode = 'staff', fill = false, listen = false }: {
  mode?: 'staff' | 'student'
  /** Fill the parent's height (the chat panel) instead of a fixed-height box. */
  fill?: boolean
  /** The chat bubble's instance answers 'smartlab:ask-lab' events (e.g. "Ask the lab about it" on Scan the lab). */
  listen?: boolean
}) {
  const student = mode === 'student'
  const [status, setStatus] = useState<AiStatus | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const end = useRef<HTMLDivElement>(null)
  // Voice (2026-10-26): push to talk -> local Whisper -> the same question path; spoken questions get spoken answers.
  const [voice, setVoice] = useState<VoiceStatus | null>(null)
  const [vphase, setVphase] = useState<'idle' | 'recording' | 'transcribing'>('idle')
  const [recMs, setRecMs] = useState(0)
  const [speaking, setSpeaking] = useState(false)
  const rec = useRef<Recording | null>(null)
  const voiceRef = useRef(voice); voiceRef.current = voice
  useEffect(() => { if (micSupported()) voiceStatus().then(setVoice) }, [])
  useEffect(() => () => { rec.current?.cancel(); stopSpeaking() }, [])
  useEffect(() => {
    if (vphase !== 'recording') return
    const t = window.setInterval(() => setRecMs(Date.now() - (rec.current?.started ?? Date.now())), 200)
    return () => window.clearInterval(t)
  }, [vphase])

  useEffect(() => {
    (student ? api.studentAiStatus() : api.aiStatus()).then(setStatus)
      .catch(() => setStatus({ configured: false, provider: null, model: null, reachable: false,
                               missing_models: [], questions_per_hour: 0 }))
  }, [student])
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [turns, busy])

  const ask = async (question: string, spoken = false) => {
    const text = question.trim()
    if (!text || busy) return
    setError('')
    const history = turns.map(t => ({ role: t.role, content: t.content }))
    setTurns(t => [...t, { role: 'user', content: text }])
    setQ('')
    setBusy(true)
    try {
      const r: AiAnswer = await (student ? api.studentAiAsk : api.aiAsk)(text, history)
      setTurns(t => [...t, { role: 'assistant', content: r.answer, tools: r.tools_used,
                             instant: r.instant, link: r.link, charts: r.charts, actions: r.actions }])
      if (spoken) {
        setSpeaking(true)
        void speak(spokenSummary(r.answer), !!voice?.tts).then(how => { if (how !== 'browser') setSpeaking(false) })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The assistant could not answer.')
      setTurns(t => t.slice(0, -1))
      setQ(text)
    } finally { setBusy(false) }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); ask(q) }
  const finishRecording = async () => {
    const r = rec.current
    if (!r) return
    rec.current = null
    setVphase('transcribing')
    try {
      const audio = await r.stop()
      const t = await transcribe(audio)
      if (!t.text || t.text.length < 2) { setError('Did not catch that - hold the mic and speak a little closer.'); return }
      await askRef.current(t.text, true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Voice failed - type the question instead.')
    } finally { setVphase('idle') }
  }
  const finishRef = useRef(finishRecording); finishRef.current = finishRecording
  const startRecording = async () => {
    if (rec.current || busy) return
    stopSpeaking(); setSpeaking(false); setError('')
    if (!micSupported()) { setError('Voice needs the secure (https) portal address and a browser with a microphone.'); return }
    if (voiceRef.current === null) { const v = await voiceStatus(); voiceRef.current = v; setVoice(v) }   // "Talk" before the status arrived
    if (!voiceRef.current?.stt) { setError(`Voice is not available: ${voiceRef.current?.reason ?? 'the voice service is not running on the lab laptop'}. Type the question instead.`); return }
    try {
      rec.current = await Recording.start(() => void finishRef.current())
      setRecMs(0); setVphase('recording')
    } catch {
      setError('The microphone is blocked - allow it for this site (lock icon in the address bar).')
    }
  }
  const startRef = useRef(startRecording); startRef.current = startRecording
  const micOn = !!voice?.stt
  useEffect(() => {
    if (!listen) return
    const on = () => { void startRef.current() }
    window.addEventListener('smartlab:talk', on)
    return () => window.removeEventListener('smartlab:talk', on)
  }, [listen])
  const askRef = useRef(ask); askRef.current = ask
  useEffect(() => {
    if (!listen) return
    const on = (e: Event) => { const t = (e as CustomEvent<string>).detail; if (typeof t === 'string') void askRef.current(t) }
    window.addEventListener('smartlab:ask-lab', on)
    return () => window.removeEventListener('smartlab:ask-lab', on)
  }, [listen])

  if (status === null) return <Skeleton className="h-40" />
  // Without a working model the chat still answers the common questions
  // instantly from the records; only open-ended ones need the model.
  const ready = status.configured && status.reachable && status.missing_models.length === 0
  return (
    <div className={`flex flex-col ${fill ? 'h-full min-h-0 text-[14.5px]' : ''}`}>
      <div className={`${fill ? 'flex-1 min-h-0' : 'max-h-[420px]'} overflow-y-auto space-y-3 pr-1`}>
        {!ready && turns.length === 0 && (student
          ? <p className="text-[12px] text-warn-soft">The AI model is offline: the suggested questions
              below still answer instantly.</p>
          : <SetupHint s={status} />)}
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
            <div className={`max-w-[85%] rounded-xl rounded-br-sm bg-accent-500/15 border border-accent-400/25
                            px-3.5 py-2 ${fill ? 'text-[14.5px]' : 'text-[13.5px]'} text-slate-100`}>{t.content}</div>
          </div>
        ) : (
          <div key={i} className="flex gap-2.5">
            <span className="mt-0.5 grid place-items-center w-7 h-7 rounded-lg bg-violet-500/15 text-violet-300 shrink-0">
              <Sparkles size={14} /></span>
            <div className="min-w-0 flex-1 rounded-xl rounded-tl-sm border border-ink-600/70 bg-ink-800/40 px-3.5 py-2.5">
              <AiText text={t.content} />
              {!!t.actions?.length && <ActionButtons actions={t.actions}
                onDone={msg => setTurns(ts => [...ts, { role: 'assistant', content: msg, instant: true }])} />}
              {!!t.charts?.length && (
                <Suspense fallback={<div className="mt-3 text-[12px] text-slate-500">Drawing the chart…</div>}>
                  <div className={`grid gap-3 ${t.charts.length > 1 ? 'xl:grid-cols-2' : ''}`}>
                    {t.charts.map((c, k) => <AiChart key={k} chart={c} />)}
                  </div>
                </Suspense>)}
              {t.link && (t.link.to.startsWith('/report') ? (
                // The report opens in its own tab. window.open (unlike a
                // target="_blank" link, which opens with noopener) gives the new
                // tab a copy of this tab's sign-in, so it does not ask again.
                <a href={t.link.to} onClick={e => { e.preventDefault(); window.open(t.link!.to, '_blank') }}
                  className="mt-2 inline-flex items-center gap-1 text-[12.5px] text-accent-300 hover:text-accent-200">
                  {t.link.label} <ArrowUpRight size={13} /></a>
              ) : (
                <Link to={t.link.to}
                  className="mt-2 inline-flex items-center gap-1 text-[12.5px] text-accent-300 hover:text-accent-200">
                  {t.link.label} <ArrowUpRight size={13} /></Link>))}
              <Feedback question={turns[i - 1]?.content ?? ''} answer={t.content} route={t.instant ? 'instant' : 'model'}
                        intent={t.tools?.[0] ?? null} />
              {t.instant ? (
                <div className="mt-2 text-[11px] text-slate-500 inline-flex items-center gap-1 ml-2">
                  <Zap size={11} className="text-ok-soft" /> Instant, from the records</div>
              ) : !!t.tools?.length && (
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
      {vphase !== 'idle' && <div className="mt-2 flex items-center gap-2 text-[12.5px]" role="status">
        {vphase === 'recording'
          ? <><span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
              <span className="text-slate-200">Listening… {(recMs / 1000).toFixed(0)} / {MAX_RECORD_MS / 1000} s - press the mic again when done</span>
              <button type="button" className="ml-auto text-slate-400 hover:text-white" onClick={() => { rec.current?.cancel(); rec.current = null; setVphase('idle') }}>Cancel</button></>
          : <><Spinner inline /><span className="text-slate-300">Turning speech into text (on this laptop)…</span></>}
      </div>}
      {speaking && <button type="button" onClick={() => { stopSpeaking(); setSpeaking(false) }}
        className="mt-2 self-start text-[12px] text-slate-400 hover:text-white inline-flex items-center gap-1"><VolumeX size={13} /> Stop speaking</button>}
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input value={q} onChange={e => setQ(e.target.value)} maxLength={1000} disabled={busy}
          placeholder={vphase === 'recording' ? 'Listening…' : student ? 'Ask about your bookings…' : 'Ask the lab…'}
          aria-label="Question for the AI assistant" className="input flex-1" />
        {micOn && <button type="button" aria-label={vphase === 'recording' ? 'Stop and send' : 'Ask by voice'}
          title={vphase === 'recording' ? 'Stop and send' : 'Ask by voice (push to talk)'}
          disabled={busy || vphase === 'transcribing'}
          onClick={() => vphase === 'recording' ? void finishRecording() : void startRecording()}
          className={`grid place-items-center w-11 rounded-xl border ${vphase === 'recording'
            ? 'bg-red-600 border-red-500 text-white' : 'border-ink-600 text-slate-300 hover:text-white hover:border-accent-400/50'}`}>
          {vphase === 'recording' ? <Square size={15} /> : <Mic size={16} />}</button>}
        <button type="submit" className="btn-primary" disabled={busy || q.trim().length < 2}>
          <Send size={15} /><span className="hidden sm:inline">Ask</span></button>
      </form>
      <p className="mt-2 text-[11px] text-slate-500">
        {student
          ? 'It only sees your own bookings and reports. It cannot book, cancel or open doors.'
          : 'Read-only: the assistant cannot change bookings, issues or doors. Check important figures on the charts.'}
        {status.provider === 'ollama' && ` Runs on a free local model (${status.model}).`}
        {micOn && <> <Volume2 size={11} className="inline" /> Voice runs on this laptop ({voice?.model}); recordings are not kept.</>}
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
    // Everyone: the agent answers the common questions even without a model.
    setAvailable(true)
  }, [user, staff])
  return available
}

const CHAT_SIZE = 'slp.chatSize'

export function ChatBubble() {
  const { user } = useAuth()
  const loc = useLocation()
  const staff = isStaff(user)
  const [open, setOpen] = useState(false)
  // 'large' = tall panel at the right; 'full' = almost the whole window.
  const [size, setSize] = useState<'large' | 'full'>(() => {
    try { return localStorage.getItem(CHAT_SIZE) === 'full' ? 'full' : 'large' } catch { return 'large' }
  })
  const available = useChatAvailable()
  // Staff and admins: a second mode for questions about the project itself (local knowledge agent).
  const [mode, setMode] = useState<'lab' | 'project'>('lab')
  const toggleSize = () => setSize(v => {
    const next = v === 'full' ? 'large' : 'full'
    try { localStorage.setItem(CHAT_SIZE, next) } catch { /* private mode */ }
    return next
  })
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [open])

  // The bubble / sidebar button opens the LAUNCHER first (staff): ask the lab, ask the project, scan with the
  // phone camera, or talk. Students go straight to their helper.
  const [launcher, setLauncher] = useState(false)
  const nav = useNavigate()
  useEffect(() => {
    const show = () => { if (staff) setLauncher(true); else setOpen(true) }
    const askLab = () => { setLauncher(false); setMode('lab'); setOpen(true) }
    window.addEventListener(OPEN_CHAT, show)
    window.addEventListener('smartlab:ask-lab', askLab)
    return () => { window.removeEventListener(OPEN_CHAT, show); window.removeEventListener('smartlab:ask-lab', askLab) }
  }, [staff])
  useEffect(() => {
    if (!launcher) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setLauncher(false) }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [launcher])
  const pick = (what: 'lab' | 'project' | 'scan' | 'talk') => {
    setLauncher(false)
    if (what === 'scan') { setOpen(false); nav('/scan'); return }
    setMode(what === 'project' ? 'project' : 'lab')
    setOpen(true)
    if (what === 'talk') window.dispatchEvent(new Event('smartlab:talk'))
  }

  if (!user || !available) return null
  // The Operations Center already shows the full panel; the bubble appears
  // there only when opened from the sidebar.
  if (loc.pathname === '/admin/operations' && !open) return null
  // Portal to <body>: the page wrapper is its own layer and would keep the
  // panel under the sidebar.
  return createPortal(
    <>
      {open && size === 'full' && (
        <div className="fixed inset-0 z-[60] bg-ink-950/60 backdrop-blur-[2px]" onClick={() => setOpen(false)} />)}
      {/* Pops out of the bubble (bottom-right). Stays mounted when closed so
          the conversation survives navigation. */}
      <div className={`fixed z-[61] card p-5 shadow-2xl flex flex-col origin-bottom-right
                       transition-[opacity,transform] duration-200 ease-out
                       ${size === 'full'
                         ? 'top-4 bottom-24 left-4 right-4 sm:top-8 sm:left-[max(2rem,calc(50vw-36rem))] sm:right-[max(2rem,calc(50vw-36rem))]'
                         : 'top-20 bottom-24 right-4 sm:right-6 w-[calc(100vw-2rem)] sm:w-[min(760px,calc(100vw-3rem))]'}
                       ${open ? 'opacity-100 scale-100' : 'opacity-0 scale-90 pointer-events-none'}`}
           role="dialog" aria-label="AI assistant" aria-hidden={!open}>
        <div className="flex items-center gap-2.5 mb-4 pb-3 border-b border-ink-600/70">
          <span className="grid place-items-center w-9 h-9 rounded-xl bg-violet-500/15 text-violet-300">
            <Sparkles size={17} /></span>
          <div className="flex-1 min-w-0">
            <div className="text-[16px] font-semibold text-white">
              {staff ? (mode === 'project' ? 'Project knowledge' : 'Ask the lab') : 'Ask Smart Lab'}</div>
            <div className="text-[12px] text-slate-400">
              {staff ? (mode === 'project' ? 'The Smart Lab project: documents, code, history - with sources'
                                           : 'Answers from the portal’s own records')
                     : 'Your bookings, reports and free labs'}</div>
          </div>
          <button onClick={toggleSize} aria-label={size === 'full' ? 'Smaller' : 'Full screen'}
                  title={size === 'full' ? 'Smaller' : 'Full screen'}
                  className="grid place-items-center w-8 h-8 rounded-lg text-slate-400 hover:text-white hover:bg-ink-700/60">
            {size === 'full' ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button>
          <button onClick={() => setOpen(false)} aria-label="Close"
                  className="grid place-items-center w-8 h-8 rounded-lg text-slate-400 hover:text-white hover:bg-ink-700/60">
            <X size={17} /></button>
        </div>
        {staff && (
          <div className="flex gap-1 mb-3 p-1 rounded-lg bg-ink-800/60 self-start" role="tablist">
            {(['lab', 'project'] as const).map(m => (
              <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
                className={`px-3 py-1 rounded-md text-[12.5px] ${mode === m ? 'bg-ink-600 text-white' : 'text-slate-400 hover:text-white'}`}>
                {m === 'lab' ? 'Lab data' : 'Project knowledge'}</button>))}
          </div>)}
        <div className="flex-1 min-h-0">
          {staff && mode === 'project' && <Suspense fallback={<Spinner />}><ProjectKnowledge /></Suspense>}
          {/* Always mounted (hidden on the project tab) so a question sent from elsewhere is never lost. */}
          <div className={`h-full min-h-0 ${staff && mode === 'project' ? 'hidden' : ''}`}>
            <AskTheLab mode={staff ? 'staff' : 'student'} fill listen /></div>
        </div>
      </div>
      {launcher && !open && <>
        <div className="fixed inset-0 z-[60]" onClick={() => setLauncher(false)} />
        <div className="fixed z-[61] bottom-24 right-4 sm:right-6 w-[min(320px,calc(100vw-2rem))] card p-2 shadow-2xl"
             role="menu" aria-label="AI assistant">
          <div className="flex items-center gap-2 px-3 pt-1.5 pb-2 mb-1 border-b border-ink-600/70">
            <span className="text-[12px] text-slate-400 flex-1">Opens {size === 'full' ? 'full screen' : 'as a side panel'}</span>
            <button type="button" onClick={toggleSize} aria-pressed={size === 'full'}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12px] border ${size === 'full'
                      ? 'border-violet-400/60 text-violet-200 bg-violet-500/15' : 'border-ink-600 text-slate-300 hover:text-white'}`}>
              {size === 'full' ? <Minimize2 size={13} /> : <Maximize2 size={13} />}{size === 'full' ? 'Smaller' : 'Enlarge'}</button>
          </div>
          {([['lab', <Bot size={17} key="i" />, 'Ask the lab', 'Live and recorded lab data'],
             ['project', <BookOpen size={17} key="i" />, 'Ask the project', 'Design, code, wiring - with sources'],
             ['scan', <ScanLine size={17} key="i" />, 'Scan the lab', 'Phone camera: point at a marker, see live state'],
             ['talk', <Mic size={17} key="i" />, 'Talk', 'Push to talk, spoken answers']] as const).map(([k, icon, t, d]) => (
            <button key={k} role="menuitem" onClick={() => pick(k)}
                    className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-ink-700/60">
              <span className="grid place-items-center w-9 h-9 rounded-lg bg-violet-500/15 text-violet-300">{icon}</span>
              <span><span className="block text-[14px] text-white">{t}</span><span className="block text-[11.5px] text-slate-400">{d}</span></span>
            </button>))}
        </div>
      </>}
      <button onClick={() => { if (open) setOpen(false); else if (staff) setLauncher(l => !l); else setOpen(true) }}
        aria-label={open ? 'Close assistant' : 'Open AI assistant'}
        className="fixed z-[62] bottom-5 right-4 sm:right-6 w-14 h-14 rounded-full grid place-items-center
                   bg-gradient-to-br from-accent-500 to-violet-500 text-white shadow-lg
                   hover:scale-105 transition-transform">
        {open ? <X size={22} /> : <MessageCircle size={22} />}
      </button>
    </>,
    document.body)
}


/** Optional thumbs up / down under an answer (2026-10-27): one tap, sent once, never blocks the chat. */
function Feedback({ question, answer, route, intent }: { question: string; answer: string; route: 'instant' | 'model'; intent: string | null }) {
  const [sent, setSent] = useState<'up' | 'down' | null>(null)
  const send = (rating: 'up' | 'down') => {
    if (sent || !question) return
    setSent(rating)
    api.aiFeedback({ question, answer: answer.slice(0, 8000), rating, route, intent }).catch(() => setSent(null))
  }
  return (
    <span className="float-right ml-2 inline-flex items-center gap-1 text-slate-500" aria-label="Rate this answer">
      {sent ? <span className="text-[11px]">{sent === 'up' ? 'Thanks' : 'Noted - it helps us fix this'}</span> : <>
        <button type="button" title="Good answer" aria-label="Good answer" onClick={() => send('up')} className="p-1 hover:text-ok-soft"><ThumbsUp size={12} /></button>
        <button type="button" title="Wrong or unhelpful" aria-label="Wrong or unhelpful" onClick={() => send('down')} className="p-1 hover:text-bad-soft"><ThumbsDown size={12} /></button></>}
    </span>)
}


/** Booking proposals from the assistant (2026-10-27): Confirm calls the normal booking endpoints as the signed-in user
 *  (same rules, permissions and audit as the booking pages); nothing happens without the tap. */
function ActionButtons({ actions, onDone }: { actions: AiAction[]; onDone: (msg: string) => void }) {
  const [state, setState] = useState<'idle' | 'busy' | 'done'>('idle')
  const run = async (a: AiAction) => {
    setState('busy')
    try {
      if (a.type === 'create_booking') {
        const b = await api.createBooking({ lab_id: a.lab_id, start_time: a.start_time, end_time: a.end_time, reason: a.reason })
        onDone(`Done - ${a.label.replace(/^Book /, '')} is booked` + (b.status === 'PENDING' ? ' (waiting for staff approval).' : '.')
               + ' Your QR code is under My bookings.')
      } else {
        await api.cancelBooking(a.booking_id)
        onDone(`Done - ${a.label.replace(/^Cancel /, '')} is cancelled.`)
      }
      setState('done')
    } catch (e) {
      setState('idle')
      onDone(`Not done: ${e instanceof Error ? e.message : 'the portal refused it'}`)
    }
  }
  if (state === 'done') return null
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {actions.map((a, i) => (
        <button key={i} type="button" disabled={state === 'busy'} onClick={() => void run(a)}
                className={a.type === 'cancel_booking' ? 'btn-ghost btn-sm !text-bad-soft' : 'btn-primary btn-sm'}>
          {state === 'busy' ? 'Working…' : `Confirm: ${a.label}`}</button>))}
      <button type="button" className="btn-ghost btn-sm" disabled={state === 'busy'} onClick={() => setState('done')}>Not now</button>
    </div>)
}
