/**
 * Laboratory category illustrations.
 *
 * Original line art in one blueprint style: dark ground, engineering grid,
 * light strokes, one accent hue per discipline, a little motion. They are
 * ILLUSTRATIONS of each discipline and are labelled as such - nothing here
 * claims to be a photograph of a GIU laboratory. When real photographs exist
 * they can replace these per lab without touching the cards.
 */
import {
  Bot, Car, CircuitBoard, Cog, FlaskConical, PenTool, Scissors, Microscope, Zap,
} from 'lucide-react'
import { ReactNode, useId } from 'react'

export interface CategoryMeta {
  key: string
  label: string
  hue: string
  icon: ReactNode
  Art: (p: { className?: string }) => JSX.Element
}

const S = '#d6e9ff'          // primary line colour

function Frame({ hue, children, className = '' }: {
  hue: string; children: ReactNode; className?: string
}) {
  const id = useId().replace(/:/g, '')
  return (
    <svg viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice"
         className={className} aria-hidden>
      <defs>
        <linearGradient id={`bg${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={hue} stopOpacity=".22" />
          <stop offset=".55" stopColor="#172841" />
          <stop offset="1" stopColor="#12213a" />
        </linearGradient>
        <pattern id={`g${id}`} width="16" height="16" patternUnits="userSpaceOnUse">
          <path d="M16 0H0V16" fill="none" stroke="#94b8e2" strokeOpacity=".07" />
        </pattern>
        <radialGradient id={`v${id}`} cx="50%" cy="40%" r="75%">
          <stop offset=".55" stopColor="#12213a" stopOpacity="0" />
          <stop offset="1" stopColor="#12213a" stopOpacity=".85" />
        </radialGradient>
      </defs>
      <rect width="320" height="180" fill={`url(#bg${id})`} />
      <rect width="320" height="180" fill={`url(#g${id})`} />
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">{children}</g>
      <rect width="320" height="180" fill={`url(#v${id})`} />
    </svg>
  )
}

/** Dimension line with ticks - the blueprint signature on every scene. */
function Dim({ x1, x2, y, label }: { x1: number; x2: number; y: number; label: string }) {
  return (
    <g stroke={S} strokeOpacity=".3" strokeWidth="1">
      <path d={`M${x1} ${y}H${x2}M${x1} ${y - 4}v8M${x2} ${y - 4}v8`} />
      <text x={(x1 + x2) / 2} y={y - 5} textAnchor="middle" fontSize="7"
            fill={S} fillOpacity=".45" stroke="none"
            fontFamily="JetBrains Mono, monospace">{label}</text>
    </g>
  )
}

function Roller({ cx, cy, r, hue }: { cx: number; cy: number; r: number; hue: string }) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} stroke={S} strokeOpacity=".6" strokeWidth="1.5" />
      <g className="art-spin-fast">
        <path d={`M${cx - r + 2} ${cy}H${cx + r - 2}M${cx} ${cy - r + 2}V${cy + r - 2}`}
              stroke={hue} strokeOpacity=".8" strokeWidth="1.2" />
      </g>
    </g>
  )
}

// --- scenes ------------------------------------------------------------------
function RoboticsArt({ className }: { className?: string }) {
  const h = '#22d3ee'
  return (
    <Frame hue={h} className={className}>
      {/* conveyor */}
      <path d="M150 138h150" stroke={S} strokeOpacity=".55" strokeWidth="2" />
      <path d="M150 150h150" stroke={S} strokeOpacity=".35" strokeWidth="1.5" />
      {[162, 196, 230, 264, 298].map(x => <Roller key={x} cx={x} cy={144} r={5} hue={h} />)}
      <path d="M150 132h150" stroke={h} strokeOpacity=".7" strokeWidth="1.4" className="art-flow" />
      <rect x="236" y="112" width="24" height="20" rx="2" stroke={S} strokeOpacity=".7" strokeWidth="1.5" />
      <rect x="276" y="116" width="18" height="16" rx="2" stroke={S} strokeOpacity=".45" strokeWidth="1.5" />
      {/* arm */}
      <path d="M58 160h60M70 160l6-16h24l6 16" stroke={S} strokeOpacity=".6" strokeWidth="2.2" />
      <path d="M88 144 L96 86 L150 60 L176 82" stroke={S} strokeOpacity=".8" strokeWidth="5" />
      <path d="M88 144 L96 86 L150 60 L176 82" stroke={h} strokeOpacity=".35" strokeWidth="9" />
      {[[88, 144, 7], [96, 86, 7], [150, 60, 6], [176, 82, 4]].map(([x, y, r], i) => (
        <circle key={i} cx={x} cy={y} r={r} fill="#172841" stroke={h} strokeWidth="2" />
      ))}
      <path d="M176 82l-6 12M176 82l8 10" stroke={S} strokeOpacity=".8" strokeWidth="2.5" />
      <circle cx="176" cy="82" r="2" fill={h} className="art-blink" />
      <path d="M40 176 A 120 120 0 0 1 206 44" stroke={h} strokeOpacity=".25"
            strokeWidth="1" className="art-flow-slow" />
      <Dim x1={150} x2={300} y={170} label="CONVEYOR 1500" />
    </Frame>
  )
}

function ManufacturingArt({ className }: { className?: string }) {
  const h = '#818cf8'
  return (
    <Frame hue={h} className={className}>
      {/* machine frame */}
      <path d="M64 160h150M78 160V40h44v120" stroke={S} strokeOpacity=".6" strokeWidth="2" />
      <rect x="116" y="46" width="72" height="36" rx="4" stroke={S} strokeOpacity=".75" strokeWidth="2" />
      <path d="M152 82v26" stroke={S} strokeOpacity=".8" strokeWidth="5" />
      <g className="art-spin-fast">
        <path d="M146 110l12 8M146 118l12-8M152 106v16" stroke={h} strokeWidth="2" />
      </g>
      <rect x="112" y="124" width="80" height="12" rx="2" stroke={S} strokeOpacity=".7" strokeWidth="1.6" />
      <rect x="132" y="118" width="40" height="6" stroke={h} strokeOpacity=".8" strokeWidth="1.4" />
      {/* chips */}
      {[[176, 116], [184, 110], [124, 114]].map(([x, y], i) => (
        <path key={i} d={`M${x} ${y}l3 -2`} stroke={h} strokeOpacity=".7" strokeWidth="1.5"
              className="art-blink" />
      ))}
      {/* control panel */}
      <rect x="220" y="58" width="60" height="44" rx="4" stroke={S} strokeOpacity=".55" strokeWidth="1.5" />
      <path d="M228 72h30M228 80h20M228 88h36" stroke={h} strokeOpacity=".6" strokeWidth="1.4" />
      <circle cx="270" cy="70" r="3" fill={h} className="art-blink" />
      {/* gear */}
      <g className="art-spin">
        <circle cx="262" cy="140" r="16" stroke={S} strokeOpacity=".45" strokeWidth="1.5" />
        <circle cx="262" cy="140" r="5" stroke={S} strokeOpacity=".45" strokeWidth="1.5" />
        {Array.from({ length: 8 }).map((_, i) => {
          const a = (i / 8) * Math.PI * 2
          return <path key={i} d={`M${262 + 16 * Math.cos(a)} ${140 + 16 * Math.sin(a)}l${4 * Math.cos(a)} ${4 * Math.sin(a)}`}
                       stroke={S} strokeOpacity=".45" strokeWidth="3" />
        })}
      </g>
      <Dim x1={112} x2={192} y={172} label="X-AXIS 800" />
    </Frame>
  )
}

function MaterialsArt({ className }: { className?: string }) {
  const h = '#2dd4bf'
  return (
    <Frame hue={h} className={className}>
      {/* tensile tester */}
      <path d="M40 162h112M52 162V34M140 162V34M46 34h100" stroke={S} strokeOpacity=".6" strokeWidth="2" />
      <rect x="52" y="54" width="88" height="10" rx="2" stroke={S} strokeOpacity=".75" strokeWidth="1.8" />
      <rect x="52" y="134" width="88" height="10" rx="2" stroke={S} strokeOpacity=".75" strokeWidth="1.8" />
      {/* dog-bone specimen */}
      <path d="M88 64h16v14l-4 6v26l4 6v18H88v-18l4-6V84l-4-6Z" stroke={h} strokeWidth="1.8" />
      <path d="M96 88v20" stroke={h} strokeOpacity=".5" strokeWidth="1" className="art-flow" />
      {/* stress-strain plot */}
      <rect x="176" y="38" width="118" height="88" rx="4" stroke={S} strokeOpacity=".45" strokeWidth="1.4" />
      <path d="M186 116V46M186 116h100" stroke={S} strokeOpacity=".4" strokeWidth="1" />
      <path d="M188 114 L214 68 Q 226 56 244 58 Q 266 62 278 74" stroke={h} strokeWidth="2" className="art-flow-slow" />
      <circle cx="278" cy="74" r="2.5" fill={h} className="art-blink" />
      <text x="190" y="54" fontSize="7" fill={S} fillOpacity=".45"
            fontFamily="JetBrains Mono, monospace">σ</text>
      <text x="280" y="124" fontSize="7" fill={S} fillOpacity=".45"
            fontFamily="JetBrains Mono, monospace">ε</text>
      {/* microscope */}
      <path d="M230 164h40M252 164v-12M244 152h16M250 152l8-22M254 128l10-8" stroke={S}
            strokeOpacity=".55" strokeWidth="2" />
      <Dim x1={176} x2={294} y={140} label="STRESS-STRAIN" />
    </Frame>
  )
}

function AutomotiveArt({ className }: { className?: string }) {
  const h = '#38bdf8'
  return (
    <Frame hue={h} className={className}>
      {/* car profile */}
      <path d="M34 124 L50 104 Q 60 92 84 90 L120 72 Q 140 62 174 62 L214 64 Q 238 68 256 90
               L284 96 Q 298 100 298 114 L298 124" stroke={S} strokeOpacity=".8" strokeWidth="2" />
      <path d="M34 124 H 64 M110 124 H 222 M268 124 H 298" stroke={S} strokeOpacity=".8" strokeWidth="2" />
      <path d="M124 74 L 118 90 H 176 V 68 M 184 68 V 90 H 244 Q 232 72 214 68 Z" stroke={S}
            strokeOpacity=".45" strokeWidth="1.4" />
      {/* drivetrain: battery pack and motor */}
      <rect x="116" y="100" width="100" height="14" rx="3" stroke={h} strokeWidth="1.5" />
      {[128, 144, 160, 176, 192].map(x => (
        <path key={x} d={`M${x} 103v8`} stroke={h} strokeOpacity=".5" />
      ))}
      <path d="M216 107 H 236" stroke={h} strokeWidth="1.5" className="art-flow" />
      <circle cx="245" cy="107" r="8" stroke={h} strokeWidth="1.5" />
      {/* wheels */}
      {[87, 245].map(x => (
        <g key={x}>
          <circle cx={x} cy="126" r="22" stroke={S} strokeOpacity=".8" strokeWidth="2" />
          <circle cx={x} cy="126" r="14" stroke={S} strokeOpacity=".35" strokeWidth="1.2" />
          <g className="art-spin-fast">
            {/* invisible bounds centre the rotation box on the hub */}
            <circle cx={x} cy="126" r="13" stroke="none" />
            {[0, 1, 2, 3, 4].map(i => {
              const a = (i / 5) * Math.PI * 2
              return <path key={i} d={`M${x} 126l${13 * Math.cos(a)} ${13 * Math.sin(a)}`}
                           stroke={h} strokeOpacity=".7" strokeWidth="1.4" />
            })}
          </g>
        </g>
      ))}
      <path d="M20 150 H 300" stroke={S} strokeOpacity=".25" />
      <Dim x1={87} x2={245} y={166} label="WHEELBASE 2700" />
    </Frame>
  )
}

function ElectricalArt({ className }: { className?: string }) {
  const h = '#a78bfa'
  return (
    <Frame hue={h} className={className}>
      {/* PCB */}
      <rect x="28" y="52" width="132" height="98" rx="6" stroke={S} strokeOpacity=".6" strokeWidth="1.8" />
      <rect x="62" y="80" width="36" height="36" rx="3" stroke={S} strokeOpacity=".8" strokeWidth="1.6" />
      {[86, 94, 102, 110].map(y => (
        <path key={y} d={`M56 ${y}h6M98 ${y}h6`} stroke={S} strokeOpacity=".6" />
      ))}
      <path d="M36 66h20v14M104 92h22v-26h24M104 108h30v30M40 140h22V116" stroke={h}
            strokeOpacity=".5" strokeWidth="1.5" />
      <path d="M104 92h22v-26h24" stroke={h} strokeWidth="1.8" className="art-flow" />
      {[[56, 80], [126, 66], [134, 138], [62, 116]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2.8" fill={h} fillOpacity=".8" />
      ))}
      <rect x="120" y="120" width="26" height="12" rx="2" stroke={S} strokeOpacity=".5" />
      {/* oscilloscope */}
      <rect x="182" y="42" width="116" height="84" rx="6" stroke={S} strokeOpacity=".65" strokeWidth="1.8" />
      <rect x="192" y="52" width="74" height="56" rx="2" stroke={S} strokeOpacity=".35" />
      <path d="M192 80h74M229 52v56" stroke={S} strokeOpacity=".15" />
      <path d="M192 80 Q 201 56 210 80 T 229 80 T 247 80 T 266 80" stroke={h} strokeWidth="2"
            className="art-flow-slow" />
      {[274, 286].map(x => [60, 78, 96].map(y => (
        <circle key={`${x}${y}`} cx={x} cy={y} r="3.5" stroke={S} strokeOpacity=".5" />
      )))}
      <path d="M232 126 Q 222 150 170 146" stroke={S} strokeOpacity=".4" strokeWidth="1.4" />
      <Dim x1={28} x2={160} y={166} label="PCB 100 × 80" />
    </Frame>
  )
}

function PowerArt({ className }: { className?: string }) {
  const h = '#7dd3fc'
  return (
    <Frame hue={h} className={className}>
      {/* motor */}
      <circle cx="92" cy="96" r="44" stroke={S} strokeOpacity=".7" strokeWidth="2" />
      <circle cx="92" cy="96" r="30" stroke={S} strokeOpacity=".35" strokeWidth="1.4" />
      <g className="art-spin-fast">
        <circle cx="92" cy="96" r="26" stroke="none" />
        {[0, 1, 2].map(i => {
          const a = (i / 3) * Math.PI * 2
          return <path key={i} d={`M92 96l${26 * Math.cos(a)} ${26 * Math.sin(a)}`}
                       stroke={h} strokeWidth="3" />
        })}
      </g>
      <circle cx="92" cy="96" r="6" fill="#172841" stroke={h} strokeWidth="2" />
      <path d="M40 150h104M56 140v10M128 140v10" stroke={S} strokeOpacity=".55" strokeWidth="2" />
      {/* three phase */}
      <rect x="170" y="40" width="128" height="92" rx="6" stroke={S} strokeOpacity=".5" strokeWidth="1.5" />
      {[0, 1, 2].map(i => (
        <path key={i}
          d={`M178 86 ${Array.from({ length: 12 }).map((_, k) => {
            const x = 178 + (k + 1) * 9.5
            const y = 86 - 26 * Math.sin(((k + 1) / 12) * Math.PI * 2 * 1.5 + (i * 2 * Math.PI) / 3)
            return `L${x.toFixed(1)} ${y.toFixed(1)}`
          }).join(' ')}`}
          stroke={h} strokeOpacity={[1, .6, .35][i]} strokeWidth="1.6"
          className={i === 0 ? 'art-flow-slow' : ''} />
      ))}
      <text x="178" y="126" fontSize="7" fill={S} fillOpacity=".45"
            fontFamily="JetBrains Mono, monospace">L1 L2 L3 · 400 V</text>
      {/* bolt */}
      <path d="M244 142 l-10 18 h10 l-6 14" stroke={h} strokeWidth="2" className="art-blink" />
      <Dim x1={48} x2={136} y={170} label="Ø 88" />
    </Frame>
  )
}

function DesignArt({ className }: { className?: string }) {
  const h = '#e879f9'
  return (
    <Frame hue={h} className={className}>
      {/* 3D printer */}
      <path d="M40 158V34h110v124M40 158h110M40 60h110" stroke={S} strokeOpacity=".6" strokeWidth="2" />
      <rect x="84" y="60" width="22" height="16" rx="2" stroke={S} strokeOpacity=".8" strokeWidth="1.6" />
      <path d="M95 76l0 8" stroke={h} strokeWidth="2" />
      <path d="M95 84 L95 118" stroke={h} strokeOpacity=".35" strokeDasharray="2 3" />
      {/* printed object, layer by layer */}
      {[0, 1, 2, 3, 4, 5].map(i => (
        <path key={i} d={`M${72 + i * 1.5} ${146 - i * 5}h${46 - i * 3}`} stroke={h}
              strokeOpacity={.35 + i * .1} strokeWidth="2.2" />
      ))}
      <path d="M60 150h70" stroke={S} strokeOpacity=".6" strokeWidth="2" />
      {/* wireframe cube */}
      <g stroke={S} strokeOpacity=".7" strokeWidth="1.4">
        <path d="M200 70 L240 52 L280 70 L240 88 Z" />
        <path d="M200 70 V 118 L240 136 L280 118 V 70 M240 88 V 136" />
      </g>
      <path d="M200 70 L240 52 L280 70" stroke={h} strokeWidth="1.6" className="art-flow-slow" />
      {[[200, 70], [240, 52], [280, 70], [240, 88], [200, 118], [240, 136], [280, 118]]
        .map(([x, y], i) => <circle key={i} cx={x} cy={y} r="2.4" fill={h} />)}
      <Dim x1={200} x2={280} y={156} label="60 mm" />
    </Frame>
  )
}

function FashionArt({ className }: { className?: string }) {
  const h = '#f0abfc'
  return (
    <Frame hue={h} className={className}>
      {/* dress form */}
      <path d="M92 36 q12 -8 24 0 M86 44 Q 80 62 88 76 Q 94 90 86 110 Q 80 128 92 136 H 116
               Q 128 128 122 110 Q 114 90 120 76 Q 128 62 122 44 Q 104 36 86 44 Z"
            stroke={S} strokeOpacity=".8" strokeWidth="2" />
      <path d="M104 136v22M86 160h36" stroke={S} strokeOpacity=".6" strokeWidth="2" />
      <path d="M86 76 Q 104 84 120 76" stroke={h} strokeWidth="1.5" strokeDasharray="3 4" />
      <path d="M88 110 Q 104 116 120 110" stroke={h} strokeWidth="1.5" strokeDasharray="3 4" />
      {/* measuring tape */}
      <path d="M60 60 Q 104 30 150 64 Q 170 80 160 104" stroke={h} strokeWidth="2"
            className="art-flow-slow" />
      {/* pattern pieces */}
      <path d="M190 44 h54 l10 30 l-18 64 h-38 l-18 -64 Z" stroke={S} strokeOpacity=".6" strokeWidth="1.6" />
      <path d="M196 50 h42 l8 24 l-15 56 h-28 l-15 -56 Z" stroke={h} strokeOpacity=".7"
            strokeWidth="1.2" strokeDasharray="4 4" />
      <path d="M262 60 h30 v60 h-30 Z" stroke={S} strokeOpacity=".45" strokeWidth="1.4" />
      <path d="M266 64 h22 v52 h-22 Z" stroke={h} strokeOpacity=".5" strokeDasharray="3 4" />
      {/* needle and thread */}
      <path d="M252 150 l30 -16" stroke={S} strokeOpacity=".8" strokeWidth="1.8" />
      <path d="M282 134 Q 296 140 290 152 Q 280 164 262 160" stroke={h} strokeWidth="1.2" />
      <Dim x1={190} x2={254} y={164} label="PATTERN A" />
    </Frame>
  )
}

function GeneralArt({ className }: { className?: string }) {
  const h = '#5eead4'
  return (
    <Frame hue={h} className={className}>
      <path d="M76 40h28M82 40v34L56 136q-4 12 8 12h52q12 0 8-12L98 74V40" stroke={S}
            strokeOpacity=".8" strokeWidth="2" />
      <path d="M66 118 q24 -8 48 0 L124 136 q4 12 -8 12 H64 q-12 0 -8 -12 Z" fill={h}
            fillOpacity=".18" stroke={h} strokeOpacity=".6" strokeWidth="1.2" />
      {[[82, 124], [96, 132], [104, 120]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2.5" stroke={h} className="art-blink" />
      ))}
      <path d="M150 64h40v76q0 8 -8 8h-24q-8 0 -8 -8Z" stroke={S} strokeOpacity=".6" strokeWidth="1.8" />
      <path d="M150 104h40" stroke={h} strokeOpacity=".6" />
      {/* molecule */}
      {[[236, 64], [276, 84], [262, 128], [218, 118], [292, 44]].map(([x, y], i, arr) => (
        <g key={i}>
          {i > 0 && <path d={`M${arr[0][0]} ${arr[0][1]}L${x} ${y}`} stroke={S} strokeOpacity=".4" />}
          <circle cx={x} cy={y} r={i === 0 ? 9 : 6} stroke={h} strokeWidth="1.8" fill="#172841" />
        </g>
      ))}
      <path d="M236 64 L276 84" stroke={h} strokeWidth="1.6" className="art-flow" />
      <Dim x1={150} x2={190} y={164} label="250 ml" />
    </Frame>
  )
}

const CATEGORIES: CategoryMeta[] = [
  { key: 'robotics', label: 'Robotics & Automation', hue: '#22d3ee', icon: <Bot size={14} />, Art: RoboticsArt },
  { key: 'manufacturing', label: 'Manufacturing', hue: '#818cf8', icon: <Cog size={14} />, Art: ManufacturingArt },
  { key: 'materials', label: 'Materials', hue: '#2dd4bf', icon: <Microscope size={14} />, Art: MaterialsArt },
  { key: 'automotive', label: 'Automotive', hue: '#38bdf8', icon: <Car size={14} />, Art: AutomotiveArt },
  { key: 'electrical', label: 'Electrical', hue: '#a78bfa', icon: <CircuitBoard size={14} />, Art: ElectricalArt },
  { key: 'power', label: 'Power', hue: '#7dd3fc', icon: <Zap size={14} />, Art: PowerArt },
  { key: 'design', label: 'Design', hue: '#e879f9', icon: <PenTool size={14} />, Art: DesignArt },
  { key: 'fashion', label: 'Fashion', hue: '#f0abfc', icon: <Scissors size={14} />, Art: FashionArt },
  { key: 'general', label: 'General', hue: '#5eead4', icon: <FlaskConical size={14} />, Art: GeneralArt },
]

/** Map a lab's free-text category to its visual identity. */
export function categoryMeta(category?: string | null): CategoryMeta {
  const c = (category ?? '').toLowerCase()
  const hit = CATEGORIES.find(m => c.includes(m.key))
    ?? (c.includes('automation') ? CATEGORIES[0]
      : c.includes('textile') ? CATEGORIES[7]
      : c.includes('electronic') ? CATEGORIES[4] : undefined)
  return hit ? { ...hit, label: category || hit.label }
    : { ...CATEGORIES[8], label: category || 'General' }
}

export function LabArt({ category, className = '' }: {
  category?: string | null; className?: string
}) {
  const { Art } = categoryMeta(category)
  return <Art className={className} />
}
