// Grouped navigation, Health Center, Sensor analytics and the exhibition screen (2026-11-24).
//   E2E_PASSWORD=... node e2e/expansion.mjs http://127.0.0.1:5176 [screenshot folder]
// Only for the test copy: it refuses the live portal's ports. It clicks nothing that controls a device.
import { chromium } from 'playwright-core'
const BASE = process.argv[2] || 'http://127.0.0.1:5176'
const SHOTS = process.argv[3]
if (!/:5176$/.test(BASE)) throw new Error('test copy only (:5176)')
const bad = []
let checks = 0
const ok = (c, what) => { checks++; if (!c) { bad.push(what); console.log('FAIL', what) } }

async function signIn(browser, email, viewport) {
  const page = await (await browser.newContext({ viewport, reducedMotion: 'reduce' })).newPage()
  page.on('console', m => { if (m.type() === 'error' && !/WebSocket|ERR_FAILED|CONNECTION_REFUSED|favicon|50[0-9]|40[34]/.test(m.text())) bad.push(`console ${email}: ${m.text().slice(0, 160)}`) })
  page.on('requestfailed', r => { if (!r.url().startsWith(BASE)) console.log('outside request failed:', r.url().slice(0, 80)) })
  page.on('pageerror', e => bad.push(`pageerror: ${e.message.slice(0, 160)}`))
  await page.goto(BASE + '/login?next=/admin/health')
  await page.fill('input[type="email"], input[autocomplete="username"], input[name="email"]', email)
  await page.fill('input[type="password"]', process.env.E2E_PASSWORD)
  await page.keyboard.press('Enter')
  await page.waitForFunction(() => !location.pathname.startsWith('/login'), null, { timeout: 20000 })
  return page
}
const open = async (page, path, heading) => {
  await page.goto(BASE + path)
  await page.getByRole('heading', { name: heading, exact: false }).first().waitFor({ timeout: 20000 })
}
const shot = async (page, name) => { if (SHOTS) { await page.waitForTimeout(900); await page.screenshot({ path: `${SHOTS}/${name}.png` }) } }
const overflow = page => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)

const browser = await chromium.launch({ channel: 'chrome' })
try {
  const p = await signIn(browser, 'admin@giu-uni.de', { width: 1440, height: 900 })
  await open(p, '/admin/health', 'Health Center')
  await p.getByText('Need attention').waitFor()
  await shot(p, 'health_center')
  ok(await p.locator('aside [data-group]').count() === 7, 'seven groups')
  ok(await p.locator('aside nav a[href="/admin/emergency"]').isVisible(), 'emergency always visible')
  ok(await p.locator('aside nav a[href="/admin/health"]').isVisible(), 'the group of the open page is open')
  ok(!await p.locator('aside nav a[href="/admin/settings"]').isVisible(), 'administration starts closed')
  const adm = p.locator('aside [data-group="admin"] button')
  await adm.focus(); await p.keyboard.press('Enter')
  ok(await p.locator('aside nav a[href="/admin/settings"]').isVisible(), 'keyboard opens a group')
  ok(await adm.getAttribute('aria-expanded') === 'true', 'aria-expanded')
  await shot(p, 'navigation_open')
  await p.reload(); await p.locator('aside nav a[href="/admin/settings"]').waitFor({ state: 'visible' })
  await p.getByRole('button', { name: 'Compact menu' }).click()
  ok((await p.locator('aside').boundingBox()).width === 76, 'compact width')
  ok(await p.locator('aside nav a[href="/admin/settings"]').isVisible(), 'all icons in compact mode')
  ok(await p.evaluate(() => { const n = document.querySelector('aside nav').parentElement; return n.scrollWidth <= n.clientWidth + 1 }), 'compact menu fits its width')
  await shot(p, 'navigation_compact')
  await p.getByRole('button', { name: 'Show menu names' }).click()
  await p.keyboard.press('Control+k'); await p.waitForTimeout(500)
  await p.keyboard.type('sensor ana'); await p.waitForTimeout(600)
  ok(await p.getByText('Sensor analytics').count() > 1, 'palette lists the page')
  ok(true, 'palette finds the new page'); await p.keyboard.press('Escape')

  await p.getByRole('button', { name: 'Everything' }).click()
  ok(await p.getByRole('button', { name: 'Why?' }).count() > 0, 'diagnose buttons')
  await p.getByRole('button', { name: 'Why?' }).first().click()
  await p.getByText('Likely causes').waitFor(); await shot(p, 'health_diagnosis')
  await p.keyboard.press('Escape')
  await p.getByRole('tab', { name: 'Data coverage' }).click(); await p.getByText('not uptime').waitFor(); await shot(p, 'health_coverage')
  await p.getByRole('tab', { name: 'Timeline' }).click(); await p.getByText('people are not listed').waitFor()

  await open(p, '/admin/sensors', 'Sensor analytics')
  await p.locator('.recharts-line-curve, .recharts-line').first().waitFor({ timeout: 20000 })
  ok(await p.getByText('simulated', { exact: true }).count() > 0, 'simulated chip')
  await shot(p, 'sensor_analytics')
  const sel = p.locator('select[aria-label="Measurement"]')
  const t = await sel.locator('option').evaluateAll(os => os.find(o => /Temperature.*DEMO_ENV_SIM/.test(o.textContent)).value)
  await sel.selectOption(t); await p.locator('select[aria-label="Period"]').selectOption('30d')
  await p.getByText('impossible value(s) left out').waitFor()
  ok(await p.getByText('lowest-highest band').count() > 0, 'band text')
  const dl = p.waitForEvent('download'); await p.getByRole('button', { name: 'CSV' }).click()
  ok(/temperature_30d\.csv$/.test((await dl).suggestedFilename()), 'csv download')

  await open(p, '/exhibit', 'Smart Research Laboratory')
  await p.getByText('LIVE', { exact: true }).waitFor(); await shot(p, 'exhibition_live')
  ok(await p.locator('main button, button:not([aria-label])').count() === 0, 'exhibition has no control')
  await p.route('**/api/**', r => r.abort())
  await p.getByText('HISTORICAL', { exact: true }).waitFor({ timeout: 32000 }); await shot(p, 'exhibition_portal_down')
  await p.unroute('**/api/**')

  for (const [w, h] of [[390, 844], [768, 1024], [1920, 1080]]) {
    await p.setViewportSize({ width: w, height: h })
    for (const [u, n] of [['/admin/health', 'Health Center'], ['/admin/sensors', 'Sensor analytics'], ['/exhibit', 'Smart Research']]) {
      await open(p, u, n); await p.waitForTimeout(700)
      const o = await overflow(p)
      ok(o <= 0, `${u} at ${w}px overflows by ${o}px`)
    }
    if (w === 390) { await open(p, '/admin/sensors', 'Sensor analytics'); await shot(p, 'sensor_analytics_phone') }
  }

  const s = await signIn(browser, 'ali@giu-uni.de', { width: 1440, height: 900 })
  for (const u of ['/admin/health', '/admin/sensors', '/exhibit']) {
    await s.goto(BASE + u); await s.waitForTimeout(1500)
    ok(new URL(s.url()).pathname === '/', `student is sent away from ${u}`)
  }
  ok(await s.locator('aside nav a[href^="/admin"]').count() === 0, 'student menu has no staff page')
  const f = await signIn(browser, 'ramy@giu-uni.de', { width: 1440, height: 900 })
  await open(f, '/admin/sensors', 'Sensor analytics')
  ok(await f.locator('aside nav a[href="/admin/emergency"]').count() === 0, 'staff menu has no administrator page')
} catch (e) { bad.push(String(e).slice(0, 400)) } finally { await browser.close() }
console.log(`${checks} checks, ${bad.length} problems`)
bad.forEach(b => console.log(' -', b))
process.exit(bad.length ? 1 : 0)
