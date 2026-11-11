// One status per lab PC from the LAN check + the agent heartbeat (2026-10-21). Offline: node --test e2e/pc_status.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { pcStatus } from '../src/lib/pcStatus.ts'

const lan = present => ({ present, ip: '192.168.1.101', mac: '60-eb-69-6b-c8-50', via: 'ping', since: '', checked_at: '' })

test('off on the LAN and no live agent: off', () => {
  assert.deepEqual(pcStatus({ online: false, state: 'RUNNING', lan: lan(false) }), { word: 'off', tone: 'bad', agent: false })
})
test('a live agent wins over the LAN scan (2026-11-03: PCs that report through the relay are not on the Smart Lab cable)', () => {
  assert.deepEqual(pcStatus({ online: true, state: 'RUNNING', lan: lan(false) }), { word: 'running', tone: 'ok', agent: true })
})
test('on the LAN without the agent: on, controls off', () => {
  const s = pcStatus({ online: null, state: null, lan: lan(true) })
  assert.equal(s.word, 'on · agent not running'); assert.equal(s.agent, false)
})
test('agent reporting: its state, controls on', () => {
  assert.deepEqual(pcStatus({ online: true, state: 'RUNNING', lan: lan(true) }), { word: 'running', tone: 'ok', agent: true })
  assert.equal(pcStatus({ online: true, state: 'IDLE', lan: null }).agent, true)     // LAN not checked: agent alone
})
test('nothing known stays honest', () => {
  assert.equal(pcStatus({ online: null, state: null, lan: null }).word, 'no data')
  assert.equal(pcStatus({ online: false, state: 'IDLE', lan: null }).word, 'offline')
})
