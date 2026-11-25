// Navigation audit on the TEST COPY only (2026-11-24): every old address for every role, sidebar inventory, console errors,
// page overflow, navigation time, screenshots. It opens pages and the menu; it presses no control on any page.
//   E2E_PASSWORD=... node e2e/nav_audit.mjs <out folder> [pictures|routes]
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
const BASE = 'http://127.0.0.1:5176', API = 'http://127.0.0.1:8100/api'
const OUT = process.argv[2], ONLY = process.argv[3]
mkdirSync(OUT, { recursive: true })
const WHO = { ADMIN: 'admin@giu-uni.de', LAB_STAFF: 'ramy@giu-uni.de', STUDENT: 'ali@giu-uni.de' }
const STUDENT = ['/', '/labs', '/labs/1', '/book', '/bookings', '/share', '/robots', '/issues', '/issues/new', '/notifications', '/profile']
const STAFF = [...STUDENT, '/command', '/admin/security', '/admin/operations', '/admin/access', '/admin/alerts', '/admin/incidents',
  '/admin/bookings', '/admin/equipment', '/admin/equipment?tab=robots', '/admin/equipment?tab=pcs', '/admin/equipment?tab=consumables',
  '/admin/equipment?tab=reusables', '/admin/equipment?tab=register', '/admin/devices', '/admin/health', '/admin/sensors', '/admin/system',
  '/admin/reliability', '/admin/reports', '/admin/users', '/admin/experiments', '/demo', '/scan', '/scan/markers', '/phone-setup',
  '/monitor', '/wall', '/exhibit', '/report', '/welcome', '/live', '/inventory', '/admin', '/me', '/admin/access-events', '/admin/assets',
  '/admin/emergency', '/admin/settings']
const ROUTES = { ADMIN: STAFF, LAB_STAFF: STAFF, STUDENT: [...STUDENT, '/command', '/admin/security', '/admin/users', '/monitor', '/admin/emergency'] }
const VIEW = { desktop: { width: 1440, height: 900 }, tablet: { width: 820, height: 1180 }, mobile: { width: 390, height: 844 } }
// Sample people for the camera bars: confirmed, tentative, guess, unknown (pictures stay offline).
const cam = (id, name, activity) => ({ id, device_id: id, device_uid: name, name, lab_id: 1, lab_code: 'TEST', online: true, source_ok: true,
  people: activity.length, last_seen_at: new Date().toISOString(), fps: 6, zones: [], activity, unknown: 2, named: [], inside: 1, open_events: 0 })
const P = (id, who, named, rest, x = {}) => ({ track_id: id, label: named ? 'USER' + id : null, who, named, colour: 'blue', posture: 'sitting',
  place: 'PC-08', hint: null, size: 1, text: `${who} (blue top) - ${rest}`, ...x })
const ACT = [P(1, 'Test Person One', true, 'sitting - at PC-08 - next to Unknown'), P(2, 'Test Person Two?', true, 'standing - near FANUC'),
  P(3, 'Unknown', false, 'sitting - at PC-09', { hint: 'Test Person Three?', pose_visibility: { knees: { state: 'OCCLUDED' }, feet: { state: 'OUT_OF_FRAME' } } }),
  P(4, 'Unknown', false, 'walking')]
const browser = await chromium.launch({ channel: 'chrome' })
const rows = [], errors = [], nav = {}, timing = [], tok = {}

async function newPage(role, vp) {
  if (!tok[role]) {
    const r = await fetch(API + '/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email: WHO[role], password: process.env.E2E_PASSWORD }) })
    tok[role] = (await r.json()).access_token
    if (!tok[role]) throw new Error('sign-in failed ' + role)
  }
  const ctx = await browser.newContext({ viewport: VIEW[vp], reducedMotion: 'reduce' })
  await ctx.addInitScript(t => { localStorage.setItem('slp.token', t) }, tok[role])
  const p = await ctx.newPage()
  const note = text => errors.push({ role, vp, url: p.url().replace(BASE, ''), text: text.slice(0, 220) })
  p.on('console', m => { if (m.type() === 'error' && !/WebSocket|Failed to load resource|favicon/.test(m.text())) note(m.text()) })
  p.on('pageerror', e => note('PAGEERROR ' + e.message))
  await p.route('**/api/security/cameras', r => r.fulfill({ json: [cam(901, 'Camera 1', ACT), cam(902, 'Camera 2', ACT.slice(0, 2))] }))
  return p
}
async function settle(p) {
  await p.waitForFunction(() => document.querySelector('h1,h2,canvas,video'), null, { timeout: 8000 }).catch(() => {})
  await p.waitForTimeout(500)
}
async function openGroups(p) {
  for (const b of await p.$$('aside nav button[aria-expanded="false"]')) await b.click()
  await p.waitForTimeout(300)
}
for (const role of Object.keys(WHO)) for (const vp of Object.keys(VIEW)) {
  const p = await newPage(role, vp)
  await p.goto(BASE + '/')
  await settle(p)
  if (vp === 'desktop') {
    nav[role] = await p.$$eval('aside nav [data-group]', gs => gs.map(g => ({ group: g.dataset.group, heading: g.querySelector('.label')?.textContent?.trim(),
      items: [...g.querySelectorAll('a')].map(a => ({ href: a.getAttribute('href'), label: a.getAttribute('title') || a.textContent.trim(), visible: a.offsetParent !== null })) })))
  }
  if (ONLY !== 'pictures') for (const r of ROUTES[role]) {
    const n = errors.length
    await p.goto(BASE + r, { waitUntil: 'domcontentloaded' })
    await settle(p)
    const m = await p.evaluate(() => ({ at: location.pathname + location.search,
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      head: (document.querySelector('main h1, h1, h2')?.textContent || '').trim().slice(0, 60),
      text: (document.querySelector('main') ?? document.body).innerText.length,
      active: [...document.querySelectorAll('aside nav a[aria-current=page]')].map(a => a.getAttribute('title')).join('|') }))
    rows.push({ role, vp, route: r, ...m, errors: errors.length - n, blank: m.text < 20 })
  }
  const pics = role === 'STUDENT' ? ['/', '/notifications'] : role === 'LAB_STAFF' ? ['/', '/command']
    : ['/', '/notifications', '/command', '/admin/security', '/admin/operations', '/admin/equipment?tab=robots', '/admin/equipment?tab=pcs', '/admin/health', '/admin/access']
  if (ONLY !== 'routes') for (const r of pics) {
    await p.goto(BASE + r)
    await settle(p)
    await p.waitForTimeout(700)
    const name = `${role}_${vp}_${r === '/' ? 'home' : r.slice(1).replace(/[^a-z]+/g, '-')}`
    await p.screenshot({ path: `${OUT}/${name}.png` })
    if (vp === 'desktop' && ['/admin/operations', '/notifications', '/admin/security'].includes(r)) {
      await p.setViewportSize({ width: 1440, height: Math.min(await p.evaluate(() => document.documentElement.scrollHeight), 6000) })
      await p.waitForTimeout(600)
      await p.screenshot({ path: `${OUT}/${name}_full.png` })
      await p.setViewportSize(VIEW.desktop)
    }
  }
  if (vp === 'desktop') {
    await p.goto(BASE + '/')
    await settle(p)
    await openGroups(p)
    const hrefs = await p.$$eval('aside nav a', as => as.filter(a => a.offsetParent && !a.querySelector('.lucide-external-link')).map(a => a.getAttribute('href')))
    for (const href of hrefs) {
      const t = await p.evaluate(h => new Promise(res => {
        const t0 = performance.now()
        document.querySelector(`aside nav a[href="${h}"]`).click()
        const f = () => {
          const ready = location.pathname === h && document.querySelector('main h1, main h2')
          if (ready) requestAnimationFrame(() => res(performance.now() - t0))
          else if (performance.now() - t0 > 5000) res(null)
          else requestAnimationFrame(f)
        }
        requestAnimationFrame(f)
      }), href)
      timing.push({ role, href, ms: t === null ? null : Math.round(t) })
      await p.waitForTimeout(150)
    }
    if (ONLY !== 'routes') {
      await p.goto(BASE + '/')
      await settle(p)
      await p.setViewportSize({ width: 1440, height: 1500 })
      await openGroups(p)
      await p.screenshot({ path: `${OUT}/${role}_sidebar_open.png`, clip: { x: 0, y: 0, width: 420, height: 1500 } })
      await p.getByRole('button', { name: 'Compact menu' }).click()
      await p.waitForTimeout(400)
      await p.screenshot({ path: `${OUT}/${role}_sidebar_compact.png`, clip: { x: 0, y: 0, width: 300, height: 1500 } })
    }
  } else if (vp === 'mobile' && ONLY !== 'routes') {
    await p.goto(BASE + '/')
    await settle(p)
    await p.getByLabel('Open navigation').click()
    await p.waitForTimeout(500)
    await p.screenshot({ path: `${OUT}/${role}_mobile_menu.png` })
  }
  await p.context().close()
  console.log(role, vp, 'done')
}
await browser.close()
writeFileSync(`${OUT}/audit.json`, JSON.stringify({ nav, rows, errors, timing }, null, 1))
const ms = timing.map(t => t.ms).filter(x => x !== null).sort((a, b) => a - b)
console.log('pages', rows.length, 'blank', rows.filter(r => r.blank).map(r => `${r.role} ${r.vp} ${r.route}`),
  'overflow', rows.filter(r => r.over > 1).map(r => `${r.role} ${r.vp} ${r.route} +${r.over}`),
  'console', errors.length, 'menu click to heading ms: median', ms[ms.length >> 1], 'p95', ms[Math.floor(ms.length * 0.95)], 'n', ms.length, 'of', timing.length)
for (const r of Object.keys(nav)) {
  const it = nav[r].flatMap(g => g.items)
  console.log(r, 'groups', nav[r].length, 'entries', it.length, 'visible at start', it.filter(i => i.visible).length)
}
