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
  Bell, Bot, Boxes, BrainCircuit, Database, Flame, Library, MessageSquare, Siren, Thermometer, Weight, Workflow,
  Camera, Cpu, CreditCard, DoorOpen, Fingerprint, FlaskConical, Lock, Play, QrCode,
  RotateCcw, ScanFace, Server, Smartphone,
} from 'lucide-react'
import { Chip, PageHeader, SectionTitle, Timeline, TimelineItem, Tone } from '../components/ui'

type Node = string
interface Step { node: Node; title: string; detail: string; tone: Tone }
interface NodeDef { key: string; label: string; icon: JSX.Element }
interface Scenario { key: string; label: string; group: string; nodes?: NodeDef[]; outcome: 'granted' | 'denied' | 'ok' | 'alarm'; result?: string; steps: Step[] }

const NODES: NodeDef[] = [
  { key: 'credential', label: 'Phone / card', icon: <Smartphone size={18} /> },
  { key: 'camera', label: 'ESP32-CAM', icon: <Camera size={18} /> },
  { key: 'portal', label: 'Portal API', icon: <Server size={18} /> },
  { key: 'master', label: 'Master ESP32', icon: <Cpu size={18} /> },
  { key: 'biometric', label: 'Face / finger', icon: <ScanFace size={18} /> },
  { key: 'relay', label: 'Relay', icon: <Lock size={18} /> },
  { key: 'door', label: 'Door', icon: <DoorOpen size={18} /> },
]

const DOOR: Scenario[] = [
  { key: 'qr-face', label: 'QR + face → granted', group: 'Door access', outcome: 'granted', steps: [
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
  { key: 'rfid-finger', label: 'RFID + fingerprint → granted', group: 'Door access', outcome: 'granted', steps: [
    { node: 'credential', title: 'Card presented', detail: 'PN532 reads the card UID', tone: 'info' },
    { node: 'portal', title: 'Card accepted', detail: 'Registered, active user → identity USER1', tone: 'ok' },
    { node: 'biometric', title: 'Fingerprint presented', detail: 'AS608 matches against its own stored templates', tone: 'info' },
    { node: 'master', title: 'Identity matched', detail: 'Step 2 (USER1) = step 1 (USER1)', tone: 'ok' },
    { node: 'master', title: 'Access granted', detail: 'Recorded by the portal as a session', tone: 'ok' },
    { node: 'relay', title: 'Relay unlocked', detail: 'Driven by the master controller', tone: 'ok' },
    { node: 'door', title: 'Door opened', detail: 'Entry time recorded', tone: 'violet' },
    { node: 'door', title: 'Door closed', detail: 'Relocked', tone: 'violet' },
  ]},
  { key: 'mismatch', label: 'Someone else\'s QR → denied', group: 'Door access', outcome: 'denied', steps: [
    { node: 'credential', title: 'QR shown at the door', detail: 'A photographed credential that belongs to USER1', tone: 'info' },
    { node: 'camera', title: 'QR scanned', detail: 'Decoded', tone: 'info' },
    { node: 'portal', title: 'QR validated', detail: 'The credential itself is valid → identity USER1', tone: 'ok' },
    { node: 'biometric', title: 'Face detected', detail: 'The face belongs to USER2', tone: 'info' },
    { node: 'master', title: 'Identity mismatch', detail: 'Step 2 (USER2) ≠ step 1 (USER1)', tone: 'bad' },
    { node: 'master', title: 'Access denied', detail: 'Logged as IDENTITY_MISMATCH; staff alerted', tone: 'bad' },
    { node: 'relay', title: 'Relay stays locked', detail: 'The door never opens', tone: 'bad' },
  ]},
  { key: 'wrong-lab', label: 'QR at the wrong lab → denied', group: 'Door access', outcome: 'denied', steps: [
    { node: 'credential', title: 'QR shown at LAB_02', detail: 'The booking is for LAB_01', tone: 'info' },
    { node: 'camera', title: 'QR scanned', detail: 'Decoded', tone: 'info' },
    { node: 'portal', title: 'QR rejected: wrong laboratory', detail: 'Checked before the time window - no biometric is even requested', tone: 'bad' },
    { node: 'master', title: 'Access denied', detail: 'Logged as WRONG_LAB', tone: 'bad' },
    { node: 'relay', title: 'Relay stays locked', detail: 'The door never opens', tone: 'bad' },
  ]},
  { key: 'offline', label: 'Portal unreachable → fails closed', group: 'Door access', outcome: 'denied', steps: [
    { node: 'credential', title: 'QR shown at the door', detail: 'A valid booking credential', tone: 'info' },
    { node: 'camera', title: 'QR scanned', detail: 'Decoded', tone: 'info' },
    { node: 'portal', title: 'No answer from the portal', detail: 'Timeout after 2.5 s', tone: 'warn' },
    { node: 'master', title: 'Access denied', detail: 'A booking QR is never accepted without the portal', tone: 'bad' },
    { node: 'relay', title: 'Relay stays locked', detail: 'Fail closed, by design', tone: 'bad' },
  ]},
]

const N = (key: string, label: string, icon: JSX.Element): NodeDef => ({ key, label, icon })
const OTHER: Scenario[] = [
  { key: 'smoke', label: 'Smoke detected', group: 'Environment & safety', outcome: 'alarm', result: 'Hazard raised, staff notified and escalated - the door safety logic itself stays on the Master ESP32.',
    nodes: [N('sensor', 'MQ-2 / flame', <Flame size={18} />), N('env', 'Environment ESP32', <Thermometer size={18} />), N('portal', 'Portal API', <Server size={18} />),
            N('alert', 'Alert + pop-up', <Siren size={18} />), N('n8n', 'n8n workflow', <Workflow size={18} />), N('staff', 'Staff', <Bell size={18} />)],
    steps: [
      { node: 'sensor', title: 'Smoke sensor triggers', detail: 'MQ-2 digital output goes active', tone: 'warn' },
      { node: 'env', title: 'Reading sent', detail: 'ENV_LAB01 posts smoke=1 with its own device key', tone: 'info' },
      { node: 'portal', title: 'Stored and checked', detail: 'sensor_readings row; threshold rule fires', tone: 'info' },
      { node: 'alert', title: 'CRITICAL alert', detail: 'Hazard pop-up on every staff screen (Live monitor, dashboard)', tone: 'bad' },
      { node: 'n8n', title: 'Escalation workflow', detail: '13 - environment hazard escalation: e-mail, repeat until acknowledged', tone: 'warn' },
      { node: 'staff', title: 'Acknowledged', detail: 'Staff acknowledge in the portal; the time to acknowledge is recorded', tone: 'ok' },
    ]},
  { key: 'emergency', label: 'Emergency evacuation', group: 'Environment & safety', outcome: 'alarm', result: 'Evacuation mode: door held open for escape, everyone alerted, recorded with who started it.',
    nodes: [N('admin', 'Admin (portal)', <Siren size={18} />), N('portal', 'Portal API', <Server size={18} />), N('master', 'Master ESP32', <Cpu size={18} />),
            N('door', 'Door', <DoorOpen size={18} />), N('alert', 'All screens', <Bell size={18} />)],
    steps: [
      { node: 'admin', title: 'Evacuation started', detail: 'Admin confirms on the Emergency page', tone: 'bad' },
      { node: 'portal', title: 'Emergency recorded', detail: 'lab_emergencies row + audit log (who, when, why)', tone: 'info' },
      { node: 'master', title: 'Master enters EVACUATE', detail: 'The controller decides how the door behaves - buzzer and red light', tone: 'bad' },
      { node: 'door', title: 'Door held open', detail: 'Unlocked for escape while the mode lasts', tone: 'warn' },
      { node: 'alert', title: 'Everyone alerted', detail: 'Banner on every signed-in screen; n8n 23 - emergency notifies', tone: 'bad' },
      { node: 'admin', title: 'Cleared', detail: 'Admin ends the emergency; door returns to normal locking', tone: 'ok' },
    ]},
  { key: 'robot', label: 'Robot moves', group: 'Robots', outcome: 'ok', result: 'The movement is shown live on the digital twin and saved for replay - monitoring only, nothing is sent to the robot.',
    nodes: [N('ur', 'UR5e controller', <Bot size={18} />), N('collector', 'RTDE collector', <Cpu size={18} />), N('portal', 'Portal API', <Server size={18} />),
            N('twin', '3D digital twin', <Bot size={18} />), N('db', 'Movement history', <Database size={18} />), N('n8n', 'n8n check', <Workflow size={18} />)],
    steps: [
      { node: 'ur', title: 'Program running', detail: 'The UR5e moves its joints (teach pendant program)', tone: 'info' },
      { node: 'collector', title: 'Joints read', detail: 'RTDE receive only, ~10 samples/s - read-only, cannot command', tone: 'info' },
      { node: 'portal', title: 'Telemetry stored', detail: 'JOINT_MOVED, MOVEMENT_STARTED events with occurred_at', tone: 'info' },
      { node: 'twin', title: 'Twin follows', detail: 'The 3D model takes the measured joint angles', tone: 'ok' },
      { node: 'db', title: 'Movement saved', detail: 'MOVEMENT_STOPPED with its full path - replayable on the robot page', tone: 'ok' },
      { node: 'n8n', title: 'Booking checked', detail: '19 - robot used without a booking? only if nobody booked the lab', tone: 'info' },
    ]},
  { key: 'bin', label: 'Take an item from the bin', group: 'Inventory', outcome: 'ok', result: 'The withdrawal is recorded against the person and the stock estimate drops; low stock is flagged.',
    nodes: [N('nfc', 'NFC card', <CreditCard size={18} />), N('bin', 'Bin ESP32', <Boxes size={18} />), N('lid', 'Servo lid', <Lock size={18} />),
            N('scale', 'Load cell', <Weight size={18} />), N('portal', 'Portal API', <Server size={18} />), N('n8n', 'n8n low stock', <Workflow size={18} />)],
    steps: [
      { node: 'nfc', title: 'Card tapped', detail: 'PN532 reads the student card at the bin', tone: 'info' },
      { node: 'bin', title: 'Person checked', detail: 'Portal confirms an active user (and booking)', tone: 'ok' },
      { node: 'lid', title: 'Lid opens', detail: 'Servo opens - a requested action, confirmed by the bin', tone: 'info' },
      { node: 'scale', title: 'Weight drops', detail: 'HX711 sees -12.4 g → about 3 items by the item weight', tone: 'info' },
      { node: 'portal', title: 'Withdrawal recorded', detail: 'inventory_transactions: WITHDRAWAL, person, estimated quantity', tone: 'ok' },
      { node: 'n8n', title: 'Stock check', detail: '15 - low stock: notifies staff when below the threshold', tone: 'warn' },
    ]},
  { key: 'n8n', label: 'Automation chain (n8n)', group: 'Automation & AI', outcome: 'ok', result: 'Every event goes out through a reliable outbox - retried if n8n is down, never lost, never sent twice.',
    nodes: [N('event', 'Lab event', <Bell size={18} />), N('outbox', 'Event outbox', <Database size={18} />), N('n8n', 'n8n webhook', <Workflow size={18} />),
            N('rule', 'Workflow logic', <Workflow size={18} />), N('out', 'E-mail / alert', <MessageSquare size={18} />)],
    steps: [
      { node: 'event', title: 'Door denied 3 times', detail: 'Three DENIED events for one card in 5 min', tone: 'warn' },
      { node: 'outbox', title: 'Queued', detail: 'integration_events row with a unique event_id (no duplicates)', tone: 'info' },
      { node: 'n8n', title: 'Delivered', detail: 'Sent to the n8n webhook on the laptop; DELIVERED recorded', tone: 'ok' },
      { node: 'rule', title: '03 - access denial intelligence', detail: 'Enriches with the user and lab, decides it is worth a message', tone: 'info' },
      { node: 'out', title: 'Staff notified', detail: 'Notification + e-mail; if n8n were down the outbox retries later', tone: 'ok' },
    ]},
  { key: 'vault', label: 'Knowledge vault search', group: 'Automation & AI', outcome: 'ok', result: 'The answer quotes the project documents and code with their sources - it never invents a source.',
    nodes: [N('q', 'Question', <MessageSquare size={18} />), N('vault', 'Obsidian vault', <Library size={18} />), N('search', 'Search index', <Database size={18} />),
            N('graph', 'Code graph', <Workflow size={18} />), N('answer', 'Answer + sources', <BrainCircuit size={18} />)],
    steps: [
      { node: 'q', title: '"How does the door decide?"', detail: 'Asked in Project knowledge', tone: 'info' },
      { node: 'vault', title: 'Notes found', detail: 'docs/ACCESS_FLOW, Master firmware notes (172 notes, 1,200+ links)', tone: 'info' },
      { node: 'search', title: 'Best passages', detail: 'Keyword + meaning search ranks the paragraphs', tone: 'info' },
      { node: 'graph', title: 'Related code', detail: 'Imports, tests and workflows linked to those files', tone: 'info' },
      { node: 'answer', title: 'Answered with sources', detail: 'Each claim labelled DOCUMENTED / TESTED / PROPOSAL', tone: 'ok' },
    ]},
  { key: 'agent', label: 'Ask the lab (AI agent)', group: 'Automation & AI', outcome: 'ok', result: 'Numbers come from the database tools, not from the language model - read-only, staff-only where needed.',
    nodes: [N('q', 'Question', <MessageSquare size={18} />), N('intent', 'Intent', <BrainCircuit size={18} />), N('tool', 'Read-only tool', <Database size={18} />),
            N('llm', 'Local model (CPU)', <BrainCircuit size={18} />), N('answer', 'Answer + link', <MessageSquare size={18} />)],
    steps: [
      { node: 'q', title: '"How is the system health?"', detail: 'Asked by a staff member', tone: 'info' },
      { node: 'intent', title: 'Recognised: system', detail: 'Exact answer available - the model is not needed', tone: 'info' },
      { node: 'tool', title: 'System analytics read', detail: 'Freshness of 9 data sources + 7-day totals from real tables', tone: 'ok' },
      { node: 'llm', title: 'Not used', detail: 'Only free-form questions go to the local model, with these tools', tone: 'info' },
      { node: 'answer', title: 'Answered', detail: 'Facts with their tables, and a link to System analytics', tone: 'ok' },
    ]},
]
const SCENARIOS: Scenario[] = [...DOOR, ...OTHER]
const GROUPS = ['Door access', 'Environment & safety', 'Robots', 'Inventory', 'Automation & AI']

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

      <PageHeader eyebrow="Demo mode" title="System simulation"
        sub="Walk through how each part of the lab works - door, safety, robots, inventory, automations, knowledge and AI - without the hardware." />

      <div className="card p-4 flex flex-wrap items-center gap-2">
        {GROUPS.map(g => <div key={g} className="w-full flex flex-wrap 2xl:flex-nowrap items-center gap-1.5">
          <span className="w-36 shrink-0 text-[11px] uppercase tracking-wide text-slate-400">{g}</span>
        {SCENARIOS.filter(s => s.group === g).map(s => (
          <button key={s.key} onClick={() => { setScenario(s); reset() }} aria-pressed={scenario.key === s.key}
            className={`btn btn-sm border whitespace-nowrap !px-2.5 !text-[13px] ${scenario.key === s.key
              ? 'bg-accent-500/15 text-accent-100 border-accent-500/45'
              : 'border-ink-500 text-slate-300 hover:text-white bg-ink-800/40'}`}>{s.label}</button>
        ))}</div>)}
        <div className="w-full flex gap-2 justify-end">
          <button className="btn-primary" onClick={play} disabled={running}>
            <Play size={15} />{shown.length ? 'Run again' : 'Run simulation'}</button>
          <button className="btn-quiet" onClick={reset} disabled={!shown.length}><RotateCcw size={15} />Reset</button>
        </div>
      </div>

      {/* the physical chain */}
      <section className="card p-5 overflow-x-auto">
        <div className="flex items-center gap-2 min-w-[760px]">
          {(scenario.nodes ?? NODES).map((n, i, chain) => {
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
                {i < chain.length - 1 && (
                  <span className={`h-0.5 w-6 rounded-full transition-colors ${
                    reached.has(chain[i + 1].key) ? 'bg-accent-400' : 'bg-ink-600'}`} />
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
          <div className={`card p-6 text-center ${done ? scenario.outcome !== 'denied'
            ? 'border-ok/45 shadow-glow-ok' : 'border-bad/45' : ''}`}>
            {!done ? <p className="text-[13px] text-slate-400">{running ? 'Running…' : 'Not run yet'}</p> : (
              <>
                <div className={`font-display text-2xl font-semibold ${scenario.outcome !== 'denied'
                  ? 'text-ok-soft' : 'text-bad-soft'}`}>
                  {scenario.outcome === 'granted' ? 'ACCESS GRANTED' : scenario.outcome === 'denied' ? 'ACCESS DENIED'
                    : scenario.outcome === 'alarm' ? 'ALARM HANDLED' : 'COMPLETED'}
                </div>
                <p className="mt-2 text-[13px] text-slate-300">
                  {scenario.result ?? (scenario.outcome === 'granted'
                    ? 'Both factors matched one identity; the master unlocked the door.'
                    : 'The door never unlocked. On the real system this refusal is logged with its reason.')}
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
