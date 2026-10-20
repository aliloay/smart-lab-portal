/**
 * Pen-tip inverse kinematics for the welcome writer (drawing only, never sent to a robot).
 * Two points of the tool are solved together - the pen TIP and the pen's BACK end - so the
 * tip lands on a target and the pen keeps pointing where we ask (at the viewer).
 */
import * as THREE from 'three'
import type { UrdfModel, Vec3 } from '../robot/robotModels'

const _m = new THREE.Matrix4(), _e = new THREE.Euler(), _q = new THREE.Quaternion()

/** Flange frame (robot base frame, Z up) for joint values q - same chain MeshArm draws. */
export function flange(model: UrdfModel, q: number[]): THREE.Matrix4 {
  const M = new THREE.Matrix4().makeRotationFromEuler(_e.set(model.baseRpy[0], model.baseRpy[1], model.baseRpy[2], 'ZYX'))
  model.joints.forEach((j, i) => {
    M.multiply(_m.makeTranslation(j.xyz[0], j.xyz[1], j.xyz[2]))
    M.multiply(_m.makeRotationFromEuler(_e.set(j.rpy[0], j.rpy[1], j.rpy[2], 'ZYX')))
    M.multiply(_m.makeRotationFromQuaternion(_q.setFromAxisAngle(new THREE.Vector3(...j.axis), q[i] ?? 0)))
  })
  return M
}

/** Tool points (flange frame) -> base frame. */
function points(model: UrdfModel, q: number[], tool: Vec3[]): number[] {
  const M = flange(model, q), out: number[] = []
  for (const p of tool) { const v = new THREE.Vector3(...p).applyMatrix4(M); out.push(v.x, v.y, v.z) }
  return out
}

/** Solve A x = b (small dense, Gaussian elimination with partial pivoting). */
function solve(A: number[][], b: number[]): number[] | null {
  const n = b.length, M = A.map((r, i) => [...r, b[i]])
  for (let c = 0; c < n; c++) {
    let p = c
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r
    if (Math.abs(M[p][c]) < 1e-12) return null
    ;[M[c], M[p]] = [M[p], M[c]]
    for (let r = 0; r < n; r++) if (r !== c) { const f = M[r][c] / M[c][c]; for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k] }
  }
  return M.map((r, i) => r[n] / r[i])
}

/**
 * Joint values bringing tool points `tool` (flange frame) to `targets` (base frame), weighted:
 * the first point (pen tip) counts most. Damped least squares, joints kept in `lim`.
 */
export function solveTool(model: UrdfModel, q0: number[], tool: Vec3[], targets: Vec3[], weights: number[],
                          lim: [number, number][], iters = 10): number[] {
  const q = [...q0], n = q.length, h = 1e-4, lambda = 0.04
  const goal = targets.flat(), w = weights.flatMap(x => [x, x, x])
  for (let it = 0; it < iters; it++) {
    const p = points(model, q, tool)
    const e = goal.map((g, i) => (g - p[i]) * w[i])
    if (Math.hypot(...e) < 3e-4) break
    const J = e.map(() => new Array(n).fill(0))
    for (let j = 0; j < n; j++) {
      const qs = [...q]; qs[j] += h
      const pj = points(model, qs, tool)
      for (let r = 0; r < e.length; r++) J[r][j] = ((pj[r] - p[r]) / h) * w[r]
    }
    // (J^T J + l^2 I) dq = J^T e
    const A = Array.from({ length: n }, (_, a) => Array.from({ length: n }, (_, b) =>
      J.reduce((s, row) => s + row[a] * row[b], 0) + (a === b ? lambda * lambda : 0)))
    const g = Array.from({ length: n }, (_, a) => J.reduce((s, row, r) => s + row[a] * e[r], 0))
    const dq = solve(A, g)
    if (!dq) break
    for (let j = 0; j < n; j++) {
      const [lo, hi] = lim[j] ?? [-Math.PI, Math.PI]
      q[j] = Math.max(lo, Math.min(hi, q[j] + Math.max(-0.25, Math.min(0.25, dq[j]))))
    }
  }
  return q
}

/** Distance (m) between the solved pen tip and its target - for checks. */
export function tipError(model: UrdfModel, q: number[], tip: Vec3, target: Vec3): number {
  const p = points(model, q, [tip])
  return Math.hypot(p[0] - target[0], p[1] - target[1], p[2] - target[2])
}
