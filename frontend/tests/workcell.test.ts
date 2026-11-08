// Workcell geometry tests. Run: npm run test:unit  (bundled with esbuild, run by node:test)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { FANUC_LRMATE200ID, UR5E, tipPosition } from '../src/components/robot/robotModels'
import { baseToWorld, chainPoints, collisions, defaultWorkcell, pointBoxDistance, tableBox, type Workcell } from '../src/components/robot/workcell'

const close = (a: number[], b: number[], tol = 1e-6) => a.forEach((v, i) => assert.ok(Math.abs(v - b[i]) < tol, `${a} vs ${b}`))

test('flange matches the twin\'s own forward kinematics (FANUC on the floor)', () => {
  for (const q of [[0, 0, 0, 0, 0, 0], [0.3, -0.4, 0.2, 1, -0.7, 0.5]]) {
    const pts = chainPoints(FANUC_LRMATE200ID, q, 0)
    close(pts[pts.length - 2], tipPosition(FANUC_LRMATE200ID, q))
  }
})

test('UR5e hangs from the frame top: base at 1.88 m, flange below it', () => {
  const q = [0, -Math.PI / 2, 0, -Math.PI / 2, 0, 0]
  const pts = chainPoints(UR5E, q, 0)
  close(pts[0], [0, 0, UR5E.ceilingHeight!])
  const tip = tipPosition(UR5E, q)                          // base frame; world = flipped about x, raised
  close(pts[pts.length - 2], [tip[0], -tip[1], UR5E.ceilingHeight! - tip[2]])
  assert.ok(pts[pts.length - 2][2] < UR5E.ceilingHeight!)
  assert.equal(baseToWorld(FANUC_LRMATE200ID)[14], 0)
})

test('point-box distance: inside 0, outside euclidean', () => {
  const b = { x: 0, y: 0, z: 0, w: 1, d: 1, h: 1 }
  assert.equal(pointBoxDistance([0.2, 0.2, 0.2], b), 0)
  assert.ok(Math.abs(pointBoxDistance([1.5, 0, 0], b) - 1) < 1e-9)
})

test('measured table is placed from its edges', () => {
  const t = tableBox(defaultWorkcell('UR5E').table!)
  close([t.x, t.y, t.z, t.w, t.d, t.h], [-0.164, 0.07, 0.355, 0.7, 1.4, 0.71], 1e-3)
})

test('an obstacle on the tool path is reported with link and obstacle; moving it away clears it', () => {
  const q = [0.3, -0.4, 0.2, 1, -0.7, 0.5]
  const tip = chainPoints(FANUC_LRMATE200ID, q).at(-1)!
  const cell: Workcell = { table: null, obstacles: [{ id: 'b1', label: 'Fixture', x: tip[0], y: tip[1], z: tip[2], w: .1, d: .1, h: .1, source: 'MANUAL' }] }
  const hits = collisions(FANUC_LRMATE200ID, q, cell)
  assert.ok(hits.some(h => h.obstacle === 'b1' && h.link === 'Tool'))
  cell.obstacles[0].x += 2
  assert.equal(collisions(FANUC_LRMATE200ID, q, cell).length, 0)
})

test('no pose (stale / missing telemetry) claims nothing', () => {
  assert.deepEqual(collisions(UR5E, null, defaultWorkcell('UR5E')), [])
  assert.deepEqual(collisions(UR5E, [0, 0], defaultWorkcell('UR5E')), [])
})

test('UR5e reaching down into the table is flagged as a table contact', () => {
  const down = [0, -Math.PI / 2, 0, -Math.PI / 2, 0, 0]          // straight down from 1.88 m
  const hits = collisions(UR5E, down, { table: { ...defaultWorkcell('UR5E').table!, height: 1.2 }, obstacles: [] })
  assert.ok(hits.some(h => h.obstacle === '__table'))
})
