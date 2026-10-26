/**
 * Robots in Equipment -> Robots & PCs: one panel per physical robot.
 *
 *   LIVE     fresh telemetry from the robot (not a simulation): the twin and the
 *            six joint bars follow the real joints; the bars are read-only.
 *   PREVIEW  no live data: the twin can be posed with the six bars (mouse) to
 *            study the arm. Nothing is ever sent to a robot - this is drawing only,
 *            and the panel says PREVIEW so it is never mistaken for the robot.
 */
import Replay, { ReplayFrame } from './Replay'
import RobotControlPanel from './RobotControlPanel'
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState, memo } from 'react'
import WorkcellEditor from './WorkcellEditor'
import { Workcell, collisions, defaultWorkcell, tableBox } from './workcell'
import { Link } from 'react-router-dom'
import { Bot, ChevronRight, Hand, Maximize2, Monitor, Radio, RotateCcw, X } from 'lucide-react'
import { api, SecurityCamera } from '../../lib/api'
import { Robot } from '../../lib/api'
import { relative } from '../../lib/time'
import { isStaff, useAuth } from '../../lib/auth'
import { useLiveMessages } from '../../lib/live'
import { pcStatus } from '../../lib/pcStatus'
import { Skeleton } from '../ui'
import { MODELS, RobotModel } from './kinematics'
import { effective, useRobots } from './robotLive'
import { FANUC_CELL, tipPosition, urdfFor } from './robotModels'

const loadTwin = () => import('./RobotTwin')
const RobotTwin = lazy(loadTwin)

/** The 3D code starts downloading as soon as this panel's code loads (it used to wait for the panel to
 *  mount). Preloading the meshes as well was measured (2026-10-19) to add duplicate requests without
 *  making the twins appear sooner - the cost is parsing ~12 MB of detailed meshes, not the download. */
let warmed = false
function warmTwins() {
  if (warmed) return
  warmed = true
  loadTwin().catch(() => {})
}
const JOINTS = ['J1 Base', 'J2 Shoulder', 'J3 Elbow', 'J4 Wrist 1', 'J5 Wrist 2', 'J6 Wrist 3']
const DEG = 180 / Math.PI

const CELLS = new Map<string, Workcell>()

export default function RobotTwinPanels() {
  const { robots } = useRobots()
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t) }, [])
  // One panel per physical robot model; its live record when one reports.
  const panels = (['UR5E', 'FANUC'] as const).map(key => {
    const model = MODELS[key]
    const rs = (robots ?? []).filter(r => `${r.model || ''} ${r.device_uid}`.toUpperCase().includes(key === 'UR5E' ? 'UR5' : 'FANUC'))
    const real = rs.find(r => !r.demo) ?? null
    return { key, model, real, sim: rs.find(r => r.demo) ?? null }
  })
  const [full, setFull] = useState<string | null>(null)
  const open = panels.find(p => p.key === full)
  return (
    <div className="space-y-5">
      <div className="grid xl:grid-cols-2 gap-4">
        {panels.map(p => <Panel key={p.key} model={p.model} robot={p.real ? effective(p.real, now) : null}
                                onFull={() => setFull(p.key)} />)}
      </div>
      <LabPcs />
      {open && (
        <div className="fixed inset-0 z-50 bg-ink-950/90 backdrop-blur-sm p-4 overflow-auto" role="dialog" aria-label="Robot full view">
          <div className="max-w-[1800px] mx-auto">
            <div className="flex justify-end mb-2">
              <button type="button" className="btn-ghost btn-sm" onClick={() => setFull(null)}><X size={14} /> Close</button>
            </div>
            <Panel model={open.model} robot={open.real ? effective(open.real, now) : null} big />
          </div>
        </div>)}
    </div>)
}

/** The lab's PCs: on / off from the LAN check (tools/lan_presence, nothing installed on the PC) and
 *  the PC agent's heartbeat; whether someone works at it comes from the security camera's PC boxes. */
function LabPcs() {
  const [cams, setCams] = useState<SecurityCamera[] | null>(null)
  const [pcs, setPcs] = useState<Awaited<ReturnType<typeof api.equipment>>>([])
  const staff = isStaff(useAuth().user)
  useEffect(() => {
    const load = () => {
      api.securityCameras().then(setCams).catch(() => setCams([]))
      if (staff) api.equipment().then(r => setPcs(r.filter(e => e.kind === 'PC'))).catch(() => {})
    }
    load(); const t = window.setInterval(load, 5000); return () => window.clearInterval(t)
  }, [staff])
  useLiveMessages(m => { if (m.type === 'pc_state' && staff) api.equipment().then(r => setPcs(r.filter(e => e.kind === 'PC'))).catch(() => {}) })
  const all = (cams ?? []).flatMap(c => c.zones ?? [])
  // The lab's real PCs (owner 2026-10-21: boxes named by the lab numbers, PC-03 removed from the lab):
  // every PC box on any camera plus every PC in the inventory. A PC seen by both cameras is "In use"
  // when either camera sees someone at it.
  const isPc = (n: string) => /^PC-\d+$/i.test(n)
  const names = Array.from(new Set([...all.map(z => String(z.name).toUpperCase()).filter(isPc),
                                    ...pcs.map(e => String(e.asset_tag ?? e.name).toUpperCase()).filter(isPc)]))
    .sort((a, b) => Number(a.slice(3)) - Number(b.slice(3)))
  const rank = (s: string) => (s === 'IN_USE' ? 3 : s === 'CHANGED' || s === 'MOTION' ? 2 : s === 'OK' ? 1 : 0)
  const zones = all.filter(z => isPc(String(z.name))).map(z => ({ ...z, name: String(z.name).toUpperCase() }))
    .sort((a, b) => rank(b.status) - rank(a.status))
  const word: Record<string, [string, string]> = {
    IN_USE: ['In use', 'border-sky-400/50 bg-sky-500/15 text-sky-200'],
    OK: ['Free', 'border-ok/40 bg-ok/10 text-ok-soft'],
    MOTION: ['Moved?', 'border-warn/50 bg-warn/15 text-warn-soft'],
    CHANGED: ['Looks different', 'border-bad/50 bg-bad/15 text-bad-soft'],
    LEARNING: ['Learning', 'border-ink-500 text-slate-400'],
  }
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Monitor size={16} className="text-accent-300" />
        <span className="font-semibold text-white">Lab PCs</span>
        <span className="text-[12px] text-slate-400">on / off over the lab LAN · details from the PC agent · use seen by the security camera</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2">
        {names.map(n => {
          const z = zones.find(x => x.name === n)
          const d = pcs.find(e => (e.asset_tag ?? e.name) === n)
          const st = d ? pcStatus(d) : null
          const stCls = !st ? 'text-slate-500' : st.tone === 'ok' ? 'text-ok-soft' : st.tone === 'warn' ? 'text-warn-soft'
            : st.tone === 'bad' ? 'text-bad-soft' : 'text-slate-300'
          // Camera and LAN together (owner 2026-10-21): a PC that is off on the LAN is not "in use" - someone
          // is only sitting there; on and nobody seated = free; off and nobody = off.
          const off = !!d?.lan && !d.lan.present
          const [w, cls] = z?.status === 'IN_USE' && off ? ['Seated · PC off', 'border-warn/50 bg-warn/15 text-warn-soft']
            : off && (!z || z.status === 'OK') ? ['Off', 'border-ink-600 text-slate-400']
            : z ? (word[z.status] ?? [z.status, 'border-ink-500 text-slate-300']) : ['No camera box', 'border-ink-600 text-slate-500']
          return (
            <div key={n} className="rounded-lg border border-ink-600/70 bg-ink-900/40 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-white font-medium">{n}</span>
                <span className={`text-[10.5px] uppercase ${stCls}`} title={d?.lan?.ip ? `LAN ${d.lan.ip} (${d.lan.via})` : undefined}>
                  {st ? st.word : 'not checked'}</span>
              </div>
              <span className={`mt-1.5 inline-block rounded-md border px-1.5 py-0.5 text-[11px] ${cls}`}>{w}</span>
            </div>)
        })}
      </div>
    </div>)
}

/** Named UR5e poses from the robot team's ROS 2 files (2026-10-16) - REFERENCE ONLY: shown in the
 *  twin, never sent. LAB_SEED = dynamic_scenario.py:261 (real lab runs since 2026-10-12), PLACE_SEED =
 *  pick_place.py:48. Owner 2026-10-16: show only Home, confirmed correct. */
/** Verified UR5e Home, read off the teach pendant (owner, 2026-10-17) - the same pose the backend homes to. */
const UR_HOME_DEG = [-15.00, -126.00, 117.03, -80.00, 91.00, 95.27]
const UR_POSES: { key: string; label: string; q: number[]; note: string }[] = [
  { key: 'home', label: 'Home', q: UR_HOME_DEG.map(v => v * Math.PI / 180), note: 'verified Home from the teach pendant (2026-10-17): -15.00, -126.00, 117.03, -80.00, 91.00, 95.27 deg' },
]

/** Who is driving the UR5e, as the controller reports it (read-only; see tools/robot_monitor/control_source.py). */
const SOURCE_LABEL: Record<string, [string, string]> = {
  HAND_GUIDING: ['Hand guiding', 'text-amber-300 border-amber-400/50'],
  PENDANT: ['Teach pendant', 'text-sky-300 border-sky-400/50'],
  PENDANT_PROGRAM: ['Program from the pendant', 'text-sky-300 border-sky-400/50'],
  MULTI_JOINT: ['Several joints - Move / Home or other', 'text-amber-300 border-amber-400/50'],
  EXTERNAL_CONTROL: ['Computer - External Control (ROS)', 'text-violet-300 border-violet-400/50'],
  REMOTE_PROGRAM: ['Network - program', 'text-violet-300 border-violet-400/50'],
  REMOTE_DIRECT: ['Network - direct commands', 'text-violet-300 border-violet-400/50'],
  IDLE: ['Idle', 'text-slate-300 border-ink-600'],
  UNKNOWN: ['Unknown', 'text-slate-400 border-ink-600'],
}
/** A security camera sees a person at this robot (its box on any camera is IN_USE) - polled every 5 s. */
function usePersonAt(robotName: string): boolean {
  const [at, setAt] = useState(false)
  useEffect(() => {
    const key = robotName.toLowerCase().startsWith('ur5') ? 'ur5' : robotName.toLowerCase().includes('fanuc') ? 'fanuc' : robotName.toLowerCase()
    let alive = true
    const load = () => api.securityCameras().then(cams => {
      if (alive) setAt(cams.some(c => (c.zones ?? []).some(z => z.status === 'IN_USE' && String(z.name).toLowerCase().startsWith(key))))
    }).catch(() => {})
    load()
    const t = window.setInterval(load, 5000)
    return () => { alive = false; window.clearInterval(t) }
  }, [robotName])
  return at
}

/** Owner 2026-10-19: one line saying who moves the robot - the controller's own report (pendant / network) plus
 *  the cameras (a person at the robot). Read-only. */
function ActivityLine({ robot, code }: { robot: Robot & { stale: boolean }; code: string | null }) {
  const person = usePersonAt(robot.model || robot.name)
  const moving = !robot.stale && robot.state === 'MOVING'
  // Owner 2026-10-21: "by teach pendant" was shown for every movement in Local mode (control_source.py).
  const by = code === 'PENDANT' ? 'by teach pendant (jogging)' : code === 'HAND_GUIDING' ? 'by hand guiding'
    : code === 'PENDANT_PROGRAM' ? 'program started on the pendant'
    : code === 'EXTERNAL_CONTROL' ? 'by a computer (External Control / ROS)'
    : code === 'MULTI_JOINT' ? 'several joints at once (pendant Move / Home, or another way)'
    : code?.startsWith('REMOTE') ? 'by network command' : null
  const [text, cls] = moving
    ? [`Moving${by ? ` - ${by}` : ''}${person ? ' - person at the robot' : ''}`, 'text-amber-200 border-amber-400/60 bg-amber-500/10']
    : person ? ['Still - person at the robot', 'text-sky-200 border-sky-400/50 bg-sky-500/10']
      : [robot.stale ? 'No live data' : 'Still - nobody at the robot', 'text-slate-300 border-ink-600']
  return <span className={`px-2 py-0.5 rounded-md border font-medium ${cls}`}>{text}</span>
}

function SourceLine({ robot }: { robot: Robot & { stale: boolean } }) {
  const code = robot.stale ? null : String(robot.extra?.control_source ?? '') || null
  const [label, cls] = code && SOURCE_LABEL[code] ? SOURCE_LABEL[code] : ['Not reported', 'text-slate-500 border-ink-600']
  return <div className="px-4 pt-3 flex flex-wrap items-center gap-2 text-[12px]">
    <ActivityLine robot={robot} code={code} />
    <span className="text-slate-400">Driven from:</span>
    <span className={`px-2 py-0.5 rounded-md border ${cls}`}>{label}</span>
    {code && robot.extra?.control_detail && <span className="text-slate-500">{String(robot.extra.control_detail)}</span>}
    {!code && <span className="text-slate-500">{robot.stale ? 'no live telemetry' : 'collector without Dashboard access'}</span>}
  </div>
}

/** Re-render a twin panel only when what it shows changes - the page clock ticks every second and
 *  re-rendering both 3D panels + their replay lists every tick made the tab sluggish. */
const samePanel = (a: PanelProps, b: PanelProps) => a.model.key === b.model.key && a.big === b.big &&
  a.robot?.state === b.robot?.state && a.robot?.stale === b.robot?.stale && a.robot?.device_id === b.robot?.device_id &&
  (a.robot?.q ?? []).join() === (b.robot?.q ?? []).join() && a.robot?.last_seen_at === b.robot?.last_seen_at &&
  JSON.stringify(a.robot?.extra ?? null) === JSON.stringify(b.robot?.extra ?? null)
type PanelProps = { model: RobotModel; robot: (Robot & { stale: boolean }) | null; onFull?: () => void; big?: boolean }
const Panel = memo(PanelInner, samePanel)
function PanelInner({ model, robot, onFull, big }: {
  model: RobotModel; robot: (Robot & { stale: boolean }) | null; onFull?: () => void; big?: boolean
}) {
  const [grip, setGrip] = useState(0)
  // Starting a 3D view blocks the browser ~0.5 s. Opening the tab used to start both at once, before
  // the page had even asked for its data (2026-10-19); now the page and data come first, then the
  // 3D views one after another while the browser is idle. The full view starts at once. Since shaders
  // compile without blocking (threeSetup, 2026-10-20) the idle wait is capped at 300 ms (was 1.5 s).
  const [mount3d, setMount3d] = useState(!!big)
  const live = !!robot && !robot.stale && !!robot.q && robot.q.length === 6
  // Instant picture (2026-10-21, "Robots & PCs very slow"): the profile showed the freeze is creating the two
  // WebGL contexts (~270 ms) and their extensions (~120 ms), not data. With a saved still of this robot, the
  // view starts as that picture and becomes live 3D only when it matters: the robot is LIVE (real motion),
  // or the user points at / clicks the view, or moves a joint. No still yet (first visit): 3D as before.
  const shotKey = `smartlab.twinShot.${model.key}`
  const [shot, setShot] = useState<string | null>(() => { try { return localStorage.getItem(shotKey) } catch { return null } })
  // A still is taken once and renewed weekly - not on every wake-up of the 3D view (each one cost a
  // ~250 ms freeze while the owner pointed at the robots, 2026-10-21).
  const [shotFresh] = useState(() => {
    try { return !!localStorage.getItem(shotKey) && Date.now() - Number(localStorage.getItem(`${shotKey}.at`) || 0) < 7 * 86400e3 }
    catch { return false }
  })
  const saveShot = useCallback((url: string) => {
    try { localStorage.setItem(shotKey, url); localStorage.setItem(`${shotKey}.at`, String(Date.now())) }
    catch { /* storage full: the 3D view still works */ }
  }, [shotKey])
  // 2026-10-27 (owner: "it freezes when I move the robot, then it disappears for a second"): the picture is only
  // the instant first view. The 3D now starts by itself shortly after the page settles (UR5e first, FANUC after
  // it, never both at once), or at once on a click / a slider; the picture stays ON TOP until the 3D has drawn
  // the robot (onReady) and then fades - no blank skeleton in between, and the sliders always move a live 3D.
  const [ready3d, setReady3d] = useState(false)
  const onReady = useCallback(() => setReady3d(true), [])
  useEffect(() => {
    warmTwins()
    if (mount3d) return
    const ric = (window as unknown as { requestIdleCallback?: (f: () => void, o?: { timeout: number }) => void }).requestIdleCallback
    const delay = shot && !live ? (model.key === 'FANUC' ? 2200 : 900) : (model.key === 'FANUC' ? 250 : 0)
    const t = window.setTimeout(() => ric ? ric(() => setMount3d(true), { timeout: 600 }) : setMount3d(true), delay)
    return () => window.clearTimeout(t)
  }, [mount3d, model.key, shot, live])
  // The 3D starts on a click only (or by itself when the robot is live). Starting it costs ~1 s of the
  // main thread (profiled 2026-10-21): a resting pointer used to start it while the owner just moved
  // around the page - each time a freeze nobody asked for.
  const wake = () => { if (!mount3d) setMount3d(true) }
  // Each robot's own home pose: UR5e upright (J2, J4 at -90 deg); FANUC all joints 0 with the
  // wrist J5 at -90 deg (the usual FANUC home - the lab's taught HOME may differ slightly).
  const homePose = model.key === 'FANUC' ? [0, 0, 0, 0, -Math.PI / 2, 0] : UR_HOME_DEG.map(v => v * Math.PI / 180)
  const [pose, setPose] = useState<number[]>(homePose)
  const [ref, setRef] = useState<string | null>(null)
  const refPose = model.key === 'UR5E' ? UR_POSES.find(p => p.key === ref) ?? null : null
  // Recorded movements of this robot, replayed in the twin (its own joint values, 10/s).
  const [replay, setReplay] = useState<ReplayFrame | null>(null)
  const q = replay ? replay.q : live ? robot!.q! : pose
  const urdf = urdfFor(model.key)
  const moving = !replay && live ? robot!.joints_moving ?? null : null
  const limits = useMemo(() => model.limitsDeg, [model])
  const wkey = model.key === 'FANUC' ? 'FANUC' : 'UR5E'
  // Shared by the card and its full view (same robot), kept while the page is open.
  const [cell, setCell] = useState<Workcell>(() => CELLS.get(wkey) ?? defaultWorkcell(wkey))
  const setCellShared = (c: Workcell) => { CELLS.set(wkey, c); setCell(c) }
  const [selObs, setSelObs] = useState<string | null>(null)
  const poseKnown = live || !robot          // preview pose is the user's own; a stale live pose is not
  const hits = useMemo(() => poseKnown ? collisions(urdf, q, cell, 0.06, wkey === 'UR5E' ? 0.15 : 0.10) : [],
                       [urdf, q, cell, poseKnown, wkey])
  // The FANUC has no measured cell: its table (if any) is drawn as a plain virtual box.
  const shown = useMemo(() => wkey === 'FANUC' && cell.table?.present
    ? { ...cell, obstacles: [...cell.obstacles, tableBox(cell.table)] } : cell, [cell, wkey])

  // Owner 2026-10-18: Full view at the top; joint bars right under the twin with just Home + STOP;
  // in the full view the right-hand column holds Home, STOP and the joint bars.
  const jointBars = <div className="space-y-2">
        {JOINTS.map((name, i) => {
          const [lo, hi] = limits[i]
          const deg = q[i] * DEG
          const pct = Math.max(0, Math.min(100, ((deg - lo) / (hi - lo)) * 100))
          const isMoving = !!moving?.[i]
          return (
            <div key={name} className="grid grid-cols-[88px_1fr_64px] items-center gap-2 text-[12px]">
              <span className={isMoving ? 'text-ok-soft font-semibold' : 'text-slate-300'}>{name}</span>
              {live ? (
                <div className="h-2.5 rounded-full bg-ink-700 overflow-hidden" title={`${lo}° … ${hi}°`}>
                  <div className={`h-full ${isMoving ? 'bg-ok' : 'bg-accent-400'}`} style={{ width: `${pct}%` }} />
                </div>
              ) : (
                <input type="range" min={lo} max={hi} step={0.5} value={deg} aria-label={`${name} (preview)`}
                       className="accent-violet-400 w-full"
                       onChange={e => { wake(); const v = [...pose]; v[i] = Number(e.target.value) / DEG; setPose(v) }} />
              )}
              <span className={`tnum text-right ${isMoving ? 'text-ok-soft' : 'text-slate-200'}`}>{deg.toFixed(1)}°</span>
            </div>)
        })}
        <div className="grid grid-cols-[88px_1fr_64px] items-center gap-2 text-[12px]">
          <span className="text-slate-300">J7 Gripper</span>
          {live ? <span className="text-slate-500">state not available from the robot</span>
                : <input type="range" min={0} max={100} value={Math.round(grip * 100)} aria-label="Gripper (preview)"
                         className="accent-violet-400 w-full" onChange={e => setGrip(Number(e.target.value) / 100)} />}
          <span className="tnum text-right text-slate-200">{live ? '—' : `${Math.round(grip * 100)}% closed`}</span>
        </div>
  </div>
  const still = shot ? <img src={shot} alt="" className="w-full h-full object-contain" draggable={false} /> : null
  const twinView = !mount3d ? (shot
      ? <button type="button" onClick={wake}
                className="relative block w-full h-72 bg-ink-950/40 group" aria-label={`${model.key === 'UR5E' ? 'UR5e' : 'FANUC'} - open the 3D view`}>
          <img src={shot} alt="" className="w-full h-full object-contain" draggable={false} />
          <span className="absolute bottom-2 right-2 rounded-md border border-ink-600 bg-ink-900/80 px-2 py-0.5 text-[11px] text-slate-300 group-hover:text-white">
            Click for the 3D view</span>
        </button>
      : <Skeleton className={`${big ? 'h-[78vh]' : 'h-72'} rounded-none`} />) : (
      <div className="relative">
      <Suspense fallback={still ? <div className={`${big ? 'h-[78vh]' : 'h-72'} bg-ink-950/40`}>{still}</div>
                                : <Skeleton className="h-72 rounded-none" />}>
        <RobotTwin onReady={onReady} model={model} q={q} homeQ={live && refPose ? refPose.q : null} moving={moving} compact={!big} views workcell={shown} hits={hits} selectedObstacle={selObs} className={`${big ? 'h-[78vh]' : 'h-72'} bg-ink-950/40`}
                   onSnapshot={big || live || shotFresh ? undefined : saveShot}
                   gripper={live || replay ? null : grip}
                   trail={replay ? replay.path.map(p => tipPosition(urdf, p)) : undefined} trailColor="#a78bfa"
                   onPose={live || replay ? undefined : setPose}
                   onJointDrag={live ? undefined : (j, d) => setPose(p => {
                     const v = [...p], [lo, hi] = limits[j]
                     v[j] = Math.max(lo / DEG, Math.min(hi / DEG, v[j] + d)); return v })} />
      </Suspense>
      {still && !big && <div aria-hidden className={`absolute inset-0 bg-ink-950/40 transition-opacity duration-300 ${ready3d ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>{still}</div>}
      </div>)
  const control = robot ? <RobotControlPanel robotId={robot.device_id} robotName={robot.name} /> : null
  return (
    <div className="card overflow-hidden">
      <div className="p-4 flex flex-wrap items-center gap-2 border-b border-ink-700/60">
        <Bot size={16} className="text-accent-300" />
        <span className="font-semibold text-white">{model.key === 'UR5E' ? 'UR5e' : 'FANUC'}</span>
        <span className="text-[12px] text-slate-400">{urdf.label}</span>
        <span className={`ml-auto rounded-md px-2 py-0.5 text-[11.5px] font-semibold border ${live
          ? 'border-ok/50 bg-ok/15 text-ok-soft' : 'border-violet-400/50 bg-violet-500/15 text-violet-200'}`}>
          {replay ? 'REPLAY · recorded movement' : live ? 'LIVE · physical robot' : 'PREVIEW · not the robot'}</span>
        {onFull && <button type="button" className="btn-primary btn-sm" onClick={onFull}><Maximize2 size={13} /> Full view</button>}
      </div>
      {big ? (
        <div className="lg:grid lg:grid-cols-[1fr_380px] lg:items-start">
          {twinView}
          <div className="p-4 space-y-4 lg:border-l border-ink-700/60">
            {control}
            {jointBars}
          </div>
        </div>
      ) : <>
      {twinView}
        {robot && <div className="px-4 pt-3 text-[13px]">
          <ActivityLine robot={robot} code={robot.stale ? null : String(robot.extra?.control_source ?? '') || null} /></div>}
        {model.key === 'FANUC' && <div className="px-4 pt-3 text-[12px] text-slate-400">
          <span className="text-slate-200 font-medium">{FANUC_CELL.name}</span> · {FANUC_CELL.width_m * 1000} × {FANUC_CELL.depth_m * 1000} × {FANUC_CELL.height_m * 1000} mm (W × D × H) · {FANUC_CELL.weight_kg} kg
          · robot {FANUC_CELL.robot} · controller {FANUC_CELL.controller}
          <div className="text-slate-500">Dimensions: <a className="link" href={FANUC_CELL.sourceUrl} target="_blank" rel="noreferrer">{FANUC_CELL.source}</a>. The 3D arm is an LR Mate 200iD stand-in; the cell's inner layout is approximate.</div></div>}
        <div className="p-4 pb-2">{jointBars}</div>
        {control && <div className="px-4 pb-2">{control}</div>}
      </>}
      {model.key === 'UR5E' && <div className="px-4 pt-3 flex flex-wrap items-center gap-1.5 text-[12px]">
        <span className="text-slate-400">Reference pose (not sent):</span>
        {UR_POSES.map(p => <button key={p.key} type="button" title={`${p.note}
${p.q.map(v => (v * 180 / Math.PI).toFixed(1) + '°').join(', ')}`}
          onClick={() => { setRef(r => r === p.key ? null : p.key); if (!live && !replay) setPose(p.q) }}
          className={`px-2 py-0.5 rounded-md border ${ref === p.key ? 'border-accent-400/70 bg-accent-500/15 text-white' : 'border-ink-600 text-slate-300'}`}>{p.label}</button>)}
        {refPose && <span className="text-slate-500">{live ? 'shown as a ghost over the live pose' : 'shown in the preview'} · {refPose.note}</span>}
      </div>}
      {model.key === 'UR5E' && robot && <SourceLine robot={robot} />}
      {robot && <div className="px-4 pt-3 border-b border-ink-700/60"><Replay robotId={robot.device_id} active onFrame={setReplay} /></div>}
      <div className="p-4 space-y-2">
        <div className="pt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-slate-400">
          {live ? <>
            <span className="flex items-center gap-1.5"><Radio size={13} />{robot!.rate_hz ? `${robot!.rate_hz} samples/s` : '—'}</span>
            <span>last sample {robot!.last_seen_at ? relative(robot!.last_seen_at) : '—'}</span>
            {robot!.telemetry_age_ms != null && <span title="Time since the collector last received a sample from the controller">
              sample age {Math.round(robot!.telemetry_age_ms)} ms</span>}
          </> : <>
            <span className="flex items-center gap-1.5"><Hand size={13} />
              {robot ? `Robot ${robot.state === 'OFFLINE' ? 'offline' : 'telemetry stale'}` : 'No telemetry yet'}
              {' '}- grab any part of the arm and drag it, or use the bars</span>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setPose(homePose)}>
              <RotateCcw size={13} /> Reset</button>
          </>}
          <span className="ml-auto flex gap-2">
            {robot && <Link to={`/robots/${robot.device_id}`} className="btn-ghost btn-sm">History <ChevronRight size={13} /></Link>}
          </span>
        </div>
        {urdf.toolLabel && <div className="text-[11.5px] text-slate-500">Tool: {urdf.toolLabel}</div>}
      </div>
      <WorkcellEditor robotKey={wkey} cell={cell} onChange={setCellShared} hits={hits} selected={selObs}
                      onSelect={setSelObs} poseKnown={poseKnown} />
    </div>)
}
