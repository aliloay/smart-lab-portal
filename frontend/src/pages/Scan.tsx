/**
 * Live Smart Lab camera ("Scan the lab", 2026-10-26; live overlays + target-aware voice 2026-10-27). Staff only.
 *
 * Layers, never mixed (backend app/services/scan.py + live_target.py):
 *   1. DETECTION   people boxes from the lab's camera-service detector - a generic class
 *   2. IDENTITY    an asset = a printed QR marker "SLAB:<kind>:<key>" decoded ON THE PHONE (its own record key);
 *                  a person = a CLEAR face match of that person's own crop (server-signed ticket, per track).
 *                  No marker / no clear match = unidentified, never guessed from looks or position.
 *   3. LIVE DATA   the authoritative record of THAT key (robot telemetry, bin measurements, readings, door, PC)
 *                  with its age and quality - pinned next to the target in the picture.
 * Voice / typed questions go to ONE target-aware endpoint (/scan/ask) with the resolved target: an explicit tap
 * first, else the only identified target in view, else the last one (20 s); two candidates = it asks which.
 * Speed: nothing queues. One decode, one people request and one face check at a time; the voice path never blocks
 * the camera loop. Stop / hiding the tab / leaving the page releases the camera, mic, loops, worker and requests.
 * No frame and no recording is stored.
 */
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Box, Camera, CameraOff, SwitchCamera, FileVideo, Loader2, Mic, Pause, Play, QrCode, RefreshCw, ScanLine, Send, ShieldAlert, Smartphone,
  Square, Users, Volume2, VolumeX, X } from 'lucide-react'
import { Recording, VoiceStatus, isSpeaking, micSupported, replayLast, speak, spokenSummary, stopSpeaking, transcribe, unlockAudio, voiceStatus } from '../lib/voice'
import { AiText } from '../components/ai'
import { ScanAnswer, ScanCard, api, scanAppearance, scanAsk, scanIdentify, scanPeople } from '../lib/api'
import { Chip } from '../components/ui'
import LiveTargetPanel, { LiveSummary, RobotBars, fmtAge } from '../components/live/LiveTargetPanel'
import { PersonTracker, Track, faceCrop } from '../components/live/tracker'

type Pt = { x: number; y: number }
type Seen = { text: string; corners: Pt[]; at: number; cx: number; cy: number; top: number }
type CardState = { card?: ScanCard; error?: string; fetchedAt: number }
type Target = { kind: 'marker'; code: string } | { kind: 'person'; track: number }
interface BarcodeDetectorLike { detect(src: CanvasImageSource): Promise<{ rawValue: string; cornerPoints: Pt[] }[]> }

const DECODE_EVERY_MS = 120           // ~8 marker checks a second
// Live history (2026-10-28, owner: "a small history of my live detections under the camera"): one line per NEW
// detection (same thing again within 15 s is not repeated), newest first, max 30; kept across Refresh.
type HistItem = { at: number; kind: 'person' | 'marker' | 'look' | 'answer'; text: string; icon?: string }
// one symbol per kind of asset (registry type / look-alike class), owner 2026-10-28
const TYPE_ICON: [RegExp, string][] = [
  [/robot|manipulator/i, '🤖'], [/door/i, '🚪'], [/entry camera/i, '📷'], [/security camera/i, '📹'],
  [/face server/i, '🧠'], [/lab pc/i, '💻'], [/reusable/i, '🧰'], [/consumables/i, '⚖️'],
  [/environment/i, '🌡️'], [/plc|automation/i, '🎛️'], [/access/i, '🔐'], [/dev board/i, '🔌'],
  [/instrument/i, '📟'], [/machine tool|machine|fabrication/i, '⚙️'], [/tool/i, '🔧'], [/vehicle/i, '🚗'],
  [/textile/i, '🧵'],
]
export function iconFor(type: string | undefined | null): string | undefined {
  return type ? TYPE_ICON.find(([rx]) => rx.test(type))?.[1] : undefined
}
const HIST: HistItem[] = []
const histLast = new Map<string, number>()
export function logHistory(kind: HistItem['kind'], key: string, text: string, icon?: string) {
  const now = Date.now()
  if (kind !== 'answer' && now - (histLast.get(key) ?? 0) < 15000) return
  histLast.set(key, now)
  HIST.unshift({ at: now, kind, text, icon })
  if (HIST.length > 30) HIST.length = 30
  window.dispatchEvent(new Event('smartlab:history'))
}
const CARD_REFRESH_MS = 5000          // a card in view is re-read this often (its own timestamp shows age)
const SELECTED_ROBOT_MS = 1000        // the selected robot's joints: once a second (the backend keeps the 50 ms feed)
const SELECTED_OTHER_MS = 3000
const SEEN_HOLD_MS = 1500             // a marker stays pinned this long after the last sighting
const LAST_TARGET_MS = 20000          // "it" may mean the last target for this long when nothing is in view
const W = 640                         // analysis width (decode + people frames)

/** Ask the lab assistant about this asset (the chat bubble listens). */
export const askLab = (q: string) => window.dispatchEvent(new CustomEvent('smartlab:ask-lab', { detail: q }))

export default function Scan() {
  const video = useRef<HTMLVideoElement>(null)
  const overlay = useRef<HTMLCanvasElement>(null)
  const grab = useRef<HTMLCanvasElement | null>(null)
  const cropC = useRef<HTMLCanvasElement | null>(null)
  const session = useRef<{
    stream?: MediaStream; raf?: number; worker?: Worker; native?: BarcodeDetectorLike; decoding: boolean
    lastDecode: number; people?: AbortController; peopleBusy: boolean; fileUrl?: string; stopped: boolean
    face?: AbortController; faceBusy?: boolean; paused?: boolean; peopleBackoff?: number; mirror?: boolean
  }>({ decoding: false, lastDecode: 0, peopleBusy: false, stopped: true })
  const seen = useRef(new Map<string, Seen>())
  const tracker = useRef(new PersonTracker())
  const objects = useRef<{ at: number; list: NonNullable<import('../lib/api').ScanPeople['objects']> } | null>(null)
  const pinEls = useRef(new Map<string, HTMLButtonElement>())
  const [tracks, setTracks] = useState<{ id: number; name: string | null; conflict: boolean; score: number; face: number | null }[]>([])
  const [mirror, setMirror] = useState(false)
  const [running, setRunning] = useState(false)
  const [paused, setPaused] = useState(false)
  const [starting, setStarting] = useState(false)
  const [facing, setFacing] = useState<'environment' | 'user'>('environment')
  const [peopleOn, setPeopleOn] = useState(true)        // owner 2026-10-27: people boxes on by default (button turns them off)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [caption, setCaption] = useState('')
  const [vPhase, setVPhase] = useState('idle')
  useEffect(() => {
    let t = 0
    let raf = 0
    // a plain caption (your question, a notice) shows at once; while the assistant speaks, its current sentence types
    // along with the audio (letters revealed by playback position), like film / video subtitles
    const c = (e: Event) => { cancelAnimationFrame(raf); window.clearTimeout(t); setCaption((e as CustomEvent<string>).detail || '') }
    const chunk = (e: Event) => {
      const d = (e as CustomEvent<{ text: string; audio?: HTMLAudioElement; upto?: number }>).detail
      cancelAnimationFrame(raf); window.clearTimeout(t)
      if (d.upto != null) { setCaption(d.text.slice(0, Math.max(1, d.upto))); return }
      const a = d.audio!
      const tick = () => {
        const dur = isFinite(a.duration) && a.duration > 0 ? a.duration : d.text.length / 14
        const n = Math.min(d.text.length, Math.ceil(d.text.length * Math.min(1, (a.currentTime + 0.15) / dur)))
        setCaption(d.text.slice(0, Math.max(1, n)))
        if (n < d.text.length && !a.paused) raf = requestAnimationFrame(tick)
      }
      tick()
    }
    const end = () => { cancelAnimationFrame(raf); window.clearTimeout(t); t = window.setTimeout(() => setCaption(''), 1800) }
    window.addEventListener('smartlab:speech-chunk', chunk); window.addEventListener('smartlab:speech-done', end)
    const ph = (e: Event) => setVPhase((e as CustomEvent<string>).detail)
    window.addEventListener('smartlab:caption', c)
    window.addEventListener('smartlab:voice-stopped', end); window.addEventListener('smartlab:voice-phase', ph)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('smartlab:speech-chunk', chunk); window.removeEventListener('smartlab:speech-done', end)
      window.removeEventListener('smartlab:caption', c)
      window.removeEventListener('smartlab:voice-stopped', end); window.removeEventListener('smartlab:voice-phase', ph); window.clearTimeout(t) }
  }, [])
  const [source, setSource] = useState<'camera' | 'file'>('camera')
  const [cards, setCards] = useState<Record<string, CardState>>({})
  const [inView, setInView] = useState<string[]>([])
  const inViewRef = useRef(inView)
  inViewRef.current = inView
  const [selected, setSelected] = useState<Target | null>(null)
  const [sessionNo, setSessionNo] = useState(0)
  const [stats, setStats] = useState({ decodeMs: 0, peopleMs: 0, peopleRtt: 0, faceMs: 0, decoder: '' })
  const cardsRef = useRef(cards); cardsRef.current = cards
  const peopleRef = useRef(peopleOn); peopleRef.current = peopleOn
  const selectedRef = useRef(selected); selectedRef.current = selected
  const lastTarget = useRef<{ t: Target; at: number } | null>(null)

  const secure = window.isSecureContext && !!navigator.mediaDevices?.getUserMedia

  const syncTracks = useCallback(() => {
    const v = tracker.current.tracks.map(t => ({ id: t.id, name: t.identity ? `${t.identity.auth_subject} · ${t.identity.name}` : null, conflict: t.conflict,
      score: Math.round((t.box.score ?? 0) * 20) * 5, face: t.identity?.score != null ? Math.round(t.identity.score * 100) : null }))
    setTracks(old => (JSON.stringify(old) === JSON.stringify(v) ? old : v))
    for (const t of v) {
      if (t.name) logHistory('person', 'p:' + t.name, `${t.name.split(' · ')[1] ?? t.name} detected (face ${t.face ?? '?'} %)`, '🙂')
      else logHistory('person', 'person', `Person detected (${t.score} %)`)
    }
  }, [])

  // ------------------------------------------------------------------ stop: releases EVERYTHING
  const stop = useCallback(() => {
    const s = session.current
    s.stopped = true
    if (s.raf) cancelAnimationFrame(s.raf)
    s.people?.abort(); s.face?.abort()
    s.worker?.terminate()
    s.stream?.getTracks().forEach(t => t.stop())
    if (s.fileUrl) URL.revokeObjectURL(s.fileUrl)
    const v = video.current
    if (v) { v.pause(); v.srcObject = null; v.removeAttribute('src'); v.load() }
    session.current = { decoding: false, lastDecode: 0, peopleBusy: false, stopped: true }
    seen.current.clear(); tracker.current.clear(); objects.current = null
    setTracks([]); setRunning(false); setPaused(false); setInView([])
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
      .catch(e => setCards(c => ({ ...c, [code]: { ...c[code], error: e instanceof Error ? e.message : 'unidentified', fetchedAt: Date.now() } })))
  }, [])
  // the selected asset is refreshed on its own clock (robot joints every second), also while paused / out of view
  const selCode = selected?.kind === 'marker' ? selected.code : null
  const selIsRobot = selCode ? cards[selCode]?.card?.live?.type === 'robot' : false
  useEffect(() => {
    if (!selCode) return
    const t = window.setInterval(() => { if (!document.hidden) loadCard(selCode) }, selIsRobot ? SELECTED_ROBOT_MS : SELECTED_OTHER_MS)
    return () => window.clearInterval(t)
  }, [selCode, selIsRobot, loadCard])

  // ------------------------------------------------------------------ who is this: one track's own crop, clear match only
  const checkFace = useCallback(() => {
    const s = session.current, v = video.current
    if (s.faceBusy || s.stopped || !v?.videoWidth) return
    const now = Date.now()
    const sel = selectedRef.current
    const t = tracker.current.nextForFace(now, sel?.kind === 'person' ? sel.track : null)
    if (!t) return
    s.faceBusy = true
    const c = faceCrop(t.raw)
    const cc = cropC.current ?? (cropC.current = document.createElement('canvas'))
    const sx = c.x * v.videoWidth, sy = c.y * v.videoHeight, sw = c.w * v.videoWidth, sh = c.h * v.videoHeight
    const k = Math.min(1, 480 / Math.max(1, sw))
    cc.width = Math.max(1, Math.round(sw * k)); cc.height = Math.max(1, Math.round(sh * k))
    cc.getContext('2d')!.drawImage(v, sx, sy, sw, sh, 0, 0, cc.width, cc.height)
    const id = t.id
    cc.toBlob(async blob => {
      if (!blob || session.current.stopped) { s.faceBusy = false; return }
      const ac = new AbortController(); s.face = ac
      try {
        const r = await scanIdentify(blob, ac.signal)
        if (r && !session.current.stopped) {
          tracker.current.applyFace(id, { known: r.known, ticket: r.ticket, score: r.score, person: r.person }, Date.now())
          setStats(st => ({ ...st, faceMs: Math.round(r.ms) }))
          syncTracks()
        }
      } catch { /* face server down: people stay "person" */ }
      finally { s.faceBusy = false }
    }, 'image/jpeg', 0.85)
  }, [syncTracks])

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
      const corners = f.corners.map(p => ({ x: p.x * sx, y: p.y * sy }))
      const cx = corners.reduce((a, p) => a + p.x, 0) / corners.length, top = Math.min(...corners.map(p => p.y))
      const old = seen.current.get(f.text)
      const a = old && now - old.at < SEEN_HOLD_MS ? 0.5 : 1    // smoothed pin position (no jitter)
      seen.current.set(f.text, { text: f.text, corners, at: now, cx: old ? old.cx + a * (cx - old.cx) : cx,
                                 cy: 0, top: old ? old.top + a * (top - old.top) : top })
      const c = cardsRef.current[f.text]
      if (!c || (now - c.fetchedAt > (c.error ? 2000 : CARD_REFRESH_MS))) loadCard(f.text)   // a failed lookup (e.g. 502 while the portal restarts) retries after 2 s
    }
    const visible = [...seen.current.values()].filter(m => now - m.at < SEEN_HOLD_MS).map(m => m.text).sort()
    setInView(v0 => (v0.join() === visible.join() ? v0 : visible))
    for (const code of visible) logHistory('marker', 'm:' + code, `QR read: ${cardsRef.current[code]?.card?.name ?? code}`, iconFor(cardsRef.current[code]?.card?.type))
    setStats(st => ({ ...st, decodeMs: Math.round(ms) }))
    s.decoding = false
    // people: one request in flight at most, on the same 640-px frame
    if (peopleRef.current && !s.peopleBusy && now >= (s.peopleBackoff ?? 0)) {
      s.peopleBusy = true
      g.toBlob(async blob => {
        if (!blob || session.current.stopped) { s.peopleBusy = false; return }
        const ac = new AbortController(); s.people = ac
        const t1 = performance.now()
        try {
          const r = await scanPeople(blob, ac.signal)
          if (r && !session.current.stopped) {
            tracker.current.update(r.boxes, Date.now())
            setNote(n => (n?.startsWith('People boxes') ? '' : n))
            objects.current = { at: Date.now(), list: r.objects ?? [] }
            syncTracks()
            setStats(st => ({ ...st, peopleMs: r.ms, peopleRtt: Math.round(performance.now() - t1) }))
            if (r.boxes.length) checkFace()
          }
        } catch (e) {
          if (!(e instanceof DOMException && e.name === 'AbortError')) {
            const m = e instanceof Error ? e.message : String(e)
            // 2026-10-27: one failed frame used to switch People boxes OFF for good ("no camera service is running"
            // while both were up) - now it pauses and retries; only the user switches it off
            if (m.includes('unavailable')) { setNote(`People boxes: ${m} - retrying in 5 s`); s.peopleBackoff = Date.now() + 5000 }
            else { setNote(`People boxes paused for 3 s: ${m}`); s.peopleBackoff = Date.now() + 3000 }   // network blip: retry
          }
        } finally { s.peopleBusy = false }
      }, 'image/jpeg', 0.65)
    }
  }, [loadCard, checkFace, syncTracks])

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
      const sel = selectedRef.current
      const mx = (x: number) => (s.mirror ? rect.width - x : x)          // the picture is shown mirrored (selfie view)
      const place = (key: string, x0: number, y: number, show: boolean) => {
        const x = mx(x0)
        const el = pinEls.current.get(key)
        if (!el) return
        el.style.display = show ? '' : 'none'
        if (show) el.style.transform = `translate(${Math.round(Math.max(60, Math.min(rect.width - 60, x)))}px, ${Math.round(Math.max(26, y))}px) translate(-50%, -100%)`
      }
      for (const t of tracker.current.tracks) {
        const b = t.box, x = ox + b.x * pw, y = oy + b.y * ph
        const fresh = now - t.lastSeen < 700
        const isSel = sel?.kind === 'person' && sel.track === t.id
        ctx.lineWidth = isSel ? 3.5 : 2
        ctx.strokeStyle = t.identity ? '#10b981' : t.conflict ? '#f59e0b' : '#38bdf8'
        ctx.globalAlpha = fresh ? 1 : 0.45
        ctx.strokeRect(s.mirror ? mx(x + b.w * pw) : x, y, b.w * pw, b.h * ph)
        ctx.globalAlpha = 1
        place(`p:${t.id}`, x + (b.w * pw) / 2, y - 4, true)
      }
      // the box look-up's frame (2026-10-28, owner: "the message appeared but no frame around the bin"): around the
      // matched points, dashed = unverified, for 5 s after the check
      const ab = apBox.current
      if (ab && now - ab.at < 5000) {
        const x = s.mirror ? mx(ox + (ab.x + ab.w) * pw) : ox + ab.x * pw, y = oy + ab.y * ph
        ctx.save(); ctx.setLineDash([10, 6]); ctx.lineWidth = 3; ctx.strokeStyle = '#38bdf8'; ctx.globalAlpha = 1
        ctx.strokeRect(x, y, ab.w * pw, ab.h * ph); ctx.restore()
      }
      // equipment (generic class): named only when one of OUR markers sits inside its box
      const ob = objects.current
      if (ob && now - ob.at < 1500) for (const o of ob.list) {
        const x = s.mirror ? mx(ox + (o.x + o.w) * pw) : ox + o.x * pw, y = oy + o.y * ph
        const m = [...seen.current.values()].find(mk => now - mk.at <= SEEN_HOLD_MS && mk.cx >= o.x && mk.cx <= o.x + o.w
                                                 && mk.top >= o.y - 0.05 && mk.top <= o.y + o.h)
        const name = m ? cardsRef.current[m.text]?.card?.name : null
        ctx.setLineDash(name ? [] : [6, 4]); ctx.lineWidth = 2; ctx.strokeStyle = name ? '#10b981' : '#94a3b8'
        ctx.strokeRect(x, y, o.w * pw, o.h * ph); ctx.setLineDash([])
        const label = name ? `${o.label} · ${name}` : `${o.label} · unidentified (scan its marker)`
        ctx.font = '600 12px Inter, sans-serif'
        const tw = ctx.measureText(label).width, ly = y + o.h * ph - 6
        ctx.fillStyle = 'rgba(2,6,23,0.75)'; ctx.fillRect(x + 2, ly - 13, tw + 8, 18)
        ctx.fillStyle = name ? '#a7f3d0' : '#cbd5e1'; ctx.fillText(label, x + 6, ly)
      }
      for (const m of seen.current.values()) {
        const vis = now - m.at <= SEEN_HOLD_MS
        if (vis) {
          const card = cardsRef.current[m.text]?.card
          const isSel = sel?.kind === 'marker' && sel.code === m.text
          ctx.lineWidth = isSel ? 4 : 3; ctx.strokeStyle = card ? '#10b981' : '#f59e0b'
          ctx.beginPath()
          m.corners.forEach((p, i) => { const x = mx(ox + p.x * pw), y = oy + p.y * ph; if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y) })
          ctx.closePath(); ctx.stroke()
        }
        place(`m:${m.text}`, ox + m.cx * pw, oy + m.top * ph - 8, vis)
      }
      if (!s.paused && now - s.lastDecode >= DECODE_EVERY_MS) { s.lastDecode = now; void decode(v) }
    }
    s.raf = requestAnimationFrame(draw)
  }, [decode])

  // ------------------------------------------------------------------ start (camera or a recorded test video)
  const begin = useCallback(async (opts: { facingMode?: 'environment' | 'user'; file?: File }) => {
    stop()
    setError(''); setNote(''); setStarting(true)
    const s = { decoding: false, lastDecode: 0, peopleBusy: false, stopped: false } as typeof session.current
    try {
      let v = video.current!
      if (opts.file) {
        s.fileUrl = URL.createObjectURL(opts.file)
        v.srcObject = null; v.src = s.fileUrl; v.loop = true
        setSource('file')
      } else {
        // the back camera, ~720p: enough for a marker across a desk, light enough for a phone
        s.stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: {
          facingMode: { ideal: opts.facingMode ?? facing }, width: { ideal: 1280 }, height: { ideal: 720 } } })
        // iPhone Safari keeps drawing a re-used <video> at the previous stream's size (selfie view small after a
        // switch, 2026-10-28): the stream goes into a FRESH element in the same place every time
        if (v.srcObject) {
          const nv = v.cloneNode(false) as HTMLVideoElement
          nv.muted = true; nv.playsInline = true
          v.replaceWith(nv)
          ;(video as { current: HTMLVideoElement | null }).current = nv
          v = nv
        }
        v.srcObject = s.stream
        setSource('camera')
        const fm = s.stream.getVideoTracks()[0]?.getSettings().facingMode
        s.mirror = fm === 'user' || (!fm && !/Android|iPhone|iPad/i.test(navigator.userAgent))
        v.style.transform = s.mirror ? 'scaleX(-1)' : ''      // the fresh element does not get React's style
      }
      v.muted = true; v.playsInline = true
      await v.play()
      const BD = (window as unknown as { BarcodeDetector?: new (o: { formats: string[] }) => BarcodeDetectorLike }).BarcodeDetector
      if (BD) { try { s.native = new BD({ formats: ['qr_code'] }) } catch { s.native = undefined } }
      if (!s.native) s.worker = new Worker(new URL('../lib/qrWorker.ts', import.meta.url), { type: 'module' })
      setStats(st => ({ ...st, decoder: s.native ? 'native BarcodeDetector' : 'jsQR (worker)' }))
      session.current = s
      setMirror(!!s.mirror)
      setRunning(true); setPaused(false); setSessionNo(n => n + 1)
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

  // "Which box is this?" - one frame against the owner's enclosure photos: a HINT, never an identification
  const [boxHint, setBoxHint0] = useState<string>('')
  const boxAt = useRef(0)
  const apBox = useRef<{ x: number; y: number; w: number; h: number; at: number; cls: string } | null>(null)
  const setBoxHint = (t: string) => { boxAt.current = Date.now(); setBoxHint0(t) }
  // a box verdict is about ONE frame: it fades after 5 s instead of staying on whatever comes next (owner 2026-10-28:
  // "my face - it says looks like the reusable bin" = the bin's verdict still on screen)
  useEffect(() => {
    if (!boxHint) return
    const t = window.setTimeout(() => { if (Date.now() - boxAt.current >= 5000) setBoxHint0('') }, 5100)
    return () => window.clearTimeout(t)
  }, [boxHint])
  const boxBusy = useRef(false)
  const boxQuietUntil = useRef(0)
  const whichBox = (auto = false) => {
    const v = video.current
    if (!v?.videoWidth || boxBusy.current) return
    boxBusy.current = true
    window.setTimeout(() => { boxBusy.current = false }, 2500)
    const g = document.createElement('canvas')
    const w = Math.min(W, v.videoWidth); g.width = w; g.height = Math.round(w * v.videoHeight / v.videoWidth)
    g.getContext('2d')!.drawImage(v, 0, 0, g.width, g.height)
    if (!auto) setBoxHint('Comparing with the enclosure photos…')
    g.toBlob(b => {
      if (!b) return
      scanAppearance(b).then(r => {
        // 2026-10-29: objects that are not registered assets (e.g. the network switch) come as type:<class> + a label
        const name = (code: string) => cardsRef.current[code]?.card?.name ?? (code.startsWith('type:') ? (r.best?.label ?? code.slice(5).replace(/_/g, ' ')) : code)
        if (r.decision === 'PROBABLE' && r.best) logHistory('look', 'a:' + r.best.code,
          `${r.best.class === 'reusable_items_dock' ? 'Reusable bin' : r.best.class.replace(/_/g, ' ')} recognised by its look (${r.best.box_kind === 'detector' ? `detector ${Math.round((r.best.confidence ?? 0) * 100)}%` : `${r.best.inliers} points`}, unverified)`,
          iconFor(r.best.class.replace(/_/g, ' ')))
        apBox.current = r.decision === 'PROBABLE' && r.best?.box ? { ...r.best.box, at: Date.now(), cls: r.best.class } : null
        setBoxHint(r.decision === 'PROBABLE' && r.best ? `Looks like ${name(r.best.code)} (unverified, ${r.best.box_kind === 'detector' ? `detector ${Math.round((r.best.confidence ?? 0) * 100)}% sure` : `${r.best.inliers} matching points`})${r.best.registered === false ? ' - not a registered asset yet, so no live data.' : ' - scan its marker to see its live data.'}`
          : r.decision === 'AMBIGUOUS' ? `Could be ${r.candidates.slice(0, 2).map(c => name(c.code)).join(' or ')} - they look alike. Scan the marker.`
          : `Not recognised${r.note.includes('no reference') ? ' (no enclosure photos yet)' : ''} - scan the marker.`)
      }).catch(e => setBoxHint(e instanceof Error ? e.message : 'Box match failed'))
    }, 'image/jpeg', 0.85)
  }
  // 2026-10-28 (owner: "it did not detect it - only the QR"): the box check also runs by itself every 3 s while no
  // marker is in view, so a sharp frame gets its chance; still a hint only - live data needs the marker
  // (the timer used to be re-created on every render - it never fired; the latest whichBox is read through a ref)
  const whichBoxRef = useRef(whichBox)
  whichBoxRef.current = whichBox
  useEffect(() => {
    if (!running || paused) return
    const t = window.setInterval(() => { if (!document.hidden && inViewRef.current.length === 0 && Date.now() > boxQuietUntil.current) whichBoxRef.current(true) }, 3000)
    return () => window.clearInterval(t)
  }, [running, paused])
  // 2026-10-28 (owner: "a refresh button - after it detects something and speaks, refresh so I can walk on faster"):
  // forget the selection, the last target, the box verdict and the tracks, stop speaking, then look again at once
  // Refresh = a clean restart, exactly as pressing Stop then Start camera (owner 2026-10-28: "as if I have just
  // started the camera"): speech stops, every frame / verdict / track / selection is gone, a new camera session starts
  // with the same camera (the voice panel starts fresh too - it is keyed by the session)
  const refreshView = () => {
    stopSpeaking()
    select(null); lastTarget.current = null
    apBox.current = null; setBoxHint0(''); boxBusy.current = false; setNote('')
    tracker.current.clear(); seen.current.clear(); objects.current = null; setInView([]); setTracks([])
    setSessionNo(n => n + 1)                       // the voice panel starts fresh
    // the camera keeps running (restarting it made iPhone draw the selfie view small) - just make sure it is live
    const v = video.current
    if (v && !session.current.paused) void v.play().catch(() => {})
  }


  // 2026-10-28 (owner: "after it detects the bin and speaks, the picture stays stuck on the bin while I move the
  // phone"): iPhone Safari pauses the live camera <video> when the spoken answer starts playing. A watchdog resumes it
  // whenever it is stopped (or its picture stops advancing) without the user pressing Pause; Refresh forces it too.
  useEffect(() => {
    if (!running) return
    const v = video.current
    if (!v) return
    let lastT = -1, still = 0
    const kick = () => {
      if (session.current.paused || session.current.stopped || document.hidden || isSpeaking()) return
      if (v.paused || v.ended) { void v.play().catch(() => {}); return }
      if (v.srcObject && v.currentTime === lastT) {          // frozen frame although "playing"
        if (++still >= 2) { still = 0; void v.play().catch(() => {}) }
      } else still = 0
      lastT = v.currentTime
    }
    const onPause = () => { if (!session.current.paused) window.setTimeout(kick, 50) }
    v.addEventListener('pause', onPause)
    const t = window.setInterval(kick, 700)
    const afterSpeech = () => window.setTimeout(() => { if (!session.current.paused && v.paused) void v.play().catch(() => {}) }, 150)
    window.addEventListener('smartlab:voice-ended', afterSpeech)
    return () => { window.clearInterval(t); v.removeEventListener('pause', onPause); window.removeEventListener('smartlab:voice-ended', afterSpeech) }
  }, [running])
  // 2026-10-28 (owner: "when switching the camera it is not filled"): iPhone Safari keeps drawing a new camera stream
  // at the old element size. On every new size / stream the element is laid out again (one frame of 99.9 % width).
  useEffect(() => {
    const v = video.current
    if (!v) return
    const relayout = () => { v.style.width = '99.9%'; requestAnimationFrame(() => requestAnimationFrame(() => { v.style.width = '' })) }
    v.addEventListener('loadedmetadata', relayout); v.addEventListener('resize', relayout); v.addEventListener('playing', relayout)
    return () => { v.removeEventListener('loadedmetadata', relayout); v.removeEventListener('resize', relayout); v.removeEventListener('playing', relayout) }
  }, [])
  const togglePause = () => {
    const s = session.current, v = video.current
    if (!running || !v) return
    s.paused = !s.paused
    if (s.paused) v.pause(); else void v.play()
    setPaused(!!s.paused)
  }
  const flip = () => { const f = facing === 'environment' ? 'user' : 'environment'; setFacing(f); select(null); lastTarget.current = null; if (running && source === 'camera') void begin({ facingMode: f }) }

  // ------------------------------------------------------------------ targets
  const select = (t: Target | null) => { setSelected(t); if (t) { lastTarget.current = { t, at: Date.now() }; if (t.kind === 'marker') loadCard(t.code) } }
  const tapVideo = (e: React.MouseEvent) => {                 // tapping inside a person box selects that person
    const v = video.current
    if (!v?.videoWidth) return
    const r = v.getBoundingClientRect()
    const k = Math.min(r.width / v.videoWidth, r.height / v.videoHeight)
    const pw = v.videoWidth * k, ph = v.videoHeight * k
    const x0 = (e.clientX - r.left - (r.width - pw) / 2) / pw, y = (e.clientY - r.top - (r.height - ph) / 2) / ph
    const x = session.current.mirror ? 1 - x0 : x0
    const hit = tracker.current.tracks.filter(t => x >= t.box.x && x <= t.box.x + t.box.w && y >= t.box.y && y <= t.box.y + t.box.h)
      .sort((a, b) => a.box.w * a.box.h - b.box.w * b.box.h)[0]
    if (hit) select({ kind: 'person', track: hit.id })
  }
  const trackById = (id: number): Track | undefined => tracker.current.tracks.find(t => t.id === id)
  const label = (t: Target): string => t.kind === 'marker' ? (cards[t.code]?.card?.name ?? t.code)
    : (trackById(t.track)?.identity?.name ?? `person #${t.track}`)

  /** The target a question is about - fixed at the moment it is asked. */
  const resolveTarget = (): { code?: string; ticket?: string; label: string } | { ambiguous: string[] } | { none: string } => {
    const now = Date.now()
    const asTarget = (t: Target) => {
      if (t.kind === 'marker') return cards[t.code]?.card ? { code: t.code, label: label(t) } : null
      const tr = trackById(t.track)
      return tr?.identity ? { ticket: tr.identity.ticket, label: `${tr.identity.auth_subject} ${tr.identity.name}` } : null
    }
    const sel = selectedRef.current
    if (sel) {
      const r = asTarget(sel)
      if (r) { lastTarget.current = { t: sel, at: now }; return r }
      // 2026-10-28 (owner: back camera on the bin's QR, but every answer was about "person #5"): a selected person
      // who has left the picture no longer blocks the target that IS in view
      const gone = sel.kind === 'person' && !(trackById(sel.track) && now - trackById(sel.track)!.lastSeen < 1500)
      if (gone) { setSelected(null); selectedRef.current = null }
      else if (sel.kind === 'person') return { none: 'The selected person is not identified (no clear face match) - nothing about them can be looked up.' }
    }
    const cands: Target[] = [
      ...inView.filter(c => cards[c]?.card).map(c => ({ kind: 'marker' as const, code: c })),
      ...tracker.current.tracks.filter(t => t.identity && now - t.lastSeen < 1500).map(t => ({ kind: 'person' as const, track: t.id })),
    ]
    if (cands.length === 1) { lastTarget.current = { t: cands[0], at: now }; return asTarget(cands[0])! }
    if (cands.length > 1) return { ambiguous: cands.map(label) }
    if (lastTarget.current && now - lastTarget.current.at < LAST_TARGET_MS) {
      const r = asTarget(lastTarget.current.t)
      if (r) return r
    }
    // no marker, but the box look-up saw a known enclosure in the last 5 s (2026-10-28, owner: "Tell me more" said
    // "nothing identified" under "looks like the reusable bin"): a CLASS-level answer - no asset ID, no live data
    // (docs/VISUAL_AI_PLAN.md, identity rule 3)
    const ab = apBox.current
    if (ab && now - ab.at < 5000) {
      const what = ab.cls === 'reusable_items_dock' ? 'the reusable items bin (the NFC check-out / return station)'
        : ab.cls.replace(/_/g, ' ')
      return { none: `This looks like ${what} - recognised from its appearance only, not confirmed. Scan its QR marker to see its live data (what is checked out and what is available).` }
    }
    return { none: '' }
  }

  // pins: one per marker in view and per tracked person (positions are set by draw(), not by React)
  const pins = useMemo(() => [
    ...inView.map(code => ({ key: `m:${code}`, t: { kind: 'marker', code } as Target, card: cards[code]?.card, err: cards[code]?.error })),
    ...tracks.map(t => ({ key: `p:${t.id}`, t: { kind: 'person', track: t.id } as Target, name: t.name, conflict: t.conflict, score: t.score, face: t.face })),
  ], [inView, tracks, cards])
  const isSel = (t: Target) => !!selected && (selected.kind === t.kind && (t.kind === 'marker' ? (selected as { code: string }).code === t.code
    : (selected as { track: number }).track === (t as { track: number }).track))
  const selCard = selected?.kind === 'marker' ? cards[selected.code]?.card ?? null : null
  const selPerson = selected?.kind === 'person' ? trackById(selected.track)?.identity?.person ?? null : null
  // the panel below the picture: the selection, else the only target in view
  const autoCard = !selected && inView.length === 1 ? cards[inView[0]]?.card ?? null : null
  const namedTracks = tracks.filter(t => t.name)
  const autoPerson = !selected && namedTracks.length === 1 ? trackById(namedTracks[0].id)?.identity?.person ?? null : null

  return (
    <div className="space-y-3 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 flex-wrap">
        <ScanLine className="text-accent-300" size={20} />
        <h1 className="text-[18px] font-semibold text-white">Live Smart Lab camera</h1>
        <span className="text-[12px] text-slate-400">Point at a marker or a person - the live record appears on it. Tap to select, then ask.</span>
        <Link to="/scan/markers" className="ml-auto btn-ghost btn-sm"><QrCode size={14} /> Markers</Link>
        <Link to="/phone-setup" className="btn-ghost btn-sm"><Smartphone size={14} /> Phone setup</Link>
      </div>

      {!secure && <div className="rounded-xl border border-warn/40 bg-warn/5 p-3 text-[13px] text-warn-soft flex gap-2">
        <ShieldAlert size={16} className="shrink-0 mt-0.5" />
        <span>The camera needs a secure page (https://). Open the portal with <b>https://</b> on this device -
          <Link to="/phone-setup" className="underline ml-1">set up this phone</Link>. A recorded test video still works below.</span></div>}

      <div className="relative rounded-xl overflow-hidden bg-black h-[78vh] sm:h-auto sm:aspect-video select-none" onClick={tapVideo}>
        <video ref={video} className="absolute inset-0 w-full h-full object-contain" style={mirror ? { transform: 'scaleX(-1)' } : undefined} muted playsInline />
        <canvas ref={overlay} className="absolute inset-0 w-full h-full pointer-events-none" />
        {/* pinned live chips - positioned every frame by draw() */}
        {running && pins.map(p => (
          <button key={p.key} ref={el => { if (el) pinEls.current.set(p.key, el); else pinEls.current.delete(p.key) }}
                  type="button" onClick={e => { e.stopPropagation(); select(isSel(p.t) ? null : p.t) }}
                  style={{ display: 'none' }}
                  className={`absolute left-0 top-0 max-w-[220px] rounded-lg border px-2 py-1 text-left text-[11.5px] leading-tight shadow-lg backdrop-blur
                    ${isSel(p.t) ? 'border-white bg-ink-900/90 ring-2 ring-accent-400/70' : 'border-ink-500/70 bg-ink-950/75'}`}>
            {'card' in p ? (p.card
              ? <><span className="block font-semibold text-white truncate">{p.card.name}</span>
                  <span className="block text-slate-300 truncate">{p.card.live ? <LiveSummary live={p.card.live} /> : p.card.status.toLowerCase()}</span>
                  {p.card.live?.type === 'robot' && isSel(p.t) && <div className="mt-1 w-[200px]"><RobotBars live={p.card.live} compact /></div>}</>
              : <span className="text-amber-200">{p.err ? 'unidentified marker' : 'looking up…'}</span>)
              : <span className={p.name ? 'font-semibold text-emerald-200' : p.conflict ? 'text-amber-200' : 'text-sky-200'}>
                  {p.name ? `${p.name} · face ${p.face ?? '?'}%` : `${p.conflict ? 'person · identity unclear' : 'person'} ${p.score}%`}
                  {!p.name && !p.conflict && <span className="block text-[10px] font-normal text-slate-400">checking face…</span>}</span>}
          </button>))}
        {!running && <div className="absolute inset-0 grid place-items-center text-slate-400 text-[13px]">
          {starting ? 'Starting the camera…' : 'Camera off'}</div>}
        {running && paused && <span className="absolute top-2 left-2"><Chip tone="warn">PAUSED</Chip></span>}
        {running && source === 'file' && <span className="absolute top-2 left-2"><Chip tone="warn">RECORDED TEST VIDEO</Chip></span>}
        {/* 2026-10-28 (owner: "the Tell me more button should be higher - I scroll down to press it"): the voice
            controls float on the picture itself, so the target stays in view while asking */}
        {running && boxHint.startsWith('Looks like') && inView.length === 0 &&
          <span className="absolute top-2 left-1/2 -translate-x-1/2 max-w-[90%] rounded-lg bg-sky-900/85 border border-sky-400/50 px-2.5 py-1 text-[12px] text-sky-100 text-center">{boxHint}</span>}
        {/* 2026-10-28 (owner): glass controls ON the live picture + a centred glass caption with who is speaking */}
        {running && (caption || vPhase !== 'idle') && <div className="absolute bottom-[76px] inset-x-3 flex justify-center pointer-events-none">
          <div className="max-w-[92%] rounded-2xl border border-white/25 bg-white/10 px-4 py-2.5 text-center shadow-xl"
               style={{ WebkitBackdropFilter: 'blur(8px)', backdropFilter: 'blur(8px)', background: 'rgba(15,23,42,.55)' }}>
            {vPhase === 'recording' ? <span className="text-[15px] font-bold text-white">🎙️ Listening… tap the mic again to ask</span>
              : vPhase === 'transcribing' ? <span className="text-[15px] font-bold text-white">Turning your voice into text…</span>
              : vPhase === 'thinking' ? <span className="text-[15px] font-bold text-white">Lab assistant is looking it up…</span>
              : <>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-sky-200">{caption.startsWith('You: ') ? 'You' : 'Lab assistant'}</div>
                  <div className="text-[15px] font-bold leading-snug text-white">{caption.replace(/^You: /, '')}</div>
                </>}
          </div></div>}
        {running && <div className="absolute top-2 right-2 flex flex-col gap-2">
          <button type="button" aria-label={`Switch to ${facing === 'environment' ? 'front' : 'back'} camera`} title={`Switch to ${facing === 'environment' ? 'front' : 'back'} camera`}
                  className="glass-btn" onClick={flip}><SwitchCamera size={18} /></button>
          <button type="button" aria-label={paused ? 'Resume' : 'Pause'} className="glass-btn" onClick={togglePause}>{paused ? <Play size={18} /> : <Pause size={18} />}</button>
          <button type="button" aria-label="Which box is this?" title="Which box is this?" className="glass-btn" onClick={() => whichBox()}><Box size={18} /></button>
          <button type="button" aria-label="Stop camera" className="glass-btn !text-red-300" onClick={stop}><CameraOff size={18} /></button>
        </div>}
        {running && <div className="absolute bottom-3 inset-x-2 flex justify-center items-center gap-3 pointer-events-none">
          <button type="button" aria-label="Refresh - start fresh" title="Refresh: start fresh"
                  className="glass-btn pointer-events-auto" onClick={refreshView}><RefreshCw size={18} /></button>
          <button type="button" className="glass-btn pointer-events-auto !w-auto !px-5 font-bold"
                  onClick={() => { unlockAudio(); window.dispatchEvent(new Event('smartlab:tell-more')) }}>Tell me more</button>
          <button type="button" aria-label="Ask by voice"
                  className={`glass-btn pointer-events-auto ${vPhase === 'recording' ? '!bg-red-600/80 animate-pulse' : ''}`}
                  onClick={() => { unlockAudio(); window.dispatchEvent(new Event('smartlab:mic')) }}><Mic size={18} /></button>
        </div>}
      </div>

      <div className="flex flex-wrap gap-2">
        {running
          ? <button className="inline-flex items-center gap-2 rounded-xl px-4 py-2 font-semibold text-white bg-red-600 hover:bg-red-500"
                    onClick={stop}><CameraOff size={15} /> Stop</button>
          : <button className="btn-primary" disabled={!secure || starting} onClick={() => begin({})}><Camera size={15} /> Start camera</button>}
        {running && <button className="btn-ghost" onClick={togglePause}>{paused ? <><Play size={15} /> Resume</> : <><Pause size={15} /> Pause</>}</button>}
        <button className="btn-ghost" disabled={!secure || starting} onClick={flip} title={`Now: ${facing === 'environment' ? 'back' : 'front'} camera`}><RefreshCw size={15} /> Switch to {facing === 'environment' ? 'front' : 'back'} camera</button>
        <button className={`btn-ghost ${peopleOn ? 'border border-sky-400/60 text-sky-200' : ''}`} onClick={() => { setNote(''); setPeopleOn(p => !p) }}>
          <Users size={15} /> People {peopleOn ? 'on' : 'off'}</button>
        {running && <button className="btn-ghost" onClick={() => whichBox()}><Box size={15} /> Which box is this?</button>}
        <label className="btn-ghost cursor-pointer"><FileVideo size={15} /> Test video
          <input type="file" accept="video/*" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) void begin({ file: f }); e.target.value = '' }} /></label>
      </div>
      {error && <p className="text-[12.5px] text-bad-soft">{error}</p>}
      {note && <p className="text-[12px] text-warn-soft">{note}</p>}
      {boxHint && <p className="text-[12.5px] text-sky-200">{boxHint}</p>}
      {running && <p className="text-[11px] text-slate-500">Markers: {stats.decoder}, {stats.decodeMs} ms per check
        {peopleOn && ` · people: detector ${stats.peopleMs} ms, round trip ${stats.peopleRtt} ms · face check ${stats.faceMs} ms`}
        {' '}- a person is named only on a clear face match of their own box; anything less stays "person".</p>}

      {pins.length > 1 && <div className="flex flex-wrap gap-1.5 items-center">
        <span className="text-[12px] text-slate-400">In view:</span>
        {pins.map(p => <button key={p.key} onClick={() => select(isSel(p.t) ? null : p.t)}
          className={`text-[12px] px-2 py-1 rounded-md border ${isSel(p.t) ? 'border-accent-400 text-white bg-accent-500/15' : 'border-ink-600 text-slate-400'}`}>
          {label(p.t)}</button>)}
        {selected && <button className="text-[12px] text-slate-400 inline-flex items-center gap-1" onClick={() => select(null)}><X size={12} /> clear</button>}
      </div>}

      <LiveHistory />
      <LiveVoice key={sessionNo} resolve={resolveTarget} />

      {(selPerson || autoPerson) && <LiveTargetPanel person={selPerson ?? autoPerson} />}
      {(selCard || autoCard) && <LiveTargetPanel card={selCard ?? autoCard} />}
      {selected?.kind === 'person' && !selPerson && <div className="card p-3 text-[13px] text-slate-400">
        Person #{selected.track}: not identified - no clear face match yet (or the face is not visible). Nothing is shown about them.</div>}
      {!selected && !autoCard && running && !inView.length && <p className="text-[12.5px] text-slate-500">No marker in view. Unmarked
        equipment stays unidentified - the camera never guesses which device it is from its look.</p>}
    </div>
  )
}

/**
 * Voice and typed questions about what the camera shows (owner 2026-10-27). Push to talk -> the lab's local speech
 * service -> the transcript (editable, re-send to correct a mishearing) -> /scan/ask with the target resolved at
 * that moment -> the answer on screen and spoken by the local voice (mutable). The conversation is this camera
 * session's only; nothing is recorded in the background; Cancel stops the request and the speech.
 */
function LiveVoice({ resolve }: { resolve: () => { code?: string; ticket?: string; label: string } | { ambiguous: string[] } | { none: string } }) {
  const [voice, setVoice] = useState<VoiceStatus | null>(null)
  const [phase, setPhase] = useState<'idle' | 'recording' | 'transcribing' | 'thinking'>('idle')
  const [q, setQ] = useState('')
  const [turns, setTurns] = useState<{ q: string; a: string; target: string | null; ms?: number; intent?: string; sources?: ScanAnswer['sources']; err?: boolean }[]>([])
  const [muted, setMuted] = useState(() => { try { return localStorage.getItem('smartlab.liveMute') === '1' } catch { return false } })
  const [speaking, setSpeaking] = useState(false)
  const [blocked, setBlocked] = useState(false)
  const rec = useRef<Recording | null>(null)
  const ac = useRef<AbortController | null>(null)
  const end = useRef<HTMLDivElement>(null)
  // the spoken answers need only the server voice, not a microphone: the status is read on every device (2026-10-27:
  // on the iPhone it was read only when recording was possible, so answers fell to the browser voice = silence)
  useEffect(() => { voiceStatus().then(setVoice).catch(() => setVoice(null)) }, [])
  const [spokeWith, setSpokeWith] = useState<string | null>(null)
  useEffect(() => () => { rec.current?.cancel(); ac.current?.abort(); stopSpeaking() }, [])
  // no page scroll on a new answer (owner 2026-10-28: "keep seeing the live screen"); the caption shows it on the picture
  // the floating buttons on the camera picture (2026-10-28) drive the same actions as the buttons below
  const askRef = useRef<(q: string) => void>(() => {})
  const micRef = useRef<() => void>(() => {})
  useEffect(() => {
    const t = () => askRef.current('Tell me more'), m = () => micRef.current()
    window.addEventListener('smartlab:tell-more', t); window.addEventListener('smartlab:mic', m)
    return () => { window.removeEventListener('smartlab:tell-more', t); window.removeEventListener('smartlab:mic', m) }
  }, [])
  useEffect(() => {
    const st = () => setSpeaking(false)                // stopped from elsewhere (Refresh): not "Speaking..." any more
    window.addEventListener('smartlab:voice-stopped', st)
    return () => window.removeEventListener('smartlab:voice-stopped', st)
  }, [])
  useEffect(() => {
    const b = () => { setBlocked(true); setSpeaking(false) }
    window.addEventListener('smartlab:audio-blocked', b)
    return () => window.removeEventListener('smartlab:audio-blocked', b)
  }, [])
  const mic = micSupported() && voice?.stt !== false

  const say = (text: string) => {
    if (muted) { window.dispatchEvent(new CustomEvent('smartlab:caption', { detail: spokenSummary(text) }))
      window.setTimeout(() => window.dispatchEvent(new Event('smartlab:speech-done')), 4000); return }
    setBlocked(false); setSpeaking(true)
    // status not known yet -> still try the lab's voice first (it falls back to the browser voice by itself)
    void speak(spokenSummary(text), voice ? !!voice.tts : true).then(how => {
      setSpokeWith(how === 'piper' ? 'lab voice (Piper)' : how === 'browser' ? 'browser voice' : 'no voice')
      if (how !== 'browser') setSpeaking(false)
    })
  }
  const ask = async (question: string) => {
    const text = question.trim()
    if (text.length < 2 || phase === 'thinking') return
    stopSpeaking(); setSpeaking(false)
    const t = resolve()
    if ('ambiguous' in t) {
      const a = `I can see ${t.ambiguous.join(' and ')}. Tap the one you mean, then ask again.`
      setTurns(ts => [...ts, { q: text, a, target: null }]); say(a); return
    }
    if ('none' in t && t.none) { setTurns(ts => [...ts, { q: text, a: t.none, target: null }]); say(t.none); return }
    setPhase('thinking')
    const c = new AbortController(); ac.current = c
    const history = turns.slice(-3).flatMap(x => [{ role: 'user' as const, content: x.q }, { role: 'assistant' as const, content: x.a }])
    try {
      const r = await scanAsk(text, 'code' in t || 'ticket' in t ? { code: (t as { code?: string }).code, ticket: (t as { ticket?: string }).ticket } : {},
                              history, c.signal)
      setTurns(ts => [...ts, { q: text, a: r.answer, target: 'label' in t ? t.label : null, ms: r.ms, intent: r.intent, sources: r.sources }])
      logHistory('answer', 'q', `${text} → ${r.answer.replace(/\s+/g, ' ').slice(0, 140)}${r.answer.length > 140 ? '…' : ''}`)
      say(r.answer)
    } catch (e) {
      if (!c.signal.aborted) setTurns(ts => [...ts, { q: text, a: e instanceof Error ? e.message : 'The question failed', target: null, err: true }])
    } finally { setPhase('idle'); ac.current = null }
  }
  const finishRec = async () => {
    const r = rec.current
    if (!r) return
    rec.current = null
    setPhase('transcribing')
    try {
      const t = await transcribe(await r.stop())
      setPhase('idle')
      if (!t.text || t.text.trim().length < 2) { setTurns(ts => [...ts, { q: '…', a: 'Did not catch that - try again a little closer.', target: null, err: true }]); return }
      setQ(t.text.trim())
      window.dispatchEvent(new CustomEvent('smartlab:caption', { detail: 'You: ' + t.text.trim() }))
      await ask(t.text)
    } catch (e) {
      setPhase('idle')
      setTurns(ts => [...ts, { q: '…', a: e instanceof Error ? e.message : 'Speech service unavailable', target: null, err: true }])
    }
  }
  const startRec = async () => {
    if (rec.current || phase !== 'idle') return
    stopSpeaking(); setSpeaking(false)
    try { rec.current = await Recording.start(() => void finishRec()); setPhase('recording') }
    catch {
      setTurns(ts => [...ts, { q: '…', a: 'The microphone is blocked - allow it for this site.', target: null, err: true }])
      window.dispatchEvent(new CustomEvent('smartlab:caption', { detail: 'The microphone is blocked - allow it for this site (aA → Website settings → Microphone).' }))
    }
  }
  const cancel = () => { rec.current?.cancel(); rec.current = null; ac.current?.abort(); stopSpeaking(); setSpeaking(false); setPhase('idle') }
  const submit = (e: FormEvent) => { e.preventDefault(); unlockAudio(); void ask(q) }
  askRef.current = q => { if (phase === 'idle') void ask(q) }
  micRef.current = () => {
    if (phase === 'recording') { void finishRec(); return }
    if (!mic) { window.dispatchEvent(new CustomEvent('smartlab:caption', { detail: 'Voice input is not available in this browser - type the question below.' })); return }
    if (phase === 'idle') void startRec()
  }
  useEffect(() => { window.dispatchEvent(new CustomEvent('smartlab:voice-phase', { detail: phase })) }, [phase])
  const status = phase === 'recording' ? 'Listening… tap again to ask' : phase === 'transcribing' ? 'Transcribing (local)…'
    : phase === 'thinking' ? 'Looking it up…' : speaking ? 'Speaking…'
    : muted ? 'Spoken answers are OFF - tap the speaker to turn them on'
    : spokeWith ? `Ask about what the camera shows · last answer spoken with the ${spokeWith}` : 'Ask about what the camera shows'

  return (
    <div className="card p-3 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        {mic && <button type="button" onClick={() => { unlockAudio(); if (phase === 'recording') void finishRec(); else void startRec() }}
                disabled={phase === 'transcribing' || phase === 'thinking'}
                aria-label={phase === 'recording' ? 'Stop and ask' : 'Ask by voice'}
                className={`grid place-items-center w-12 h-12 rounded-full shrink-0 ${phase === 'recording' ? 'bg-red-600 text-white animate-pulse' : 'bg-accent-500/20 text-accent-200 border border-accent-400/50'}`}>
          {phase === 'recording' ? <Square size={18} /> : phase === 'transcribing' || phase === 'thinking' ? <Loader2 size={20} className="animate-spin" /> : <Mic size={20} />}</button>}
        <div className="text-[13px] text-white mr-auto">{status}</div>
        <button type="button" className="btn-ghost btn-sm" disabled={phase !== 'idle'} onClick={() => { unlockAudio(); void ask('Tell me more') }}>Tell me more</button>
        {blocked && <button type="button" className="btn-primary btn-sm" onClick={() => { setBlocked(false); setSpeaking(true); void replayLast().finally(() => setSpeaking(false)) }}>
          <Volume2 size={14} /> Play answer</button>}
        <button type="button" className="btn-ghost btn-sm" aria-pressed={muted} title={muted ? 'Spoken answers off' : 'Spoken answers on'}
                onClick={() => { const m = !muted; setMuted(m); if (m) { stopSpeaking(); setSpeaking(false) } try { localStorage.setItem('smartlab.liveMute', m ? '1' : '0') } catch { /* private */ } }}>
          {muted ? <VolumeX size={14} /> : <Volume2 size={14} />}</button>
        {(phase !== 'idle' || speaking) && <button type="button" className="btn-ghost btn-sm" onClick={cancel}><X size={14} /> Cancel</button>}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input className="input flex-1" value={q} onChange={e => setQ(e.target.value)} maxLength={500}
               placeholder='e.g. "Tell me more", "What is joint 3 doing?", "How much is left?", "Who is this?"' />
        <button className="btn-primary" disabled={q.trim().length < 2 || phase === 'thinking'} aria-label="Ask"><Send size={15} /></button>
      </form>
      {turns.length > 0 && <div className="max-h-72 overflow-y-auto space-y-2.5 pr-1">
        {turns.map((t, i) => <div key={i} className="space-y-1">
          <div className="text-[12.5px] text-slate-400">You: <span className="text-slate-200">{t.q}</span>
            {t.target && <span className="text-slate-500"> · about {t.target}</span>}</div>
          <div className={t.err ? 'text-[13px] text-warn-soft' : ''}>{t.err ? t.a : <AiText text={t.a} />}</div>
          {(t.ms != null || t.sources?.length) && <div className="text-[10.5px] text-slate-500">
            {t.intent === 'model' ? 'local AI with the live record as context' : t.intent ? `from the live record (${t.intent})` : ''}
            {t.ms != null ? ` · ${(t.ms / 1000).toFixed(2)} s` : ''}
            {t.sources?.map((s, j) => <span key={j}> · {s.label}: {s.quality}{s.at ? ` @ ${new Date(s.at).toLocaleTimeString()}` : ''}</span>)}</div>}
        </div>)}
        <div ref={end} />
      </div>}
    </div>
  )
}

export { fmtAge }


function LiveHistory() {
  const [, force] = useState(0)
  useEffect(() => {
    const f = () => force(n => n + 1)
    window.addEventListener('smartlab:history', f)
    return () => window.removeEventListener('smartlab:history', f)
  }, [])
  if (!HIST.length) return null
  const icon = { person: '🧍', marker: '🔳', look: '📦', answer: '🔊' } as const
  return (
    <div className="card p-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-[13px] font-semibold text-white">Live history</div>
        <button type="button" className="text-[11.5px] text-slate-400 hover:text-white"
                onClick={() => { HIST.length = 0; histLast.clear(); force(n => n + 1) }}>Clear</button>
      </div>
      <ul className="space-y-1 max-h-56 overflow-y-auto">
        {HIST.map((h, i) => (
          <li key={h.at + ':' + i} className="text-[12.5px] text-slate-200 flex gap-2">
            <span className="tnum text-slate-500 shrink-0">{new Date(h.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            <span aria-hidden>{h.icon ?? icon[h.kind]}</span><span className="min-w-0">{h.text}</span>
          </li>))}
      </ul>
    </div>)
}
