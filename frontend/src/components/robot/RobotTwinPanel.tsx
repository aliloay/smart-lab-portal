/**
 * Robots in Equipment -> Robots & PCs: one panel per physical robot.
 *
 *   LIVE     fresh telemetry from the robot (not a simulation): the twin and the
 *            six joint bars follow the real joints; the bars are read-only.
 *   PREVIEW  no live data: the twin can be posed with the six bars (mouse) to
 *            study the arm. Nothing is ever sent to a robot - this is drawing only,
 *            and the panel says PREVIEW so it is never mistaken for the robot.
 */
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bot, ChevronRight, Hand, Maximize2, Monitor, Radio, RotateCcw, X } from 'lucide-react'
import { api, SecurityCamera } from '../../lib/api'
import { Robot } from '../../lib/api'
import { relative } from '../../lib/time'
import { Skeleton } from '../ui'
import { MODELS, RobotModel } from './kinematics'
import { effective, useRobots } from './robotLive'
import { urdfFor } from './robotModels'

const RobotTwin = lazy(() => import('./RobotTwin'))
const JOINTS = ['J1 Base', 'J2 Shoulder', 'J3 Elbow', 'J4 Wrist 1', 'J5 Wrist 2', 'J6 Wrist 3']
const DEG = 180 / Math.PI

export default function RobotTwinPanels() {
  const { robots } = useRobots()
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(t) }, [])
  // One panel per physical robot model; its live record when one reports.
  const panels = (['UR5E', 'FANUC'] as const).map(key => {
    const model = MODELS[key]
    const rs = (robots ?? []).filter(r => (r.model || '').toUpperCase().includes(key === 'UR5E' ? 'UR5' : 'FANUC'))
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
          <div className="max-w-6xl mx-auto">
            <div className="flex justify-end mb-2">
              <button type="button" className="btn-ghost btn-sm" onClick={() => setFull(null)}><X size={14} /> Close</button>
            </div>
            <Panel model={open.model} robot={open.real ? effective(open.real, now) : null} big />
          </div>
        </div>)}
    </div>)
}

/** The lab's PCs: no PC agent yet, so each is OFFLINE as a device; whether
 *  someone works at it comes from the security camera's PC boxes. */
function LabPcs() {
  const [cams, setCams] = useState<SecurityCamera[] | null>(null)
  useEffect(() => {
    const load = () => api.securityCameras().then(setCams).catch(() => setCams([]))
    load(); const t = window.setInterval(load, 3000); return () => window.clearInterval(t)
  }, [])
  const zones = (cams ?? []).flatMap(c => c.zones ?? [])
  const names = Array.from({ length: 11 }, (_, i) => `PC-${String(i + 1).padStart(2, '0')}`)
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
        <span className="text-[12px] text-slate-400">device OFFLINE until its PC agent is installed · use seen by the security camera</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2">
        {names.map(n => {
          const z = zones.find(x => x.name === n)
          const [w, cls] = z ? (word[z.status] ?? [z.status, 'border-ink-500 text-slate-300']) : ['No camera box', 'border-ink-600 text-slate-500']
          return (
            <div key={n} className="rounded-lg border border-ink-600/70 bg-ink-900/40 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-white font-medium">{n}</span>
                <span className="text-[10.5px] text-slate-500">OFFLINE</span>
              </div>
              <span className={`mt-1.5 inline-block rounded-md border px-1.5 py-0.5 text-[11px] ${cls}`}>{w}</span>
            </div>)
        })}
      </div>
    </div>)
}

function Panel({ model, robot, onFull, big }: {
  model: RobotModel; robot: (Robot & { stale: boolean }) | null; onFull?: () => void; big?: boolean
}) {
  const [grip, setGrip] = useState(0)
  const live = !!robot && !robot.stale && !!robot.q && robot.q.length === 6
  const [pose, setPose] = useState<number[]>([0, -Math.PI / 2, 0, -Math.PI / 2, 0, 0])
  const q = live ? robot!.q! : pose
  const urdf = urdfFor(model.key)
  const moving = live ? robot!.joints_moving ?? null : null
  const limits = useMemo(() => model.limitsDeg, [model])

  return (
    <div className="card overflow-hidden">
      <div className="p-4 flex flex-wrap items-center gap-2 border-b border-ink-700/60">
        <Bot size={16} className="text-accent-300" />
        <span className="font-semibold text-white">{model.key === 'UR5E' ? 'UR5e' : 'FANUC'}</span>
        <span className="text-[12px] text-slate-400">{urdf.label}</span>
        <span className={`ml-auto rounded-md px-2 py-0.5 text-[11.5px] font-semibold border ${live
          ? 'border-ok/50 bg-ok/15 text-ok-soft' : 'border-violet-400/50 bg-violet-500/15 text-violet-200'}`}>
          {live ? 'LIVE · physical robot' : 'PREVIEW · not the robot'}</span>
      </div>
      <Suspense fallback={<Skeleton className="h-72 rounded-none" />}>
        <RobotTwin model={model} q={q} moving={moving} compact={!big} className={`${big ? 'h-[62vh]' : 'h-72'} bg-ink-950/40`}
                   gripper={live ? null : grip}
                   onJointDrag={live ? undefined : (j, d) => setPose(p => {
                     const v = [...p], [lo, hi] = limits[j]
                     v[j] = Math.max(lo / DEG, Math.min(hi / DEG, v[j] + d)); return v })} />
      </Suspense>
      <div className="p-4 space-y-2">
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
                       onChange={e => { const v = [...pose]; v[i] = Number(e.target.value) / DEG; setPose(v) }} />
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
        <div className="pt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-slate-400">
          {live ? <>
            <span className="flex items-center gap-1.5"><Radio size={13} />{robot!.rate_hz ? `${robot!.rate_hz} samples/s` : '—'}</span>
            <span>last sample {robot!.last_seen_at ? relative(robot!.last_seen_at) : '—'}</span>
          </> : <>
            <span className="flex items-center gap-1.5"><Hand size={13} />
              {robot ? `Robot ${robot.state === 'OFFLINE' ? 'offline' : 'telemetry stale'}` : 'No telemetry yet'}
              {' '}- hold a link and drag, or use the bars</span>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setPose([0, -Math.PI / 2, 0, -Math.PI / 2, 0, 0])}>
              <RotateCcw size={13} /> Reset</button>
          </>}
          <span className="ml-auto flex gap-2">
            {onFull && <button type="button" className="btn-ghost btn-sm" onClick={onFull}><Maximize2 size={13} /> Full view</button>}
            {robot && <Link to={`/robots/${robot.device_id}`} className="btn-ghost btn-sm">History <ChevronRight size={13} /></Link>}
          </span>
        </div>
        {urdf.toolLabel && <div className="text-[11.5px] text-slate-500">Tool: {urdf.toolLabel}</div>}
      </div>
    </div>)
}
