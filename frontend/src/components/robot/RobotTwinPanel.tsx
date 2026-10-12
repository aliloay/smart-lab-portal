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
import { Bot, ChevronRight, Hand, Radio, RotateCcw } from 'lucide-react'
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
  return (
    <div className="grid xl:grid-cols-2 gap-4">
      {panels.map(p => <Panel key={p.key} model={p.model} robot={p.real ? effective(p.real, now) : null} />)}
    </div>)
}

function Panel({ model, robot }: { model: RobotModel; robot: (Robot & { stale: boolean }) | null }) {
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
        <RobotTwin model={model} q={q} moving={moving} compact className="h-72 bg-ink-950/40" />
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
        <div className="pt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-slate-400">
          {live ? <>
            <span className="flex items-center gap-1.5"><Radio size={13} />{robot!.rate_hz ? `${robot!.rate_hz} samples/s` : '—'}</span>
            <span>last sample {robot!.last_seen_at ? relative(robot!.last_seen_at) : '—'}</span>
          </> : <>
            <span className="flex items-center gap-1.5"><Hand size={13} />
              {robot ? `Robot ${robot.state === 'OFFLINE' ? 'offline' : 'telemetry stale'} - drag the bars to pose the preview`
                     : 'No telemetry from this robot yet - drag the bars to pose the preview'}</span>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setPose([0, -Math.PI / 2, 0, -Math.PI / 2, 0, 0])}>
              <RotateCcw size={13} /> Reset</button>
          </>}
          {robot && <Link to={`/robots/${robot.device_id}`} className="ml-auto btn-ghost btn-sm">Details <ChevronRight size={13} /></Link>}
        </div>
        {urdf.toolLabel && <div className="text-[11.5px] text-slate-500">Tool: {urdf.toolLabel}</div>}
      </div>
    </div>)
}
