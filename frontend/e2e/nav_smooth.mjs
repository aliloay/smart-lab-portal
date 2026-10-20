// Sidebar navigation smoothness on the live portal: per page, time to the new route, time until its
// API calls are done, and main-thread FREEZES (long tasks > 50 ms) while getting there.
// Usage: SMARTLAB_PASSWORD=... node e2e/nav_smooth.mjs [rounds]   (credentials from the environment)
import { chromium } from 'playwright-core'
const BASE = process.env.BASE || 'http://192.168.1.200'
const ROUNDS = Number(process.argv[2] || 2)
const LINKS = (process.env.LINKS || '/command,/admin/security,/admin/operations,/admin/access,/admin/bookings,/admin/equipment,/admin/devices,/admin/incidents,/admin/alerts,/admin/system,/admin/reliability,/labs,/').split(',')
const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * s.length))] }
const browser = await chromium.launch({ channel: 'chrome' })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
await page.addInitScript(() => {
  window.__lt = []
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push(e.duration) }).observe({ type: 'longtask', buffered: true })
})
await page.goto(`${BASE}/login`)
await page.fill('input[type=email]', process.env.SMARTLAB_EMAIL || 'admin@giu-uni.de')
await page.fill('input[type=password]', process.env.SMARTLAB_PASSWORD || '')
await page.click('button[type=submit]'); await page.waitForURL(u => !u.pathname.startsWith('/login'))
await page.goto(BASE + '/admin/system', { waitUntil: 'networkidle' })
let pending = 0, calls = 0
page.on('request', r => { if (r.url().includes('/api/')) { pending++; calls++ } })
page.on('requestfinished', r => { if (r.url().includes('/api/')) pending-- })
page.on('requestfailed', r => { if (r.url().includes('/api/')) pending-- })
const res = {}
for (let i = 0; i < ROUNDS; i++) for (const to of LINKS) {
  const a = page.locator(`aside a[href="${to}"]`).first()
  if (!(await a.count())) { res[to] = { missing: true }; continue }
  await page.evaluate(() => { window.__lt = [] })
  calls = 0
  const t0 = Date.now()
  await a.click()
  await page.waitForURL(u => u.pathname === to)
  const shell = Date.now() - t0
  await page.waitForFunction(() => !document.querySelector('[data-loading], .animate-spin'), null, { timeout: 15000 }).catch(() => {})
  const s = Date.now(); while (pending > 0 && Date.now() - s < 15000) await page.waitForTimeout(20)
  const data = Date.now() - t0
  const lt = await page.evaluate(() => window.__lt)
  const r = (res[to] ??= { shell: [], data: [], freeze: [], longest: [], calls: [] })
  r.shell.push(shell); r.data.push(data); r.freeze.push(Math.round(lt.reduce((x, y) => x + y, 0)))
  r.longest.push(Math.round(Math.max(0, ...lt))); r.calls.push(calls)
  await page.waitForTimeout(400)
}
await browser.close()
const out = {}
for (const [k, v] of Object.entries(res)) {
  if (v.missing) { out[k] = 'not in sidebar'; continue }
  out[k] = { route_ms: q(v.shell, .5), data_ms: q(v.data, .5), data_max: Math.max(...v.data),
             main_thread_blocked_ms: q(v.freeze, .5), longest_freeze_ms: Math.max(...v.longest), api_calls: q(v.calls, .5) }
}
console.log(JSON.stringify(out, null, 1))
