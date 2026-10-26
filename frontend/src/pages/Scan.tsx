/**
 * "Scan the lab" - the phone camera in the AI assistant (2026-10-26). Staff only.
 *
 * Three layers, never mixed (backend app/services/scan.py):
 *   1. DETECTION   people boxes from the lab's camera-service detector (optional; a generic class, never a name)
 *   2. IDENTIFICATION   a printed QR marker "SLAB:<kind>:<key>" = the asset's own record key - decoded ON THE PHONE
 *                       (native BarcodeDetector, else jsQR in a worker). No marker = unidentified, never guessed.
 *   3. LIVE DATA   the card of that exact record (heartbeat, readings, bin measurements, robot / PC state) with
 *                  its timestamp and quality.
 * Speed: nothing queues. One decode and one people request at a time; a busy detector (429) just skips the frame.
 * Stop (or hiding the tab / leaving the page) stops the camera tracks, loops, worker and requests at once.
 * No frame is stored anywhere.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Camera, CameraOff, FileVideo, MessageCircle, Mic, QrCode, RefreshCw, ScanLine, ShieldAlert, Smartphone, Square, Users, VolumeX } from 'lucide-react'
import { Recording, VoiceStatus, micSupported, speak, spokenSummary, stopSpeaking, transcribe, voiceStatus } from '../lib/voice'
import { AiText } from '../components/ai'
import { ScanCard, ScanPeople, api, scanPeople } from '../lib/api'
import { Chip } from '../components/ui'

type Pt = { x: number; y: number }
type Seen = { text: string; corners: Pt[]; at: number }
type CardState = { card?: ScanCard; error?: string; fetchedAt: number }
interface BarcodeDetectorLike { detect(src: CanvasImageSource): Promise<{ rawValue: string; cornerPoints: Pt[] }[]> }

const DECODE_EVERY_MS = 120           // ~8 marker checks a second
const CARD_REFRESH_MS = 5000          // a card in view is re-read this often (its own timestamp shows age)
const SEEN_HOLD_MS = 1500             // a marker outline stays this long after the last sighting
const PEOPLE_HOLD_MS = 1200
const W = 640                         // analysis width (decode + people frames)

const fmtAge = (s: number | null) => s == null ? 'never' : s < 90 ? `${s} s ago` : s < 5400 ? `${Math.round(s / 60)} min ago`
  : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`
const tone = (q: string) => (q === 'LIVE' || q === 'VALID' || q === 'ONLINE' || q === 'AVAILABLE') ? 'ok'
  : (q === 'STALE' || q === 'NO_DATA' || q === 'MISSING') ? 'warn' : q === 'RECORD' ? 'idle' : 'bad'

/** Ask the lab assistant about this asset (the chat bubble listens). */
export const askLab = (q: string) => window.dispatchEvent(new CustomEvent('smartlab:ask-lab', { detail: q }))

export default function Scan() {
  const video = useRef<HTMLVideoElement>(null)
  const overlay = useRef<HTMLCanvasElement>(null)
  const grab = useRef<HTMLCanvasElement | null>(null)
  const session = useRef<{
    stream?: MediaStream; raf?: number; worker?: Worker; native?: BarcodeDetectorLike; decoding: boolean
    lastDecode: number; people?: AbortController; peopleBusy: boolean; fileUrl?: string; stopped: boolean
  }>({ decoding: false, lastDecode: 0, peopleBusy: false, stopped: true })
  const seen = useRef(new Map<string, Seen>())
  const boxes = useRef<{ at: number; r: ScanPeople } | null>(null)
  const [running, setRunning] = useState(false)
  const [starting, setStarting] = useState(false)
  const [facing, setFacing] = useState<'environment' | 'user'>('environment')
  const [peopleOn, setPeopleOn] = useState(true)        // owner 2026-10-27: people boxes on by default (button turns them off)
  const [error, setError] = useState('')
  const [source, setSource] = useState<'camera' | 'file'>('camera')
  const [cards, setCards] = useState<Record<string, CardState>>({})
  const [inView, setInView] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [stats, setStats] = useState({ decodeMs: 0, peopleMs: 0, peopleRtt: 0, decoder: '' })
  const cardsRef = useRef(cards); cardsRef.current = cards
  const peopleRef = useRef(peopleOn); peopleRef.current = peopleOn

  const secure = window.isSecureContext && !!navigator.mediaDevices?.getUserMedia

  // ------------------------------------------------------------------ stop: releases EVERYTHING
  const stop = useCallback(() => {
    const s = session.current
    s.stopped = true
    if (s.raf) cancelAnimationFrame(s.raf)
    s.people?.abort()
    s.worker?.terminate()
    s.stream?.getTracks().forEach(t => t.stop())
    if (s.fileUrl) URL.revokeObjectURL(s.fileUrl)
    const v = video.current
    if (v) { v.pause(); v.srcObject = null; v.removeAttribute('src'); v.load() }
    session.current = { decoding: false, lastDecode: 0, peopleBusy: false, stopped: true }
    seen.current.clear(); boxes.current = null
    setRunning(false); setInView([])
  }, [])

  useEffect(() => {
    const hide = () => { if (document.hidden) stop() }     // a hidden tab never keeps the camera
    document.addEventListener('visibilitychange', hide)
    return () => { document.removeEventListener('visibilitychange', hide); stop() }
  }, [stop])

  // ------------------------------------------------------------------ live card per marker
  const loadCard = useCallback((code: string) => {
    setCards(c => ({ ...c, [code]: { ...c[code], fetchedAt: Date.now() } }))
    api.scanAsset(code)
      .then(card => setCards(c => ({ ...c, [code]: { card, fetchedAt: Date.now() } })))
      .catch(e => setCards(c => ({ ...c, [code]: { error: e instanceof Error ? e.message : 'unidentified', fetchedAt: Date.now() } })))
  }, [])

  // ------------------------------------------------------------------ one marker decode (never two at once)
  const decode = useCallback(async (v: HTMLVideoElement) => {
    const s = session.current
    if (s.decoding || !v.videoWidth) return
    s.decoding = true
    const g = grab.current ?? (grab.current = document.createElement('canvas'))
    const w = Math.min(W, v.videoWidth), h = Math.round(w * v.videoHeight / v.videoWidth)
    g.width = w; g.height = h
    const ctx = g.getContext('2d', { willReadFrequently: true })!
    ctx.drawImage(v, 0, 0, w, h)
    const t0 = performance.now()
    let found: { text: string; corners: Pt[] }[] = []
    try {
      if (s.native) {
        found = (await s.native.detect(g)).map(b => ({ text: b.rawValue, corners: b.cornerPoints }))
      } else if (s.worker) {
        const img = ctx.getImageData(0, 0, w, h)
        found = await new Promise(res => {
          const wk = s.worker!
          wk.onmessage = (e: MessageEvent<{ codes: { text: string; corners: Pt[] }[] }>) => res(e.data.codes)
          wk.postMessage({ id: 0, data: img.data, w, h }, [img.data.buffer])
        })
      }
    } catch { found = [] }
    if (s.stopped) return
    const ms = performance.now() - t0
    const now = Date.now(), sx = 1 / w, sy = 1 / h
    for (const f of found) {
      if (!f.text.startsWith('SLAB:')) continue              // only our markers; any other QR is ignored
      seen.current.set(f.text, { text: f.text, corners: f.corners.map(p => ({ x: p.x * sx, y: p.y * sy })), at: now })
      const c = cardsRef.current[f.text]
      if (!c || (now - c.fetchedAt > CARD_REFRESH_MS)) loadCard(f.text)
    }
    const visible = [...seen.current.values()].filter(m => now - m.at < SEEN_HOLD_MS).map(m => m.text)
    setInView(v0 => (v0.join() === visible.join() ? v0 : visible))
    setStats(st => ({ ...st, decodeMs: Math.round(ms) }))
    s.decoding = false
    // people: one request in flight at most, on the same 640-px frame
    if (peopleRef.current && !s.peopleBusy) {
      s.peopleBusy = true
      g.toBlob(async blob => {
        if (!blob || session.current.stopped) { s.peopleBusy = false; return }
        const ac = new AbortController(); s.people = ac
        const t1 = performance.now()
        try {
          const r = await scanPeople(blob, ac.signal)
          if (r && !session.current.stopped) {
            boxes.current = { at: Date.now(), r }
            setStats(st => ({ ...st, peopleMs: r.ms, peopleRtt: Math.round(performance.now() - t1) }))
          }
        } catch (e) {
          if (!(e instanceof DOMException && e.name === 'AbortError')) { setError(e instanceof Error ? e.message : String(e)); setPeopleOn(false) }
        } finally { s.peopleBusy = false }
      }, 'image/jpeg', 0.65)
    }
  }, [loadCard])

  // ------------------------------------------------------------------ overlay (every display frame)
  const draw = useCallback(() => {
    const s = session.current
    if (s.stopped) return
    const v = video.current, c = overlay.current
    if (v && c && v.videoWidth) {
      const rect = v.getBoundingClientRect()
      const dpr = Math.min(2, window.devicePixelRatio || 1)
      if (c.width !== Math.round(rect.width * dpr)) { c.width = Math.round(rect.width * dpr); c.height = Math.round(rect.height * dpr) }
      // object-contain: where the picture actually sits inside the element
      const k = Math.min(rect.width / v.videoWidth, rect.height / v.videoHeight)
      const pw = v.videoWidth * k, ph = v.videoHeight * k, ox = (rect.width - pw) / 2, oy = (rect.height - ph) / 2
      const ctx = c.getContext('2d')!
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, rect.width, rect.height)
      const now = Date.now()
      const b = boxes.current
      if (b && now - b.at < PEOPLE_HOLD_MS) {
        ctx.lineWidth = 2; ctx.strokeStyle = '#38bdf8'; ctx.fillStyle = '#38bdf8'; ctx.font = '12px Inter, sans-serif'
        for (const p of b.r.boxes) {
          const x = ox + p.x * pw, y = oy + p.y * ph
          ctx.strokeRect(x, y, p.w * pw, p.h * ph)
          ctx.fillText(`person ${Math.round(p.score * 100)}%`, x + 3, Math.max(12, y - 4))
        }
      }
      for (const m of seen.current.values()) {
        if (now - m.at > SEEN_HOLD_MS) continue
        const card = cardsRef.current[m.text]?.card
        ctx.lineWidth = 3; ctx.strokeStyle = card ? '#10b981' : '#f59e0b'
        ctx.beginPath()
        m.corners.forEach((p, i) => { const x = ox + p.x * pw, y = oy + p.y * ph; if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y) })
        ctx.closePath(); ctx.stroke()
        const p0 = m.corners[0]
        const label = card ? `${card.name} · ${card.status.toLowerCase()}` : cardsRef.current[m.text]?.error ? 'unidentified' : 'looking up…'
        ctx.font = '600 13px Inter, sans-serif'
        const tw = ctx.measureText(label).width
        const lx = ox + p0.x * pw, ly = oy + p0.y * ph - 8
        ctx.fillStyle = 'rgba(2,6,23,0.8)'; ctx.fillRect(lx - 3, ly - 15, tw + 8, 20)
        ctx.fillStyle = card ? '#a7f3d0' : '#fde68a'; ctx.fillText(label, lx + 1, ly)
      }
      if (now - s.lastDecode >= DECODE_EVERY_MS) { s.lastDecode = now; void decode(v) }
    }
    s.raf = requestAnimationFrame(draw)
  }, [decode])

  // ------------------------------------------------------------------ start (camera or a recorded test video)
  const begin = useCallback(async (opts: { facingMode?: 'environment' | 'user'; file?: File }) => {
    stop()
    setError(''); setStarting(true)
    const s = { decoding: false, lastDecode: 0, peopleBusy: false, stopped: false } as typeof session.current
    try {
      const v = video.current!
      if (opts.file) {
        s.fileUrl = URL.createObjectURL(opts.file)
        v.srcObject = null; v.src = s.fileUrl; v.loop = true
        setSource('file')
      } else {
        // the back camera, ~720p: enough for a marker across a desk, light enough for a phone
        s.stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: {
          facingMode: { ideal: opts.facingMode ?? facing }, width: { ideal: 1280 }, height: { ideal: 720 } } })
        v.srcObject = s.stream
        setSource('camera')
      }
      v.muted = true; v.playsInline = true
      await v.play()
      const BD = (window as unknown as { BarcodeDetector?: new (o: { formats: string[] }) => BarcodeDetectorLike }).BarcodeDetector
      if (BD) { try { s.native = new BD({ formats: ['qr_code'] }) } catch { s.native = undefined } }
      if (!s.native) s.worker = new Worker(new URL('../lib/qrWorker.ts', import.meta.url), { type: 'module' })
      setStats(st => ({ ...st, decoder: s.native ? 'native BarcodeDetector' : 'jsQR (worker)' }))
      session.current = s
      setRunning(true)
      s.raf = requestAnimationFrame(draw)
    } catch (e) {
      s.stream?.getTracks().forEach(t => t.stop())
      const n = e instanceof DOMException ? e.name : ''
      setError(n === 'NotAllowedError' ? 'Camera permission was refused. Allow the camera for this site in the browser settings, then press Start again.'
        : n === 'NotFoundError' || n === 'OverconstrainedError' ? 'No camera found on this device (or the chosen one is not available).'
        : n === 'NotReadableError' ? 'The camera is busy in another app or tab. Close it there and press Start again.'
        : e instanceof Error ? e.message : 'The camera could not start.')
    } finally { setStarting(false) }
  }, [draw, facing, stop])

  const flip = () => { const f = facing === 'environment' ? 'user' : 'environment'; setFacing(f); if (running && source === 'camera') void begin({ facingMode: f }) }
  const shown = selected ?? inView[0] ?? null
  const cs = shown ? cards[shown] : undefined

  return (
    <div className="space-y-3 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 flex-wrap">
        <ScanLine className="text-accent-300" size={20} />
        <h1 className="text-[18px] font-semibold text-white">Scan the lab</h1>
        <span className="text-[12px] text-slate-400">Point at a Smart Lab marker - the card shows that asset's live record.</span>
        <Link to="/scan/markers" className="ml-auto btn-ghost btn-sm"><QrCode size={14} /> Markers</Link>
        <Link to="/phone-setup" className="btn-ghost btn-sm"><Smartphone size={14} /> Phone setup</Link>
      </div>

      {!secure && <div className="rounded-xl border border-warn/40 bg-warn/5 p-3 text-[13px] text-warn-soft flex gap-2">
        <ShieldAlert size={16} className="shrink-0 mt-0.5" />
        <span>The camera needs a secure page (https://). Open the portal with <b>https://</b> on this device -
          <Link to="/phone-setup" className="underline ml-1">set up this phone</Link>. A recorded test video still works below.</span></div>}

      <div className="relative rounded-xl overflow-hidden bg-black aspect-video">
        <video ref={video} className="absolute inset-0 w-full h-full object-contain" muted playsInline />
        <canvas ref={overlay} className="absolute inset-0 w-full h-full pointer-events-none" />
        {!running && <div className="absolute inset-0 grid place-items-center text-slate-400 text-[13px]">
          {starting ? 'Starting the camera…' : 'Camera off'}</div>}
        {running && source === 'file' && <span className="absolute top-2 left-2"><Chip tone="warn">RECORDED TEST VIDEO</Chip></span>}
      </div>

      <div className="flex flex-wrap gap-2">
        {running
          ? <button className="inline-flex items-center gap-2 rounded-xl px-4 py-2 font-semibold text-white bg-red-600 hover:bg-red-500"
                    onClick={stop}><CameraOff size={15} /> Stop</button>
          : <button className="btn-primary" disabled={!secure || starting} onClick={() => begin({})}><Camera size={15} /> Start camera</button>}
        <button className="btn-ghost" disabled={!secure || starting} onClick={flip}><RefreshCw size={15} /> {facing === 'environment' ? 'Back' : 'Front'} camera</button>
        <button className={`btn-ghost ${peopleOn ? 'border border-sky-400/60 text-sky-200' : ''}`} onClick={() => setPeopleOn(p => !p)}>
          <Users size={15} /> People boxes {peopleOn ? 'on' : 'off'}</button>
        <label className="btn-ghost cursor-pointer"><FileVideo size={15} /> Test video
          <input type="file" accept="video/*" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) void begin({ file: f }); e.target.value = '' }} /></label>
      </div>
      {error && <p className="text-[12.5px] text-bad-soft">{error}</p>}
      {running && <p className="text-[11px] text-slate-500">Markers: {stats.decoder}, {stats.decodeMs} ms per check
        {peopleOn && ` · people: detector ${stats.peopleMs} ms, round trip ${stats.peopleRtt} ms (boxes are "person" only - never a name)`}</p>}

      {inView.length > 1 && <div className="flex flex-wrap gap-1.5">{inView.map(c => (
        <button key={c} onClick={() => setSelected(c)} className={`text-[12px] px-2 py-1 rounded-md border ${shown === c ? 'border-accent-400 text-white' : 'border-ink-600 text-slate-400'}`}>
          {cards[c]?.card?.name ?? c}</button>))}</div>}

      <ScanVoice card={cs?.card} />

      {shown && <AssetCard code={shown} state={cs} onRefresh={() => loadCard(shown)} />}
      {!shown && running && <p className="text-[12.5px] text-slate-500">No marker in view. Unmarked equipment stays unidentified -
        the camera never guesses which device it is from its look.</p>}
    </div>
  )
}

function AssetCard({ code, state, onRefresh }: { code: string; state?: CardState; onRefresh: () => void }) {
  const c = state?.card
  if (!c) return <div className="card p-3 text-[13px]">{state?.error
    ? <span className="text-warn-soft">Unidentified marker <span className="mono">{code}</span> - {state.error}</span>
    : <span className="text-slate-400">Looking up <span className="mono">{code}</span>…</span>}</div>
  return (
    <div className="card p-3.5 space-y-2.5">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[15px] font-semibold text-white">{c.name}</span>
        <span className="text-[12px] text-slate-400">{c.type}{c.lab_code ? ` · ${c.lab_code}` : ''}</span>
        <span className="ml-auto"><Chip tone={tone(c.status)}>{c.status.replace(/_/g, ' ').toLowerCase()}</Chip></span>
      </div>
      <div className="text-[11.5px] text-slate-500">Last report: {fmtAge(c.seconds_since_seen)}
        {c.last_seen_at ? ` (${new Date(c.last_seen_at).toLocaleString()})` : ''} · marker <span className="mono">{c.code}</span></div>
      {c.facts.length > 0 && <ul className="grid sm:grid-cols-2 gap-x-4 gap-y-1 text-[13px]">
        {c.facts.map(f => <li key={f.label} className="flex gap-2"><span className="text-slate-400">{f.label}</span>
          <span className="text-slate-100">{f.value}</span>
          {f.quality !== 'RECORD' && <Chip tone={tone(f.quality)}>{f.quality.toLowerCase()}</Chip>}</li>)}</ul>}
      {c.readings.length > 0 && <ul className="grid sm:grid-cols-3 gap-2">
        {c.readings.map(r => <li key={r.metric} className="rounded-lg border border-ink-600 px-2.5 py-1.5">
          <div className="text-[11px] text-slate-400">{r.metric}</div>
          <div className="text-[15px] text-white tnum">{Number.isInteger(r.value) ? r.value : r.value.toFixed(1)} {r.unit}</div>
          <div className={`text-[10.5px] ${r.quality === 'LIVE' ? 'text-slate-500' : 'text-warn-soft'}`}>{fmtAge(r.age_s)}{r.quality === 'STALE' ? ' - stale' : ''}</div></li>)}</ul>}
      {c.type === 'Sensor node' && c.readings.length === 0 &&
        <div className="text-[12.5px] text-warn-soft">No readings from this node in the last 24 h - nothing is shown instead of old values.</div>}
      <div className="text-[12px] text-slate-400">{c.open_alerts} open alert{c.open_alerts === 1 ? '' : 's'} on this device ·
        {' '}{c.open_issues_in_lab} open issue{c.open_issues_in_lab === 1 ? '' : 's'} in {c.lab_code ?? 'the lab'}</div>
      <div className="flex flex-wrap gap-2">
        <button className="btn-primary btn-sm" onClick={() => askLab(c.ask)}><MessageCircle size={14} /> Ask the lab about it</button>
        <Link to={c.link} className="btn-ghost btn-sm">Open in the portal</Link>
        <button className="btn-ghost btn-sm" onClick={onRefresh}><RefreshCw size={13} /> Refresh</button>
      </div>
    </div>
  )
}

/** What the camera shows right now, as plain text for the assistant (only the portal's own record, with its age). */
export function cardContext(c: ScanCard): string {
  const parts = [`I am looking at ${c.name} (${c.type}${c.lab_code ? `, ${c.lab_code}` : ''}, marker ${c.code}) through the phone camera.`,
    `Its record in the portal: status ${c.status.replace(/_/g, ' ').toLowerCase()}, last report ${fmtAge(c.seconds_since_seen)}.`]
  if (c.facts.length) parts.push('Facts: ' + c.facts.map(f => `${f.label} ${f.value}${f.quality !== 'RECORD' ? ` (${f.quality.toLowerCase()})` : ''}`).join('; ') + '.')
  if (c.readings.length) parts.push('Readings: ' + c.readings.map(r => `${r.metric} ${r.value} ${r.unit} (${fmtAge(r.age_s)}${r.quality === 'STALE' ? ', stale' : ''})`).join('; ') + '.')
  parts.push(`${c.open_alerts} open alerts on it, ${c.open_issues_in_lab} open issues in ${c.lab_code ?? 'the lab'}.`)
  return parts.join(' ').slice(0, 3500)
}

/**
 * Voice while scanning (owner 2026-10-27): ask by voice about the asset in view (its live card goes along as context)
 * or about anything in the lab. Same path as typing - /ai/ask with the same permissions; the camera keeps running.
 * The context travels as an earlier turn, so the instant database answers and the tool router still see only the
 * question itself.
 */
function ScanVoice({ card }: { card?: ScanCard }) {
  const [voice, setVoice] = useState<VoiceStatus | null>(null)
  const [phase, setPhase] = useState<'idle' | 'recording' | 'thinking'>('idle')
  const [q, setQ] = useState('')
  const [answer, setAnswer] = useState('')
  const [err, setErr] = useState('')
  const [speaking, setSpeaking] = useState(false)
  const rec = useRef<Recording | null>(null)
  const cardRef = useRef(card); cardRef.current = card
  useEffect(() => { if (micSupported()) voiceStatus().then(setVoice) }, [])
  useEffect(() => () => { rec.current?.cancel(); stopSpeaking() }, [])
  if (!micSupported() || voice?.stt === false) return null

  const finish = async () => {
    const r = rec.current
    if (!r) return
    rec.current = null
    setPhase('thinking')
    try {
      const t = await transcribe(await r.stop())
      if (!t.text || t.text.length < 2) { setErr('Did not catch that - try again a little closer.'); return }
      setQ(t.text)
      const c = cardRef.current
      const history = c ? [{ role: 'user' as const, content: cardContext(c) },
                           { role: 'assistant' as const, content: `Understood - you are looking at ${c.name}.` }] : []
      const a = await api.aiAsk(t.text, history)
      setAnswer(a.answer)
      setSpeaking(true)
      void speak(spokenSummary(a.answer), !!voice?.tts).then(how => { if (how !== 'browser') setSpeaking(false) })
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Voice failed')
    } finally { setPhase('idle') }
  }
  const startRec = async () => {
    if (rec.current || phase === 'thinking') return
    stopSpeaking(); setSpeaking(false); setErr(''); setAnswer('')
    try { rec.current = await Recording.start(() => void finish()); setPhase('recording') }
    catch { setErr('The microphone is blocked - allow it for this site.') }
  }
  return (
    <div className="card p-3 space-y-2">
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => phase === 'recording' ? void finish() : void startRec()} disabled={phase === 'thinking'}
                aria-label={phase === 'recording' ? 'Stop and ask' : 'Ask by voice'}
                className={`grid place-items-center w-12 h-12 rounded-full shrink-0 ${phase === 'recording' ? 'bg-red-600 text-white animate-pulse' : 'bg-accent-500/20 text-accent-200 border border-accent-400/50'}`}>
          {phase === 'recording' ? <Square size={18} /> : <Mic size={20} />}</button>
        <div className="text-[13px] min-w-0">
          <div className="text-white">{phase === 'recording' ? 'Listening… tap again to ask' : phase === 'thinking' ? 'Thinking…'
            : card ? <>Ask about <b>{card.name}</b> or anything in the lab</> : 'Ask anything about the lab by voice'}</div>
          {q && <div className="text-slate-400 truncate">You: {q}</div>}
        </div>
        {speaking && <button className="ml-auto btn-ghost btn-sm" onClick={() => { stopSpeaking(); setSpeaking(false) }}><VolumeX size={13} /> Stop</button>}
      </div>
      {answer && <AiText text={answer} />}
      {err && <p className="text-[12px] text-bad-soft">{err}</p>}
    </div>
  )
}
