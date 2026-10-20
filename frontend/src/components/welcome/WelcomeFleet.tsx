/**
 * Welcome finale backdrop: an ABB IRB 2400 (ROS-Industrial, Apache-2.0) that "writes" the heading as it
 * types, and a UR5e (Universal Robots, BSD-3) working beside it - published meshes and joint chains. Decorative demo motion only - not lab
 * equipment, nothing is read from or sent to a robot. Renders only while on screen; static under
 * reduced motion. `compact` (phones): two arms.
 */
import { Suspense, useEffect, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { flange, solveTool } from './penWriter'
import { WRITE } from './writeState'
import * as THREE from 'three'
import MeshArm from '../robot/MeshArm'
import { UR5E, UrdfModel, solveToward } from '../robot/robotModels'
import { ABB_IRB2400 } from './industrial'
import { KINOVA_GEN3 } from './kinova'
import { noShaderChecks } from '../robot/threeSetup'

// The writer: ABB IRB 2400 with a parallel gripper (drawn as simple boxes) holding a big white pen
// along the tool axis. Boxes = illustration, not manufacturer CAD.
const ABB_WRITER: UrdfModel = { ...ABB_IRB2400, toolBoxes: [
  { size: [0.05, 0.11, 0.09], xyz: [0.025, 0, 0], color: '#2b3442' },     // gripper body
  { size: [0.07, 0.018, 0.05], xyz: [0.08, 0.03, 0], color: '#94a3b8' },  // finger
  { size: [0.07, 0.018, 0.05], xyz: [0.08, -0.03, 0], color: '#94a3b8' }, // finger
] }

type Cell = { model: UrdfModel; scale?: number; at: [number, number]; face: number; home: number[]; amp: number[]; w: number[]; ph: number; ped: number; writer?: boolean }
// Two arms: the ABB on the left WRITES the heading (its motion follows `write`, 0..1, the share of
// the text typed so far); the UR5e on the right works on its own. Different speeds, never in step.
const CELLS: Cell[] = [
  // the writer (pose comes from the pen IK below, not from these numbers)
  { model: ABB_WRITER, at: [0, 0], face: -Math.PI / 2, ped: 0.2, ph: 0, writer: true, home: [0, 0.3, 0.1, 0, 0.5, 0], amp: [0, 0, 0, 0, 0, 0], w: [0, 0, 0, 0, 0, 0] },
  // sides - two DIFFERENT robots
  { model: KINOVA_GEN3, scale: 1.2, at: [-2.6, -1.2], face: 0.6, ped: 0.5, ph: 3.3, home: [0, 0.5, 2.0, 0, 0.9, 0], amp: [1.4, 0.5, 0.55, 1.4, 0.7, 2.0], w: [0.7, 0.9, 0.8, 1.1, 1.0, 1.4] },
  { model: UR5E, scale: 1.1, at: [2.6, -1.2], face: -0.7, ped: 0.55, ph: 2.1, home: [0, -1.2, 1.5, -1.9, -1.57, 0], amp: [1.4, 0.55, 0.65, 0.6, 0.45, 1.8], w: [0.6, 0.8, 0.7, 1.0, 0.9, 1.3] },
]

/** Pen points in the flange frame (tool axis +x): tip and back end. */
const PEN_TIP: [number, number, number] = [0.36, 0, 0], PEN_BACK: [number, number, number] = [0.04, 0, 0]
const PLANE_Z = 0.95                                   // writing plane, world z (between robot and viewer)
const LIM_W: [number, number][] = Array(6).fill([-Math.PI, Math.PI])

/** The writer: every frame the pen tip is solved onto the typing caret of the heading (its screen
 *  position projected onto a plane in front of the robot), the pen pointing at the viewer. */
function Writer({ c, t, still }: { c: Cell; t: number; still: boolean }) {
  const { camera, gl } = useThree()
  const frame = useRef<THREE.Group>(null)
  const q = useRef<number[]>([0, 0.2, 0.3, 0, -0.3, 0])
  const smooth = useRef<THREE.Vector3 | null>(null)
  const lastCaret = useRef<[number, number] | null>(null)
  const lastSolve = useRef(0)
  const [, tick] = useState(0)
  const ray = useRef(new THREE.Raycaster()).current
  const plane = useRef(new THREE.Plane(new THREE.Vector3(0, 0, 1), -PLANE_Z)).current
  useFrame(() => {
    const write = still ? 1 : WRITE.v
    const g = frame.current
    if (!g) return
    const r = gl.domElement.getBoundingClientRect()
    const caret = document.querySelector('#wl-end .wl-caret') as HTMLElement | null
    const h2 = document.querySelector('#wl-end h2') as HTMLElement | null
    let sx: number, sy: number, lift = 0
    if (caret && write > 0 && write < 1) {
      const cr = caret.getBoundingClientRect(); sx = cr.left; sy = cr.top + cr.height * 0.55
      lastCaret.current = [sx, sy]
    } else if (lastCaret.current && write >= 0.95) {   // finished: stay where it stopped writing, pen lifted
      [sx, sy] = lastCaret.current; lift = 0.12
    } else if (h2) {                                    // not started: wait above the start of line 1
      const hr = h2.getBoundingClientRect(); sx = hr.left + hr.width * 0.1; sy = hr.top; lift = 0.18
      lastCaret.current = null
    } else return
    ray.setFromCamera(new THREE.Vector2(((sx - r.left) / r.width) * 2 - 1, -((sy - r.top) / r.height) * 2 + 1), camera)
    const hit = new THREE.Vector3()
    if (!ray.ray.intersectPlane(plane, hit)) return
    if (write > 0 && write < 1) hit.y += Math.sin(t * 34) * 0.012          // pen strokes
    // ease toward the target: travels (line 1 -> line 2, in / out) glide instead of jumping
    if (!smooth.current) smooth.current = hit.clone()
    smooth.current.lerp(hit, write > 0 && write < 0.95 ? 0.5 : 0.1)
    hit.copy(smooth.current)
    const toCam = camera.position.clone().sub(hit).normalize()
    hit.addScaledVector(toCam, lift)
    // pen leans back and up (like a hand holding it) so its whole length stays visible
    const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), toCam).normalize()
    const dirBack = toCam.clone().multiplyScalar(-0.35).add(new THREE.Vector3(0, 0.9, 0)).addScaledVector(right, 0.3).normalize()
    const back = hit.clone().addScaledVector(dirBack, PEN_TIP[0] - PEN_BACK[0])
    g.updateMatrixWorld()
    const tipL = g.worldToLocal(hit.clone()), backL = g.worldToLocal(back)
    const now = performance.now()
    if (now - lastSolve.current < 33) return
    lastSolve.current = now
    const sol = solveTool(c.model, q.current, [PEN_TIP, PEN_BACK], [[tipL.x, tipL.y, tipL.z], [backL.x, backL.y, backL.z]], [1, 0.6], LIM_W, 14)
    q.current = q.current.map((v, i) => v + (sol[i] - v) * 0.6)      // ease the joints: no jumps
    tick(k => (k + 1) % 1000)
  })
  return (
    <group position={[c.at[0], 0, c.at[1]]} rotation={[0, c.face, 0]}>
      <mesh position={[0, c.ped / 2, 0]}><cylinderGeometry args={[0.2, 0.24, c.ped, 32]} /><meshStandardMaterial color="#1e3a5f" metalness={0.6} roughness={0.35} /></mesh>
      <mesh position={[0, 0.01, 0]}><cylinderGeometry args={[0.38, 0.4, 0.02, 48]} /><meshStandardMaterial color="#24d4f2" emissive="#24d4f2" emissiveIntensity={WRITE.v > 0 && WRITE.v < 1 ? 1.2 : 0.35} transparent opacity={0.3} /></mesh>
      <group ref={frame} position={[0, c.ped, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <MeshArm model={c.model} q={q.current} accent="#24d4f2" />
        <Marker m={flange(c.model, q.current)} />
      </group>
    </group>)
}

/** A whiteboard marker held along the tool axis (+x): white barrel, grey cap end, cyan felt tip. */
function Marker({ m }: { m: THREE.Matrix4 }) {
  return (
    <group matrixAutoUpdate={false} matrix={m}>
      <group rotation={[0, 0, -Math.PI / 2]}>{/* cylinders run along y; turn them onto +x */}
        <mesh position={[0, 0.17, 0]}><cylinderGeometry args={[0.016, 0.016, 0.24, 24]} /><meshStandardMaterial color="#ffffff" roughness={0.35} /></mesh>
        <mesh position={[0, 0.045, 0]}><cylinderGeometry args={[0.017, 0.017, 0.02, 24]} /><meshStandardMaterial color="#64748b" /></mesh>
        <mesh position={[0, 0.3, 0]}><cylinderGeometry args={[0.012, 0.016, 0.03, 24]} /><meshStandardMaterial color="#e2e8f0" /></mesh>
        <mesh position={[0, 0.34, 0]}><coneGeometry args={[0.009, 0.05, 20]} /><meshStandardMaterial color="#24d4f2" emissive="#24d4f2" emissiveIntensity={0.6} /></mesh>
      </group>
    </group>)
}

function Arm({ c }: { c: Cell }) {
  // Each side robot runs its OWN clock (independent of the page's typing re-renders), so it moves
  // from the first moment the section is on screen.
  const [t, setT] = useState(0)
  const last = useRef(0)
  useFrame(() => { const e = performance.now() / 1000;   // wall clock: R3F's clock only advances in continuous mode
    if (e - last.current > 1 / 25) { last.current = e; setT(e) } })
  const q = c.home.map((h, i) => h + c.amp[i] * Math.sin(t * c.w[i] + c.ph + i * 0.8))
  return (
    <group position={[c.at[0], 0, c.at[1]]} rotation={[0, c.face, 0]} scale={c.scale ?? 1}>
      <mesh position={[0, c.ped / 2, 0]}><cylinderGeometry args={[0.16, 0.2, c.ped, 32]} /><meshStandardMaterial color="#1e3a5f" metalness={0.6} roughness={0.35} /></mesh>
      <mesh position={[0, 0.01, 0]}><cylinderGeometry args={[0.32, 0.34, 0.02, 48]} /><meshStandardMaterial color="#24d4f2" emissive="#24d4f2" emissiveIntensity={0.35} transparent opacity={0.3} /></mesh>
      {/* robot frames are Z-up; three.js is Y-up */}
      <group position={[0, c.ped, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <MeshArm model={c.model} q={q} accent="#24d4f2" />
      </group>
    </group>)
}

function Scene({ still, compact }: { still: boolean; compact: boolean }) {
  const [t, setT] = useState(0)
  const last = useRef(0)
  useFrame(({ clock, camera }) => {
    if (still) return
    const e = performance.now() / 1000
    if (e - last.current > 1 / 45) { last.current = e; setT(e) }
  })
  const cells = compact ? [CELLS[0], { ...CELLS[2], at: [1.4, -1.2] as [number, number] }] : CELLS
  return <>{cells.map((c, i) => c.writer ? <Writer key={i} c={c} t={t} still={still} /> : <Arm key={i} c={c} />)}</>
}

export default function WelcomeFleet({ className = '' }: { className?: string }) {
  const box = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  const still = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const compact = typeof window !== 'undefined' && window.innerWidth < 860
  useEffect(() => {
    const el = box.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: '120px' })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <div ref={box} className={className}>
      <Canvas frameloop={still ? 'demand' : 'always'} dpr={1} camera={{ position: [0, 1.6, 3.6], fov: 42 }}
              onCreated={st => { noShaderChecks(st); st.camera.lookAt(0, 0.75, -0.9) }}>
        <fog attach="fog" args={['#071426', 4, 10]} />
        <hemisphereLight args={['#e0f2fe', '#0f172a', 0.9]} />
        <ambientLight intensity={0.35} />
        <directionalLight position={[3, 5, 3]} intensity={1.8} />
        <pointLight position={[-2, 1.6, 0.5]} intensity={2} distance={5} color="#24d4f2" />
        <pointLight position={[2.4, 1.4, 0.2]} intensity={1.6} distance={5} color="#ffb547" />
        <gridHelper args={[14, 70, '#1f6f8b', '#10263f']} />
        <Suspense fallback={null}><Scene still={still} compact={compact} /></Suspense>
      </Canvas>
    </div>)
}
