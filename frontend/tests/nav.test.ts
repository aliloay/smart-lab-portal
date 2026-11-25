// 2026-11-24: grouped navigation keeps every old address, roles stay separate; exhibition source labels; CSV safety.
import test from 'node:test'
import assert from 'node:assert/strict'
import { isHere, navFor, pagesFor, tabsFor } from '../src/lib/nav'
import { SIMULATED, choose, snapshot } from '../src/lib/exhibit'
import { csv } from '../src/lib/metricCsv'

const at = (role?: string) => navFor(role).flatMap(g => g.items.map(i => i.to))
const OLD_STAFF = ['/', '/labs', '/command', '/monitor', '/admin/security', '/share', '/admin/operations', '/admin/access',
  '/admin/bookings', '/admin/equipment', '/admin/devices', '/issues', '/admin/incidents', '/admin/alerts', '/notifications',
  '/admin/system', '/admin/reliability', '/admin/users']
const OLD_ADMIN = [...OLD_STAFF, '/admin/emergency', '/admin/reports', '/admin/settings']

const pages = (role?: string) => pagesFor(role).map(p => p.to)
// /share is the Screen sharing tab for staff, /notifications is the bell; both stay addresses and palette entries
const moved = (p: string) => p === '/share' ? '/admin/equipment?tab=pcs' : p
test('no page of the old menu is lost (menu, tabs or Ctrl+K), none appears twice', () => {
  for (const p of OLD_STAFF) assert.ok(pages('LAB_STAFF').includes(moved(p)), p)
  for (const p of OLD_ADMIN) assert.ok(pages('ADMIN').includes(moved(p)), p)
  for (const p of ['/', '/labs', '/book', '/bookings', '/share', '/robots', '/issues', '/notifications', '/profile']) assert.ok(pages('STUDENT').includes(p), p)
  for (const r of ['ADMIN', 'LAB_STAFF', 'STUDENT']) {
    assert.equal(new Set(at(r)).size, at(r).length)
    assert.equal(new Set(pages(r)).size, pages(r).length)
  }
})
test('roles: students and unknown roles get no staff page, staff no administrator page', () => {
  for (const r of ['STUDENT', undefined, 'SOMETHING']) {
    assert.ok(pages(r).every(p => !p.startsWith('/admin') && !['/command', '/monitor', '/exhibit', '/wall', '/scan', '/demo'].includes(p)))
    assert.equal(tabsFor(r, '/command'), null)
  }
  for (const p of ['/admin/emergency', '/admin/settings', '/admin/reports']) assert.ok(!pages('LAB_STAFF').includes(p), p)
  assert.ok(!tabsFor('LAB_STAFF', '/admin/health')!.tabs.some(t => t.to === '/admin/reports'))
  assert.ok(tabsFor('ADMIN', '/admin/health')!.tabs.some(t => t.to === '/admin/reports'))
})
test('the menu: no Notifications and no Share screen for staff; safety is one group, open at the start', () => {
  for (const r of ['ADMIN', 'LAB_STAFF']) {
    assert.ok(!at(r).includes('/notifications') && !at(r).includes('/share') && !at(r).includes('/admin/security'))
    const g = navFor(r).find(x => x.id === 'safety')!
    assert.ok(!g.pinned && !g.closed)
    assert.deepEqual(g.items.map(x => x.to), ['/admin/access', '/admin/alerts', '/admin/incidents', ...(r === 'ADMIN' ? ['/admin/emergency'] : [])])
  }
})
test('one entry is active on each page that has tabs', () => {
  for (const [p, to] of [['/admin/security', '/command'], ['/admin/reliability', '/admin/health'], ['/admin/reports', '/admin/health'],
                         ['/bookings/4', '/admin/bookings'], ['/equipment/7', '/admin/equipment'], ['/admin/equipment', '/admin/equipment']])
    assert.deepEqual(navFor('ADMIN').flatMap(g => g.items).filter(e => isHere(e, p)).map(e => e.to), [to], p)
  assert.deepEqual(tabsFor('LAB_STAFF', '/admin/security')!.tabs.map(t => t.to), ['/command', '/admin/security'])
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
