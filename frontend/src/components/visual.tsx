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
 * The lab door as a scene - red door with its maglock, the MC210 camera above, the NFC/QR tablet
 * and fingerprint reader, the Master ESP32 and the PC running the face server. Everything that
 * moves or lights up follows what the devices LAST REPORTED: the door leaf swings open only when
 * the door sensor reports open; a device's light is green / red / grey (grey = no data, never
 * assumed "fine"); the data lines flow only while both ends are online. Nothing is simulated.
 */
export function DoorSchematic({ controller, camera, face, doorClosed, className = '' }: {
  controller: Tri; camera: Tri; face: Tri; doorClosed: Tri; className?: string
}) {
  const col = (s: Tri) => s === true ? '#22c55e' : s === false ? '#ef4444' : '#64748b'
  const open = doorClosed === false
  const lock = doorClosed === true ? '#22c55e' : doorClosed === false ? '#f59e0b' : '#64748b'
  const Lamp = ({ x, y, s }: { x: number; y: number; s: Tri }) =>
    <g><circle cx={x} cy={y} r="5" fill={col(s)} />{s === true && <circle cx={x} cy={y} r="9" fill={col(s)} opacity=".25" className="ds-pulse" />}</g>
  return (
    <svg viewBox="0 0 760 440" className={className} role="img"
         aria-label={`Lab door scene: door ${doorClosed === true ? 'closed' : open ? 'open' : 'not reported'}, controller ${controller === true ? 'online' : controller === false ? 'offline' : 'unknown'}`}>
      <defs>
        <linearGradient id="ds-red" x1="0" x2="1"><stop offset="0" stopColor="#9f1d22" /><stop offset=".5" stopColor="#c62a2f" /><stop offset="1" stopColor="#8c181d" /></linearGradient>
        <linearGradient id="ds-wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#10243f" /><stop offset="1" stopColor="#0a1a2f" /></linearGradient>
        <radialGradient id="ds-cam" cx=".4" cy=".35"><stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#c9d3df" /></radialGradient>
        <linearGradient id="ds-scr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#0b2a47" /><stop offset="1" stopColor="#071426" /></linearGradient>
        <linearGradient id="ds-room" x1="0" x2="1"><stop offset="0" stopColor="#1e3a5f" /><stop offset="1" stopColor="#0b1d36" /></linearGradient>
      </defs>
      <style>{`.ds-pulse{animation:dsPulse 2s ease-in-out infinite}@keyframes dsPulse{50%{opacity:.05}}
        .ds-leaf{transform-box:view-box;transform-origin:138px 250px;transition:transform 1.2s cubic-bezier(.4,0,.2,1)}
        .ds-flow{stroke-dasharray:6 8;animation:dsFlow 1.2s linear infinite}@keyframes dsFlow{to{stroke-dashoffset:-28}}
        @media (prefers-reduced-motion:reduce){.ds-pulse,.ds-flow{animation:none}.ds-leaf{transition:none}}`}</style>
      <rect width="760" height="440" rx="14" fill="url(#ds-wall)" />
      <rect y="392" width="760" height="48" fill="#081627" /><path d="M0 392H760" stroke="#1f3a60" />
      {/* door frame, the room behind it, and the leaf (opens only when reported open) */}
      <rect x="128" y="96" width="176" height="296" rx="3" fill="#1d2f4a" />
      <rect x="138" y="104" width="156" height="288" fill="url(#ds-room)" />
      <g className="ds-leaf" style={{ transform: open ? 'scaleX(0.16)' : 'scaleX(1)' }}>
        <rect x="138" y="104" width="156" height="288" rx="2" fill="url(#ds-red)" />
        <rect x="160" y="128" width="112" height="70" rx="3" fill="#0d1f36" stroke="#5e1014" strokeWidth="3" opacity=".9" />
        <rect x="190" y="214" width="52" height="16" rx="3" fill="#e5e7eb" />
        <text x="216" y="226" textAnchor="middle" fontSize="10" fontWeight="700" fill="#111827" fontFamily="monospace">LAB_01</text>
        <rect x="270" y="252" width="10" height="44" rx="5" fill="#d1d5db" /><rect x="262" y="270" width="24" height="7" rx="3" fill="#e5e7eb" />
      </g>
      {/* maglock on the frame: green locked+closed, amber open, grey unknown */}
      <rect x="186" y="98" width="60" height="10" rx="2" fill="#9ca3af" />
      <circle cx="252" cy="103" r="5" fill={lock} />
      <text x="216" y="90" textAnchor="middle" fontSize="10" fill="#94a3b8" fontFamily="monospace">
        {doorClosed === true ? 'CLOSED · LOCKED' : open ? 'OPEN' : 'NOT REPORTED'}</text>
      {/* MC210 camera above the door */}
      <g transform="translate(340 66)">
        <rect x="-20" y="-6" width="40" height="8" rx="3" fill="#94a3b8" />
        <rect x="-16" y="2" width="32" height="20" rx="8" fill="url(#ds-cam)" />
        <circle cy="40" r="25" fill="url(#ds-cam)" stroke="#aab6c5" />
        <rect x="-21" y="31" width="42" height="18" rx="9" fill="#111827" />
        <circle cx="-4" cy="40" r="7" fill="#0b1220" stroke="#24d4f2" strokeWidth="1.5" />
        <Lamp x={30} y={10} s={camera} />
        <text y="82" textAnchor="middle" fontSize="10" fill="#cbd5e1" fontFamily="monospace">ENTRY CAMERA</text>
        {camera === true && <path d="M-10 64 L-150 330 M10 64 L40 330" stroke="#24d4f2" strokeOpacity=".2" />}
      </g>
      {/* tablet (QR / NFC) and fingerprint reader */}
      <g transform="translate(30 168)">
        <rect width="78" height="108" rx="9" fill="#0b1220" stroke="#475569" />
        <rect x="6" y="8" width="66" height="90" rx="4" fill="url(#ds-scr)" />
        <g stroke="#24d4f2" fill="none" strokeWidth="2" strokeLinecap="round" opacity={controller === true ? 1 : .35}>
          <path d="M33 42a8 8 0 0 1 0 12" /><path d="M38 37a15 15 0 0 1 0 22" /><path d="M43 32a22 22 0 0 1 0 32" /></g>
        <rect x="22" y="42" width="9" height="12" rx="2" fill="#24d4f2" opacity={controller === true ? 1 : .35} />
        <text x="39" y="80" textAnchor="middle" fontSize="8" fill="#cbd5e1">Tap card / QR</text>
        <rect x="19" y="124" width="40" height="52" rx="8" fill="#1f2937" stroke="#475569" />
        <ellipse cx="39" cy="148" rx="11" ry="14" fill="#0b1220" stroke="#24d4f2" strokeOpacity=".7" />
        <Lamp x={70} y={130} s={controller} />
        <text x="39" y="198" textAnchor="middle" fontSize="9" fill="#cbd5e1" fontFamily="monospace">NFC · QR · FINGER</text>
      </g>
      {/* Master ESP32 */}
      <g transform="translate(400 250)">
        <rect width="128" height="78" rx="6" fill="#1e293b" stroke="#ffb547" />
        <rect x="10" y="10" width="62" height="40" rx="3" fill="#0f172a" stroke="#334155" />
        <rect x="20" y="16" width="42" height="28" rx="2" fill="#94a3b8" />
        <text x="41" y="34" textAnchor="middle" fontSize="7" fill="#0f172a" fontFamily="monospace" fontWeight="700">ESP32</text>
        <rect x="84" y="12" width="32" height="24" rx="2" fill="#2563eb" />
        <text x="100" y="28" textAnchor="middle" fontSize="6.5" fill="#fff" fontFamily="monospace">RELAY</text>
        <Lamp x={100} y={50} s={controller} />
        <text x="64" y="96" textAnchor="middle" fontSize="10.5" fill="#ffd08a" fontFamily="monospace" fontWeight="700">MASTER ESP32</text>
      </g>
      {/* PC running the face server */}
      <g transform="translate(570 120)">
        <rect width="170" height="112" rx="8" fill="#0b1220" stroke="#475569" />
        <rect x="7" y="7" width="156" height="90" rx="3" fill="url(#ds-scr)" />
        <text x="85" y="46" textAnchor="middle" fontSize="12" fontWeight="700" fill="#fff">FACE SERVER</text>
        <text x="85" y="66" textAnchor="middle" fontSize="9" fill="#94a3b8">{face === true ? 'online' : face === false ? 'offline' : 'not reported'}</text>
        <Lamp x={152} y={18} s={face} />
        <rect x="74" y="112" width="22" height="22" fill="#334155" /><rect x="50" y="132" width="70" height="7" rx="3" fill="#475569" />
        <text x="85" y="160" textAnchor="middle" fontSize="10" fill="#cbd5e1" fontFamily="monospace">LAB PC · 5000</text>
      </g>
      {/* links: drawn grey; they flow only while both ends report online */}
      {[['M108 230 C 180 300, 330 300, 400 290', controller], ['M464 250 C 464 200, 300 140, 252 108', controller],
        ['M528 290 C 600 290, 650 260, 655 236', controller === true && face === true], ['M368 112 C 440 112, 520 140, 570 160', camera === true && face === true]]
        .map(([d, on], i) => <g key={i}>
          <path d={d as string} stroke="#33507a" strokeWidth="1.6" fill="none" />
          {on === true && <path d={d as string} stroke="#24d4f2" strokeWidth="2" fill="none" className="ds-flow" />}
        </g>)}
    </svg>
  )
}
