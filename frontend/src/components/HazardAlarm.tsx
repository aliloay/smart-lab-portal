/**
 * The portal-wide smoke / flame alarm.
 *
 * When an environment node reports a hazard, the backend opens a CRITICAL
 * alert and pushes a `hazard` message to every signed-in page. This shows it
 * full-screen, in red, with a siren - on every device that has the portal
 * open (laptop, tablet, phone). Open hazards are also loaded over REST, so a
 * page opened after the alarm started still shows it.
 *
 * "Acknowledge" only quiets THIS screen (siren off, a red bar stays at the
 * top). The alarm itself ends when the sensor clears. Admins get a direct
 * way into Emergency mode. Indicators only - not a certified fire alarm.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Flame, ShieldAlert, Volume2, VolumeX, Wind } from 'lucide-react'
import { ActiveHazard, api } from '../lib/api'
import { isAdmin, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'

const ICON = { flame: Flame, smoke: Wind } as Record<string, typeof Flame>
const HEADLINE: Record<string, string> = {
  flame: 'FLAME DETECTED', smoke: 'SMOKE / GAS DETECTED',
}

// A two-tone siren made in the browser - no sound file, works offline.
function useSiren() {
  const ctx = useRef<AudioContext | null>(null)
  const timer = useRef<number | undefined>()
  const [playing, setPlaying] = useState(false)
  const [blocked, setBlocked] = useState(false)

  const stop = useCallback(() => {
    window.clearInterval(timer.current)
    timer.current = undefined
    setPlaying(false)
  }, [])

  const start = useCallback(() => {
    try {
      if (!ctx.current) ctx.current = new (window.AudioContext || (window as any).webkitAudioContext)()
      const c = ctx.current
      c.resume().catch(() => {})
      if (c.state !== 'running') { setBlocked(true); return }   // needs one tap first
      setBlocked(false)
      if (timer.current) return
      const sweep = () => {
        const o = c.createOscillator(), g = c.createGain(), t = c.currentTime
        o.type = 'sawtooth'
        o.frequency.setValueAtTime(650, t)
        o.frequency.linearRampToValueAtTime(1350, t + 0.45)
        o.frequency.linearRampToValueAtTime(650, t + 0.9)
        g.gain.setValueAtTime(0.0001, t)
        g.gain.exponentialRampToValueAtTime(0.25, t + 0.05)
        g.gain.setValueAtTime(0.25, t + 0.85)
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.9)
        o.connect(g); g.connect(c.destination)
        o.start(t); o.stop(t + 0.92)
      }
      sweep()
      timer.current = window.setInterval(sweep, 1000)
      setPlaying(true)
    } catch { setBlocked(true) }
  }, [])

  useEffect(() => stop, [stop])
  return { start, stop, playing, blocked }
}

const ACK_KEY = 'hazard-ack'
function loadAck(): number[] {
  try { return JSON.parse(sessionStorage.getItem(ACK_KEY) || '[]') } catch { return [] }
}

export default function HazardAlarm() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [hazards, setHazards] = useState<ActiveHazard[]>([])
  const [acked, setAcked] = useState<number[]>(loadAck)
  const [cleared, setCleared] = useState<string | null>(null)
  const siren = useSiren()

  // The database is the truth: re-check every 10 s too, so a missed live
  // message can never leave an alarm stuck on screen (or hide a new one).
  useEffect(() => {
    if (!user) return
    const load = () => api.activeHazards().then(list => {
      setHazards(prev => {
        if (prev.length > 0 && list.length === 0) setCleared('the sensors report no danger')
        return list
      })
    }).catch(() => {})
    load()
    const t = window.setInterval(load, 10000)
    return () => window.clearInterval(t)
  }, [user])

  useLiveMessages(m => {
    if (m.type !== 'hazard') return
    if (m.state === 'raised') {
      setHazards(h => [{ alert_id: m.alert_id ?? 0, lab_id: m.lab_id, lab_code: m.lab_code,
        metric: m.metric, label: m.label, title: m.title, detail: m.detail, at: m.at },
        ...h.filter(x => !(x.lab_id === m.lab_id && x.metric === m.metric))])
    } else {
      setHazards(h => {
        const rest = h.filter(x => !(x.lab_id === m.lab_id && x.metric === m.metric))
        if (rest.length === 0) setCleared(`${m.label} cleared in ${m.lab_code}`)
        return rest
      })
    }
  })

  const unacked = hazards.filter(h => !acked.includes(h.alert_id))
  const showOverlay = unacked.length > 0

  useEffect(() => {
    if (showOverlay) siren.start(); else siren.stop()
  }, [showOverlay]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!cleared) return
    const t = window.setTimeout(() => setCleared(null), 8000)
    return () => window.clearTimeout(t)
  }, [cleared])

  const acknowledge = () => {
    const next = [...acked, ...unacked.map(h => h.alert_id)]
    setAcked(next)
    try { sessionStorage.setItem(ACK_KEY, JSON.stringify(next)) } catch { /* private mode */ }
    siren.stop()
  }

  if (!user) return null
  const top = unacked[0] ?? hazards[0]

  return (
    <>
      {/* After acknowledging: a red bar stays (bottom of the screen, never over the
          header) until the sensor clears. */}
      {!showOverlay && hazards.length > 0 && (
        <div className="fixed bottom-0 inset-x-0 z-[60] bg-bad text-white text-sm font-bold
                        flex items-center justify-center gap-3 py-2 px-4 animate-pulse">
          <ShieldAlert size={18} />
          {hazards.map(h => `${HEADLINE[h.metric] ?? h.label.toUpperCase()} - ${h.lab_code}`).join('  ·  ')}
          {isAdmin(user) && (
            <button onClick={() => nav('/admin/emergency')}
              className="ml-2 rounded bg-white text-bad px-3 py-0.5 text-xs font-extrabold">
              EMERGENCY MODE</button>
          )}
        </div>
      )}

      {cleared && hazards.length === 0 && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[60] rounded-lg bg-ok text-white
                        font-semibold px-5 py-3 shadow-lift">✓ All clear - {cleared}</div>
      )}

      {showOverlay && top && (
        <div role="alertdialog" aria-modal="true" aria-label="Laboratory hazard alarm"
          className="fixed inset-0 z-[70] flex items-center justify-center bg-red-950/90 backdrop-blur-sm p-4">
          <div className="absolute inset-0 animate-pulse bg-bad/25 pointer-events-none" />
          <div className="relative w-full max-w-3xl rounded-2xl border-4 border-white/80 bg-bad
                          text-white shadow-2xl p-6 sm:p-10 text-center">
            {(() => { const Icon = ICON[top.metric] ?? ShieldAlert
              return <Icon className="mx-auto mb-3" size={72} strokeWidth={2.5} /> })()}
            <div className="text-4xl sm:text-6xl font-black tracking-tight leading-none">
              {HEADLINE[top.metric] ?? top.label.toUpperCase()}</div>
            <div className="mt-3 text-2xl sm:text-3xl font-extrabold">LAB {top.lab_code}</div>
            <div className="mt-2 text-base sm:text-lg text-white/90">
              {new Date(top.at ?? Date.now()).toLocaleTimeString()} · {top.detail}</div>
            {unacked.length > 1 && (
              <div className="mt-3 text-lg font-bold">
                + {unacked.slice(1).map(h => `${HEADLINE[h.metric] ?? h.label} (${h.lab_code})`).join(', ')}</div>
            )}

            {/* Two choices only: take charge (Emergency mode) or clear it from this screen. */}
            <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
              {isAdmin(user) && (
                <button onClick={() => { acknowledge(); nav('/admin/emergency') }}
                  className="rounded-xl bg-white text-bad text-xl font-black px-10 py-4 shadow-lift
                             hover:scale-[1.02] transition">
                  EMERGENCY MODE</button>
              )}
              <button onClick={acknowledge}
                className="rounded-xl border-4 border-white text-white text-xl font-black px-10 py-4
                           hover:bg-white/10 transition">
                CLEAR</button>
            </div>
            <div className="mt-3 text-sm text-white/80">
              Clear only closes this screen - while the sensor still detects it, a red bar stays at the bottom.</div>

            {siren.blocked && (
              <button onClick={siren.start}
                className="mt-5 inline-flex items-center gap-2 text-white underline text-base">
                <Volume2 size={18} /> Tap to sound the siren on this device</button>
            )}
            {siren.playing && (
              <button onClick={siren.stop}
                className="mt-5 inline-flex items-center gap-2 text-white/80 text-sm">
                <VolumeX size={16} /> Silence this device</button>
            )}
            <div className="mt-4 text-xs text-white/70">
              Indicator only - not a certified fire alarm. Follow the building procedure.</div>
          </div>
        </div>
      )}
    </>
  )
}
