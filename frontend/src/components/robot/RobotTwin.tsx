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
import { Suspense, memo, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RobotModel, forward } from './kinematics'
import MeshArm from './MeshArm'
import { FANUC_CELL, Vec3, mountRotation, solveToward, tipPosition, urdfFor } from './robotModels'
import { FanucCell } from './FanucCell'
import type { Hit, Table, Workcell } from './workcell'
import { noShaderChecks } from './threeSetup'

// Each twin keeps its OWN view controls (two twins on one page used to share one, so grabbing one
// arm could leave the other's view stuck). Kept on the canvas element.
type ViewName = 'front' | 'back' | 'right' | 'left' | 'top' | 'bottom' | 'iso'
const orbitOf = (el: HTMLElement) => (el as HTMLElement & { __orbit?: OrbitControls }).__orbit ?? null

function Controls({ resetKey, size, view, lookY, turned = false }: { resetKey: number; size: number; view: { name: ViewName; n: number }; lookY?: number; turned?: boolean }) {
  const { camera, gl, invalidate } = useThree()
  const side = turned ? -1 : 1
  useEffect(() => {
    // View buttons: the camera jumps to that side of the robot, same distance, looking at it.
    const c = orbitOf(gl.domElement)
    if (!c || view.n === 0) return
    const k = size / 0.85, d = 2.4 * k, t = c.target
    const at: Record<ViewName, [number, number, number]> = {
      // turned (FANUC, owner 2026-10-15): its real front faces what the default view called "right".
      ...(turned ? { front: [0, 0, -d], back: [0, 0, d], right: [-d, 0, 0], left: [d, 0, 0] }
                 : { front: [d, 0, 0], back: [-d, 0, 0], right: [0, 0, -d], left: [0, 0, d] }) as Record<'front' | 'back' | 'right' | 'left', [number, number, number]>,
      top: [0.001, d, 0], bottom: [0.001, -d, 0],
      // 3D: from the front-right (turned: the FANUC cell's doors and controller face the viewer)
      iso: [1.55 * k * side, 1.05 * k - 0.38 * k, 1.65 * k * side] }
    const [x, y, z] = at[view.name]
    camera.position.set(t.x + x, t.y + y, t.z + z)
    camera.lookAt(t); c.update(); invalidate()
  }, [view, camera, gl, invalidate, size, side])
  useEffect(() => {
    // Framed from the arm's own size: the whole robot in view, from front-right, slightly above.
    const k = size / 0.85
    camera.position.set(1.55 * k * side, 1.05 * k, 1.65 * k * side)
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
    // The wheel scrolls the PAGE over an embedded twin (it used to zoom the robot instead, which felt like
    // the page froze while scrolling past the two robots - 2026-10-21); Ctrl + wheel zooms, like a map.
    // In the full-screen view (a dialog) the plain wheel zooms. Capture phase: decided before OrbitControls.
    const onWheel = (e: WheelEvent) => { c.enableZoom = e.ctrlKey || e.metaKey || !!gl.domElement.closest('[role="dialog"]') }
    gl.domElement.addEventListener('wheel', onWheel, { capture: true, passive: true })
    gl.domElement.title = 'Drag to turn the view · Ctrl + mouse wheel to zoom'
    c.update()
    invalidate()
    return () => { gl.domElement.removeEventListener('wheel', onWheel, { capture: true }); c.dispose() }
  }, [camera, gl, invalidate, resetKey, size, lookY, side])
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

/** A still of the finished 3D view, for the instant picture shown next time (2026-10-21): the page then opens
 *  without creating a WebGL context at all (measured: ~270 ms per context + ~120 ms extensions, two robots).
 *  Taken right after an explicit render (no preserveDrawingBuffer); a blank frame - shaders still compiling -
 *  is tiny and retried. Encoded with toBlob (off the main thread): toDataURL froze the page ~250 ms per
 *  still (profile 2026-10-21). */
function Snapshot({ onShot }: { onShot: (url: string) => void }) {
  const { gl, scene, camera } = useThree()
  useEffect(() => {
    let tries = 0, done = false, busy = false
    const t = window.setInterval(() => {
      if (done || busy) return
      if (++tries > 20) { window.clearInterval(t); return }
      try {
        gl.render(scene, camera)
        busy = true
        gl.domElement.toBlob(b => {             // pixels are read now, encoded in the background
          busy = false
          if (done || !b || b.size < 11000) return
          done = true; window.clearInterval(t)
          const r = new FileReader()
          r.onload = () => { if (typeof r.result === 'string') onShot(r.result) }
          r.readAsDataURL(b)
        }, 'image/webp', 0.8)
      } catch { window.clearInterval(t) }
    }, 400)
    return () => { done = true; window.clearInterval(t) }
  }, [gl, scene, camera, onShot])
  return null
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
// The FANUC Educational Cell is drawn in FanucCell.tsx (shared with the Welcome page).
export { FanucCell }

export function UR5eCell({ table }: { table?: Table | null }) {
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

/** The parts that never move with the joints (2026-10-21, owner: "Robots & PCs freezes, especially live"): with
 *  both robots live (8 joint updates a second) every update re-rendered the whole scene - ~30 frame beams, the
 *  FANUC cell, obstacles, lights, ring, controls - and R3F re-diffed them all (prepareUpdate / equ, ~0.5 s per
 *  12 s; 2 freezes > 200 ms). Memoized, a joint update re-renders the arm only. */
const ControlsStatic = memo(Controls)
const FanucCellStatic = memo(FanucCell)
const UR5eCellStatic = memo(UR5eCell, (a, b) => JSON.stringify(a.table ?? null) === JSON.stringify(b.table ?? null))
const ObstaclesStatic = memo(Obstacles, (a, b) => a.cell === b.cell && a.selected === b.selected &&
  a.hits.map(h => h.obstacle).join() === b.hits.map(h => h.obstacle).join())
const Decor = memo(function Decor({ reach, accent }: { reach: number; accent: string }) {
  return <>
    <hemisphereLight args={['#dbeafe', '#0f172a', 0.7]} />
    <ambientLight intensity={0.35} />
    <directionalLight position={[2, 3, 2]} intensity={1.4} />
    <directionalLight position={[-2, 1.5, -1]} intensity={0.35} />
    <gridHelper args={[3, 30, '#334155', '#1e293b']} />
    {/* reach ring: the arm's working circle on the floor (from its geometry) */}
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.002, 0]}>
      <ringGeometry args={[reach - 0.006, reach, 96]} />
      <meshBasicMaterial color={accent} transparent opacity={0.35} />
    </mesh>
  </>
})

function Scene(props: TwinProps & { resetKey: number; view: { name: ViewName; n: number } }) {
  const { invalidate, camera, gl } = useThree()
  const baseRef = useRef<THREE.Group>(null)
  const qRef = useRef<number[]>(props.q ?? [])
  qRef.current = props.q ?? []
  // Redraw only when the VALUES change (2026-10-21): the panel re-renders every second (its staleness clock) and
  // handed over new arrays with the same numbers - each one forced a full 3D redraw while the user scrolled.
  const drawKey = JSON.stringify([props.q, props.selected, props.moving, props.homeQ, props.trail?.length, props.gripper])
  useEffect(() => { invalidate() }, [drawKey, invalidate])
  const q = props.q ?? new Array(6).fill(0)
  const reach = props.model.dh.reduce((n, p) => n + Math.abs(p.a) + Math.abs(p.d), 0) * 0.62
  const urdf = urdfFor(props.model.key)
  return (
    <>
      <ControlsStatic resetKey={props.resetKey} view={props.view} turned={props.model.key === 'FANUC'} lookY={urdf.ceilingHeight ? urdf.ceilingHeight / 2 : urdf.mountHeight ? FANUC_CELL.height_m / 2 : undefined}
                size={(reach / 0.62 / 1.4) * (props.compact ? 0.74 : 1) * (urdf.ceilingHeight ? 2.1 : urdf.mountHeight ? 1.9 : 1)} />
      <Decor reach={reach} accent={props.model.accent} />
      {/* Robot frames are Z-up; three.js is Y-up. */}
      <group rotation={[-Math.PI / 2, 0, 0]}>
       {props.model.key === 'UR5E' && urdf.ceilingHeight && <UR5eCellStatic table={props.workcell ? props.workcell.table : undefined} />}
       {props.model.key === 'FANUC' && urdf.mountHeight && <FanucCellStatic />}
       {props.workcell && <ObstaclesStatic cell={props.workcell} hits={props.hits ?? []} selected={props.selectedObstacle} />}
       <group ref={baseRef} position={[0, 0, urdf.ceilingHeight ?? urdf.mountHeight ?? 0]} rotation={mountRotation(urdf)}>
        {urdf.ceilingHeight && <mesh position={[0, 0, -0.012]}>
          <boxGeometry args={[0.5, 0.5, 0.02]} /><meshStandardMaterial color="#9ca3af" metalness={0.5} roughness={0.4} /></mesh>}
        {/* The manufacturer's meshes; the simple cylinder arm shows while they load. */}
        {props.trail && <Trail points={props.trail} color={props.trailColor ?? props.model.accent} />}
        <Suspense fallback={<Arm model={props.model} q={q} selected={props.selected} moving={props.moving} />}>
          <Loaded onLoad={invalidate} />
          {props.onSnapshot && <Snapshot onShot={props.onSnapshot} />}
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
  /** Show the Front / Back / Left ... view bar even when compact (the Lab Equipment robot cards). */
  views?: boolean
  model: RobotModel
  q: number[] | null
  homeQ?: number[] | null
  selected?: number | null
  moving?: boolean[] | null
  onSelect?: (j: number) => void
  onSnapshot?: (dataUrl: string) => void
}

const VIEWS: [ViewName, string][] = [['front', 'Front'], ['back', 'Back'], ['right', 'Right'], ['left', 'Left'], ['top', 'Top'], ['bottom', 'Bottom'], ['iso', '3D']]

type RobotTwinProps = TwinProps & { resetKey?: number; className?: string; label?: string }

/** Same data = no re-render (2026-10-21): the panels re-render every second for their staleness clock; the
 *  3D view (and R3F's scene reconcile, ~0.9 s per 5 s of scrolling in the profile) skips identical props.
 *  Callbacks are not compared - they are state setters / handlers built from the same model. */
function sameTwinProps(a: RobotTwinProps, b: RobotTwinProps): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<keyof RobotTwinProps>
  for (const k of keys) {
    const x = a[k], y = b[k]
    if (typeof x === 'function' || typeof y === 'function') continue
    if (x === y) continue
    if (typeof x === 'object' && typeof y === 'object' && JSON.stringify(x) === JSON.stringify(y)) continue
    return false
  }
  return true
}

export default memo(RobotTwinView, sameTwinProps)

function RobotTwinView(props: RobotTwinProps) {
  const [view, setView] = useState<{ name: ViewName; n: number }>({ name: 'iso', n: 0 })
  // Off screen (scrolled away): no drawing at all until it is visible again.
  const box = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    const el = box.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: '100px' })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <div ref={box} className={`relative bg-[radial-gradient(ellipse_at_50%_35%,rgba(56,189,248,0.10),transparent_65%)] ${props.className ?? 'h-80'}`}
         aria-label={props.label ?? `${props.model.label} 3D view`} data-trail-points={props.trail?.length ?? 0}>
      <Canvas onCreated={noShaderChecks} frameloop={visible ? 'demand' : 'never'} dpr={[1, 1.75]} camera={{ fov: 40, near: 0.05, far: 20 }}
              style={{ opacity: props.q ? (props.stale ? 0.55 : 1) : 0.45, filter: props.stale ? 'grayscale(0.7)' : undefined }}>
        <Scene {...props} resetKey={props.resetKey ?? 0} view={view} />
      </Canvas>
      {/* Compact thumbnails (fleet cards) are too small for the view bar - it spilled over the card. */}
      {(!props.compact || props.views) && <div className="absolute bottom-2 right-2 flex flex-wrap gap-1 justify-end">
        {VIEWS.map(([v, label]) => (
          <button key={v} type="button" onClick={() => setView(o => ({ name: v, n: o.n + 1 }))}
                  className={`px-2 py-0.5 rounded-md text-[11px] border ${view.name === v && view.n ? 'bg-accent-500/25 border-accent-400/60 text-white' : 'bg-ink-900/75 border-ink-600 text-slate-300 hover:text-white'}`}>
            {label}</button>))}
      </div>}
      {!props.q && !props.compact && <div className="absolute inset-0 grid place-items-center pointer-events-none text-[12.5px] text-slate-400">
        No telemetry - pose unknown</div>}
      {props.q && props.stale && !props.compact && <div className="absolute top-2 left-2 pointer-events-none text-[11.5px] px-2 py-0.5 rounded-md bg-ink-900/80 text-warn-soft border border-warn/30">
        Last known pose - no fresh telemetry</div>}
    </div>)
}
