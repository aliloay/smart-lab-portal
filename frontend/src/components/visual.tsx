/**
 * Decorative layers.
 *
 * All pure SVG and CSS — no images, no 3D, no extra dependencies. The whole
 * set adds a couple of kilobytes and never blocks a render, which is the
 * point: atmosphere must not cost the person anything.
 *
 * Everything here is aria-hidden and sits behind the interface. If any of it
 * failed to load, not one piece of information would be lost.
 */
import { motion } from 'framer-motion'

/** Faint engineering grid with a soft radial falloff. */
export function GridBackdrop({ className = '' }: { className?: string }) {
  return (
    <div aria-hidden className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}>
      <div className="absolute inset-0 bg-grid-fine bg-grid-fine opacity-[0.55]" />
      <div className="absolute inset-0 bg-sheen" />
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(120% 80% at 50% -10%, transparent 30%, #05080f 78%)',
        }}
      />
    </div>
  )
}

/**
 * Articulated arm silhouette. Drawn from a real kinematic chain — base,
 * shoulder, elbow, wrist, tool — rather than a generic robot shape, because
 * an engineering audience reads the joints.
 */
export function RoboticArm({ className = '' }: { className?: string }) {
  const stroke = 'currentColor'
  return (
    <svg aria-hidden viewBox="0 0 420 460" fill="none"
         className={className} strokeLinecap="round" strokeLinejoin="round">
      {/* base */}
      <path d="M120 430h180M150 430l14-42h92l14 42" stroke={stroke}
            strokeWidth="6" opacity=".55" />
      <rect x="168" y="352" width="84" height="38" rx="8" stroke={stroke}
            strokeWidth="6" opacity=".55" />

      {/* shoulder link */}
      <path d="M210 352V214" stroke={stroke} strokeWidth="14" opacity=".38" />
      <circle cx="210" cy="352" r="16" stroke={stroke} strokeWidth="6" opacity=".6" />

      {/* elbow */}
      <circle cx="210" cy="214" r="18" stroke={stroke} strokeWidth="6" opacity=".6" />
      <path d="M210 214 L318 128" stroke={stroke} strokeWidth="13" opacity=".38" />

      {/* wrist */}
      <circle cx="318" cy="128" r="14" stroke={stroke} strokeWidth="6" opacity=".6" />
      <path d="M318 128 L352 72" stroke={stroke} strokeWidth="10" opacity=".38" />

      {/* tool flange + gripper */}
      <circle cx="352" cy="72" r="9" stroke={stroke} strokeWidth="5" opacity=".6" />
      <path d="M352 72 l-18 -22 M352 72 l16 -24" stroke={stroke}
            strokeWidth="6" opacity=".45" />

      {/* work envelope arc — the reach of the arm, not decoration */}
      <path d="M96 300 A 150 150 0 0 1 366 196" stroke={stroke}
            strokeWidth="1.5" strokeDasharray="5 9" opacity=".3" />
    </svg>
  )
}

/**
 * A small network of IoT nodes with connecting lines. The pulse travels along
 * an edge, which is what makes it read as a network rather than a pattern.
 */
export function NodeNetwork({ className = '' }: { className?: string }) {
  const nodes = [
    { x: 40,  y: 120 }, { x: 140, y: 58 },  { x: 250, y: 108 },
    { x: 196, y: 210 }, { x: 78,  y: 226 }, { x: 320, y: 196 },
  ]
  const edges: [number, number][] = [
    [0, 1], [1, 2], [2, 3], [3, 4], [4, 0], [2, 5], [3, 5],
  ]
  return (
    <svg aria-hidden viewBox="0 0 360 280" fill="none" className={className}>
      {edges.map(([a, b], i) => (
        <line key={i}
              x1={nodes[a].x} y1={nodes[a].y}
              x2={nodes[b].x} y2={nodes[b].y}
              stroke="currentColor" strokeWidth="1" opacity=".22" />
      ))}
      {edges.map(([a, b], i) => (
        <motion.circle
          key={`p-${i}`} r="2.5" fill="currentColor"
          // cx/cy MUST be set on the initial state as well as animated.
          // Without them the first rendered frame has cx="undefined", which
          // the SVG parser rejects and the browser logs as an error.
          initial={{ opacity: 0, cx: nodes[a].x, cy: nodes[a].y }}
          animate={{
            cx: [nodes[a].x, nodes[b].x],
            cy: [nodes[a].y, nodes[b].y],
            opacity: [0, 0.9, 0],
          }}
          transition={{
            duration: 2.8, delay: i * 0.55, repeat: Infinity,
            repeatDelay: 1.6, ease: 'easeInOut',
          }}
        />
      ))}
      {nodes.map((n, i) => (
        <g key={`n-${i}`}>
          <circle cx={n.x} cy={n.y} r="9" fill="currentColor" opacity=".08" />
          <circle cx={n.x} cy={n.y} r="3.4" fill="currentColor" opacity=".65" />
        </g>
      ))}
    </svg>
  )
}

/**
 * Circuit-trace corner ornament. Right angles and via dots, the way a real
 * PCB routes — diagonal traces would look like decoration.
 */
export function CircuitTrace({ className = '' }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 240 160" fill="none" className={className}
         strokeLinecap="round">
      <path d="M0 24h56v38h62v34h60v40h62" stroke="currentColor"
            strokeWidth="1.2" opacity=".35" />
      <path d="M0 96h34v44h52" stroke="currentColor" strokeWidth="1.2" opacity=".25" />
      <path d="M118 0v38" stroke="currentColor" strokeWidth="1.2" opacity=".25" />
      {[[56, 24], [118, 62], [178, 96], [240, 136], [34, 96], [86, 140]]
        .map(([cx, cy], i) => (
          <circle key={i} cx={cx} cy={cy} r="2.6"
                  fill="currentColor" opacity=".5" />
        ))}
    </svg>
  )
}

/**
 * Status rail used on the login screen. Reads as instrumentation coming
 * online. The labels are static text, not fabricated telemetry — nothing here
 * claims to be a live reading.
 */
export function SystemBoot({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2">
      {items.map((t, i) => (
        <motion.li
          key={t}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.35 + i * 0.12, duration: 0.35 }}
          className="flex items-center gap-2.5 mono text-slate-500"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-ok animate-pulse-dot" />
          {t}
        </motion.li>
      ))}
    </ul>
  )
}


// ---------------------------------------------------------------------------
// Names the page components import.
// ---------------------------------------------------------------------------

/** The grid layer on its own, for use inside a positioned container. */
export function GridField({ className = '' }: { className?: string }) {
  return (
    <div aria-hidden
         className={`pointer-events-none absolute inset-0 bg-grid-fine
                     bg-grid-fine opacity-[0.5] ${className}`} />
  )
}

/**
 * A soft cyan light source. Gives a flat dark surface somewhere for the eye
 * to rest, which is what stops a dark interface reading as a black rectangle.
 */
export function Bloom({ className = '' }: { className?: string }) {
  return (
    <div aria-hidden
         className={`pointer-events-none absolute -top-24 left-1/3 w-[520px]
                     h-[320px] rounded-full blur-3xl animate-breathe
                     bg-accent-500/[0.13] ${className}`} />
  )
}

/** NodeNetwork positioned as a background field. */
export function NodeField({ className = '' }: { className?: string }) {
  return (
    <NodeNetwork
      className={`pointer-events-none text-accent-400/50 ${className}`} />
  )
}

/** Small technical status pill, e.g. SYSTEM ONLINE. */
export function SystemBadge({ label, tone = 'ok' }: {
  label: string; tone?: 'ok' | 'idle'
}) {
  return (
    <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md
                     border border-ink-500/80 bg-ink-800/60 mono
                     text-slate-400">
      <span className={`w-1.5 h-1.5 rounded-full ${
        tone === 'ok' ? 'bg-ok animate-pulse-dot' : 'bg-slate-600'}`} />
      {label}
    </span>
  )
}
