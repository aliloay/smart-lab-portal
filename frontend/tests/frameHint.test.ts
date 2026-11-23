// 2026-11-23: which screen pictures a live "frame_hint" refreshes, and the fallback polling.
import test from 'node:test'
import assert from 'node:assert/strict'
import { hintMatches, nextDelay } from '../src/lib/frameHint'

test('a PC hint refreshes only that PC', () => {
  assert.ok(hintMatches('/equipment/12/screen.jpg', { scope: 'pc', device_id: 12 }))
  assert.ok(!hintMatches('/equipment/1/screen.jpg', { scope: 'pc', device_id: 12 }))
  assert.ok(!hintMatches('/equipment/broadcast/frame.jpg?s=1', { scope: 'pc', device_id: 1 }))
})

test('a share hint refreshes the share only', () => {
  assert.ok(hintMatches('/equipment/broadcast/frame.jpg?s=1', { scope: 'broadcast' }))
  assert.ok(!hintMatches('/equipment/12/screen.jpg', { scope: 'broadcast' }))
})

test('polling: fast until the first picture, slow while hints arrive, normal without them', () => {
  assert.equal(nextDelay(false, 1000, 0), 200)
  assert.equal(nextDelay(true, 500, 1000), 2500)
  assert.equal(nextDelay(true, 500, 10_000), 500)
})
