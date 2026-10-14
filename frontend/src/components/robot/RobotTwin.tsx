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
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RobotModel, forward } from './kinematics'
import MeshArm from './MeshArm'
import { Vec3, solveToward, tipPosition, urdfFor } from './robotModels'
import type { Hit, Table, Workcell } from './workcell'

// Each twin keeps its OWN view controls (two twins on one page used to share one, so grabbing one
// arm could leave the other's view stuck). Kept on the canvas element.
type ViewName = 'front' | 'back' | 'right' | 'left' | 'top' | 'bottom' | 'iso'
const orbitOf = (el: HTMLElement) => (el as HTMLElement & { __orbit?: OrbitControls }).__orbit ?? null

function Controls({ resetKey, size, view, lookY }: { resetKey: number; size: number; view: { name: ViewName; n: number }; lookY?: number }) {
  const { camera, gl, invalidate } = useThree()
  useEffect(() => {
    // View buttons: the camera jumps to that side of the robot, same distance, looking at it.
    const c = orbitOf(gl.domElement)
    if (!c || view.n === 0) return
    const k = size / 0.85, d = 2.4 * k, t = c.target
    const at: Record<ViewName, [number, number, number]> = {
      front: [d, 0, 0], back: [-d, 0, 0], right: [0, 0, -d], left: [0, 0, d], top: [0.001, d, 0], bottom: [0.001, -d, 0],
      iso: [1.55 * k, 1.05 * k - 0.38 * k, 1.65 * k] }
    const [x, y, z] = at[view.name]
    camera.position.set(t.x + x, t.y + y, t.z + z)
    camera.lookAt(t); c.update(); invalidate()
  }, [view, camera, gl, invalidate, size])
  useEffect(() => {
    // Framed from the arm's own size: the whole robot in view, from front-right, slightly above.
    const k = size / 0.85
    camera.position.set(1.55 * k, 1.05 * k, 1.65 * k)
    const ty = lookY ?? 0.38 * k
    camera.position.y += ty - 0.38 * k
    camera.lookAt(0, ty, 0)
    const c = new OrbitControls(camera, gl.domElement)
    c.target.set(0, ty, 0)
    c.enableDamping = false
    c.minDistance = 0.4
    c.maxDistance = 4
    c.addEventListener('change', () => invalidate())
    ;(gl.domElement as HTMLElement & { __orbit?: OrbitControls }).__orbit = c
    c.update()
    invalidate()
    return () => c.dispose()
  }, [camera, gl, invalidate, resetKey, size, lookY])
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

// The UR5e's cell at the university: aluminium frame (robot hangs from its top) and the table.
// Lab measurements of 2026-10-07 (robot touched marks); world: +x front, +y Kinect side, z up,
// origin = floor under the robot base. Drawing only.
const BEAM = 0.05
function Box({ c, s, color, opacity = 1 }: { c: [number, number, number]; s: [number, number, number]; color: string; opacity?: number }) {
  return <mesh position={c}><boxGeometry args={s} />
    <meshStandardMaterial color={color} metalness={0.4} roughness={0.5} transparent={opacity < 1} opacity={opacity} /></mesh>
}
function UR5eCell({ table }: { table?: Table | null }) {
  const fx = [-0.769, 0.731], fy = [-0.880, 1.135], H = 1.88
  const cx = (fx[0] + fx[1]) / 2, cy = (fy[0] + fy[1]) / 2, lx = fx[1] - fx[0], ly = fy[1] - fy[0]
  const t = table === undefined ? { present: true, x0: -0.514, x1: 0.186, y0: -0.630, y1: 0.770, height: 0.71 } : table
  const tx = [t?.x0 ?? 0, t?.x1 ?? 0], ty = [t?.y0 ?? 0, t?.y1 ?? 0], T = t?.height ?? 0, alu = '#94a3b8', wood = '#c9a46a'
  const beams: JSX.Element[] = []
  for (const x of fx) for (const y of fy) beams.push(<Box key={`p${x}${y}`} c={[x, y, H / 2]} s={[BEAM, BEAM, H]} color={alu} />)
  for (const z of [BEAM / 2, H]) {
    for (const x of fx) beams.push(<Box key={`y${x}${z}`} c={[x, cy, z]} s={[BEAM, ly, BEAM]} color={alu} />)
    for (const y of fy) beams.push(<Box key={`x${y}${z}`} c={[cx, y, z]} s={[lx, BEAM, BEAM]} color={alu} />)
  }
  const legs = [[tx[0], ty[0]], [tx[0], ty[1]], [tx[1], ty[0]], [tx[1], ty[1]]].map(([x, y], i) =>
    <Box key={`l${i}`} c={[x + (x < 0 ? 0.025 : -0.025), y + (y < 0 ? 0.025 : -0.025), (T - 0.05) / 2]} s={[0.05, 0.05, T - 0.05]} color={alu} />)
  return <group>{beams}{t?.present && legs}
    {t?.present && <Box c={[(tx[0] + tx[1]) / 2, (ty[0] + ty[1]) / 2, T - 0.025]} s={[tx[1] - tx[0], ty[1] - ty[0], 0.05]} color={wood} opacity={0.9} />}</group>
}

/** Virtual obstacles (world frame, z up). Amber = MANUAL, violet = CAMERA_ESTIMATE (rough),
 *  red = the model predicts a contact. Never drawn as "verified". */
function Obstacles({ cell, hits, selected }: { cell: Workcell; hits: Hit[]; selected?: string | null }) {
  const hit = new Set(hits.map(h => h.obstacle))
  return <group>{cell.obstacles.map(o => (
    <group key={o.id}>
      <Box c={[o.x, o.y, o.z]} s={[o.w, o.d, o.h]} opacity={0.55}
           color={hit.has(o.id) ? '#ef4444' : o.source === 'CAMERA_ESTIMATE' ? '#a78bfa' : '#f59e0b'} />
      {selected === o.id && <mesh position={[o.x, o.y, o.z]}><boxGeometry args={[o.w + 0.01, o.d + 0.01, o.h + 0.01]} />
        <meshBasicMaterial color="#ffffff" wireframe /></mesh>}
    </group>))}</group>
}

function Scene(props: TwinProps & { resetKey: number; view: { name: ViewName; n: number } }) {
  const { invalidate, camera, gl } = useThree()
  const baseRef = useRef<THREE.Group>(null)
  const qRef = useRef<number[]>(props.q ?? [])
  qRef.current = props.q ?? []
  useEffect(() => { invalidate() }, [props.q, props.selected, props.moving, props.homeQ, props.trail, invalidate])
  const q = props.q ?? new Array(6).fill(0)
  const reach = props.model.dh.reduce((n, p) => n + Math.abs(p.a) + Math.abs(p.d), 0) * 0.62
  const urdf = urdfFor(props.model.key)
  return (
    <>
      <Controls resetKey={props.resetKey} view={props.view} lookY={urdf.ceilingHeight ? urdf.ceilingHeight / 2 : undefined}
                size={(reach / 0.62 / 1.4) * (props.compact ? 0.74 : 1) * (urdf.ceilingHeight ? 2.1 : 1)} />
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
       {props.model.key === 'UR5E' && urdf.ceilingHeight && <UR5eCell table={props.workcell ? props.workcell.table : undefined} />}
       {props.workcell && <Obstacles cell={props.workcell} hits={props.hits ?? []} selected={props.selectedObstacle} />}
       <group ref={baseRef} position={[0, 0, urdf.ceilingHeight ?? 0]} rotation={[urdf.ceilingHeight ? Math.PI : 0, 0, 0]}>
        {urdf.ceilingHeight && <mesh position={[0, 0, -0.012]}>
          <boxGeometry args={[0.5, 0.5, 0.02]} /><meshStandardMaterial color="#9ca3af" metalness={0.5} roughness={0.4} /></mesh>}
        {/* The manufacturer's meshes; the simple cylinder arm shows while they load. */}
        {props.trail && <Trail points={props.trail} color={props.trailColor ?? props.model.accent} />}
        <Suspense fallback={<Arm model={props.model} q={q} selected={props.selected} moving={props.moving} />}>
          <Loaded onLoad={invalidate} />
          {props.homeQ && <MeshArm model={urdf} q={props.homeQ} ghost accent={props.model.accent} />}
          <MeshArm model={urdf} q={q} selected={props.selected} moving={props.moving} accent={props.model.accent}
                   onSelect={props.onSelect} gripper={props.gripper}
                   onGrab={props.onPose && baseRef.current ? () => {
                     // Hand-guiding (preview): grab any part, the tool flange follows the
                     // mouse on a plane facing the viewer; the joints come from IK.
                     const base = baseRef.current!
                     base.updateMatrixWorld()
                     const tip = new THREE.Vector3(...tipPosition(urdf, qRef.current)).applyMatrix4(base.matrixWorld)
                     const n = new THREE.Vector3(); camera.getWorldDirection(n)
                     const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(n, tip)
                     const ray = new THREE.Raycaster(), hit = new THREE.Vector3(), toBase = base.matrixWorld.clone().invert()
                     const lim = props.model.limitsDeg.map(([lo, hi]) => [lo * Math.PI / 180, hi * Math.PI / 180] as [number, number])
                     const unfreeze = freezeView(camera, gl.domElement, invalidate)
                     const move = (e: PointerEvent) => {
                       const r = gl.domElement.getBoundingClientRect()
                       ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera)
                       if (!ray.ray.intersectPlane(plane, hit)) return
                       const t = hit.clone().applyMatrix4(toBase)
                       props.onPose!(solveToward(urdf, qRef.current, [t.x, t.y, t.z], lim))
                     }
                     const up = () => {
                       window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
                       unfreeze()
                     }
                     window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
                   } : props.onJointDrag ? (j, x0) => {
                     // Hold a link and drag left / right: that joint turns. The view
                     // does not orbit while a link is held. Drawing only.
                     let last = x0
                     const unfreeze = freezeView(camera, gl.domElement, invalidate)
                     const move = (e: PointerEvent) => { props.onJointDrag!(j, (e.clientX - last) * 0.01); last = e.clientX }
                     const up = () => {
                       window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
                       unfreeze()
                     }
                     window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
                   } : undefined} />
        </Suspense>
       </group>
      </group>
    </>)
}

/** While a robot part is held the view must not turn: OrbitControls may already have started
 *  rotating (it sees the same pointerdown), so its controls are switched off AND the camera is put
 *  back where it was on every move until the part is released. */
function freezeView(camera: THREE.Camera, el: HTMLElement, invalidate: () => void) {
  const c = orbitOf(el)
  const pos = camera.position.clone(), quat = camera.quaternion.clone(), tgt = c?.target.clone()
  if (c) c.enabled = false
  const pin = () => { camera.position.copy(pos); camera.quaternion.copy(quat); if (c && tgt) c.target.copy(tgt); invalidate() }
  window.addEventListener('pointermove', pin, true)
  return () => { window.removeEventListener('pointermove', pin, true); pin(); if (c) { c.enabled = true; c.update() } }
}

export interface TwinProps {
  /** Virtual workcell (planning aid): table + obstacles, and the modelled contacts to highlight. */
  workcell?: Workcell | null
  hits?: Hit[]
  selectedObstacle?: string | null
  /** Preview only: a link was dragged - turn joint j by d rad (never sent to a robot). */
  onJointDrag?: (j: number, d: number) => void
  /** Preview only: hand-guiding - grab any part and the whole arm follows (IK). */
  onPose?: (q: number[]) => void
  /** Preview only: gripper 0 open .. 1 closed. */
  gripper?: number | null
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

const VIEWS: [ViewName, string][] = [['front', 'Front'], ['back', 'Back'], ['right', 'Right'], ['left', 'Left'], ['top', 'Top'], ['bottom', 'Bottom'], ['iso', '3D']]

export default function RobotTwin(props: TwinProps & { resetKey?: number; className?: string; label?: string }) {
  const [view, setView] = useState<{ name: ViewName; n: number }>({ name: 'iso', n: 0 })
  return (
    <div className={`relative bg-[radial-gradient(ellipse_at_50%_35%,rgba(56,189,248,0.10),transparent_65%)] ${props.className ?? 'h-80'}`}
         aria-label={props.label ?? `${props.model.label} 3D view`} data-trail-points={props.trail?.length ?? 0}>
      <Canvas frameloop="demand" dpr={[1, 1.75]} camera={{ fov: 40, near: 0.05, far: 20 }}
              style={{ opacity: props.q ? (props.stale ? 0.55 : 1) : 0.45, filter: props.stale ? 'grayscale(0.7)' : undefined }}>
        <Scene {...props} resetKey={props.resetKey ?? 0} view={view} />
      </Canvas>
      <div className="absolute bottom-2 right-2 flex flex-wrap gap-1 justify-end">
        {VIEWS.map(([v, label]) => (
          <button key={v} type="button" onClick={() => setView(o => ({ name: v, n: o.n + 1 }))}
                  className={`px-2 py-0.5 rounded-md text-[11px] border ${view.name === v && view.n ? 'bg-accent-500/25 border-accent-400/60 text-white' : 'bg-ink-900/75 border-ink-600 text-slate-300 hover:text-white'}`}>
            {label}</button>))}
      </div>
      {!props.q && <div className="absolute inset-0 grid place-items-center pointer-events-none text-[12.5px] text-slate-400">
        No telemetry - pose unknown</div>}
      {props.q && props.stale && <div className="absolute top-2 left-2 pointer-events-none text-[11.5px] px-2 py-0.5 rounded-md bg-ink-900/80 text-warn-soft border border-warn/30">
        Last known pose - no fresh telemetry</div>}
    </div>)
}
