/**
 * Push-to-talk for any question box (2026-10-27): tap = record, tap again (or the silence auto-stop) = the
 * lab's own local speech service transcribes it, and the text is handed to onText. Nothing is recorded
 * in the background; the microphone is released as soon as the recording stops or the component unmounts.
 */
import { useEffect, useRef, useState } from 'react'
import { Loader2, Mic, Square } from 'lucide-react'
import { Recording, micSupported, transcribe } from '../lib/voice'

export default function MicButton({ onText, disabled, className = '' }: {
  onText: (text: string) => void; disabled?: boolean; className?: string
}) {
  const [phase, setPhase] = useState<'idle' | 'recording' | 'transcribing'>('idle')
  const [err, setErr] = useState('')
  const rec = useRef<Recording | null>(null)
  const ac = useRef<AbortController | null>(null)
  useEffect(() => () => { rec.current?.cancel(); ac.current?.abort() }, [])
  if (!micSupported()) return null

  const finish = async () => {
    const r = rec.current
    if (!r) return
    rec.current = null
    setPhase('transcribing')
    const c = new AbortController(); ac.current = c
    try {
      const t = await transcribe(await r.stop(), c.signal)
      if (t.text && t.text.trim().length > 1) onText(t.text.trim())
      else setErr('Did not catch that - try again.')
    } catch (e) {
      if (!c.signal.aborted) setErr(e instanceof Error ? e.message : 'Speech service unavailable')
    } finally { setPhase('idle'); ac.current = null }
  }
  const start = async () => {
    setErr('')
    try { rec.current = await Recording.start(() => void finish()); setPhase('recording') }
    catch { setErr('The microphone is blocked - allow it for this site.') }
  }
  const label = phase === 'recording' ? 'Stop and ask' : phase === 'transcribing' ? 'Transcribing' : 'Ask by voice'
  return (
    <span className="relative inline-flex">
      <button type="button" aria-label={label} title={label} disabled={disabled || phase === 'transcribing'}
              onClick={() => phase === 'recording' ? void finish() : void start()}
              className={`grid place-items-center w-11 h-11 rounded-xl shrink-0 ${phase === 'recording'
                ? 'bg-red-600 text-white animate-pulse' : 'btn-ghost !px-0 text-accent-200'} ${className}`}>
        {phase === 'recording' ? <Square size={16} /> : phase === 'transcribing' ? <Loader2 size={17} className="animate-spin" /> : <Mic size={18} />}
      </button>
      {err && <span className="absolute bottom-full mb-1 right-0 whitespace-nowrap text-[11px] text-bad-soft">{err}</span>}
    </span>
  )
}
