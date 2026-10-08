/**
 * Robot geometry for the 3D twins (standard Denavit-Hartenberg).
 *
 * UR5e: Universal Robots' published DH parameters for the UR5e - the twin's
 * link lengths and joint axes are the real robot's; the link SHAPES are
 * simple cylinders (not the CAD meshes).
 *
 * FANUC: the controller / arm model in the lab is NOT confirmed yet, so this
 * is a GENERIC 6-axis anthropomorphic arm of similar size, labelled as a
 * placeholder in the UI. Replace `dh` with the real model's parameters once
 * known (docs/ROBOTS.md) - nothing else changes.
 *
 * New robots: add an entry; the twin, joint table and page work from it.
 */
export interface DH { a: number; d: number; alpha: number; offset?: number }
export interface RobotModel {
  key: string
  label: string
  exact: boolean                  // true = published geometry of that model
  note: string
  dh: DH[]
  limitsDeg: [number, number][]
  color: string                   // body colour (the real robot's livery)
  accent: string
}

const PI = Math.PI

export const MODELS: Record<string, RobotModel> = {
  UR5E: {
    key: 'UR5E', label: 'Universal Robots UR5e', exact: true,
    note: "Universal Robots' own UR5e meshes and kinematics (the cylinders show only while they load).",
    dh: [
      { a: 0, d: 0.1625, alpha: PI / 2 },
      { a: -0.425, d: 0, alpha: 0 },
      { a: -0.3922, d: 0, alpha: 0 },
      { a: 0, d: 0.1333, alpha: PI / 2 },
      { a: 0, d: 0.0997, alpha: -PI / 2 },
      { a: 0, d: 0.0996, alpha: 0 },
    ],
    limitsDeg: [[-360, 360], [-360, 360], [-180, 180], [-360, 360], [-360, 360], [-360, 360]],
    color: '#c9d1d9', accent: '#38bdf8',
  },
  FANUC: {
    key: 'FANUC', label: 'FANUC LR Mate 200iD (model to be confirmed)', exact: false,
    note: "ROS-Industrial LR Mate 200iD meshes and kinematics. The lab arm's exact model is not confirmed yet.",
    dh: [
      { a: 0.05, d: 0.33, alpha: -PI / 2 },
      { a: 0.33, d: 0, alpha: 0, offset: -PI / 2 },
      { a: 0.035, d: 0, alpha: -PI / 2 },
      { a: 0, d: 0.335, alpha: PI / 2 },
      { a: 0, d: 0, alpha: -PI / 2 },
      { a: 0, d: 0.08, alpha: 0 },
    ],
    limitsDeg: [[-170, 170], [-100, 145], [-140, 213], [-190, 190], [-125, 125], [-360, 360]],
    color: '#facc15', accent: '#f59e0b',
  },
}

export function modelFor(name: string | null | undefined): RobotModel {
  const n = (name || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
  if (n.includes('FANUC')) return MODELS.FANUC
  return MODELS.UR5E
}

type M4 = number[]   // column-major 4x4

function mul(a: M4, b: M4): M4 {
  const o = new Array(16).fill(0)
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++)
    for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k]
  return o
}

function dhMatrix(p: DH, q: number): M4 {
  const th = q + (p.offset ?? 0)
  const ct = Math.cos(th), st = Math.sin(th), ca = Math.cos(p.alpha), sa = Math.sin(p.alpha)
  // Rz(th) Tz(d) Tx(a) Rx(alpha), column-major
  return [ct, st, 0, 0, -st * ca, ct * ca, sa, 0, st * sa, -ct * sa, ca, 0, p.a * ct, p.a * st, p.d, 1]
}

/** Frames 0..6 (base, then after each joint): origin and z-axis (joint axis) in metres. */
export function forward(model: RobotModel, q: number[]): { origin: [number, number, number]; z: [number, number, number] }[] {
  let T: M4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
  const out = [{ origin: [0, 0, 0] as [number, number, number], z: [0, 0, 1] as [number, number, number] }]
  model.dh.forEach((p, i) => {
    T = mul(T, dhMatrix(p, q[i] ?? 0))
    out.push({ origin: [T[12], T[13], T[14]], z: [T[8], T[9], T[10]] })
  })
  return out
}

export const deg = (r: number) => (r * 180) / Math.PI
