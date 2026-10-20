/**
 * Welcome page: a hand-movable robot - the same twin and the same grab/drag
 * (IK) as the Equipment preview. Local pose only: nothing is sent to a robot.
 */
import { useState } from 'react'
import RobotTwin from '../robot/RobotTwin'
import { MODELS } from '../robot/kinematics'

const DEG = 180 / Math.PI
const START: Record<'UR5E' | 'FANUC', number[]> = {
  UR5E: [0, -1.2, 1.5, -1.9, -1.57, 0],
  FANUC: [0, 0.2, -0.3, 0, -0.9, 0],
}

export default function DragTwin({ robot, className = '' }: { robot: 'UR5E' | 'FANUC'; className?: string }) {
  const model = MODELS[robot]
  const [q, setQ] = useState(START[robot])
  const [n, setN] = useState(0)
  return (
    <div className={`relative ${className}`}>
      <RobotTwin model={model} q={q} compact resetKey={n} className="h-full" label={`${model.label} - drag any part to move it`}
                 onPose={setQ}
                 onJointDrag={(j, d) => setQ(p => {
                   const v = [...p], [lo, hi] = model.limitsDeg[j]
                   v[j] = Math.max(lo / DEG, Math.min(hi / DEG, v[j] + d)); return v })} />
      <button type="button" onClick={() => { setQ(START[robot]); setN(k => k + 1) }}
              className="absolute top-2 right-2 px-2 py-0.5 rounded-md text-[11px] border border-ink-600 bg-ink-900/80 text-slate-300 hover:text-white">
        Reset pose</button>
    </div>)
}
