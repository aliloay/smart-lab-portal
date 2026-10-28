/**
 * Voice for the assistant (2026-10-26): push-to-talk recording -> local Whisper (via /api/voice/transcribe) -> the
 * normal question path; short spoken answers from local Piper (/api/voice/speak), else the browser's own voice.
 * Nothing is stored. The microphone is opened only while recording and released at once (tracks stopped).
 */
import { getToken } from './api'

export const MAX_RECORD_MS = 30000

export interface VoiceStatus { stt: boolean; tts: boolean; model?: string; voice?: string; reason?: string }

const auth = (): Record<string, string> => { const t = getToken(); return t ? { Authorization: `Bearer ${t}` } : {} }

export async function voiceStatus(): Promise<VoiceStatus> {
  try {
    const r = await fetch('/api/voice/status', { headers: auth(), cache: 'no-store' })
    return r.ok ? r.json() : { stt: false, tts: false }
  } catch { return { stt: false, tts: false } }
}

export function micSupported(): boolean {
  return typeof window !== 'undefined' && window.isSecureContext && !!navigator.mediaDevices?.getUserMedia
    && typeof MediaRecorder !== 'undefined'
}

function pickMime(): string {
  for (const m of ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4', 'audio/webm']) {
    if (MediaRecorder.isTypeSupported?.(m)) return m
  }
  return ''
}

/** One recording. stop() resolves with the audio; cancel() throws it away. The mic is released either way. */
export class Recording {
  private rec: MediaRecorder
  private chunks: Blob[] = []
  private done: Promise<Blob>
  private timer: number
  readonly started = Date.now()

  private constructor(private stream: MediaStream, onAutoStop: () => void) {
    const mime = pickMime()
    this.rec = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 32000 } : undefined)
    this.rec.ondataavailable = e => { if (e.data.size) this.chunks.push(e.data) }
    this.done = new Promise(res => { this.rec.onstop = () => res(new Blob(this.chunks, { type: this.rec.mimeType || mime })) })
    this.rec.start(250)
    this.timer = window.setTimeout(onAutoStop, MAX_RECORD_MS)
  }

  static async start(onAutoStop: () => void): Promise<Recording> {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
    return new Recording(stream, onAutoStop)
  }

  private release() {
    window.clearTimeout(this.timer)
    this.stream.getTracks().forEach(t => t.stop())
  }

  async stop(): Promise<Blob> {
    if (this.rec.state !== 'inactive') this.rec.stop()
    const b = await this.done
    this.release()
    return b
  }

  cancel() {
    try { if (this.rec.state !== 'inactive') this.rec.stop() } catch { /* already stopped */ }
    this.release()
  }
}

export async function transcribe(audio: Blob, signal?: AbortSignal): Promise<{ text: string; ms: number; audio_s: number }> {
  const r = await fetch('/api/voice/transcribe', {
    method: 'POST', body: audio, signal, cache: 'no-store',
    headers: { 'Content-Type': audio.type || 'application/octet-stream', ...auth() },
  })
  if (!r.ok) {
    let msg = `Voice failed (${r.status})`
    try { msg = (await r.json()).detail ?? msg } catch { /* not json */ }
    throw new Error(msg)
  }
  return r.json()
}

/** Markdown answer -> the first few sentences, as plain speech (figures stay, formatting goes). */
export function spokenSummary(answer: string, maxChars = 320): string {
  const plain = answer.replace(/\*\*/g, '').replace(/^#+\s*/gm, '').replace(/^\s*([-*•]|\d+[.)])\s+/gm, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/[`_>|]/g, ' ').replace(/\s+/g, ' ').trim()
  if (plain.length <= maxChars) return plain
  const cut = plain.slice(0, maxChars)
  const end = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf('? '), cut.lastIndexOf('! '))
  return (end > 80 ? cut.slice(0, end + 1) : cut.slice(0, cut.lastIndexOf(' ')) + '…')
}

let current: HTMLAudioElement | null = null
let generation = 0
// 2026-10-27 (owner: "no sound comes out of the laptop"): a browser blocks sound that starts after an await unless
// the element was started inside the click. One player is primed in the click (unlockAudio) and reused; a play
// that is still refused raises 'smartlab:audio-blocked' so the page can offer a Play button instead of silence.
let player: HTMLAudioElement | null = null
let lastBlob: Blob | null = null
const SILENT = 'data:audio/wav;base64,UklGRiYAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQIAAACAgA=='

/** Call synchronously inside a click / tap handler before any await. */
export function unlockAudio() {
  try {
    if (!player) player = new Audio()
    player.src = SILENT
    void player.play().catch(() => { /* still primed for the next play */ })
    const AC = (window as unknown as { AudioContext?: typeof AudioContext }).AudioContext
    if (AC) { const c = new AC(); void c.resume().finally(() => c.close()) }
    // iPhone Safari: the browser voice (fallback) also speaks later only if it was started once inside the tap
    if ('speechSynthesis' in window) { const u = new SpeechSynthesisUtterance(' '); u.volume = 0; window.speechSynthesis.speak(u) }
  } catch { /* no audio on this device */ }
}

/** Play the last spoken answer again (from a user tap - always allowed). */
export function replayLast(): Promise<void> {
  return lastBlob ? play(lastBlob, ++generation) : Promise.resolve()
}

// the pending play()'s finish - called on stop so the speaking chain ends instead of waiting forever for 'ended'
// (2026-10-28, owner: "pressing refresh freezes the screen" - a paused answer left the page stuck on "Speaking...")
let currentDone: (() => void) | null = null

/** True while a spoken answer is playing (the camera watchdog must not restart the video then - on iPhone that pauses
 *  the speech mid-answer, 2026-10-28). */
export function isSpeaking(): boolean { return !!current && !current.paused }

export function stopSpeaking() {
  generation++
  if (current) { const c = current; current = null; c.pause() }   // cleared first: our own stop is not "resumed"
  const d = currentDone; currentDone = null; d?.()
  window.dispatchEvent(new Event('smartlab:voice-stopped'))
  try { window.speechSynthesis?.cancel() } catch { /* no browser voice */ }
}

/** Sentences grouped into short pieces: the first piece plays while the next one is synthesised. */
export function speechChunks(text: string, max = 140): string[] {
  const parts = text.match(/[^.!?]+[.!?]+["')\]]*\s*|[^.!?]+$/g) ?? [text]
  const out: string[] = []
  for (const p of parts.map(x => x.trim()).filter(Boolean)) {
    // the FIRST piece is one short sentence (or its first clause) so the voice starts at once
    if (!out.length && p.length > 90) { const k = p.lastIndexOf(',', 90); if (k > 30) { out.push(p.slice(0, k + 1)); out.push(p.slice(k + 1).trim()); continue } }
    if (out.length && out[out.length - 1].length + p.length + 1 <= max && out.length > 1) out[out.length - 1] += ' ' + p
    else out.push(p)
  }
  return out
}

async function fetchWav(text: string): Promise<Blob | null> {
  // a busy voice (429) or a blip is retried twice - one refusal used to end the answer mid-sentence (2026-10-28)
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const r = await fetch('/api/voice/speak', { method: 'POST', cache: 'no-store',
        headers: { 'Content-Type': 'application/json', ...auth() }, body: JSON.stringify({ text }) })
      if (r.ok) return r.blob()
      if (r.status !== 429 && r.status < 500) return null
    } catch { /* network blip: retry */ }
    await new Promise(res => setTimeout(res, 400 * (attempt + 1)))
  }
  return null
}

function play(blob: Blob, gen: number): Promise<void> {
  return new Promise(res => {
    if (gen !== generation) return res()
    lastBlob = blob
    const a = player ?? new Audio()
    const url = URL.createObjectURL(blob)
    a.src = url
    current = a
    let finished = false
    const done = () => {
      if (finished) return
      finished = true
      URL.revokeObjectURL(url); if (current === a) current = null; a.onended = null; a.onerror = null; a.onpause = null
      if (currentDone === done) currentDone = null
      window.dispatchEvent(new Event('smartlab:voice-ended'))
      res()
    }
    currentDone = done
    a.onended = done; a.onerror = done
    a.onpause = () => { if (current === a && !a.ended) window.setTimeout(() => { if (current === a) void a.play().catch(done) }, 120) }
    a.play().catch(e => {
      if (e instanceof DOMException && e.name === 'NotAllowedError') window.dispatchEvent(new Event('smartlab:audio-blocked'))
      done()
    })
  })
}

/** Speak with the local Piper voice, piece by piece; fall back to the browser's voice. Resolves when finished. */
export async function speak(text: string, localTts: boolean): Promise<'piper' | 'browser' | 'none'> {
  stopSpeaking()
  const gen = generation
  if (!text) return 'none'
  if (localTts) {
    const chunks = speechChunks(text)
    let next = fetchWav(chunks[0])
    let ok = false
    for (let i = 0; i < chunks.length; i++) {
      const blob = await next
      if (gen !== generation) return 'piper'
      if (!blob) { if (!ok) break; return 'piper' }
      ok = true
      next = i + 1 < chunks.length ? fetchWav(chunks[i + 1]) : Promise.resolve(null)
      await play(blob, gen)
    }
    if (ok) return 'piper'
  }
  if ('speechSynthesis' in window && gen === generation) {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-US'; u.rate = 1.05
    window.speechSynthesis.speak(u)
    return 'browser'
  }
  return 'none'
}
