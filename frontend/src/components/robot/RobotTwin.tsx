/**
 * 3D twin of a robot arm, driven only by real telemetry (q in rad). No
 * telemetry = the arm is shown greyed at its last known pose (or zero pose,
 * labelled "no data") - it never moves on its own.
 *
 * Rendering is on demand (frameloop="demand"): a frame is drawn only when the
 * joints, the selection or the view change, so an open twin costs nothing
 * while the robot is still. Loaded lazily (three.js stays out of other pages).
 */
import { Canvas, ThreeEvent, useThree } from '@react-three/fiber'
import { Suspense, useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RobotModel, forward } from './kinematics'
import MeshArm from './MeshArm'
import { Vec3, urdfFor } from './robotModels'

function Controls({ resetKey, size }: { resetKey: number; size: number }) {
  const { camera, gl, invalidate } = useThree()
  useEffect(() => {
    // Framed from the arm's own size: the whole robot in view, from front-right, slightly above.
    const k = size / 0.85
    camera.position.set(1.55 * k, 1.05 * k, 1.65 * k)
    camera.lookAt(0, 0.38 * k, 0)
    const c = new OrbitControls(camera, gl.domElement)
    c.target.set(0, 0.38 * k, 0)
    c.enableDamping = false
    c.minDistance = 0.4
    c.maxDistance = 4
    c.addEventListener('change', () => invalidate())
    c.update()
    invalidate()
    return () => c.dispose()
  }, [camera, gl, invalidate, resetKey, size])
  return null
}

function Segment({ from, to, radius, color, opacity = 1 }: {
  from: THREE.Vector3; to: THREE.Vector3; radius: number; color: string; opacity?: number
}) {
  const len = from.distanceTo(to)
  const mid = useMemo(() => from.clone().add(to).multiplyScalar(0.5), [from, to])
  const quat = useMemo(() => new THREE.Quaternion().setFromUnitVectors(
    new THREE.Vector3(0, 1, 0), to.clone().sub(from).normalize()), [from, to])
  if (len < 0.01) return null
  return (
    <mesh position={mid} quaternion={quat}>
      <cylinderGeometry args={[radius, radius, len, 20]} />
      <meshStandardMaterial color={color} transparent={opacity < 1} opacity={opacity} metalness={0.25} roughness={0.55} />
    </mesh>)
}

function Arm({ model, q, ghost = false, selected, moving, onSelect }: {
  model: RobotModel; q: number[]; ghost?: boolean; selected?: number | null; moving?: boolean[] | null
  onSelect?: (j: number) => void
}) {
  const frames = useMemo(() => forward(model, q).map(f => ({
    o: new THREE.Vector3(...f.origin), z: new THREE.Vector3(...f.z) })), [model, q])
  const op = ghost ? 0.18 : 1
  return (
    <group>
      {frames.slice(1).map((f, i) => (
        <Segment key={`l${i}`} from={frames[i].o} to={f.o} radius={i === 0 ? 0.045 : 0.035}
                 color={ghost ? '#94a3b8' : model.color} opacity={op} />))}
      {frames.slice(0, 6).map((f, i) => {
        const active = !ghost && (selected === i)
        const isMoving = !ghost && !!moving?.[i]
        const color = ghost ? '#94a3b8' : active ? model.accent : isMoving ? '#22c55e' : '#334155'
        const half = f.z.clone().multiplyScalar(0.055)
        return (
          <group key={`j${i}`} onClick={(e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); onSelect?.(i) }}>
            <Segment from={f.o.clone().sub(half)} to={f.o.clone().add(half)} radius={0.052} color={color} opacity={op} />
          </group>)
      })}
      {!ghost && <mesh position={frames[6].o}><sphereGeometry args={[0.025, 16, 16]} />
        <meshStandardMaterial color={model.accent} emissive={model.accent} emissiveIntensity={0.4} /></mesh>}
    </group>)
}

/** The tool tip's path as a glowing tube: newest part bright, older part fading. */
function Trail({ points, color }: { points: Vec3[]; color: string }) {
  const mesh = useMemo(() => {
    const pts: THREE.Vector3[] = []
    for (const p of points) {                     // drop repeats (a still arm adds the same point)
      const v = new THREE.Vector3(...p)
      if (!pts.length || pts[pts.length - 1].distanceTo(v) > 0.002) pts.push(v)
    }
    if (pts.length < 2) return null
    const curve = new THREE.CatmullRomCurve3(pts)
    const seg = Math.min(400, pts.length * 4)
    const g = new THREE.TubeGeometry(curve, seg, 0.009, 8, false)
    // Colour along the tube: dark (old) -> full colour (new).
    const c = new THREE.Color(color), bg = new THREE.Color('#0b1220')
    const n = g.attributes.position.count, ring = 9
    const col = new Float32Array(n * 3)
    for (let i = 0; i < n; i++) {
      const m = bg.clone().lerp(c, 0.45 + 0.55 * (Math.floor(i / ring) / seg))
      col.set([m.r, m.g, m.b], i * 3)
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3))
    return new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 }))
  }, [points, color])
  useEffect(() => () => { if (mesh) { mesh.geometry.dispose(); (mesh.material as THREE.Material).dispose() } }, [mesh])
  if (!mesh) return null
  return <primitive object={mesh} />
}

/** Draws one frame once the meshes are in (on-demand rendering). */
function Loaded({ onLoad }: { onLoad: () => void }) {
  useEffect(() => { onLoad() }, [onLoad])
  return null
}

function Scene(props: TwinProps & { resetKey: number }) {
  const { invalidate } = useThree()
  useEffect(() => { invalidate() }, [props.q, props.selected, props.moving, props.homeQ, props.trail, invalidate])
  const q = props.q ?? new Array(6).fill(0)
  const reach = props.model.dh.reduce((n, p) => n + Math.abs(p.a) + Math.abs(p.d), 0) * 0.62
  const urdf = urdfFor(props.model.key)
  return (
    <>
      <Controls resetKey={props.resetKey} size={(reach / 0.62 / 1.4) * (props.compact ? 0.74 : 1) * (urdf.ceilingHeight ? 1.35 : 1)} />
      <hemisphereLight args={['#dbeafe', '#0f172a', 0.7]} />
      <ambientLight intensity={0.35} />
      <directionalLight position={[2, 3, 2]} intensity={1.4} />
      <directionalLight position={[-2, 1.5, -1]} intensity={0.35} />
      <gridHelper args={[3, 30, '#334155', '#1e293b']} />
      {/* reach ring: the arm's working circle on the floor (from its geometry) */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.002, 0]}>
        <ringGeometry args={[reach - 0.006, reach, 96]} />
        <meshBasicMaterial color={props.model.accent} transparent opacity={0.35} />
      </mesh>
      {/* Robot frames are Z-up; three.js is Y-up. */}
      <group rotation={[-Math.PI / 2, 0, 0]}>
       <group position={[0, 0, urdf.ceilingHeight ?? 0]} rotation={[urdf.ceilingHeight ? Math.PI : 0, 0, 0]}>
        {urdf.ceilingHeight && <mesh position={[0, 0, -0.012]}>
          <boxGeometry args={[0.5, 0.5, 0.02]} /><meshStandardMaterial color="#9ca3af" metalness={0.5} roughness={0.4} /></mesh>}
        {/* The manufacturer's meshes; the simple cylinder arm shows while they load. */}
        {props.trail && <Trail points={props.trail} color={props.trailColor ?? props.model.accent} />}
        <Suspense fallback={<Arm model={props.model} q={q} selected={props.selected} moving={props.moving} />}>
          <Loaded onLoad={invalidate} />
          {props.homeQ && <MeshArm model={urdf} q={props.homeQ} ghost accent={props.model.accent} />}
          <MeshArm model={urdf} q={q} selected={props.selected} moving={props.moving} accent={props.model.accent}
                   onSelect={props.onSelect} />
        </Suspense>
       </group>
      </group>
    </>)
}

export interface TwinProps {
  /** Tool-tip path to draw (m, robot base frame). */
  trail?: Vec3[] | null
  trailColor?: string
  /** No fresh telemetry: the pose is the last one known. */
  stale?: boolean
  /** Small card: a closer camera. */
  compact?: boolean
  model: RobotModel
  q: number[] | null
  homeQ?: number[] | null
  selected?: number | null
  moving?: boolean[] | null
  onSelect?: (j: number) => void
}

export default function RobotTwin(props: TwinProps & { resetKey?: number; className?: string; label?: string }) {
  return (
    <div className={`relative bg-[radial-gradient(ellipse_at_50%_35%,rgba(56,189,248,0.10),transparent_65%)] ${props.className ?? 'h-80'}`}
         aria-label={props.label ?? `${props.model.label} 3D view`} data-trail-points={props.trail?.length ?? 0}>
      <Canvas frameloop="demand" dpr={[1, 1.75]} camera={{ fov: 40, near: 0.05, far: 20 }}
              style={{ opacity: props.q ? (props.stale ? 0.55 : 1) : 0.45, filter: props.stale ? 'grayscale(0.7)' : undefined }}>
        <Scene {...props} resetKey={props.resetKey ?? 0} />
      </Canvas>
      {!props.q && <div className="absolute inset-0 grid place-items-center pointer-events-none text-[12.5px] text-slate-400">
        No telemetry - pose unknown</div>}
      {props.q && props.stale && <div className="absolute top-2 left-2 pointer-events-none text-[11.5px] px-2 py-0.5 rounded-md bg-ink-900/80 text-warn-soft border border-warn/30">
        Last known pose - no fresh telemetry</div>}
    </div>)
}
