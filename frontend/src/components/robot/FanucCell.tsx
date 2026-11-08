/**
 * The lab's FANUC ER-4iA Educational Cell around the arm, after the owner's photos (2026-10-19) on the
 * manufacturer's overall size (FANUC_CELL, 1.30 x 0.70 x 1.80 m): aluminium frame with round corner posts on
 * casters; clear polycarbonate panels, the two front doors with hinges and knob, the yellow FANUC sticker; the
 * slotted work surface with the black parts plate and its white cylinders; the open lower shelf with the
 * R-30iB Mate Plus controller, the teach pendant and a storage crate; the yellow FANUC panels on both sides.
 * Everything except the overall size is APPROXIMATE (read off the photos) - for recognition, not measurement.
 *
 * Drawn in the cell's own frame (z up, front = -y, x to the right seen from the front), then turned half a turn
 * so the front faces the robot's +y - the FANUC's real front (owner 2026-10-15, the twin's Front view) - with the
 * robot base at the origin (FANUC_CELL.robotAt).
 */
import { useMemo } from 'react'
import * as THREE from 'three'
import { FANUC_CELL, FANUC_CELL_WORK_SURFACE_M } from './robotModels'
import { DecorKey, Facing, decorTexture, facingQuaternion } from './robotDecor'

type V3 = [number, number, number]
const ALU = '#aeb4bd', DARK = '#15171b'

function Box({ c, s, color, metal = 0.35, rough = 0.5 }: { c: V3; s: V3; color: string; metal?: number; rough?: number }) {
  return <mesh position={c}><boxGeometry args={s} /><meshStandardMaterial color={color} metalness={metal} roughness={rough} /></mesh>
}

/** Cylinder along world z (posts, cylinders on the plate) or along y (buttons on a front face). */
function Cyl({ c, r, h, color, along = 'z' }: { c: V3; r: number; h: number; color: string; along?: 'y' | 'z' | 'x' }) {
  const rot: V3 = along === 'z' ? [Math.PI / 2, 0, 0] : along === 'x' ? [0, 0, Math.PI / 2] : [0, 0, 0]
  return <mesh position={c} rotation={rot}><cylinderGeometry args={[r, r, h, 24]} />
    <meshStandardMaterial color={color} metalness={0.3} roughness={0.45} /></mesh>
}

/** A printed surface: a plane with one of the decor textures, just in front of what it is printed on. */
function Print({ tex, c, size, facing }: { tex: DecorKey; c: V3; size: [number, number]; facing: Facing }) {
  const q = useMemo(() => facingQuaternion(facing), [facing])
  return <mesh position={c} quaternion={q}><planeGeometry args={size} />
    <meshStandardMaterial map={decorTexture(tex)} roughness={0.55} metalness={0.05}
                          polygonOffset polygonOffsetFactor={-2} /></mesh>
}

/** Clear polycarbonate: faint blue tint, light edges so the panel reads as glass without hiding the arm. */
function Glass({ c, s }: { c: V3; s: V3 }) {
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(...s)), [s[0], s[1], s[2]])  // eslint-disable-line react-hooks/exhaustive-deps
  return <group position={c}>
    <mesh><boxGeometry args={s} />
      <meshStandardMaterial color="#dbeafe" transparent opacity={0.17} roughness={0.05} metalness={0.1}
                            depthWrite={false} side={THREE.DoubleSide} /></mesh>
    <lineSegments geometry={edges}><lineBasicMaterial color="#e2e8f0" transparent opacity={0.45} /></lineSegments>
  </group>
}

export function FanucCell() {
  const W = FANUC_CELL.width_m, D = FANUC_CELL.depth_m, H = FANUC_CELL.height_m, S = FANUC_CELL_WORK_SURFACE_M
  const [rx, ry] = FANUC_CELL.robotAt
  const pr = 0.03, px = W / 2 - pr, py = D / 2 - pr          // corner posts (centres)
  const yF = -py, lowTop = S - 0.09, lowBot = 0.15            // front glass plane; lower cabinet span
  const seam = 0.09                                           // where the two front doors meet
  const parts: JSX.Element[] = []
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
    const k = `${sx}${sy}`
    parts.push(<Cyl key={`post${k}`} c={[sx * px, sy * py, (H + 0.09) / 2]} r={pr} h={H - 0.09} color={ALU} />)
    parts.push(<Box key={`cb${k}`} c={[sx * px, sy * py, 0.082]} s={[0.07, 0.07, 0.02]} color="#6b7280" />)
    parts.push(<Cyl key={`wh${k}`} c={[sx * px, sy * py, 0.04]} r={0.038} h={0.03} color={DARK} along="x" />)
  }
  for (const [z, t] of [[0.115, 0.05], [S - 0.05, 0.08], [H - 0.025, 0.05]] as const) {
    for (const sy of [-1, 1]) parts.push(<Box key={`rx${z}${sy}`} c={[0, sy * py, z]} s={[W - 2 * pr, 0.04, t]} color={ALU} />)
    for (const sx of [-1, 1]) parts.push(<Box key={`ry${z}${sx}`} c={[sx * px, 0, z]} s={[0.04, D - 2 * pr, t]} color={ALU} />)
  }
  // Two black handles on each side, on the rail under the glass.
  for (const sx of [-1, 1]) for (const hy of [-0.17, 0.17])
    parts.push(<Box key={`h${sx}${hy}`} c={[sx * (W / 2 + 0.008), hy, S - 0.045]} s={[0.025, 0.17, 0.028]} color={DARK} />)
  // Front door hinges (left and right posts) and the knob at the seam.
  for (const sx of [-1, 1]) for (const hz of [S + 0.12, H - 0.16])
    parts.push(<Box key={`hg${sx}${hz}`} c={[sx * (px - 0.035), yF - 0.012, hz]} s={[0.03, 0.02, 0.055]} color={DARK} />)
  // White parts standing in eight of the plate's twelve holes.
  const holes: [number, number][] = []
  for (const hx of [-0.15, -0.05, 0.05, 0.15]) for (const hy of [-0.09, 0, 0.09]) holes.push([hx, hy])
  const plate: V3 = [-0.30, 0.02, S]
  holes.filter((_, i) => ![0, 3, 8, 11].includes(i)).forEach(([hx, hy], i) =>
    parts.push(<Cyl key={`part${i}`} c={[plate[0] + hx, plate[1] + hy, S + 0.012 + 0.025]} r={0.0175} h={0.05} color="#f1f2f4" />))

  return <group rotation={[0, 0, Math.PI]}><group position={[-rx, -ry, 0]}>
    {parts}
    {/* lower cabinet: shelf, back, yellow FANUC sides (printed outside); front left open as in the photos */}
    <Box c={[0, 0, 0.14]} s={[W - 0.08, D - 0.08, 0.02]} color="#a9b0b8" />
    <Box c={[0, D / 2 - 0.035, (lowBot + lowTop) / 2]} s={[W - 0.08, 0.01, lowTop - lowBot]} color="#d3d7dc" metal={0.1} />
    {[-1, 1].map(sx => <group key={`side${sx}`}>
      <Box c={[sx * (W / 2 - 0.02), 0, (lowBot + lowTop) / 2]} s={[0.012, D - 0.07, lowTop - lowBot]} color="#ffd100" metal={0.05} />
      <Print tex="side-panel" c={[sx * (W / 2 - 0.0135), 0, (lowBot + lowTop) / 2]} size={[D - 0.08, lowTop - lowBot - 0.01]}
             facing={sx > 0 ? '+x' : '-x'} />
    </group>)}
    {/* R-30iB Mate Plus controller with its emergency stop, the teach pendant, a storage crate */}
    <Box c={[-0.375, -0.12, 0.35]} s={[0.43, 0.38, 0.40]} color="#e8e2cf" metal={0.05} rough={0.7} />
    <Print tex="controller" c={[-0.375, -0.3115, 0.35]} size={[0.43, 0.40]} facing="-y" />
    <Cyl c={[-0.214, -0.315, 0.447]} r={0.03} h={0.006} color="#ffd100" along="y" />
    <Cyl c={[-0.214, -0.324, 0.447]} r={0.021} h={0.022} color="#d61f26" along="y" />
    <Box c={[0.06, yF + 0.10, 0.42]} s={[0.22, 0.05, 0.31]} color={DARK} />
    <Print tex="pendant" c={[0.06, yF + 0.0735, 0.42]} size={[0.21, 0.30]} facing="-y" />
    <Box c={[0.06, yF + 0.11, 0.60]} s={[0.06, 0.03, 0.05]} color="#6b7280" />
    <Box c={[0.36, 0.06, 0.285]} s={[0.42, 0.36, 0.27]} color="#4b5058" metal={0.05} rough={0.8} />
    {/* work surface: slotted aluminium, the parts plate, the cable duct along the front left */}
    <Box c={[0, 0, S - 0.015]} s={[W - 0.07, D - 0.07, 0.03]} color="#b8bec6" />
    <Print tex="slotted-table" c={[0, 0, S + 0.0008]} size={[W - 0.08, D - 0.08]} facing="+z" />
    <Box c={[plate[0], plate[1], S + 0.006]} s={[0.40, 0.28, 0.012]} color="#16181c" metal={0.1} />
    <Print tex="parts-plate" c={[plate[0], plate[1], S + 0.0125]} size={[0.40, 0.28]} facing="+z" />
    <Box c={[-0.355, yF + 0.045, S + 0.025]} s={[0.45, 0.035, 0.05]} color="#a7adb5" metal={0.1} />
    {/* upper compartment: clear panels (two front doors), the FANUC sticker, the vision camera at the top */}
    <Glass c={[(-px + 0.02 + seam) / 2, yF, (S + H - 0.05) / 2]} s={[seam + px - 0.02, 0.006, H - S - 0.05]} />
    <Glass c={[(seam + px - 0.02) / 2, yF, (S + H - 0.05) / 2]} s={[px - 0.02 - seam, 0.006, H - S - 0.05]} />
    <Box c={[seam, yF - 0.006, (S + H - 0.05) / 2]} s={[0.012, 0.006, H - S - 0.06]} color={DARK} />
    <Cyl c={[seam - 0.035, yF - 0.02, S + 0.40]} r={0.013} h={0.03} color={DARK} along="y" />
    <Glass c={[0, py, (S + H - 0.05) / 2]} s={[2 * px - 0.04, 0.006, H - S - 0.05]} />
    {[-1, 1].map(sx => <Glass key={`gl${sx}`} c={[sx * px, 0, (S + H - 0.05) / 2]} s={[0.006, 2 * py - 0.04, H - S - 0.05]} />)}
    <Print tex="sticker" c={[-px + 0.15, yF - 0.0045, H - 0.12]} size={[0.21, 0.105]} facing="-y" />
    <Box c={[-0.12, yF + 0.12, H - 0.08]} s={[0.05, 0.06, 0.05]} color="#1f2937" />
    <Cyl c={[-0.12, yF + 0.12, H - 0.12]} r={0.013} h={0.03} color="#0b0d10" />
  </group></group>
}
