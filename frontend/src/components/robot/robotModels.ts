/**
 * Real robot models for the twins: the manufacturers' meshes, placed exactly
 * as their robot description packages place them (URDF semantics:
 * joint origin xyz + rpy, rotation about `axis` by the joint value, visual
 * origin per link). Values copied from:
 *
 *   UR5e   Universal_Robots_ROS2_Description: urdf/ur_macro.xacro,
 *          config/ur5e/default_kinematics.yaml, config/ur5e/visual_parameters.yaml
 *   FANUC  ros-industrial/fanuc: fanuc_lrmate200id_support/urdf/lrmate200id_macro.xacro
 *          (the lab arm's exact model is NOT confirmed yet - shown as LR Mate 200iD)
 *
 * Meshes: public/models (licences and sources in public/models/README.md).
 */
import * as THREE from 'three'
export type Vec3 = [number, number, number]
export interface LinkVisual { mesh: string; xyz: Vec3; rpy: Vec3; color?: string }
export interface UrdfJoint { xyz: Vec3; rpy: Vec3; axis: Vec3 }
export interface UrdfModel {
  key: string
  label: string
  /** fixed transform base_link -> first visual link */
  baseRpy: Vec3
  base: LinkVisual
  joints: UrdfJoint[]                 // J1..J6
  links: LinkVisual[]                 // the link each joint moves, J1..J6
  format: 'dae' | 'stl'
  /** End effector: fixed (COLLADA) visuals in the last link's frame. */
  tool?: LinkVisual[]
  /** Simple boxes for a tool with no mesh (size, centre in the flange frame, m). */
  toolBoxes?: { size: Vec3; xyz: Vec3; color: string }[]
  /** Mounted upside down under a gantry at this height (m): the lab's UR5e. */
  ceilingHeight?: number
  toolLabel?: string
  note: string
}

const PI = Math.PI
const D = (deg: number) => (deg * PI) / 180

export const UR5E: UrdfModel = {
  key: 'UR5E', label: 'Universal Robots UR5e', format: 'dae',
  // In the lab the UR5e hangs from the gantry frame (photos 2026-10-08); height approximate.
  ceilingHeight: 1.15,
  // The lab arm carries a Robotiq 2F-85 (photos 2026-10-08): UR-to-Robotiq adapter on the tool flange.
  toolLabel: 'Robotiq 2F-85 gripper',
  tool: [
    { mesh: '/models/robotiq_2f85/ur_to_robotiq_adapter.dae', xyz: [0.00000, 0, 0.00000], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/robotiq_base.dae', xyz: [0.00000, 0, 0.01100], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/left_knuckle.dae', xyz: [0.03060, 0, 0.06590], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/right_knuckle.dae', xyz: [-0.03060, 0, 0.06590], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/left_finger.dae', xyz: [0.06213, 0, 0.06214], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/right_finger.dae', xyz: [-0.06213, 0, 0.06214], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/left_inner_knuckle.dae', xyz: [0.01270, 0, 0.07242], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/right_inner_knuckle.dae', xyz: [-0.01270, 0, 0.07242], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/left_finger_tip.dae', xyz: [0.06776, 0, 0.10933], rpy: [0, 0, 0] },
    { mesh: '/models/robotiq_2f85/right_finger_tip.dae', xyz: [-0.06776, 0, 0.10933], rpy: [0, 0, 0] },
  ],
  note: 'Universal Robots\' own UR5e meshes and kinematics (Universal_Robots_ROS2_Description, BSD-3).',
  baseRpy: [0, 0, PI],                                           // base_link -> base_link_inertia
  base: { mesh: '/models/ur5e/base.dae', xyz: [0, 0, 0], rpy: [0, 0, D(180)] },
  joints: [
    { xyz: [0, 0, 0.1625], rpy: [0, 0, 0], axis: [0, 0, 1] },                       // shoulder_pan
    { xyz: [0, 0, 0], rpy: [1.570796327, 0, 0], axis: [0, 0, 1] },                  // shoulder_lift
    { xyz: [-0.425, 0, 0], rpy: [0, 0, 0], axis: [0, 0, 1] },                       // elbow
    { xyz: [-0.3922, 0, 0.1333], rpy: [0, 0, 0], axis: [0, 0, 1] },                 // wrist_1
    { xyz: [0, -0.0997, 0], rpy: [1.570796327, 0, 0], axis: [0, 0, 1] },            // wrist_2
    { xyz: [0, 0.0996, 0], rpy: [1.570796326589793, PI, PI], axis: [0, 0, 1] },     // wrist_3
  ],
  links: [
    { mesh: '/models/ur5e/shoulder.dae', xyz: [0, 0, 0], rpy: [0, 0, D(180)] },
    { mesh: '/models/ur5e/upperarm.dae', xyz: [0, 0, 0.138], rpy: [D(90), 0, D(-90)] },
    { mesh: '/models/ur5e/forearm.dae', xyz: [0, 0, 0.007], rpy: [D(90), 0, D(-90)] },
    { mesh: '/models/ur5e/wrist1.dae', xyz: [0, 0, -0.127], rpy: [D(90), 0, 0] },
    { mesh: '/models/ur5e/wrist2.dae', xyz: [0, 0, -0.0997], rpy: [0, 0, 0] },
    { mesh: '/models/ur5e/wrist3.dae', xyz: [0, -0.0005, -0.0989], rpy: [D(90), 0, 0] },
  ],
}

// fanuc_resources/urdf/common_materials.xacro colours
const YELLOW = '#f5c21f', GRAY = '#474747', BLACK = '#262626'

export const FANUC_LRMATE200ID: UrdfModel = {
  key: 'FANUC', label: 'FANUC ER-4iA · R-30iB Mate Plus (3D: LR Mate 200iD stand-in)', format: 'stl',
  note: 'ROS-Industrial fanuc_lrmate200id_support meshes and kinematics (BSD). The lab arm\'s exact model is not confirmed yet.',
  baseRpy: [0, 0, 0],
  base: { mesh: '/models/fanuc_lrmate200id/base_link.stl', xyz: [0, 0, 0], rpy: [0, 0, 0], color: GRAY },
  joints: [
    { xyz: [0, 0, 0.330], rpy: [0, 0, 0], axis: [0, 0, 1] },
    { xyz: [0.050, 0, 0], rpy: [0, 0, 0], axis: [0, 1, 0] },
    { xyz: [0, 0, 0.330], rpy: [0, 0, 0], axis: [0, -1, 0] },
    { xyz: [0, 0, 0.035], rpy: [0, 0, 0], axis: [-1, 0, 0] },
    { xyz: [0.335, 0, 0], rpy: [0, 0, 0], axis: [0, -1, 0] },
    { xyz: [0.080, 0, 0], rpy: [0, 0, 0], axis: [-1, 0, 0] },
  ],
  links: [1, 2, 3, 4, 5].map(i => ({ mesh: `/models/fanuc_lrmate200id/link_${i}.stl`, xyz: [0, 0, 0] as Vec3,
                                      rpy: [0, 0, 0] as Vec3, color: YELLOW }))
    .concat([{ mesh: '/models/fanuc_lrmate200id/link_6.stl', xyz: [0, 0, 0], rpy: [0, 0, 0], color: BLACK }]),
  // Gripper identified from its plate (owner's photos 2026-10-14): SCHUNK EGP 40-N-N-B, an
  // ELECTRIC parallel gripper (24 V, 1 A, 140 N), on an aluminium adapter plate. Drawn as simple
  // boxes in proportion to the photos - APPROXIMATE, not the manufacturer's CAD. Tool axis = +x.
  toolBoxes: [
    { size: [0.014, 0.060, 0.050], xyz: [0.007, 0, 0], color: '#c9ccd1' },     // adapter plate
    { size: [0.075, 0.040, 0.032], xyz: [0.052, 0, 0], color: '#b8bcc2' },     // EGP 40 body
    { size: [0.032, 0.010, 0.022], xyz: [0.105, 0.012, 0], color: '#6e7277' }, // finger
    { size: [0.032, 0.010, 0.022], xyz: [0.105, -0.012, 0], color: '#6e7277' },
  ],
  toolLabel: 'SCHUNK EGP 40-N-N-B electric gripper (drawn approximately)',
}

export function urdfFor(model: string | null | undefined): UrdfModel {
  return (model || '').toUpperCase().includes('FANUC') ? FANUC_LRMATE200ID : UR5E
}

// ------------------------------------------------------------ tool tip ---

const _m = new THREE.Matrix4()
const _q = new THREE.Quaternion()
const _e = new THREE.Euler()

/** Tool flange position (m, robot base frame, Z up) for joint values q - the
 *  same chain MeshArm draws, so the path and the arm always agree. */
export function tipPosition(model: UrdfModel, q: number[]): Vec3 {
  const M = new THREE.Matrix4().makeRotationFromEuler(_e.set(model.baseRpy[0], model.baseRpy[1], model.baseRpy[2], 'ZYX'))
  model.joints.forEach((j, i) => {
    M.multiply(_m.makeTranslation(j.xyz[0], j.xyz[1], j.xyz[2]))
    M.multiply(_m.makeRotationFromEuler(_e.set(j.rpy[0], j.rpy[1], j.rpy[2], 'ZYX')))
    M.multiply(_m.makeRotationFromQuaternion(_q.setFromAxisAngle(new THREE.Vector3(...j.axis), q[i] ?? 0)))
  })
  return [M.elements[12], M.elements[13], M.elements[14]]
}

/** Preview hand-guiding: joint values that bring the tool flange toward `target`
 *  (m, base frame) - damped least squares on the numerical Jacobian, joints kept
 *  inside `limitsRad`. Drawing only; never sent to a robot. */
export function solveToward(model: UrdfModel, q: number[], target: Vec3,
                            limitsRad: [number, number][], iters = 12): number[] {
  const x = [...q]
  const lambda = 0.05, h = 1e-4
  for (let it = 0; it < iters; it++) {
    const p = tipPosition(model, x)
    const e = [target[0] - p[0], target[1] - p[1], target[2] - p[2]]
    if (Math.hypot(e[0], e[1], e[2]) < 5e-4) break
    // J: 3 x n
    const J: number[][] = [[], [], []]
    for (let j = 0; j < x.length; j++) {
      const xs = [...x]; xs[j] += h
      const pj = tipPosition(model, xs)
      for (let r = 0; r < 3; r++) J[r][j] = (pj[r] - p[r]) / h
    }
    // dq = J^T (J J^T + l^2 I)^-1 e
    const A = [0, 1, 2].map(r => [0, 1, 2].map(c => J[r].reduce((s, v, k) => s + v * J[c][k], 0) + (r === c ? lambda * lambda : 0)))
    const det = A[0][0] * (A[1][1] * A[2][2] - A[1][2] * A[2][1]) - A[0][1] * (A[1][0] * A[2][2] - A[1][2] * A[2][0])
              + A[0][2] * (A[1][0] * A[2][1] - A[1][1] * A[2][0])
    if (Math.abs(det) < 1e-12) break
    const inv = [
      [A[1][1] * A[2][2] - A[1][2] * A[2][1], A[0][2] * A[2][1] - A[0][1] * A[2][2], A[0][1] * A[1][2] - A[0][2] * A[1][1]],
      [A[1][2] * A[2][0] - A[1][0] * A[2][2], A[0][0] * A[2][2] - A[0][2] * A[2][0], A[0][2] * A[1][0] - A[0][0] * A[1][2]],
      [A[1][0] * A[2][1] - A[1][1] * A[2][0], A[0][1] * A[2][0] - A[0][0] * A[2][1], A[0][0] * A[1][1] - A[0][1] * A[1][0]],
    ].map(row => row.map(v => v / det))
    const y = [0, 1, 2].map(r => inv[r][0] * e[0] + inv[r][1] * e[1] + inv[r][2] * e[2])
    for (let j = 0; j < x.length; j++) {
      const dq = J[0][j] * y[0] + J[1][j] * y[1] + J[2][j] * y[2]
      const [lo, hi] = limitsRad[j] ?? [-Math.PI * 2, Math.PI * 2]
      x[j] = Math.max(lo, Math.min(hi, x[j] + dq))
    }
  }
  return x
}
