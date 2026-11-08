// Relevance of the global search (owner 2026-10-20). Offline: node --test e2e/search_rank.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { prepare, rank, PAGE_WORDS } from '../src/lib/searchRank.ts'

const ROBO = 'robot robots robotics robotic arm arms cobot ur5e ur5 fanuc gripper automation workcell'
const L1 = 'Robotics Lab LAB_01'
const items = [
  { type: 'lab', title: 'Robotics Lab', subtitle: 'LAB_01', to: '/labs/1', keys: 'LAB_01', words: 'lab laboratory ' + ROBO, lab: '' },
  { type: 'lab', title: 'PLC Lab', subtitle: 'LAB_02', to: '/labs/2', keys: 'LAB_02', words: 'lab laboratory plc automation siemens hmi', lab: '' },
  { type: 'lab', title: 'CAD & Digital Design Laboratory', subtitle: 'LAB_10', to: '/labs/10', keys: 'LAB_10', words: 'lab laboratory cad digital design', lab: '' },
  { type: 'lab', title: 'Fashion Design & Textiles Lab', subtitle: 'LAB_11', to: '/labs/11', keys: 'LAB_11', words: 'lab laboratory fashion textile', lab: '' },
  { type: 'device', title: 'UR5e (physical)', subtitle: 'robot · UR5E_01', to: '/robots/10', keys: 'UR5E_01', words: 'device robot robots arm cobot twin', lab: L1 },
  { type: 'device', title: 'FANUC ER-4iA (physical)', subtitle: 'robot · FANUC_01', to: '/robots/11', keys: 'FANUC_01', words: 'device robot robots arm cobot twin', lab: L1 },
  { type: 'device', title: 'Door Controller (Master ESP32)', subtitle: 'master controller · MASTER_LAB01', to: '/admin/devices', keys: 'MASTER_LAB01', words: 'device door lock access entry master controller esp32 nfc fingerprint', lab: L1 },
  { type: 'device', title: 'Security camera', subtitle: 'security camera · SECCAM_LAB01', to: '/admin/security', keys: 'SECCAM_LAB01', words: 'device camera cameras cctv security', lab: L1 },
  { type: 'device', title: 'Environment node', subtitle: 'sensor node · ENV_LAB01', to: '/admin/devices', keys: 'ENV_LAB01', words: 'device sensor node environment temperature humidity gas', lab: L1 },
  { type: 'equipment', title: 'UR5e Collaborative Arm', subtitle: 'equipment · RB-001', to: '/equipment/1', keys: 'RB-001', words: 'equipment ' + ROBO, lab: L1 },
  { type: 'incident', title: 'UR5e (physical) offline', subtitle: 'resolved', to: '/admin/incidents?open=7', keys: 'INC-000007 7', words: 'incident alert', lab: L1, resolved: true },
  { type: 'incident', title: 'Temperature high', subtitle: 'open', to: '/admin/incidents?open=12', keys: 'INC-000012 12', words: 'incident alert', lab: L1 },
  { type: 'person', title: 'Hemaly Ahmed', subtitle: 'lab staff', to: '/admin/users?find=hemaly@giu', keys: 'hemaly', words: 'user person staff', lab: '' },
  { type: 'page', title: 'Security camera', subtitle: 'Live lab', to: '/admin/security', words: 'Live lab ' + PAGE_WORDS['/admin/security'] },
  { type: 'page', title: 'Access & audit', subtitle: 'Safety & access', to: '/admin/access', words: PAGE_WORDS['/admin/access'] },
  { type: 'page', title: 'Bookings', subtitle: 'Safety & access', to: '/admin/bookings', words: PAGE_WORDS['/admin/bookings'] },
]
const P = prepare(items)
const top = (q, n = 1) => rank(P, q).slice(0, n).map(x => x.to)

test('lab codes in any spelling find the lab first', () => {
  for (const q of ['lab1', 'lab 1', 'LAB_01', 'lab01', 'Lab 01']) assert.equal(top(q)[0], '/labs/1', q)
  assert.equal(top('lab10')[0], '/labs/10'); assert.equal(top('lab11')[0], '/labs/11')
})
test('subject words find the Robotics Lab, then its robots', () => {
  assert.equal(top('robot')[0], '/labs/1')
  const r = top('robot', 4)
  assert.ok(r.includes('/robots/10') && r.includes('/robots/11'), JSON.stringify(r))
  assert.equal(top('robotics')[0], '/labs/1')
  assert.ok(top('arm', 3).includes('/equipment/1'))
})
test('the thing comes before its old resolved incident', () => {
  const r = rank(P, 'ur5e').map(x => x.to)
  assert.ok(r.indexOf('/robots/10') < r.indexOf('/admin/incidents?open=7'))
})
test('meaning: door, temperature, cctv, people', () => {
  assert.ok(top('door', 3).includes('/admin/devices') && top('door', 3).includes('/admin/access'))
  assert.ok(top('temperature', 2).includes('/admin/devices'))
  assert.ok(top('cctv', 2).includes('/admin/security'))
  assert.equal(top('hemaly')[0], '/admin/users?find=hemaly@giu')
})
test('typos and prefixes', () => {
  assert.equal(top('robtics')[0], '/labs/1')            // one letter missing
  assert.equal(top('fanu')[0], '/robots/11')
  assert.equal(top('textil')[0], '/labs/11')
})
test('incident numbers', () => {
  assert.equal(top('inc12')[0], '/admin/incidents?open=12')
  assert.equal(top('INC-000012')[0], '/admin/incidents?open=12')
})
test('several words must all match', () => {
  assert.equal(top('robotics lab')[0], '/labs/1')
  assert.deepEqual(rank(P, 'fanuc textile'), [])
})
test('natural phrases find the right place', () => {
  assert.ok(top('person keeps disappearing on camera', 3).includes('/admin/security'), JSON.stringify(top('person keeps disappearing on camera', 5)))
  assert.ok(top('temperature too high', 3).includes('/admin/incidents?open=12'), JSON.stringify(top('temperature too high', 5)))
  assert.ok(top('booking access denied', 3).includes('/admin/access'), JSON.stringify(top('booking access denied', 5)))
  assert.ok(top('door wont unlock', 3).includes('/admin/devices'))
  assert.deepEqual(rank(P, 'the of to'), [])                                   // only filler words: nothing
})

test('fast enough for every keystroke', () => {
  const many = prepare(Array.from({ length: 40 }, () => items).flat())     // 600 items
  const t = performance.now(); for (let i = 0; i < 50; i++) rank(many, 'robot arm'); const ms = (performance.now() - t) / 50
  assert.ok(ms < 8, `${ms.toFixed(2)} ms per query`)
})
