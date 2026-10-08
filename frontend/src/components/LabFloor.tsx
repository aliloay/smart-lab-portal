/**
 * The Robotics Lab from above - a live schematic (not to scale), every mark
 * driven by real state:
 *   robots   their telemetry state (pulse while moving), HOME, fusion
 *   PCs      the camera's box for each PC (in use / changed / moving / ok)
 *   door     the door controller, or the camera's view of the red door leaf
 *   people   counts only: the camera sees people in its picture, not on the
 *            floor, so nobody is drawn at a made-up position
 * Layout as seen from the security camera on 2026-10-07: door and FANUC cell
 * on the left, the long PC table in the middle, two PCs by the window, the
 * UR5e frame on the right.
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

function pcState(cam: SecurityCamera | null, name: string): ZoneStatus | null {
  const z = cam?.zones.find(z => z.name.toUpperCase() === name)
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

export default function LabFloor({ tile, cam, robots }: {
  tile: MonitorTile | null; cam: SecurityCamera | null; robots: Robot[]
}) {
  const ur = robots.find(r => (r.model ?? '').toUpperCase().includes('UR') && !r.demo)
    ?? robots.find(r => (r.model ?? '').toUpperCase().includes('UR'))
  const fanuc = robots.find(r => (r.model ?? '').toUpperCase().includes('FANUC') && !r.demo)
    ?? robots.find(r => (r.model ?? '').toUpperCase().includes('FANUC'))
  const doorOpen = tile?.controller_online ? tile.door_closed === false : cam?.door_open ?? null
  const longTable = Array.from({ length: 8 }, (_, i) => `PC-${String(i + 1).padStart(2, '0')}`)
  const live = !!cam?.online
  return (
    <div className="relative">
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
        {/* windows on the back wall */}
        {[42, 52, 62].map(x => <line key={x} x1={x} y1={4} x2={x + 7} y2={4} stroke="#7dd3fc" strokeWidth={0.9} opacity={0.6} />)}
        <text x={57} y={2.8} textAnchor="middle" fontSize={1.8} fill="#64748b">windows</text>
        {/* door on the left wall */}
        <g>
          <rect x={1.2} y={14} width={1.6} height={9} fill={doorOpen ? '#f87171' : doorOpen === false ? '#22c55e' : '#64748b'} />
          {doorOpen && <path d="M 2.8 14 A 9 9 0 0 1 11.8 23" fill="none" stroke="#f87171" strokeWidth={0.35} strokeDasharray="1 0.6" />}
          <text x={4.4} y={12.6} fontSize={2} fill="#cbd5e1">Door {doorOpen == null ? '· no data' : doorOpen ? '· OPEN' : '· closed'}</text>
        </g>
        <RobotCell x={5} y={34} w={13} h={14} label="FANUC" robot={fanuc} frame="cage" />
        <RobotCell x={76} y={22} w={18} h={20} label="UR5e" robot={ur} frame="gantry" />
        {/* long PC table */}
        <rect x={24} y={30} width={44} height={6} rx={0.8} fill="#111827" stroke="#334155" strokeWidth={0.3} />
        {longTable.map((n, i) => {
          const st = pcState(cam, n)
          return (
            <g key={n}>
              <rect x={25 + i * 5.3} y={31} width={4.4} height={4} rx={0.6}
                    fill={st ? PC_FILL[st] : '#1e293b'} stroke="#475569" strokeWidth={0.2}>
                {st === 'IN_USE' && <animate attributeName="opacity" values="1;0.65;1" dur="2.4s" repeatCount="indefinite" />}
              </rect>
              <text x={27.2 + i * 5.3} y={39} textAnchor="middle" fontSize={1.5} fill="#94a3b8">{n.slice(3)}</text>
            </g>)
        })}
        <text x={46} y={28.6} textAnchor="middle" fontSize={1.8} fill="#64748b">PC table</text>
        {/* PCs by the window */}
        {['PC-09', 'PC-10'].map((n, i) => {
          const st = pcState(cam, n)
          return (
            <g key={n}>
              <rect x={44 + i * 9} y={9} width={7} height={4.5} rx={0.6} fill={st ? PC_FILL[st] : '#1e293b'} stroke="#475569" strokeWidth={0.2} />
              <text x={47.5 + i * 9} y={16.5} textAnchor="middle" fontSize={1.5} fill="#94a3b8">{n}</text>
            </g>)
        })}
        {/* security camera and its view */}
        <path d="M 60 57 L 8 6 L 96 6 Z" fill="url(#cone)" opacity={live ? 1 : 0.25} />
        <circle cx={60} cy={57} r={1.4} fill={live ? '#38bdf8' : '#64748b'} />
        <text x={60} y={61} textAnchor="middle" fontSize={1.8} fill="#94a3b8">camera {live ? '· live' : '· offline'}</text>
      </svg>
      <div className="absolute top-2 right-3 flex flex-col items-end gap-1 text-[11.5px] text-slate-300 pointer-events-none">
        <span><b className="text-white tnum">{tile?.people.length ?? 0}</b> inside (door)</span>
        <span><b className="text-white tnum">{cam?.online ? cam.people ?? 0 : '–'}</b> seen by camera</span>
        {tile?.environment?.temperature && <span><b className="text-white tnum">{tile.environment.temperature.value.toFixed(1)}</b>{tile.environment.temperature.unit}</span>}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500">
        <span><i className="inline-block w-2 h-2 rounded-sm align-middle mr-1" style={{ background: PC_FILL.IN_USE }} />PC in use</span>
        <span><i className="inline-block w-2 h-2 rounded-sm align-middle mr-1" style={{ background: PC_FILL.CHANGED }} />changed</span>
        <span><i className="inline-block w-2 h-2 rounded-sm align-middle mr-1" style={{ background: PC_FILL.MOTION }} />moving, nobody at it</span>
        <span><i className="inline-block w-2 h-2 rounded-full align-middle mr-1" style={{ background: ROBOT_COLOR.MOVING }} />robot moving</span>
        <span className="ml-auto">Schematic, not to scale · people are counted, not placed (no floor calibration)</span>
      </div>
    </div>)
}
