/**
 * Access flow SIMULATION, for presenting the system without the hardware.
 *
 * Isolation is structural, not a flag: this page never calls the API. It
 * sends nothing to the portal, the database or any device, so a simulated
 * scan cannot appear in the audit trail, occupancy, reports or anyone's
 * notifications. Every surface is labelled SIMULATION.
 *
 * The scenarios mirror the real decision path (see docs/ACCESS_FLOW.md):
 * step 1 identifies, step 2 must match that identity, and only the master
 * controller drives the relay.
 */
import { useEffect, useRef, useState } from 'react'
import {
  Camera, Cpu, CreditCard, DoorOpen, Fingerprint, FlaskConical, Lock, Play, QrCode,
  RotateCcw, ScanFace, Server, Smartphone,
} from 'lucide-react'
import { Chip, PageHeader, SectionTitle, Timeline, TimelineItem, Tone } from '../components/ui'

type Node = 'credential' | 'camera' | 'portal' | 'master' | 'biometric' | 'relay' | 'door'
interface Step { node: Node; title: string; detail: string; tone: Tone }

const NODES: { key: Node; label: string; icon: JSX.Element }[] = [
  { key: 'credential', label: 'Phone / card', icon: <Smartphone size={18} /> },
  { key: 'camera', label: 'ESP32-CAM', icon: <Camera size={18} /> },
  { key: 'portal', label: 'Portal API', icon: <Server size={18} /> },
  { key: 'master', label: 'Master ESP32', icon: <Cpu size={18} /> },
  { key: 'biometric', label: 'Face / finger', icon: <ScanFace size={18} /> },
  { key: 'relay', label: 'Relay', icon: <Lock size={18} /> },
  { key: 'door', label: 'Door', icon: <DoorOpen size={18} /> },
]

const SCENARIOS: { key: string; label: string; outcome: 'granted' | 'denied'; steps: Step[] }[] = [
  { key: 'qr-face', label: 'QR + face → granted', outcome: 'granted', steps: [
    { node: 'credential', title: 'QR shown at the door', detail: 'Booking credential on the student\'s phone', tone: 'info' },
    { node: 'camera', title: 'QR scanned', detail: 'ESP32-CAM frame decoded by OpenCV', tone: 'info' },
    { node: 'portal', title: 'QR validated', detail: 'Token, laboratory, booking, time window and user all check out → identity USER1', tone: 'ok' },
    { node: 'biometric', title: 'Face detected', detail: 'Face server compares against enrolled faces', tone: 'info' },
    { node: 'master', title: 'Identity matched', detail: 'Step 2 (USER1) = step 1 (USER1)', tone: 'ok' },
    { node: 'master', title: 'Access granted', detail: 'The master decides; the portal only records it', tone: 'ok' },
    { node: 'relay', title: 'Relay unlocked', detail: 'Driven by the master controller, never by the portal', tone: 'ok' },
    { node: 'door', title: 'Door opened', detail: 'Reed sensor reports open - entry time recorded', tone: 'violet' },
    { node: 'door', title: 'Door closed', detail: 'Relocked. The person is inside; no exit is assumed', tone: 'violet' },
  ]},
  { key: 'rfid-finger', label: 'RFID + fingerprint → granted', outcome: 'granted', steps: [
    { node: 'credential', title: 'Card presented', detail: 'MFRC522 reads the card UID', tone: 'info' },
    { node: 'portal', title: 'Card accepted', detail: 'Registered, active user → identity USER1', tone: 'ok' },
    { node: 'biometric', title: 'Fingerprint presented', detail: 'AS608 matches against its own stored templates', tone: 'info' },
    { node: 'master', title: 'Identity matched', detail: 'Step 2 (USER1) = step 1 (USER1)', tone: 'ok' },
    { node: 'master', title: 'Access granted', detail: 'Recorded by the portal as a session', tone: 'ok' },
    { node: 'relay', title: 'Relay unlocked', detail: 'Driven by the master controller', tone: 'ok' },
    { node: 'door', title: 'Door opened', detail: 'Entry time recorded', tone: 'violet' },
    { node: 'door', title: 'Door closed', detail: 'Relocked', tone: 'violet' },
  ]},
  { key: 'mismatch', label: 'Someone else\'s QR → denied', outcome: 'denied', steps: [
    { node: 'credential', title: 'QR shown at the door', detail: 'A photographed credential that belongs to USER1', tone: 'info' },
    { node: 'camera', title: 'QR scanned', detail: 'Decoded', tone: 'info' },
    { node: 'portal', title: 'QR validated', detail: 'The credential itself is valid → identity USER1', tone: 'ok' },
    { node: 'biometric', title: 'Face detected', detail: 'The face belongs to USER2', tone: 'info' },
    { node: 'master', title: 'Identity mismatch', detail: 'Step 2 (USER2) ≠ step 1 (USER1)', tone: 'bad' },
    { node: 'master', title: 'Access denied', detail: 'Logged as IDENTITY_MISMATCH; staff alerted', tone: 'bad' },
    { node: 'relay', title: 'Relay stays locked', detail: 'The door never opens', tone: 'bad' },
  ]},
  { key: 'wrong-lab', label: 'QR at the wrong lab → denied', outcome: 'denied', steps: [
    { node: 'credential', title: 'QR shown at LAB_02', detail: 'The booking is for LAB_01', tone: 'info' },
    { node: 'camera', title: 'QR scanned', detail: 'Decoded', tone: 'info' },
    { node: 'portal', title: 'QR rejected: wrong laboratory', detail: 'Checked before the time window - no biometric is even requested', tone: 'bad' },
    { node: 'master', title: 'Access denied', detail: 'Logged as WRONG_LAB', tone: 'bad' },
    { node: 'relay', title: 'Relay stays locked', detail: 'The door never opens', tone: 'bad' },
  ]},
  { key: 'offline', label: 'Portal unreachable → fails closed', outcome: 'denied', steps: [
    { node: 'credential', title: 'QR shown at the door', detail: 'A valid booking credential', tone: 'info' },
    { node: 'camera', title: 'QR scanned', detail: 'Decoded', tone: 'info' },
    { node: 'portal', title: 'No answer from the portal', detail: 'Timeout after 2.5 s', tone: 'warn' },
    { node: 'master', title: 'Access denied', detail: 'A booking QR is never accepted without the portal', tone: 'bad' },
    { node: 'relay', title: 'Relay stays locked', detail: 'Fail closed, by design', tone: 'bad' },
  ]},
]

export default function Simulation() {
  const [scenario, setScenario] = useState(SCENARIOS[0])
  const [shown, setShown] = useState<{ step: Step; at: Date }[]>([])
  const [running, setRunning] = useState(false)
  const timer = useRef<number>()

  useEffect(() => () => window.clearTimeout(timer.current), [])

  function play() {
    window.clearTimeout(timer.current)
    setShown([]); setRunning(true)
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const gap = reduce ? 150 : 850
    let i = 0
    const next = () => {
      const step = scenario.steps[i]
      setShown(p => [...p, { step, at: new Date() }])
      i++
      if (i < scenario.steps.length) timer.current = window.setTimeout(next, gap)
      else setRunning(false)
    }
    timer.current = window.setTimeout(next, 250)
  }

  function reset() { window.clearTimeout(timer.current); setShown([]); setRunning(false) }

  const active = shown.length ? shown[shown.length - 1].step.node : null
  const reached = new Set(shown.map(s => s.step.node))
  const done = !running && shown.length === scenario.steps.length
  const items: TimelineItem[] = shown.map((s, i) => ({
    key: i,
    time: s.at.toLocaleTimeString([], { hour12: false }),
    title: s.step.title,
    detail: s.step.detail,
    tone: s.step.tone,
  }))

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border-2 border-dashed border-warn/50 bg-warn/[0.07] px-5 py-3
                      flex flex-wrap items-center gap-3">
        <Chip tone="warn" dot>Simulation</Chip>
        <span className="text-[13.5px] text-amber-100">
          Nothing on this page is real or recorded. No request is sent to the portal, the
          database or any device - simulated steps never enter the audit trail.
        </span>
      </div>

      <PageHeader eyebrow="Demo mode" title="Access flow simulation"
        sub="Walk through the two-factor door sequence for a presentation, without the hardware." />

      <div className="card p-4 flex flex-wrap items-center gap-2">
        {SCENARIOS.map(s => (
          <button key={s.key} onClick={() => { setScenario(s); reset() }} aria-pressed={scenario.key === s.key}
            className={`btn btn-sm border ${scenario.key === s.key
              ? 'bg-accent-500/15 text-accent-100 border-accent-500/45'
              : 'border-ink-500 text-slate-300 hover:text-white bg-ink-800/40'}`}>{s.label}</button>
        ))}
        <div className="ml-auto flex gap-2">
          <button className="btn-primary" onClick={play} disabled={running}>
            <Play size={15} />{shown.length ? 'Run again' : 'Run simulation'}</button>
          <button className="btn-quiet" onClick={reset} disabled={!shown.length}><RotateCcw size={15} />Reset</button>
        </div>
      </div>

      {/* the physical chain */}
      <section className="card p-5 overflow-x-auto">
        <div className="flex items-center gap-2 min-w-[760px]">
          {NODES.map((n, i) => {
            const on = reached.has(n.key)
            const current = active === n.key
            const last = shown.filter(s => s.step.node === n.key).slice(-1)[0]?.step.tone
            const ring = !on ? 'border-ink-500 text-slate-500 bg-ink-900/40'
              : last === 'bad' ? 'border-bad/60 text-bad-soft bg-bad/10'
              : last === 'warn' ? 'border-warn/60 text-warn-soft bg-warn/10'
              : last === 'ok' ? 'border-ok/60 text-ok-soft bg-ok/10'
              : 'border-accent-400/60 text-accent-200 bg-accent-500/10'
            return (
              <div key={n.key} className="flex items-center gap-2 flex-1">
                <div className="flex flex-col items-center gap-2 flex-1">
                  <span className={`grid place-items-center w-14 h-14 rounded-2xl border-2 transition-all
                                    duration-300 ${ring} ${current ? 'scale-110 shadow-glow' : ''}`}>
                    {n.key === 'credential' && scenario.key === 'rfid-finger' ? <CreditCard size={18} />
                      : n.key === 'biometric' && scenario.key === 'rfid-finger' ? <Fingerprint size={18} />
                      : n.key === 'credential' ? <QrCode size={18} /> : n.icon}
                  </span>
                  <span className={`text-[11.5px] text-center ${on ? 'text-slate-100' : 'text-slate-500'}`}>{n.label}</span>
                </div>
                {i < NODES.length - 1 && (
                  <span className={`h-0.5 w-6 rounded-full transition-colors ${
                    reached.has(NODES[i + 1].key) ? 'bg-accent-400' : 'bg-ink-600'}`} />
                )}
              </div>
            )
          })}
        </div>
      </section>

      <div className="grid xl:grid-cols-3 gap-6">
        <section className="xl:col-span-2">
          <SectionTitle icon={<FlaskConical size={15} />} sub="Simulated timeline - timestamps are this browser's clock.">
            Simulated events
          </SectionTitle>
          <div className="card p-5 min-h-[240px]">
            {items.length === 0
              ? <p className="text-[13px] text-slate-400">Choose a scenario and run it.</p>
              : <Timeline items={items} />}
          </div>
        </section>
        <aside>
          <SectionTitle>Outcome</SectionTitle>
          <div className={`card p-6 text-center ${done ? scenario.outcome === 'granted'
            ? 'border-ok/45 shadow-glow-ok' : 'border-bad/45' : ''}`}>
            {!done ? <p className="text-[13px] text-slate-400">{running ? 'Running…' : 'Not run yet'}</p> : (
              <>
                <div className={`font-display text-2xl font-semibold ${scenario.outcome === 'granted'
                  ? 'text-ok-soft' : 'text-bad-soft'}`}>
                  {scenario.outcome === 'granted' ? 'ACCESS GRANTED' : 'ACCESS DENIED'}
                </div>
                <p className="mt-2 text-[13px] text-slate-300">
                  {scenario.outcome === 'granted'
                    ? 'Both factors matched one identity; the master unlocked the door.'
                    : 'The door never unlocked. On the real system this refusal is logged with its reason.'}
                </p>
                <div className="mt-4"><Chip tone="warn">simulation · not recorded</Chip></div>
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
