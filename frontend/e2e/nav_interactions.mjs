// What people click in the new navigation (2026-11-24). TEST COPY ONLY; presses no device, door, robot or emergency control.
//   E2E_PASSWORD=... node e2e/nav_interactions.mjs [screenshot folder]
import { chromium } from 'playwright-core'
const BASE = 'http://127.0.0.1:5176', API = 'http://127.0.0.1:8100/api', SHOTS = process.argv[2]
let n = 0
const bad = []
const ok = (c, what) => { n++; if (!c) bad.push(what); console.log(c ? 'ok  ' : 'FAIL', what) }
const browser = await chromium.launch({ channel: 'chrome' })
async function signIn(email, viewport = { width: 1440, height: 900 }, touch = false) {
  const r = await fetch(API + '/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email, password: process.env.E2E_PASSWORD }) })
  const { access_token } = await r.json()
  const ctx = await browser.newContext({ viewport, hasTouch: touch, reducedMotion: 'reduce' })
  await ctx.addInitScript(t => localStorage.setItem('slp.token', t), access_token)
  const p = await ctx.newPage()
  p.on('console', m => { if (m.type() === 'error' && !/WebSocket|Failed to load resource|favicon/.test(m.text())) bad.push('console: ' + m.text().slice(0, 160)) })
  p.on('pageerror', e => bad.push('pageerror: ' + e.message))
  await p.goto(BASE + '/')
  await p.locator('aside nav a').first().waitFor({ state: 'attached' })
  return p
}
const at = p => new URL(p.url()).pathname + new URL(p.url()).search
const shot = async (p, name) => { if (SHOTS) { await p.waitForTimeout(400); await p.screenshot({ path: `${SHOTS}/${name}.png` }) } }
const unread = async p => Number((await p.locator('[data-testid="notification-summary"] button').nth(1).innerText()).match(/\d+/)?.[0])

const p = await signIn('admin@giu-uni.de')
// Access & safety
const safety = p.locator('[data-group="safety"] > button')
ok(await safety.getAttribute('aria-expanded') === 'true', 'safety open at the start')
ok(await p.locator('[data-group="safety"] a').count() === 4, 'safety has four pages')
await safety.click()
ok(!await p.locator('aside a[href="/admin/emergency"]').isVisible(), 'safety closes')
await p.reload()
await safety.waitFor()
ok(await safety.getAttribute('aria-expanded') === 'false', 'closed is remembered')
await p.goto(BASE + '/admin/incidents')
await safety.waitFor()
ok(await safety.getAttribute('aria-expanded') === 'true', 'opens by itself on one of its pages')
ok(await p.locator('aside a[aria-current="page"]').innerText() === 'Incidents', 'Incidents is the active entry')
// bell
const bell = p.locator('a[aria-label^="Notifications"]:visible')
await bell.hover()
await p.getByText('Open the Notifications Center').waitFor({ timeout: 3000 })
ok(await p.locator('ul li button:visible').count() <= 5, 'preview shows at most five')
await shot(p, 'bell_preview')
await bell.click()
await p.getByRole('heading', { name: 'Notifications Center' }).waitFor()
ok(at(p) === '/notifications', 'the bell opens the Notifications Center')
await p.locator('[data-testid="notification-list"] section').first().waitFor()
await p.mouse.move(700, 800)
const u0 = await unread(p)
ok(u0 > 2, `opening it marked nothing read (${u0} unread)`)
await p.getByRole('button', { name: /^Mark read:/ }).first().click()
await p.waitForTimeout(500)
ok(await unread(p) === u0 - 1, 'one marked read: the count follows')
await p.getByRole('button', { name: 'Mark all read' }).click()
await shot(p, 'mark_all_confirm')
await p.getByRole('button', { name: 'Cancel' }).click()
ok(await unread(p) === u0 - 1, 'cancel marks nothing')
await p.locator('[data-testid="notification-summary"] button').nth(2).click()
await p.waitForTimeout(600)
ok(await p.locator('[data-testid="notification-list"] section button.flex-1').count() === 16, 'Critical card filters (16)')
await p.getByLabel('Search notifications').fill('notification 2')
await p.waitForTimeout(800)
ok(await p.getByText('TEST notification 2', { exact: true }).count() === 1, 'search works')
await p.getByLabel('Search notifications').fill('')
await p.locator('[data-testid="notification-summary"] button').first().click()
await p.getByRole('button', { name: /Load more/ }).click()
await p.waitForTimeout(800)
ok(await p.locator('[data-testid="notification-list"] section button.flex-1').count() === 64, 'load more shows all 64')
const box = await p.locator('[data-testid="notification-list"]').boundingBox()
ok(box.width > 1050, `list width ${Math.round(box.width)} px (was 896 at most)`)
// live monitoring
await p.locator('aside a[href="/command"]').click()
const tabs = p.locator('[data-page-tabs="live"] nav a')
await tabs.first().waitFor()
ok(await tabs.count() === 2, 'two tabs')
let streams = 0
p.on('request', r => { if (/frame\.jpg|\/stream|\/latest/.test(r.url()) && /security/.test(r.url())) streams++ })
await tabs.nth(1).click()
await p.getByRole('heading', { name: 'Security camera' }).waitFor()
ok(at(p) === '/admin/security' && await p.locator('aside a[aria-current="page"]').innerText() === 'Live Monitoring', 'cameras tab, one active entry')
await p.goBack()
ok(at(p) === '/command', 'back button returns to IoT & sensors')
await p.waitForTimeout(1500)
streams = 0
await p.waitForTimeout(3000)
ok(await p.getByRole('heading', { name: 'Security camera' }).count() === 0, 'only the open tab is mounted')
console.log('    camera requests in 3 s on IoT & sensors:', streams)
await p.getByRole('button', { name: 'Screens' }).click()
ok(await p.locator('[data-page-tabs="live"] a[href="/wall"], [data-page-tabs="live"] a[href="/monitor"], [data-page-tabs="live"] a[href="/exhibit"]').count() === 3, 'Screens lists the three displays')
await shot(p, 'screens_menu')
await p.keyboard.press('Escape')
// equipment / share
await p.goto(BASE + '/share')
await p.waitForURL('**/admin/equipment?tab=pcs')
const sel = () => p.locator('main [role=tab][aria-selected=true]').first().innerText()
await p.getByRole('heading', { name: /Shared screen|is sharing/ }).waitFor()
ok(await p.getByRole('heading', { level: 1 }).count() === 1, 'one page heading')
ok(await p.locator('main canvas').count() === 0, 'PCs & screens loads no 3D view')
for (const [t, want] of [['noncons', '2 · Robots'], ['share', '3 · PCs & screens'], ['robots', '2 · Robots'], ['pcs', '3 · PCs & screens'],
                         ['consumables', '4 · Consumables'], ['reusables', '5 · Reusables'], ['register', 'Equipment register'], ['nonsense', '1 · Physical environment']]) {
  await p.goto(BASE + '/admin/equipment?tab=' + t)
  await p.locator('main [role=tab]').first().waitFor()
  ok((await sel()).trim() === want, `tab=${t} opens ${want}`)
}
await p.goto(BASE + '/share?t=x')
await p.waitForTimeout(1200)
ok(at(p) === '/share?t=x', 'a watch link keeps its address')
// palette
for (const [word, title] of [['wall', 'Wall display'], ['notifications', 'Notifications'], ['screen sharing', 'PCs & screen sharing'], ['simulation', 'Simulation'], ['sensors', 'Sensors']]) {
  await p.goto(BASE + '/')
  await p.locator('aside nav a').first().waitFor()
  await p.waitForTimeout(500)
  await p.keyboard.press('Control+k')
  const dlg = p.getByRole('dialog', { name: 'Search' })
  await dlg.locator('input').fill(word)
  await p.waitForTimeout(400)
  ok(await dlg.getByText(title, { exact: true }).count() > 0, `Ctrl+K finds ${title}`)
  await p.keyboard.press('Escape')
}
// keyboard only
await p.goto(BASE + '/')
const adm = p.locator('[data-group="admin"] > button')
await adm.focus()
await p.keyboard.press('Enter')
ok(await p.locator('aside a[href="/admin/settings"]').isVisible(), 'keyboard opens a group')

const s = await signIn('ali@giu-uni.de')
const sl = await s.$$eval('aside nav a', a => a.map(x => x.getAttribute('href')))
ok(sl.includes('/share') && !sl.includes('/notifications') && sl.every(h => !h.startsWith('/admin')), 'student menu')
await s.goto(BASE + '/share')
await s.waitForTimeout(800)
ok(at(s) === '/share' && await s.locator('[data-page-tabs]').count() === 0, 'student keeps /share')
await s.goto(BASE + '/live')
await s.waitForTimeout(800)
ok(at(s) === '/', 'student is sent home from /live')
// phone: a tap on the bell opens the page directly
const m = await signIn('ali@giu-uni.de', { width: 390, height: 844 }, true)
await m.locator('a[aria-label^="Notifications"]:visible').tap()
await m.getByRole('heading', { name: 'Notifications Center' }).waitFor()
ok(at(m) === '/notifications', 'phone: a tap opens the Notifications Center')
await browser.close()
console.log(`${n - bad.length} of ${n} checks`, bad)
process.exit(bad.length ? 1 : 0)
