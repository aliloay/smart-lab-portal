/**
 * Decorative and diagrammatic layers.
 *
 * Pure SVG and CSS - no images, no WebGL, no extra dependencies. Motion is
 * CSS so it never depends on a JavaScript animation completing, and it stops
 * under prefers-reduced-motion. Everything decorative is aria-hidden and sits
 * behind the information; the diagrams that carry state (the lab network,
 * the door schematic) take that state from real data and show "no data"
 * honestly.
 */
import { ReactNode, useId } from 'react'
import { Link } from 'react-router-dom'

/** Engineering grid, major lines and a soft falloff: the page's ground. */
export function GridBackdrop({ className = '' }: { className?: string }) {
  return (
    <div aria-hidden className={`pointer-events-none overflow-hidden ${className}`}>
      <div className="absolute inset-0 bg-grid-fine bg-grid-fine opacity-50" />
      <div className="absolute inset-0 bg-grid-major bg-grid-major opacity-60" />
      {/* faint circuit traces - texture, never content */}
      <div className="absolute inset-0 bg-circuit bg-circuit opacity-[0.05]" />
      <div className="absolute inset-0"
           style={{ background:
             'radial-gradient(90% 70% at 50% 0%, transparent 35%, rgba(16,30,53,.85) 90%)' }} />
    </div>
  )
}

/** The grid on its own, for use inside a positioned card. */
export function GridField({ className = '' }: { className?: string }) {
  return (
    <div aria-hidden
         className={`pointer-events-none absolute inset-0 bg-grid-fine bg-grid-fine
                     opacity-70 fade-b ${className}`} />
  )
}

/** A soft light source, so a dark surface has somewhere for the eye to rest. */
export function Bloom({ className = '', tone = 'accent' }: {
  className?: string; tone?: 'accent' | 'teal' | 'violet'
}) {
  const c = tone === 'teal' ? 'bg-teal-400/[0.12]' : tone === 'violet'
    ? 'bg-violet-400/[0.12]' : 'bg-accent-400/[0.14]'
  return (
    <div aria-hidden
         className={`pointer-events-none absolute -top-24 left-1/3 w-[520px] h-[320px]
                     rounded-full blur-3xl animate-breathe ${c} ${className}`} />
  )
}

/**
 * Articulated arm. Drawn from a real kinematic chain - base, shoulder, elbow,
 * wrist, tool - and each joint rotates about its own axis, so it reads as a
 * manipulator working rather than a picture of one.
 */
export function RoboticArm({ className = '', animated = true }: {
  className?: string; animated?: boolean
}) {
  const a = animated ? '' : 'paused'
  const link = `arm-link-${useId().replace(/:/g, '')}`
  return (
    <svg aria-hidden viewBox="0 0 420 460" fill="none" className={className}
         strokeLinecap="round" strokeLinejoin="round">
      <defs>
        <linearGradient id={link} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7dd3fc" stopOpacity=".55" />
          <stop offset="1" stopColor="#2dd4bf" stopOpacity=".35" />
        </linearGradient>
      </defs>
      {/* work envelope - the reach of the arm, not decoration */}
      <path d="M86 318 A 170 170 0 0 1 378 184" stroke="#7dd3fc" strokeOpacity=".25"
            strokeWidth="1.5" className="art-flow-slow" />
      <circle cx="210" cy="352" r="150" stroke="#7dd3fc" strokeOpacity=".06" />

      {/* base */}
      <path d="M118 432h184" stroke="#94b8e2" strokeOpacity=".5" strokeWidth="5" />
      <path d="M150 432l14-42h92l14 42" stroke="#94b8e2" strokeOpacity=".55"
            strokeWidth="5" />
      <rect x="168" y="352" width="84" height="38" rx="9" stroke="#94b8e2"
            strokeOpacity=".6" strokeWidth="5" />

      <g className={`arm-shoulder ${a}`} style={{ transformOrigin: '210px 352px' }}>
        <path d="M210 352V214" stroke={`url(#${link})`} strokeWidth="16" />
        <circle cx="210" cy="352" r="17" fill="#172841" stroke="#7dd3fc"
                strokeOpacity=".7" strokeWidth="5" />
        <g className={`arm-elbow ${a}`} style={{ transformOrigin: '210px 214px' }}>
          <path d="M210 214 L318 128" stroke={`url(#${link})`} strokeWidth="14" />
          <circle cx="210" cy="214" r="18" fill="#172841" stroke="#7dd3fc"
                  strokeOpacity=".7" strokeWidth="5" />
          <g className={`arm-wrist ${a}`} style={{ transformOrigin: '318px 128px' }}>
            <path d="M318 128 L352 72" stroke={`url(#${link})`} strokeWidth="11" />
            <circle cx="318" cy="128" r="14" fill="#172841" stroke="#7dd3fc"
                    strokeOpacity=".7" strokeWidth="5" />
            <circle cx="352" cy="72" r="9" fill="#172841" stroke="#2dd4bf"
                    strokeOpacity=".8" strokeWidth="4" />
            <path d="M352 72 l-18 -22 M352 72 l16 -24" stroke="#2dd4bf"
                  strokeOpacity=".6" strokeWidth="6" />
            {/* status light on the tool */}
            <circle cx="352" cy="72" r="3" fill="#2dd4bf" className="art-blink" />
          </g>
        </g>
      </g>
    </svg>
  )
}

/** Circuit-trace ornament: right angles and vias, the way a PCB routes. */
export function CircuitTrace({ className = '' }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 240 160" fill="none" className={className}
         strokeLinecap="round">
      <path d="M0 24h56v38h62v34h60v40h62" stroke="currentColor" strokeWidth="1.2"
            opacity=".4" />
      <path d="M0 24h56v38h62v34h60v40h62" stroke="#38bdf8" strokeWidth="1.4"
            opacity=".55" className="art-flow" />
      <path d="M0 96h34v44h52" stroke="currentColor" strokeWidth="1.2" opacity=".28" />
      <path d="M118 0v38" stroke="currentColor" strokeWidth="1.2" opacity=".28" />
      {[[56, 24], [118, 62], [178, 96], [240, 136], [34, 96], [86, 140]]
        .map(([cx, cy], i) => (
          <circle key={i} cx={cx} cy={cy} r="2.8" fill="currentColor" opacity=".55" />
        ))}
    </svg>
  )
}

/** A small IoT mesh with signals travelling along its edges. */
export function NodeNetwork({ className = '' }: { className?: string }) {
  const nodes = [
    { x: 40, y: 120 }, { x: 140, y: 58 }, { x: 250, y: 108 },
    { x: 196, y: 210 }, { x: 78, y: 226 }, { x: 320, y: 196 },
  ]
  const edges: [number, number][] = [
    [0, 1], [1, 2], [2, 3], [3, 4], [4, 0], [2, 5], [3, 5],
  ]
  return (
    <svg aria-hidden viewBox="0 0 360 280" fill="none" className={className}>
      {edges.map(([a, b], i) => (
        <g key={i}>
          <line x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y}
                stroke="currentColor" strokeWidth="1" opacity=".22" />
          <line x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y}
                stroke="#38bdf8" strokeWidth="1.4" opacity=".45"
                className={i % 2 ? 'art-flow' : 'art-flow-slow'} />
        </g>
      ))}
      {nodes.map((n, i) => (
        <g key={i}>
          <circle cx={n.x} cy={n.y} r="10" fill="currentColor" opacity=".08" />
          <circle cx={n.x} cy={n.y} r="3.6" fill="currentColor" opacity=".7" />
        </g>
      ))}
    </svg>
  )
}

export function NodeField({ className = '' }: { className?: string }) {
  return <NodeNetwork className={`pointer-events-none text-accent-300/60 ${className}`} />
}

/** Small technical status pill. Shows only what the caller knows. */
export function SystemBadge({ label, tone = 'ok' }: {
  label: string; tone?: 'ok' | 'idle' | 'warn'
}) {
  return (
    <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md
                     border border-ink-500/80 bg-ink-800/70 mono text-slate-300">
      <span className={`w-1.5 h-1.5 rounded-full ${tone === 'ok'
        ? 'bg-ok animate-pulse-dot' : tone === 'warn' ? 'bg-warn' : 'bg-slate-500'}`} />
      {label}
    </span>
  )
}

/**
 * The two-factor path as a diagram: identity, biometric, door. The moving
 * signal shows direction; it is not a status and claims nothing.
 */
export function AccessFlow({ steps, className = '' }: {
  steps: { icon: ReactNode; title: string; detail?: string }[]
  className?: string
}) {
  return (
    <ol className={`relative grid gap-3 ${className}`}>
      {steps.map((s, i) => (
        <li key={s.title} className="relative flex items-start gap-3.5">
          {i < steps.length - 1 && (
            <svg aria-hidden className="absolute left-[19px] top-10 h-[calc(100%-18px)] w-1"
                 preserveAspectRatio="none" viewBox="0 0 2 40">
              <line x1="1" y1="0" x2="1" y2="40" stroke="#41618f" strokeWidth="2" />
              <line x1="1" y1="0" x2="1" y2="40" stroke="#38bdf8" strokeWidth="2"
                    className="art-flow" />
            </svg>
          )}
          <span className="relative grid place-items-center w-10 h-10 rounded-xl
                           border border-accent-500/35 bg-accent-500/10 text-accent-300
                           shrink-0">
            {s.icon}
          </span>
          <div className="pt-1 min-w-0">
            <div className="text-[13.5px] font-medium text-slate-100">{s.title}</div>
            {s.detail && <div className="text-[12.5px] text-slate-400 leading-relaxed">
              {s.detail}</div>}
          </div>
        </li>
      ))}
    </ol>
  )
}

export interface NetNode {
  id: number
  code: string
  name: string
  /** hardware state: true online, false offline, null no hardware / no data */
  online: boolean | null
  hasHardware: boolean
  occupied: boolean
  issues: number
}

/**
 * The laboratory network, drawn from live rows: every lab is a node around
 * the portal. Lines to labs with a reporting controller carry a signal; a lab
 * without hardware is drawn but disconnected, because that is the truth.
 */
export function LabNetworkMap({ nodes, className = '' }: {
  nodes: NetNode[]; className?: string
}) {
  const glow = `hub-glow-${useId().replace(/:/g, '')}`
  const W = 640, H = 340, cx = W / 2, cy = H / 2
  const rx = 250, ry = 125
  const placed = nodes.map((n, i) => {
    const a = (i / Math.max(1, nodes.length)) * Math.PI * 2 - Math.PI / 2
    return { ...n, x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a) }
  })
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={className} role="img"
         aria-label="Laboratory network: each laboratory connected to the portal">
      <defs>
        <radialGradient id={glow}>
          <stop offset="0" stopColor="#38bdf8" stopOpacity=".35" />
          <stop offset="1" stopColor="#38bdf8" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="none" stroke="#33507a"
               strokeDasharray="3 7" />
      <ellipse cx={cx} cy={cy} rx={rx * 0.55} ry={ry * 0.55} fill="none"
               stroke="#273e62" />
      {placed.map(n => (
        <g key={`e-${n.id}`}>
          <line x1={cx} y1={cy} x2={n.x} y2={n.y}
                stroke={n.hasHardware ? '#41618f' : '#273e62'} strokeWidth="1.2"
                strokeDasharray={n.hasHardware ? undefined : '2 6'} />
          {n.online && (
            <line x1={cx} y1={cy} x2={n.x} y2={n.y} stroke="#2dd4bf"
                  strokeWidth="1.8" className="art-flow" />
          )}
        </g>
      ))}
      {/* hub: the portal */}
      <circle cx={cx} cy={cy} r="70" fill={`url(#${glow})`} />
      <circle cx={cx} cy={cy} r="30" fill="#172841" stroke="#38bdf8" strokeWidth="1.5" />
      <circle cx={cx} cy={cy} r="38" fill="none" stroke="#38bdf8" strokeOpacity=".25"
              strokeDasharray="4 6" className="art-spin" />
      <text x={cx} y={cy - 2} textAnchor="middle" fontSize="10" fill="#e0f2fe"
            fontFamily="Space Grotesk, Inter, sans-serif" fontWeight="600"
            letterSpacing="1.5">PORTAL</text>
      <text x={cx} y={cy + 11} textAnchor="middle" fontSize="7.5" fill="#94a3b8"
            fontFamily="JetBrains Mono, monospace">API · DB</text>

      {placed.map(n => {
        const color = n.online === true ? '#10b981' : n.online === false ? '#ef4444'
          : n.hasHardware ? '#94a3b8' : '#5776a3'
        const labelRight = n.x >= cx
        return (
          <Link key={n.id} to={`/labs/${n.id}`}>
            <g className="cursor-pointer group">
              <title>{`${n.code} · ${n.name}`}</title>
              {n.occupied && (
                <circle cx={n.x} cy={n.y} r="16" fill="none" stroke="#f59e0b"
                        strokeOpacity=".5" className="art-blink" />
              )}
              <circle cx={n.x} cy={n.y} r="11" fill="#1b2e4b" stroke={color}
                      strokeWidth="2" />
              <circle cx={n.x} cy={n.y} r="4" fill={color} />
              {n.issues > 0 && (
                <g>
                  <circle cx={n.x + 10} cy={n.y - 10} r="7" fill="#f59e0b" />
                  <text x={n.x + 10} y={n.y - 7.2} textAnchor="middle" fontSize="8"
                        fontWeight="700" fill="#12213a">{n.issues}</text>
                </g>
              )}
              <text x={n.x + (labelRight ? 18 : -18)} y={n.y + 3.5}
                    textAnchor={labelRight ? 'start' : 'end'} fontSize="10"
                    fill="#cbd5e1" fontFamily="JetBrains Mono, monospace"
                    className="group-hover:fill-white">{n.code}</text>
            </g>
          </Link>
        )
      })}
    </svg>
  )
}

export type Tri = boolean | null | undefined

/**
 * The door as a schematic: reader, camera, controller, lock, door sensor,
 * each with a light driven by what the devices last reported. Grey means
 * "no data", not "fine".
 */
export function DoorSchematic({ controller, camera, face, doorClosed, className = '' }: {
  controller: Tri; camera: Tri; face: Tri; doorClosed: Tri; className?: string
}) {
  const col = (s: Tri) => s === true ? '#10b981' : s === false ? '#ef4444' : '#64748b'
  const door = doorClosed === true ? '#10b981' : doorClosed === false ? '#f59e0b' : '#64748b'
  return (
    <svg viewBox="0 0 520 220" className={className} role="img"
         aria-label="Door access hardware schematic">
      {/* wall and door frame */}
      <path d="M20 200h480" stroke="#41618f" strokeWidth="2" />
      <rect x="210" y="40" width="100" height="160" fill="#172841" stroke="#5776a3"
            strokeWidth="2" rx="3" />
      <rect x="222" y="52" width="76" height="136" fill="none" stroke="#33507a" />
      <circle cx="288" cy="124" r="4" fill="#94b8e2" />
      {/* lock + reed sensor */}
      <rect x="302" y="104" width="14" height="40" rx="3" fill="#1b2e4b"
            stroke={door} strokeWidth="2" />
      <circle cx="309" cy="98" r="3.5" fill={door} />

      {/* reader panel */}
      <rect x="140" y="92" width="44" height="64" rx="6" fill="#1b2e4b"
            stroke="#5776a3" strokeWidth="1.5" />
      <rect x="148" y="100" width="28" height="18" rx="2" fill="#12213a" stroke="#41618f" />
      <circle cx="162" cy="134" r="8" fill="none" stroke="#7dd3fc" strokeOpacity=".7" />
      <circle cx="162" cy="134" r="4" fill="none" stroke="#7dd3fc" strokeOpacity=".5" />
      <circle cx="176" cy="148" r="3" fill={col(controller)} />

      {/* camera */}
      <rect x="146" y="46" width="32" height="20" rx="4" fill="#1b2e4b"
            stroke="#5776a3" strokeWidth="1.5" />
      <circle cx="162" cy="56" r="5" fill="#12213a" stroke="#7dd3fc" />
      <circle cx="176" cy="48" r="3" fill={col(camera)} />
      <path d="M162 66 L132 118 M162 66 L192 118" stroke="#38bdf8" strokeOpacity=".18" />

      {/* controller box */}
      <rect x="360" y="70" width="92" height="56" rx="6" fill="#1b2e4b"
            stroke="#5776a3" strokeWidth="1.5" />
      <text x="406" y="94" textAnchor="middle" fontSize="9" fill="#cbd5e1"
            fontFamily="JetBrains Mono, monospace">ESP32</text>
      <text x="406" y="108" textAnchor="middle" fontSize="7.5" fill="#94a3b8"
            fontFamily="JetBrains Mono, monospace">MASTER</text>
      <circle cx="444" cy="78" r="3" fill={col(controller)} />

      {/* face server */}
      <rect x="40" y="70" width="70" height="46" rx="6" fill="#1b2e4b"
            stroke="#5776a3" strokeWidth="1.5" />
      <text x="75" y="92" textAnchor="middle" fontSize="8" fill="#cbd5e1"
            fontFamily="JetBrains Mono, monospace">FACE</text>
      <text x="75" y="104" textAnchor="middle" fontSize="7.5" fill="#94a3b8"
            fontFamily="JetBrains Mono, monospace">SERVER</text>
      <circle cx="104" cy="76" r="3" fill={col(face)} />

      {/* wiring / network */}
      <path d="M184 124 H 210" stroke="#41618f" strokeWidth="1.5" />
      <path d="M316 124 H 340 V 100 H 360" stroke="#41618f" strokeWidth="1.5" fill="none" />
      <path d="M178 56 H 340 V 84 H 360" stroke="#41618f" strokeWidth="1.2"
            strokeDasharray="3 5" fill="none" />
      <path d="M110 92 H 146" stroke="#41618f" strokeWidth="1.2" strokeDasharray="3 5" />
      {controller && (
        <path d="M316 124 H 340 V 100 H 360" stroke="#2dd4bf" strokeWidth="1.6"
              fill="none" className="art-flow" />
      )}
      {camera && (
        <path d="M178 56 H 340 V 84 H 360" stroke="#2dd4bf" strokeWidth="1.4"
              fill="none" className="art-flow-slow" />
      )}
    </svg>
  )
}
