/**
 * A robot drawn from its manufacturer's meshes, posed exactly as its URDF
 * chain says (robotModels.ts): for each joint, translate + rotate by the
 * joint origin, rotate about the joint axis by the joint value, then draw the
 * link's mesh at its visual origin.
 *
 * Meshes load once (useLoader caches them) and are shared; each arm gets its
 * own material copies so a selected / moving link can be tinted, and the HOME
 * "ghost" arm is drawn translucent.
 */
import { ThreeEvent, useLoader } from '@react-three/fiber'
import { useMemo } from 'react'
import * as THREE from 'three'
import { ColladaLoader } from 'three/examples/jsm/loaders/ColladaLoader.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { LinkVisual, UrdfModel, Vec3 } from './robotModels'

const euler = (rpy: Vec3) => new THREE.Euler(rpy[0], rpy[1], rpy[2], 'ZYX')   // URDF fixed-axis roll-pitch-yaw

type Look = { ghost: boolean; tint: string | null }

function useMeshObject(model: UrdfModel, v: LinkVisual, look: Look): THREE.Object3D {
  const loaded = useLoader((model.format === 'dae' ? ColladaLoader : STLLoader) as never, v.mesh) as unknown
  return useMemo(() => {
    let obj: THREE.Object3D
    if (model.format === 'dae') {
      obj = (loaded as { scene: THREE.Object3D }).scene.clone(true)
      // The loader rotates Z-up assets to Y-up; URDF meshes are placed in their raw frame.
      obj.rotation.set(0, 0, 0)
    } else {
      obj = new THREE.Mesh(loaded as THREE.BufferGeometry,
                           new THREE.MeshStandardMaterial({ color: v.color ?? '#cccccc', metalness: 0.2, roughness: 0.55 }))
    }
    obj.traverse(o => {
      const m = o as THREE.Mesh
      if (!m.isMesh) return
      const mats = (Array.isArray(m.material) ? m.material : [m.material]).map(src => {
        const mat = (src as THREE.MeshStandardMaterial).clone()
        if (look.ghost) { mat.transparent = true; mat.opacity = 0.16; mat.depthWrite = false }
        if (look.tint && 'emissive' in mat) {
          mat.emissive = new THREE.Color(look.tint)
          mat.emissiveIntensity = 0.45
        }
        return mat
      })
      m.material = Array.isArray(m.material) ? mats : mats[0]
    })
    return obj
  }, [loaded, model.format, v.color, look.ghost, look.tint])
}

function Visual({ model, v, look, onClick }: { model: UrdfModel; v: LinkVisual; look: Look; onClick?: () => void }) {
  const obj = useMeshObject(model, v, look)
  return (
    <group position={v.xyz} rotation={euler(v.rpy)}
           onClick={onClick ? (e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); onClick() } : undefined}>
      <primitive object={obj} />
    </group>)
}

export default function MeshArm({ model, q, ghost = false, selected, moving, accent, onSelect }: {
  model: UrdfModel; q: number[]; ghost?: boolean; selected?: number | null; moving?: boolean[] | null
  accent: string; onSelect?: (j: number) => void
}) {
  const look = (i: number): Look => ({
    ghost, tint: ghost ? null : selected === i ? accent : moving?.[i] ? '#22c55e' : null })
  // Nested joints, J1 outermost.
  const chain = model.joints.reduceRight<JSX.Element | null>((child, j, i) => (
    <group position={j.xyz} rotation={euler(j.rpy)}>
      <group quaternion={new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(...j.axis), q[i] ?? 0)}>
        <Visual model={model} v={model.links[i]} look={look(i)} onClick={onSelect ? () => onSelect(i) : undefined} />
        {i === model.joints.length - 1 && model.tool?.map(t =>
          <Visual key={t.mesh} model={{ ...model, format: 'dae' }} v={t} look={look(i)} />)}
        {i === model.joints.length - 1 && model.toolBoxes?.map((b, k) =>
          <mesh key={`tb${k}`} position={b.xyz}>
            <boxGeometry args={b.size} />
            <meshStandardMaterial color={b.color} metalness={0.4} roughness={0.5}
                                  transparent={ghost} opacity={ghost ? 0.16 : 1} />
          </mesh>)}
        {child}
      </group>
    </group>), null)
  return (
    <group rotation={euler(model.baseRpy)}>
      <Visual model={model} v={model.base} look={{ ghost, tint: null }} />
      {chain}
    </group>)
}
