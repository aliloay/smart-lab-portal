/**
 * The administrator's emergency message, on every signed-in screen (any
 * role, laptop, tablet, phone): shown at the top and READ ALOUD with the
 * device's own voice, repeated every 20 s, until
 *   - this person presses "Stop voice" (this screen only - the text stays),
 *   - CLEAR ALL on this screen (voice off and the banner hidden), or
 *   - the administrator clears the message or presses Clear sound / Clear all.
 * A NEW message (new version) is shown and read aloud again.
 * The door tablet does the same on its own page (firmware tablet_display.h).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { MessageSquareWarning, Volume2, VolumeX, X } from 'lucide-react'
import { EmergencyBroadcast, api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'

const REPEAT_MS = 20000
const KEY = 'emergency-msg-'
const keyOf = (b: EmergencyBroadcast) => `${b.lab_id}:${b.version}`
function load(name: string): string[] {
  try { return JSON.parse(sessionStorage.getItem(KEY + name) || '[]') } catch { return [] }
}
function save(name: string, v: string[]) {
  try { sessionStorage.setItem(KEY + name, JSON.stringify(v)) } catch { /* private mode */ }
}

function say(text: string): boolean {
  const s = window.speechSynthesis
  if (!s) return false
  try {
    s.cancel()
    const u = new SpeechSynthesisUtterance(text)
    const v = s.getVoices().filter(x => /^en/i.test(x.lang))
    const local = v.filter(x => x.localService)            // these work without internet
    const voice = local[0] ?? v[0]
    if (voice) { u.voice = voice; u.lang = voice.lang } else u.lang = 'en-US'
    u.rate = 0.95
    s.speak(u)
    return true
  } catch { return false }
}

export default function EmergencyMessage() {
  const { user } = useAuth()
  const [items, setItems] = useState<EmergencyBroadcast[]>([])
  const [muted, setMuted] = useState<string[]>(() => load('muted'))
  const [hidden, setHidden] = useState<string[]>(() => load('hidden'))
  const lastSaid = useRef<Record<string, number>>({})

  const refresh = useCallback(() => {
    api.emergencyActive().then(setItems).catch(() => {})
  }, [])
  useEffect(() => {
    if (!user) return
    refresh()
    const t = window.setInterval(refresh, 10000)          // the database is the truth
    return () => window.clearInterval(t)
  }, [user, refresh])

  useLiveMessages(m => {
    if (m.type !== 'emergency_broadcast') return
    const b: EmergencyBroadcast = m
    setItems(list => [...list.filter(x => x.lab_id !== b.lab_id), ...(b.message || b.alarm ? [b] : [])])
  })

  const shown = items.filter(b => b.message && !hidden.includes(keyOf(b)))
  const speaking = shown.filter(b => b.speak && !muted.includes(keyOf(b)))

  // Read each message aloud now, then every REPEAT_MS, while it should be.
  useEffect(() => {
    if (!speaking.length) { try { window.speechSynthesis?.cancel() } catch { /* none */ } return }
    const tick = () => {
      const now = Date.now()
      const due = speaking.find(b => now - (lastSaid.current[keyOf(b)] ?? 0) >= REPEAT_MS)
      if (!due) return
      lastSaid.current[keyOf(due)] = now
      say(`Message from the lab administrator, ${due.lab_code.replace('_', ' ')}. ${due.message}`)
    }
    tick()
    const t = window.setInterval(tick, 1000)
    return () => window.clearInterval(t)
  }, [speaking.map(keyOf).join(',')]) // eslint-disable-line react-hooks/exhaustive-deps

  const mute = (b: EmergencyBroadcast) => {
    const next = [...muted, keyOf(b)]; setMuted(next); save('muted', next)
    try { window.speechSynthesis?.cancel() } catch { /* none */ }
  }
  const hide = (b: EmergencyBroadcast) => {
    mute(b)
    const next = [...hidden, keyOf(b)]; setHidden(next); save('hidden', next)
  }
  // CLEAR ALL on this screen: voice off and every message hidden.
  useEffect(() => {
    const h = () => {
      const keys = items.map(keyOf)
      const m = [...muted, ...keys], hd = [...hidden, ...keys]
      setMuted(m); save('muted', m); setHidden(hd); save('hidden', hd)
      try { window.speechSynthesis?.cancel() } catch { /* none */ }
    }
    window.addEventListener('smartlab:clear-all', h)
    return () => window.removeEventListener('smartlab:clear-all', h)
  })

  if (!user || !shown.length) return null
  return (
    <div className="fixed top-3 left-1/2 -translate-x-1/2 z-[66] w-[min(720px,calc(100vw-2rem))] space-y-2">
      {shown.map(b => {
        const voiceOn = b.speak && !muted.includes(keyOf(b))
        return (
          <div key={keyOf(b)} role="alert" data-testid="emergency-message"
            className="rounded-xl border-2 border-bad bg-[#3a0d0d]/95 text-white shadow-2xl px-4 py-3">
            <div className="flex items-start gap-3">
              <MessageSquareWarning className="shrink-0 mt-0.5 text-bad-soft" size={26} />
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-bold tracking-wider text-bad-soft">
                  MESSAGE FROM THE LAB ADMINISTRATOR · {b.lab_code}</div>
                <div className="text-xl font-extrabold leading-snug break-words">{b.message}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {voiceOn ? (
                    <button onClick={() => mute(b)}
                      className="rounded-lg border border-white/60 text-sm font-bold px-3 py-1 inline-flex items-center gap-1.5">
                      <VolumeX size={15} /> Stop voice</button>
                  ) : b.speak ? (
                    <button onClick={() => { setMuted(m => { const n = m.filter(k => k !== keyOf(b)); save('muted', n); return n }); lastSaid.current[keyOf(b)] = 0 }}
                      className="rounded-lg border border-white/40 text-sm px-3 py-1 inline-flex items-center gap-1.5 text-white/80">
                      <Volume2 size={15} /> Read aloud again</button>
                  ) : <span className="text-xs text-white/60 self-center">Voice switched off by the administrator</span>}
                  <button onClick={() => hide(b)}
                    className="rounded-lg border border-white/30 text-sm px-3 py-1 inline-flex items-center gap-1.5 text-white/80">
                    <X size={15} /> Hide on this screen</button>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
