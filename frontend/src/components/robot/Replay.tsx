/**
 * 3D replay of a recorded movement: the robot's own joint values as its
 * collector recorded them (10 a second, robot_state.py), played back in the
 * twin - not a reconstruction. Play / pause, speed, scrub; the tool path of
 * the whole movement is drawn.
 */
import { useEffect, useRef, useState } from 'react'
import { History, Pause, Play, X } from 'lucide-react'
import { RobotEventRow, api } from '../../lib/api'
import { relative } from '../../lib/time'

export interface ReplayFrame { q: number[]; t: number; duration: number; path: number[][] }

export default function Replay({ robotId, onFrame, active }: {
  robotId: number
  /** Called with the pose to show, or null when the replay ends (back to live). */
  onFrame: (f: ReplayFrame | null) => void
  active: boolean
}) {
  const [moves, setMoves] = useState<RobotEventRow[] | null>(null)
  const [tr, setTr] = useState<{ id: number; t: number[]; q: number[][] } | null>(null)
  const [pos, setPos] = useState(0)                // seconds into the movement
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const raf = useRef(0)

  useEffect(() => { api.robotMovements(robotId, 20).then(setMoves).catch(() => setMoves([])) }, [robotId])
  useEffect(() => { if (!active) { setTr(null); setPlaying(false) } }, [active])

  const duration = tr ? tr.t[tr.t.length - 1] ?? 0 : 0
  // Pose at time `pos`: linear between the two recorded samples around it.
  useEffect(() => {
    if (!tr || !tr.t.length) return
    let i = tr.t.findIndex(t => t >= pos)
    if (i <= 0) i = i === -1 ? tr.t.length - 1 : 0
    const a = Math.max(0, i - 1), t0 = tr.t[a], t1 = tr.t[i]
    const k = t1 > t0 ? Math.min(1, Math.max(0, (pos - t0) / (t1 - t0))) : 1
    const q = tr.q[a].map((v, j) => v + (tr.q[i][j] - v) * k)
    onFrame({ q, t: pos, duration, path: tr.q })
  }, [tr, pos])                                    // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!playing) return
    let last = performance.now()
    const step = (now: number) => {
      const dt = (now - last) / 1000
      last = now
      setPos(p => {
        const n = p + dt * speed
        if (n >= duration) { setPlaying(false); return duration }
        return n
      })
      raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [playing, speed, duration])

  async function open(e: RobotEventRow) {
    const m = await api.robotMovement(robotId, e.id)
    setTr({ id: e.id, ...m.trajectory })
    setPos(0)
    setPlaying(true)
  }
  function close() { setTr(null); setPlaying(false); onFrame(null) }

  return (
    <div className="card p-4 space-y-3">
      <div className="label flex items-center gap-1.5"><History size={13} /> Replay a movement
        {tr && <button className="ml-auto btn-ghost btn-sm normal-case tracking-normal" onClick={close}><X size={12} /> Back to live</button>}
      </div>
      {tr ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <button className="btn-primary btn-sm" onClick={() => { if (pos >= duration) setPos(0); setPlaying(p => !p) }}
                    aria-label={playing ? 'Pause' : 'Play'}>{playing ? <Pause size={13} /> : <Play size={13} />}</button>
            <input type="range" min={0} max={duration || 0.01} step={0.05} value={pos} className="flex-1 accent-sky-400"
                   onChange={e => { setPlaying(false); setPos(Number(e.target.value)) }} aria-label="Replay position" />
            <span className="mono text-[12px] text-slate-300 tnum w-20 text-right">{pos.toFixed(1)} / {duration.toFixed(1)} s</span>
          </div>
          <div className="flex gap-1.5 text-[12px]">
            {[0.5, 1, 2, 4].map(s => <button key={s} className={`btn-sm ${speed === s ? 'btn-primary' : 'btn-ghost'}`}
                                             onClick={() => setSpeed(s)}>{s}x</button>)}
            <span className="ml-auto self-center text-slate-500">recorded joint values, {tr.t.length} samples</span>
          </div>
        </div>
      ) : moves === null ? <p className="text-[12.5px] text-slate-500">Loading…</p> : !moves.length ? (
        <p className="text-[12.5px] text-slate-500">No recorded movement yet - every movement is kept with its path once it ends.</p>
      ) : (
        <ul className="space-y-1 max-h-44 overflow-auto text-[12.5px]">
          {moves.map(m => (
            <li key={m.id}>
              <button className="w-full flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-ink-700/40 text-left" onClick={() => open(m)}>
                <Play size={12} className="text-accent-300" />
                <span className="text-slate-200">{new Date(m.occurred_at).toLocaleTimeString()}</span>
                <span className="text-slate-500">{relative(m.occurred_at)}</span>
                <span className="ml-auto mono text-slate-400">{Number((m.detail as { duration_s?: number } | null)?.duration_s ?? 0).toFixed(1)} s</span>
                {m.provenance === 'DEMO_DATA' && <span className="text-violet-300 text-[11px]">demo</span>}
              </button>
            </li>))}
        </ul>)}
    </div>)
}
