// AR box motion following (Scan.tsx estimateShift, 2026-11-21 audit F-15). Pure function: no DOM, no camera.
import test from 'node:test'
import assert from 'node:assert/strict'
import { estimateShift } from '../src/pages/arshift'

const W = 64, H = 48
function scene(ox = 0, oy = 0): Uint8Array {
  const a = new Uint8Array(W * H)
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const sx = x - ox, sy = y - oy                      // the same textured scene, moved by (ox, oy)
    a[y * W + x] = ((Math.floor(sx / 4) * 37 + Math.floor(sy / 4) * 91) % 200) + (sx > 20 && sx < 34 && sy > 10 && sy < 30 ? 50 : 0)
  }
  return a
}

test('no motion gives zero shift and a near-perfect match', () => {
  const r = estimateShift(scene(), scene())
  assert.equal(r.dx, 0); assert.equal(r.dy, 0); assert.ok(r.err < 1)
})

test('a moved view is found (boxes then follow it)', () => {
  const r = estimateShift(scene(), scene(5, -3))
  assert.equal(Math.round(r.dx * W), 5); assert.equal(Math.round(r.dy * H), -3)
})

test('an unrelated view matches badly', () => {
  const noise = new Uint8Array(W * H).map((_, i) => (i * 7919) % 251)
  assert.ok(estimateShift(scene(), noise).err > 20)
})
