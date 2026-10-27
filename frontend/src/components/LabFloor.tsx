/**
 * The Robotics Lab from above - a live schematic (not to scale), every mark
 * driven by real state:
 *   robots   their telemetry state (pulse while moving), HOME, fusion
 *   PCs      the camera's box for each PC (in use / changed / moving / ok)
 *   door     the door controller, or the camera's view of the red door leaf
 *   people   counts only: the camera sees people in its picture, not on the
 *            floor, so nobody is drawn at a made-up position
 * Approximate top view based on the 2026-10-07 camera image and the lab
 * engineer's description: the entrance, FANUC, and camera share the lower
 * long side; the UR5e is opposite; lab PCs are in the middle; the engineer's
 * desk (PC-01, PC-04) and the desk in front of it (PC-02, PC-03) are across from
 * the entrance (owner's numbering, 2026-10-27). This is not surveyed.
 */
import { Link } from 'react-router-dom'
import { MonitorTile, Robot, SecurityCamera } from '../lib/api'

type ZoneStatus = 'LEARNING' | 'OK' | 'IN_USE' | 'CHANGED' | 'MOTION'
const PC_FILL: Record<string, string> = {
  IN_USE: '#38bdf8', CHANGED: '#f87171', MOTION: '#fbbf24', OK: '#334155', LEARNING: '#1e293b',
}
const ROBOT_COLOR: Record<string, string> = {
  MOVING: '#22c55e', STATIONARY: '#38bdf8', TELEMETRY_STALE: '#fbbf24', OFFLINE: '#f87171', UNKNOWN: '#64748b',
}

function pcState(cam: SecurityCamera | null, name: string, other?: SecurityCamera | null): ZoneStatus | null {
  // Either camera may have the PC boxed (2026-10-27: camera 2 sees PC-05..13); the first that does decides.
  const z = cam?.zones.find(z => z.name.toUpperCase() === name) ?? other?.zones.find(z => z.name.toUpperCase() === name)
  return (z?.status as ZoneStatus) ?? null
}

function RobotCell({ x, y, w, h, label, robot, frame }: {
  x: number; y: number; w: number; h: number; label: string; robot: Robot | undefined; frame: 'cage' | 'gantry'
}) {
  const st = robot?.state ?? 'UNKNOWN'
  const c = ROBOT_COLOR[st] ?? ROBOT_COLOR.UNKNOWN
  const moving = st === 'MOVING'
  const body = (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={1.5} fill="#0b1220" stroke={c} strokeWidth={0.45}
            strokeDasharray={frame === 'cage' ? '1.4 0.8' : undefined} opacity={0.95} />
      {frame === 'gantry' && <>
        <line x1={x + 1} y1={y + 1} x2={x + w - 1} y2={y + h - 1} stroke="#334155" strokeWidth={0.3} />
        <line x1={x + w - 1} y1={y + 1} x2={x + 1} y2={y + h - 1} stroke="#334155" strokeWidth={0.3} />
      </>}
      {moving && <circle cx={x + w / 2} cy={y + h / 2} r={Math.min(w, h) / 2.2} fill="none" stroke={c} strokeWidth={0.4}>
        <animate attributeName="r" from={Math.min(w, h) / 5} to={Math.min(w, h) / 1.6} dur="1.6s" repeatCount="indefinite" />
        <animate attributeName="opacity" from="0.9" to="0" dur="1.6s" repeatCount="indefinite" />
      </circle>}
      <circle cx={x + w / 2} cy={y + h / 2} r={1.8} fill={c} />
      <text x={x + w / 2} y={y - 1.2} textAnchor="middle" fontSize={2.3} fill="#e2e8f0" fontWeight={600}>{label}</text>
      <text x={x + w / 2} y={y + h + 2.8} textAnchor="middle" fontSize={1.8} fill={c}>
        {robot ? (robot.demo ? `${st.toLowerCase()} · demo` : st.toLowerCase().replace('_', ' ')) : 'not connected'}</text>
    </g>)
  return robot ? <Link to={`/robots/${robot.device_id}`}>{body}</Link> : body
}

const camLabel = (c: SecurityCamera | null | undefined) => !c || c.online == null || c.source_ok == null
  ? 'unknown' : c.online === false ? 'offline' : c.source_ok === false ? 'no frames' : 'live'

export default function LabFloor({ tile, cam, cams = [], robots, compact = false }: {
  tile: MonitorTile | null; cam: SecurityCamera | null
  /** Every camera of this lab (2026-10-27): camera 1 is drawn at the lower-right corner, camera 2 diagonally
   *  opposite (upper-left), as mounted. Without it only `cam` is drawn. */
  cams?: SecurityCamera[]
  robots: Robot[]; compact?: boolean
}) {
  const ordered = cams.length ? [...cams].sort((a, b) => a.device_uid.localeCompare(b.device_uid)) : cam ? [cam] : []
  const cam1 = ordered[0] ?? null
  const cam2 = ordered[1] ?? null
  const ur = robots.find(r => (r.model ?? '').toUpperCase().includes('UR') && !r.demo)
    ?? robots.find(r => (r.model ?? '').toUpperCase().includes('UR'))
  const fanuc = robots.find(r => (r.model ?? '').toUpperCase().includes('FANUC') && !r.demo)
    ?? robots.find(r => (r.model ?? '').toUpperCase().includes('FANUC'))
  const doorOpen = tile?.controller_online ? tile.door_closed === false : cam1?.door_open ?? cam2?.door_open ?? null
  // Owner's numbering (2026-10-27): central table PC-05..09 on the near row, PC-15..10 on the far row (left to
  // right); the engineer's desk PC-01 + PC-04; the desk in front of it PC-02 + PC-03 (PC-03 currently removed).
  const pcName = (n: number) => `PC-${String(n).padStart(2, '0')}`
  const rowA = [5, 6, 7, 8, 9].map(pcName)
  const rowB = [15, 14, 13, 12, 11, 10].map(pcName)
  const REMOVED = new Set(['PC-03'])
  const Pc = ({ n, x, y, w = 4.6, h = 3.2 }: { n: string; x: number; y: number; w?: number; h?: number }) => {
    const st = pcState(cam1, n, cam2)
    const gone = REMOVED.has(n)
    const lightFill = st === 'IN_USE' || st === 'MOTION'
    return (
      <g>
        <rect x={x} y={y} width={w} height={h} rx={0.6} fill={gone ? '#0b1220' : st ? PC_FILL[st] : '#1e293b'}
              stroke={gone ? '#f87171' : '#475569'} strokeWidth={0.2} strokeDasharray={gone ? '0.6 0.4' : undefined}>
          {st === 'IN_USE' && !gone && <animate attributeName="opacity" values="1;0.65;1" dur="2.4s" repeatCount="indefinite" />}
        </rect>
        {gone && <path d={`M ${x + 0.6} ${y + 0.6} L ${x + w - 0.6} ${y + h - 0.6} M ${x + w - 0.6} ${y + 0.6} L ${x + 0.6} ${y + h - 0.6}`}
                       stroke="#f87171" strokeWidth={0.3} />}
        <text x={x + w / 2} y={y + h / 2 + 0.45} textAnchor="middle" fontSize={1.25} fontWeight={600}
              fill={gone ? '#fca5a5' : lightFill ? '#0b1220' : '#cbd5e1'}>{gone ? '' : n}</text>
        {gone && <text x={x + w / 2} y={y + h + 1.6} textAnchor="middle" fontSize={1.1} fill="#fca5a5">{n} removed</text>}
      </g>)
  }
  // A reachable vision service is not a live picture unless its source is
  // reporting frames as well.
  const live = cam1?.online === true && cam1.source_ok === true
  const live2 = cam2?.online === true && cam2.source_ok === true
  const cameraLabel = camLabel(cam1)
  return (
    <div className={'relative ' + (compact ? 'lab-floor--wall' : '')}>
      <div className="relative z-10 mb-2 flex shrink-0 flex-wrap items-center justify-start gap-x-4 gap-y-1 border-b border-white/[.06] bg-[#0d131a] px-2 py-1 text-[11.5px] text-slate-300">
        <span><b className="text-white tnum">{tile?.people.length ?? 0}</b> inside (door)</span>
        {/* Two cameras can see the same person: each count on its own, never added up. */}
        <span><b className="text-white tnum">{cam1?.online ? cam1.people ?? 0 : '–'}</b> seen by camera{cam2 ? ' 1' : ''}</span>
        {cam2 && <span><b className="text-white tnum">{cam2.online ? cam2.people ?? 0 : '–'}</b> seen by camera 2</span>}
        {tile?.environment?.temperature && <span><b className="text-white tnum">{tile.environment.temperature.value.toFixed(1)}</b>{tile.environment.temperature.unit}</span>}
      </div>
      <svg viewBox="0 0 100 62" className="w-full h-auto select-none" role="img"
           aria-label="Robotics Lab floor plan with live robot, PC, door and people state">
        <defs>
          <pattern id="grid" width="4" height="4" patternUnits="userSpaceOnUse">
            <path d="M 4 0 L 0 0 0 4" fill="none" stroke="#1e293b" strokeWidth="0.15" />
          </pattern>
          <linearGradient id="cone" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0" stopColor="#38bdf8" stopOpacity="0.22" />
            <stop offset="1" stopColor="#38bdf8" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x={2} y={4} width={96} height={54} rx={2} fill="url(#grid)" stroke="#475569" strokeWidth={0.5} />
        {/* windows along the wall opposite the door, behind the engineer desk and the UR5e (owner 2026-10-27) */}
        {[16, 30, 44, 58, 72, 86].map(x => <line key={x} x1={x} y1={4} x2={x + 8} y2={4} stroke="#7dd3fc" strokeWidth={0.9} opacity={0.6} />)}
        <text x={50} y={6.4} textAnchor="middle" fontSize={1.5} fill="#64748b">windows</text>
        {/* Entrance on the same long side as FANUC and the security camera. */}
        <g>
          <rect x={9} y={56.4} width={10} height={1.6} fill={doorOpen ? '#f87171' : doorOpen === false ? '#22c55e' : '#64748b'} />
          {doorOpen && <path d="M 19 56.4 A 10 10 0 0 0 29 46.4" fill="none" stroke="#f87171" strokeWidth={0.35} strokeDasharray="1 0.6" />}
          <text x={9} y={54.5} fontSize={2} fill="#cbd5e1">Door {doorOpen == null ? '· no data' : doorOpen ? '· OPEN' : '· closed'}</text>
        </g>
        {/* Security camera view is drawn behind furniture and status marks. */}
        <path d="M 95 57 L 9 11 L 16 47 Z" fill="url(#cone)" opacity={live ? 1 : 0.25} />
        {cam2 && <path d="M 4 5.5 L 92 38 L 70 55 Z" fill="url(#cone)" opacity={live2 ? 0.8 : 0.2} />}
        {/* FANUC and UR5e sit along opposite long sides, near each other. */}
        <RobotCell x={50} y={45.5} w={9} h={8} label="FANUC" robot={fanuc} frame="cage" />
        <RobotCell x={76} y={10} w={14} h={11} label="UR5e" robot={ur} frame="gantry" />
        {/* Central table: two rows facing each other (5 + 6 PCs). Names sit INSIDE their boxes - nothing below
            them to collide with the next row. */}
        <text x={52} y={29.4} textAnchor="middle" fontSize={1.7} fill="#64748b">Central PC table · 05–15</text>
        <rect x={32} y={30.6} width={40} height={10} rx={1} fill="#111827" stroke="#334155" strokeWidth={0.3} />
        {rowA.map((n, i) => <Pc key={n} n={n} x={34.6 + i * 7} y={31.4} />)}
        {rowB.map((n, i) => <Pc key={n} n={n} x={33.2 + i * 6.4} y={36.6} />)}
        {/* The engineer's desk (PC-01, PC-04) and the desk in front of it (PC-02, PC-03), across from the door. */}
        <rect x={6} y={12} width={10} height={17} rx={0.8} fill="#111827" stroke="#334155" strokeWidth={0.3} />
        <text x={11} y={14.2} textAnchor="middle" fontSize={1.5} fill="#94a3b8">Lab engineer</text>
        <Pc n="PC-01" x={8.7} y={16} />
        <Pc n="PC-04" x={8.7} y={22.4} />
        <rect x={19} y={12} width={9} height={17} rx={0.8} fill="#111827" stroke="#334155" strokeWidth={0.3} />
        <text x={23.5} y={14.2} textAnchor="middle" fontSize={1.5} fill="#94a3b8">Front desk</text>
        <Pc n="PC-02" x={21.2} y={16} />
        <Pc n="PC-03" x={21.2} y={22.4} />
        {/* Security camera at the lower-right corner, facing back across the room. */}
        <path d="M 92.5 56.5 h3.2 l1.3 -1.5 v-2 h-5.8 z" fill={live ? '#38bdf8' : '#64748b'} stroke="#cbd5e1" strokeWidth={0.25} />
        <text x={96.8} y={51.6} textAnchor="end" fontSize={1.7} fill="#94a3b8">Camera{cam2 ? ' 1' : ''} · {cameraLabel}</text>
        {/* Camera 2, diagonally opposite camera 1 (docs/LAB_GO_NOGO_2026-10-18.md 1.3), facing back across the room. */}
        {cam2 && <g>
          <path d="M 7.5 5.5 h-3.2 l-1.3 1.5 v2 h5.8 z" fill={live2 ? '#38bdf8' : '#64748b'} stroke="#cbd5e1" strokeWidth={0.25} />
          <text x={9.2} y={8.4} fontSize={1.7} fill="#94a3b8">Camera 2 · {camLabel(cam2)}</text>
        </g>}
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500">
        <span><i className="inline-block w-2 h-2 rounded-sm align-middle mr-1" style={{ background: PC_FILL.IN_USE }} />PC in use</span>
        <span><i className="inline-block w-2 h-2 rounded-sm align-middle mr-1" style={{ background: PC_FILL.CHANGED }} />changed</span>
        <span><i className="inline-block w-2 h-2 rounded-sm align-middle mr-1" style={{ background: PC_FILL.MOTION }} />moving, nobody at it</span>
        <span><i className="inline-block w-2 h-2 rounded-full align-middle mr-1" style={{ background: ROBOT_COLOR.MOVING }} />robot moving</span>
        <span className="ml-auto">Approximate schematic, not to scale · people are counted, not placed</span>
      </div>
    </div>)
}
