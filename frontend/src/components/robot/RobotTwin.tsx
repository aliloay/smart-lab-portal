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
import { useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RobotModel, forward } from './kinematics'

function Controls({ resetKey }: { resetKey: number }) {
  const { camera, gl, invalidate } = useThree()
  useEffect(() => {
    camera.position.set(0.85, 0.7, 0.95)
    camera.lookAt(0, 0.35, 0)
    const c = new OrbitControls(camera, gl.domElement)
    c.target.set(0, 0.35, 0)
    c.enableDamping = false
    c.minDistance = 0.4
    c.maxDistance = 4
    c.addEventListener('change', () => invalidate())
    c.update()
    invalidate()
    return () => c.dispose()
  }, [camera, gl, invalidate, resetKey])
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

function Scene(props: TwinProps & { resetKey: number }) {
  const { invalidate } = useThree()
  useEffect(() => { invalidate() }, [props.q, props.selected, props.moving, props.homeQ, invalidate])
  const q = props.q ?? new Array(6).fill(0)
  return (
    <>
      <Controls resetKey={props.resetKey} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[2, 3, 2]} intensity={1.1} />
      <directionalLight position={[-2, 1.5, -1]} intensity={0.35} />
      <gridHelper args={[3, 30, '#334155', '#1e293b']} />
      {/* Robot frames are Z-up; three.js is Y-up. */}
      <group rotation={[-Math.PI / 2, 0, 0]}>
        <mesh position={[0, 0, 0.02]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.09, 0.1, 0.04, 32]} />
          <meshStandardMaterial color="#1f2937" />
        </mesh>
        {props.homeQ && <Arm model={props.model} q={props.homeQ} ghost />}
        <Arm model={props.model} q={q} selected={props.selected} moving={props.moving} onSelect={props.onSelect} />
      </group>
    </>)
}

export interface TwinProps {
  model: RobotModel
  q: number[] | null
  homeQ?: number[] | null
  selected?: number | null
  moving?: boolean[] | null
  onSelect?: (j: number) => void
}

export default function RobotTwin(props: TwinProps & { resetKey?: number; className?: string; label?: string }) {
  return (
    <div className={`relative ${props.className ?? 'h-80'}`} aria-label={props.label ?? `${props.model.label} 3D view`}>
      <Canvas frameloop="demand" dpr={[1, 1.75]} camera={{ fov: 40, near: 0.05, far: 20 }}
              style={{ opacity: props.q ? 1 : 0.45 }}>
        <Scene {...props} resetKey={props.resetKey ?? 0} />
      </Canvas>
      {!props.q && <div className="absolute inset-0 grid place-items-center pointer-events-none text-[12.5px] text-slate-400">
        No telemetry - pose unknown</div>}
    </div>)
}
