// Search palette speed on the live portal: Ctrl+K, type, pick the first result -> page ready; plus the
// sign-in -> welcome -> Enter Dashboard path. Credentials from SMARTLAB_PASSWORD. Usage: node e2e/palette_speed.mjs
import { chromium } from 'playwright-core'
const BASE = process.env.BASE || 'http://192.168.1.200'
const b = await chromium.launch({ channel: 'chrome' })
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } })
await p.addInitScript(() => { window.__lt = []; new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push(e.duration) }).observe({ type: 'longtask', buffered: true }) })
let pending = 0
p.on('request', r => { if (r.url().includes('/api/')) pending++ })
p.on('requestfinished', r => { if (r.url().includes('/api/')) pending-- })
p.on('requestfailed', r => { if (r.url().includes('/api/')) pending-- })
const settle = async (t0) => {
  await p.waitForFunction(() => !document.querySelector('[data-loading], .animate-spin'), null, { timeout: 15000 }).catch(() => {})
  const s = Date.now(); while (pending > 0 && Date.now() - s < 15000) await p.waitForTimeout(20)
  const lt = await p.evaluate(() => { const v = window.__lt; window.__lt = []; return v })
  return { ms: Date.now() - t0, frozen_ms: Math.round(lt.reduce((a, c) => a + c, 0)), longest_ms: Math.round(Math.max(0, ...lt)) }
}
// sign-in -> welcome -> enter
await p.goto(`${BASE}/login`)
await p.fill('input[type=email]', 'admin@giu-uni.de'); await p.fill('input[type=password]', process.env.SMARTLAB_PASSWORD || '')
let t0 = Date.now()
await p.click('button[type=submit]'); await p.waitForURL(u => u.pathname.startsWith('/welcome'), { timeout: 20000 })
console.log('sign-in -> welcome', JSON.stringify(await settle(t0)))
const enter = p.getByRole('button', { name: /enter|skip/i }).first()
await enter.waitFor({ timeout: 15000 })
t0 = Date.now(); await enter.click(); await p.waitForURL(u => u.pathname === '/', { timeout: 20000 })
await p.waitForSelector('aside a', { timeout: 20000 })
console.log('welcome -> dashboard', JSON.stringify(await settle(t0)))
for (const term of ['UR5', 'bookings', 'camera', 'BIN']) {
  await p.keyboard.press('Control+k')
  await p.waitForSelector('[role=dialog][aria-label=Search] input')
  t0 = Date.now()
  await p.fill('[role=dialog][aria-label=Search] input', term)
  await p.waitForTimeout(400)
  const first = p.locator('[role=dialog][aria-label=Search] li button').first()
  const what = (await first.innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 60)
  const shown = Date.now() - t0
  const t1 = Date.now(); await first.click()
  const r = await settle(t1)
  console.log(`search "${term}" -> results ${shown} ms -> "${what}" ${p.url().replace(BASE, '')}`, JSON.stringify(r))
}
await b.close()
