/**
 * The welcome page's moving robots: the lab's two real arms drawn from the
 * manufacturers' meshes (the same URDF chains as the digital twin), moving
 * through a smooth DEMO motion. Nothing here reads or commands a robot - the
 * caption says so. Rendering stops while the canvas is off screen.
 */
import { Suspense, useEffect, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import MeshArm from '../robot/MeshArm'
import { FANUC_LRMATE200ID, UR5E, UrdfModel } from '../robot/robotModels'
import { noShaderChecks } from '../robot/threeSetup'

type Wave = { home: number[]; amp: number[]; w: number[] }
// Gentle pick-and-place style sweeps (rad). Shapes only - not a recorded trajectory.
const UR_WAVE: Wave = { home: [0, -1.2, 1.5, -1.9, -1.57, 0], amp: [0.9, 0.35, 0.4, 0.4, 0.3, 1.2], w: [0.32, 0.45, 0.4, 0.55, 0.5, 0.7] }
const FA_WAVE: Wave = { home: [0, 0.2, -0.3, 0, -0.9, 0], amp: [0.85, 0.35, 0.35, 0.6, 0.45, 1.4], w: [0.28, 0.42, 0.5, 0.6, 0.55, 0.8] }

function Moving({ model, wave, accent, phase, still }: { model: UrdfModel; wave: Wave; accent: string; phase: number; still: boolean }) {
  const [q, setQ] = useState(wave.home)
  const last = useRef(0)
  useFrame(({ clock }) => {
    if (still) return
    const t = clock.elapsedTime
    if (t - last.current < 1 / 40) return               // ~40 updates/s is smooth and cheap
    last.current = t
    setQ(wave.home.map((h, i) => h + wave.amp[i] * Math.sin(t * wave.w[i] + phase + i * 0.7)))
  })
  return <MeshArm model={model} q={q} accent={accent} gripper={still ? 0 : (Math.sin(performance.now() / 900) + 1) / 2} />
}

/** spread: place the arms far apart (a backdrop behind centred text). */
export default function WelcomeArms({ className = '', spread = false }: { className?: string; spread?: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  const still = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  useEffect(() => {
    const el = box.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: '120px' })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <div ref={box} className={className}>
      <Canvas frameloop={visible && !still ? 'always' : 'demand'} dpr={[1, 1.6]} camera={{ position: [0.1, 1.15, 3.7], fov: 40 }}
              onCreated={st => { noShaderChecks(st); st.camera.lookAt(0, 0.85, 0) }}>
        <hemisphereLight args={['#dbeafe', '#0f172a', 0.8]} />
        <ambientLight intensity={0.35} />
        <directionalLight position={[2, 3, 2]} intensity={1.6} />
        <directionalLight position={[-2, 1.2, -1]} intensity={0.5} color="#24d4f2" />
        <gridHelper args={[4, 32, '#1f6f8b', '#13304f']} />
        <Suspense fallback={null}>
          {/* Robot frames are Z-up; three.js is Y-up. */}
          <group rotation={[-Math.PI / 2, 0, 0]}>
            {/* FANUC ER-4iA on the floor, left */}
            <group position={[spread ? -1.75 : -0.6, 0, 0]}>
              <Moving model={FANUC_LRMATE200ID} wave={FA_WAVE} accent="#facc15" phase={0} still={still} />
            </group>
            {/* UR5e hanging upside down from its gantry, right - as in the lab */}
            <group position={[spread ? 1.75 : 0.55, 0, UR5E.ceilingHeight ?? 1.4]} rotation={[Math.PI, 0, 0]}>
              <mesh position={[0, 0, -0.012]}><boxGeometry args={[0.4, 0.4, 0.02]} /><meshStandardMaterial color="#9ca3af" metalness={0.5} roughness={0.4} /></mesh>
              <Moving model={UR5E} wave={UR_WAVE} accent="#24d4f2" phase={1.3} still={still} />
            </group>
          </group>
        </Suspense>
      </Canvas>
    </div>)
}
