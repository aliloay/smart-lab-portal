/**
 * Robotics overview. Students: availability (state, home) only. Staff: a live
 * 3D twin per robot from its telemetry, telemetry health, a link to the full
 * robot page. Monitoring only - nothing here can move a robot.
 */
import { Suspense, lazy, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bot, ChevronRight, Radio } from 'lucide-react'
import { isStaff, useAuth } from '../lib/auth'
import { relative } from '../lib/time'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../components/ui'
import { modelFor } from '../components/robot/kinematics'
import { DemoBadge, FusionChip, HomeChip, RobotStateChip, useRobots } from '../components/robot/robotLive'

const RobotTwin = lazy(() => import('../components/robot/RobotTwin'))

export default function Robots() {
  const { user } = useAuth()
  const staff = isStaff(user)
  const [showDemos, setShowDemos] = useState(false)
  const { robots, stoppedDemos, error } = useRobots({ includeStoppedDemos: showDemos })
  return (
    <div className="space-y-5">
      <PageHeader eyebrow="Robotics" title="Robots"
        sub={staff ? 'Live state of every robot from its read-only telemetry. Monitoring only: the portal cannot move a robot.'
                   : 'Which robots are available right now.'} />
      {error && <ErrorBanner message={error} />}
      {staff && stoppedDemos > 0 && <label className="flex items-center gap-2 text-[12.5px] text-slate-400 w-fit">
        <input type="checkbox" className="accent-violet-500" checked={showDemos} onChange={e => setShowDemos(e.target.checked)} />
        Show {stoppedDemos} stopped simulation{stoppedDemos > 1 ? 's' : ''}</label>}
      {robots === null ? <div className="grid md:grid-cols-2 gap-4"><Skeleton className="h-80" /><Skeleton className="h-80" /></div>
        : !robots.length ? (
          <div className="card"><EmptyState icon={<Bot size={18} />} title="No robot is reporting yet"
            detail="A robot appears here once its read-only collector runs on the lab laptop (tools/robot_monitor). The UR5e needs the lab network switch; the FANUC's interface is being identified." /></div>
        ) : (
          <div className="grid lg:grid-cols-2 gap-4">
            {robots.map(r => {
              const model = modelFor(r.model)
              return (
                <div key={r.device_id} className="card overflow-hidden">
                  <div className="p-4 flex flex-wrap items-center gap-2 border-b border-ink-700/60">
                    <Bot size={16} className="text-accent-300" />
                    <span className="font-semibold text-white">{r.name}</span>
                    <span className="text-[12px] text-slate-400">{model.label}</span>
                    <span className="ml-auto flex flex-wrap gap-1.5">
                      {r.demo && <DemoBadge />}
                      <RobotStateChip state={r.state} />
                      <HomeChip home={r.home} state={r.state} />
                      {staff && <FusionChip fusion={r.fusion} />}
                    </span>
                  </div>
                  {staff ? (
                    <>
                      <Suspense fallback={<Skeleton className="h-64 rounded-none" />}>
                        <RobotTwin model={model} q={r.q ?? null} moving={r.joints_moving} stale={r.stale} compact className="h-64 bg-ink-950/40" />
                      </Suspense>
                      <div className="p-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-[12.5px] text-slate-400">
                        <span className="flex items-center gap-1.5"><Radio size={13} />
                          {r.rate_hz ? `${r.rate_hz} samples/s` : 'no rate yet'}</span>
                        <span>source {r.source ?? '—'}</span>
                        <span>last report {r.last_seen_at ? relative(r.last_seen_at) : 'never'}</span>
                        {!model.exact && <span className="text-warn-soft" title="The lab arm is an ER-4iA; the 3D arm uses LR Mate 200iD meshes and link lengths as a stand-in">3D arm: stand-in geometry</span>}
                        <Link to={`/robots/${r.device_id}`} className="ml-auto btn-ghost btn-sm">
                          Open <ChevronRight size={13} /></Link>
                      </div>
                    </>
                  ) : (
                    <div className="p-4 text-[13px] text-slate-300">
                      {r.state === 'MOVING' ? 'In use right now.' : r.state === 'STATIONARY' ? 'Not moving.' : 'Status not available.'}
                      {' '}Book it from the laboratory's page.</div>
                  )}
                </div>)
            })}
          </div>)}
    </div>)
}
