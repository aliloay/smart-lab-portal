/**
 * Welcome page: the lab's two robots in ONE workcell, at true relative scale
 * (both models are in metres; same floor, same world frame). The UR5e hangs
 * inverted under its measured gantry, the FANUC stands beside it. The camera
 * fits both robots on load and on resize; orbit / zoom / pan stay available.
 *
 * Drag any link to turn its joint - a local preview only: nothing here talks to
 * a robot. FANUC geometry is the LR Mate 200iD stand-in (see public/models/README.md).
 */
import { Suspense, useEffect, useRef, useState } from 'react'
import { Canvas, Camera, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import MeshArm from '../robot/MeshArm'
import { FanucCell, UR5eCell } from '../robot/RobotTwin'
import { FANUC_CELL_WORK_SURFACE_M, FANUC_LRMATE200ID, UR5E, UrdfModel, mountRotation, solveToward, tipPosition } from '../robot/robotModels'
import { MODELS } from '../robot/kinematics'
import { noShaderChecks } from '../robot/threeSetup'

const DEG = Math.PI / 180
// UR5e starts at the lab's own Home (backend robot_control.UR_HOME_Q_DEG, the pendant pose) - a bent, well-conditioned
// pose, so dragging either arm moves smoothly from the first grab (owner 2026-10-20).
const UR_HOME_DEG = [-15.00, -126.00, 117.03, -80.00, 91.00, 95.27]
const START = { UR5E: UR_HOME_DEG.map(d => d * Math.PI / 180), FANUC: [0, 0.2, -0.3, 0, -0.9, 0] }
type Key = keyof typeof START
const FANUC_AT: [number, number, number] = [0, -1.75, 0]   // beside the gantry, on the same floor (m)

/** Fit the camera to everything in the scene; re-run when the canvas resizes or `fitKey` changes. */
function Fit({ group, fitKey, orbit }: { group: React.RefObject<THREE.Group>; fitKey: number; orbit: React.MutableRefObject<OrbitControls | null> }) {
  const { camera, gl, size, invalidate } = useThree()
  useEffect(() => {
    if (!orbit.current) {
      const c = new OrbitControls(camera, gl.domElement)
      c.enableDamping = false; c.minDistance = 1; c.maxDistance = 9
      c.addEventListener('change', () => invalidate())
      orbit.current = c
    }
    return () => { orbit.current?.dispose(); orbit.current = null }
  }, [camera, gl, invalidate, orbit])
  useEffect(() => {
    const c = orbit.current
    if (!c) return
    // The cell's real extent (three.js frame, metres): gantry frame x -0.8..0.8, height 0..1.95,
    // FANUC beside it at z ~1.75 - fixed, so the framing never depends on meshes finishing loading.
    const box = new THREE.Box3(new THREE.Vector3(-0.9, 0, -1.2), new THREE.Vector3(0.9, 1.95, 2.45))   // cell turned: 1.30 m deep along z
    const centre = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3())
    const cam = camera as THREE.PerspectiveCamera
    const vfov = cam.fov * DEG, hfov = 2 * Math.atan(Math.tan(vfov / 2) * cam.aspect)
    const need = Math.max((s.y * 0.6) / Math.tan(vfov / 2), (Math.max(s.x, s.z) * 0.6) / Math.tan(hfov / 2))
    const dist = need * 1.15                                   // a comfortable margin
    const dir = new THREE.Vector3(1.0, 0.45, 0.85).normalize()
    cam.position.copy(centre).addScaledVector(dir, dist)
    cam.near = 0.05; cam.far = dist * 6; cam.updateProjectionMatrix()
    c.target.copy(centre); c.update(); invalidate()
  }, [camera, size.width, size.height, fitKey, orbit, invalidate])
  return null
}

export default function WelcomePair({ className = '' }: { className?: string }) {
  const [q, setQ] = useState<Record<Key, number[]>>({ UR5E: [...START.UR5E], FANUC: [...START.FANUC] })
  const [fitKey, setFitKey] = useState(0)
  const group = useRef<THREE.Group>(null)
  const orbit = useRef<OrbitControls | null>(null)

  // Hand-guiding (preview, same as the robot pages): grab any part and the WHOLE arm follows -
  // the tool flange tracks the mouse on a plane facing the viewer, joints from IK (solveToward).
  const view = useRef<{ camera: Camera; el: HTMLElement } | null>(null)
  const bases = { UR5E: useRef<THREE.Group>(null), FANUC: useRef<THREE.Group>(null) }
  const qRef = useRef(q); qRef.current = q
  const URDF: Record<Key, UrdfModel> = { UR5E, FANUC: FANUC_LRMATE200ID }
  const grab = (robot: Key) => () => {
    const v = view.current, base = bases[robot].current
    if (!v || !base) return
    if (orbit.current) orbit.current.enabled = false
    base.updateMatrixWorld()
    const urdf = URDF[robot]
    const tip = new THREE.Vector3(...tipPosition(urdf, qRef.current[robot])).applyMatrix4(base.matrixWorld)
    const n = new THREE.Vector3(); v.camera.getWorldDirection(n)
    const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(n, tip)
    const ray = new THREE.Raycaster(), hit = new THREE.Vector3(), toBase = base.matrixWorld.clone().invert()
    const lim = MODELS[robot].limitsDeg.map(([lo, hi]) => [lo * DEG, hi * DEG] as [number, number])
    const move = (e: PointerEvent) => {
      const r = v.el.getBoundingClientRect()
      ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), v.camera)
      if (!ray.ray.intersectPlane(plane, hit)) return
      const t = hit.clone().applyMatrix4(toBase)
      setQ(p => ({ ...p, [robot]: solveToward(urdf, p[robot], [t.x, t.y, t.z], lim) }))
    }
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); if (orbit.current) orbit.current.enabled = true }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }

  return (
    <div className={className || "relative h-full"}>
      <Canvas onCreated={noShaderChecks} frameloop="demand" dpr={[1, 1.75]} camera={{ fov: 38 }} shadows={false}>
        <hemisphereLight args={['#e0f2fe', '#1e293b', 0.9]} />
        <ambientLight intensity={0.45} />
        <directionalLight position={[3, 4, 3]} intensity={1.5} />
        <directionalLight position={[-3, 2, -2]} intensity={0.45} color="#7dd3fc" />
        <gridHelper args={[8, 40, '#1f4f6e', '#132a44']} position={[0, 0.001, 0]} />
        <Suspense fallback={null}>
          {/* robot frames are Z-up; three.js is Y-up */}
          <group ref={group} rotation={[-Math.PI / 2, 0, 0]}>
            <UR5eCell />
            <group ref={bases.UR5E} position={[0, 0, UR5E.ceilingHeight ?? 1.88]} rotation={mountRotation(UR5E)}>
              <MeshArm model={UR5E} q={q.UR5E} accent="#24d4f2" onGrab={grab('UR5E')} />
            </group>
            {/* cell and arm turned together so the cell's FRONT (doors, FANUC sticker, controller) faces the
                viewer, its long side beside the gantry (owner 2026-10-20, after three tries) */}
            <group position={FANUC_AT} rotation={[0, 0, -Math.PI / 2]}>
              <FanucCell />
              <group ref={bases.FANUC} position={[0, 0, FANUC_CELL_WORK_SURFACE_M]} rotation={mountRotation(FANUC_LRMATE200ID)}>
                <MeshArm model={FANUC_LRMATE200ID} q={q.FANUC} accent="#facc15" onGrab={grab('FANUC')} />
              </group>
            </group>
          </group>
          <Fit group={group} fitKey={fitKey} orbit={orbit} />
          <View into={view} />
        </Suspense>
      </Canvas>
      <button type="button" onClick={() => { setQ({ UR5E: [...START.UR5E], FANUC: [...START.FANUC] }); setFitKey(k => k + 1) }}
              className="absolute top-2 right-2 px-2 py-0.5 rounded-md text-[11px] border border-ink-600 bg-ink-900/80 text-slate-300 hover:text-white">
        Reset view</button>
    </div>)
}

function View({ into }: { into: React.MutableRefObject<{ camera: Camera; el: HTMLElement } | null> }) {
  const { camera, gl } = useThree()
  into.current = { camera, el: gl.domElement }
  return null
}
