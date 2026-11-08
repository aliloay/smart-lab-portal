// One status per lab PC from the LAN check + the agent heartbeat (2026-10-21). Offline: node --test e2e/pc_status.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { pcStatus } from '../src/lib/pcStatus.ts'

const lan = present => ({ present, ip: '192.168.1.101', mac: '60-eb-69-6b-c8-50', via: 'ping', since: '', checked_at: '' })

test('cable out wins over a heartbeat that is not stale yet', () => {
  assert.deepEqual(pcStatus({ online: true, state: 'RUNNING', lan: lan(false) }), { word: 'off', tone: 'bad', agent: false })
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
