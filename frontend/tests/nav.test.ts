// 2026-11-24: grouped navigation keeps every old address, roles stay separate; exhibition source labels; CSV safety.
import test from 'node:test'
import assert from 'node:assert/strict'
import { isHere, navFor } from '../src/lib/nav'
import { SIMULATED, choose, snapshot } from '../src/lib/exhibit'
import { csv } from '../src/lib/metricCsv'

const at = (role?: string) => navFor(role).flatMap(g => g.items.map(i => i.to))
const OLD_STAFF = ['/', '/labs', '/command', '/monitor', '/admin/security', '/share', '/admin/operations', '/admin/access',
  '/admin/bookings', '/admin/equipment', '/admin/devices', '/issues', '/admin/incidents', '/admin/alerts', '/notifications',
  '/admin/system', '/admin/reliability', '/admin/users']
const OLD_ADMIN = [...OLD_STAFF, '/admin/emergency', '/admin/reports', '/admin/settings']

test('no address of the old menu is lost, none appears twice', () => {
  for (const p of OLD_STAFF) assert.ok(at('LAB_STAFF').includes(p), p)
  for (const p of OLD_ADMIN) assert.ok(at('ADMIN').includes(p), p)
  for (const r of ['ADMIN', 'LAB_STAFF', 'STUDENT']) assert.equal(new Set(at(r)).size, at(r).length)
})
test('roles: students and unknown roles get no staff page, staff no administrator page', () => {
  for (const r of ['STUDENT', undefined, 'SOMETHING'])
    assert.ok(at(r).every(p => !p.startsWith('/admin') && !['/command', '/monitor', '/exhibit'].includes(p)))
  for (const p of ['/admin/emergency', '/admin/settings', '/admin/reports']) assert.ok(!at('LAB_STAFF').includes(p), p)
})
test('safety is never behind a closed group', () => {
  assert.ok(navFor('ADMIN').find(g => g.items.some(i => i.to === '/admin/emergency'))!.pinned)
})
test('active page: the dashboard only on its own address', () => {
  const home = navFor('ADMIN')[0].items[0]
  assert.ok(isHere(home, '/') && !isHere(home, '/labs'))
  const labs = navFor('ADMIN').flatMap(g => g.items).find(i => i.to === '/labs')!
  assert.ok(isHere(labs, '/labs/3') && !isHere(labs, '/labsx'))
})

const svc = (group: string | undefined, name: string, state: string) =>
  ({ key: name, name, group, state, latency_ms: null, detail: 'secret 192.168.1.9' }) as never
const val = (metric_name: string, quality: string, simulated = false) => ({ metric_name, label: metric_name, kind: 'gauge',
  unit: 'u', value: 21.04, quality, timestamp: '2026-11-22T14:28:00Z', metadata: { provenance: null, simulated } }) as never

test('exhibition: live, then historical, then simulated', () => {
  assert.equal(choose(null, null).source, 'SIMULATED')
  assert.equal(choose(null, SIMULATED).source, 'HISTORICAL')
  assert.equal(choose(SIMULATED, null).source, 'LIVE')
})
test('exhibition: groups only, no host name, no address, no PC load, no simulated value', () => {
  const s = snapshot([svc('pc', 'PC-HOST-7', 'ONLINE'), svc('pc', 'PC-HOST-8', 'OFFLINE'), svc('robot', 'SIM', 'SIMULATION')],
    [val('temperature', 'STALE'), val('pc_cpu_pct', 'VALID'), val('motion', 'VALID'), val('humidity', 'VALID', true), val('smoke', 'OUT_OF_RANGE')], 'x')
  const t = JSON.stringify(s)
  assert.ok(!/HOST|192\.168|pc_cpu|motion|humidity|smoke/.test(t))
  assert.deepEqual(s.parts, [{ name: 'Lab computers', state: '1 of 2 online' }])
  assert.equal(s.readings[0].live, false)
  assert.match(s.readings[0].note, /last stored 2026-11-22 14:28 UTC/)
})
test('csv: empty buckets stay empty, formulas are neutral, negative numbers stay numbers', () => {
  const out = csv({ series: [{ t: 't', avg: null, min: -5, max: 1, n: 0, rejected: 0 }] },
    { device_uid: '=HYPERLINK("x")', metric_name: 'temperature', unit: '°C', metadata: { provenance: null, simulated: true } })
  assert.match(out, /"'=HYPERLINK\(""x""\)"/)
  assert.ok(out.includes(',,-5,1,0,0,yes\r\n'))
})
