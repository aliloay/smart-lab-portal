/**
 * Virtual workcell: table + obstacles around a robot twin, and a MODELLED collision check.
 *
 * Planning aid only - NOT a safety system. Objects are MANUAL (typed in) or CAMERA_ESTIMATE
 * (rough), never "verified"; a hit here means "the model says these overlap", not that the
 * real robot touched anything. Pure math (no three.js) so it can run on every telemetry sample.
 *
 * World frame (lab measurements 2026-10-07): metres, +x front, +y Kinect side, z up, origin on
 * the floor under the robot base. The UR5e hangs upside down from the frame top.
 */
import type { UrdfModel, Vec3 } from './robotModels'

export type Source = 'MANUAL' | 'CAMERA_ESTIMATE'
export interface Obstacle { id: string; label: string; x: number; y: number; z: number; w: number; d: number; h: number; source: Source; uncertainty_m?: number | null }
export interface Table { present: boolean; x0: number; x1: number; y0: number; y1: number; height: number }
export interface Workcell { table: Table | null; obstacles: Obstacle[] }
export interface Hit { link: string; obstacle: string; label: string; distance: number }

/** The UR5e cell as measured in the lab (MANUAL: entered from tape / touch-off measurements). */
export const UR5E_TABLE: Table = { present: true, x0: -0.514, x1: 0.186, y0: -0.630, y1: 0.770, height: 0.71 }
export const defaultWorkcell = (key: string): Workcell => ({ table: key === 'UR5E' ? { ...UR5E_TABLE } : null, obstacles: [] })

// ---- 4x4 matrices, column-major like three.js (only what the chain needs) ----
type M4 = number[]
const I = (): M4 => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
function mul(a: M4, b: M4): M4 {
  const o = new Array(16).fill(0)
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++)
    for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k]
  return o
}
const T = (x: number, y: number, z: number): M4 => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]
/** Euler XYZ angles applied in 'ZYX' order (three.js Euler order 'ZYX' = Rz * Ry * Rx). */
function eulerZYX(rx: number, ry: number, rz: number): M4 {
  const [a, b, c, d, e, f] = [Math.cos(rx), Math.sin(rx), Math.cos(ry), Math.sin(ry), Math.cos(rz), Math.sin(rz)]
  return [c * e, c * f, -d, 0,  e * d * b - a * f, f * d * b + a * e, c * b, 0,  e * d * a + b * f, f * d * a - b * e, c * a, 0,  0, 0, 0, 1]
}
function axisAngle([x, y, z]: Vec3, t: number): M4 {
  const n = Math.hypot(x, y, z) || 1; x /= n; y /= n; z /= n
  const c = Math.cos(t), s = Math.sin(t), v = 1 - c
  return [x * x * v + c, y * x * v + z * s, z * x * v - y * s, 0,  x * y * v - z * s, y * y * v + c, z * y * v + x * s, 0,
          x * z * v + y * s, y * z * v - x * s, z * z * v + c, 0,  0, 0, 0, 1]
}
const apply = (m: M4, [x, y, z]: Vec3): Vec3 => [m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14]]

/** Robot base -> world: the UR5e hangs from the frame top (rotated 180 deg about x). */
export function baseToWorld(model: UrdfModel): M4 {
  return model.ceilingHeight ? mul(T(0, 0, model.ceilingHeight), axisAngle([1, 0, 0], Math.PI)) : I()
}

/** World positions of every joint origin, the flange, and the tool tip (`toolLength` along flange z). */
export function chainPoints(model: UrdfModel, q: number[], toolLength = 0.15): Vec3[] {
  let m = mul(baseToWorld(model), eulerZYX(model.baseRpy[0], model.baseRpy[1], model.baseRpy[2]))
  const pts: Vec3[] = [apply(m, [0, 0, 0])]
  model.joints.forEach((j, i) => {
    m = mul(m, T(j.xyz[0], j.xyz[1], j.xyz[2]))
    m = mul(m, eulerZYX(j.rpy[0], j.rpy[1], j.rpy[2]))
    m = mul(m, axisAngle(j.axis, q[i] ?? 0))
    pts.push(apply(m, [0, 0, 0]))
  })
  pts.push(apply(m, [0, 0, toolLength]))
  return pts
}

/** Distance from a point to an axis-aligned box (0 inside). */
export function pointBoxDistance(p: Vec3, o: Pick<Obstacle, 'x' | 'y' | 'z' | 'w' | 'd' | 'h'>): number {
  const dx = Math.max(Math.abs(p[0] - o.x) - o.w / 2, 0)
  const dy = Math.max(Math.abs(p[1] - o.y) - o.d / 2, 0)
  const dz = Math.max(Math.abs(p[2] - o.z) - o.h / 2, 0)
  return Math.hypot(dx, dy, dz)
}

/** Closest approach of segment a-b to a box, by sampling every ~1 cm (cheap and plenty here). */
export function segmentBoxDistance(a: Vec3, b: Vec3, o: Obstacle): number {
  const n = Math.max(2, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) / 0.01))
  let best = Infinity
  for (let i = 0; i <= n; i++) {
    const t = i / n
    best = Math.min(best, pointBoxDistance([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t], o))
  }
  return best
}

export const tableBox = (t: Table): Obstacle => ({ id: '__table', label: 'Table', source: 'MANUAL',
  x: (t.x0 + t.x1) / 2, y: (t.y0 + t.y1) / 2, z: t.height / 2, w: t.x1 - t.x0, d: t.y1 - t.y0, h: t.height })

/**
 * Modelled contacts: each link (segment between consecutive chain points, drawn as a capsule of
 * `radius`) against each obstacle and the table. The first segment (base mount) is skipped.
 */
export function collisions(model: UrdfModel, q: number[] | null, cell: Workcell, radius = 0.06, toolLength = 0.15): Hit[] {
  if (!q || q.length < 6) return []                          // no pose: nothing is claimed
  const pts = chainPoints(model, q, toolLength)
  const names = ['Base', ...model.joints.map((_, i) => `Link ${i + 1}`), 'Tool']
  const boxes = [...cell.obstacles, ...(cell.table?.present ? [tableBox(cell.table)] : [])]
  const hits: Hit[] = []
  for (let s = 1; s < pts.length - 1; s++) {
    for (const o of boxes) {
      const dist = segmentBoxDistance(pts[s], pts[s + 1], o) - radius
      if (dist <= 0) hits.push({ link: names[s + 1] ?? `Segment ${s}`, obstacle: o.id, label: o.label, distance: dist })
    }
  }
  return hits
}
