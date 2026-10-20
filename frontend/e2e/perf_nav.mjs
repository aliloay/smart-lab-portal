// In-app (sidebar) navigation timing: click a link -> new page's main heading rendered and its first
// API responses back. Usage: node e2e/perf_nav.mjs [rounds]
import { chromium } from 'playwright-core'
const BASE = process.env.BASE || 'http://192.168.1.200'
const ROUNDS = Number(process.argv[2] || 3)
const LINKS = ['/labs', '/admin/access', '/admin/reports', '/admin/system', '/admin/equipment', '/admin/devices', '/admin/alerts', '/bookings', '/']
const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * s.length))] }
const browser = await chromium.launch({ channel: 'chrome' })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
await page.goto(`${BASE}/login`)
await page.fill('input[type=email]', 'admin@giu-uni.de'); await page.fill('input[type=password]', 'Admin#2026')
await page.click('button[type=submit]'); await page.waitForURL(u => !u.pathname.startsWith('/login'))
await page.goto(BASE + '/', { waitUntil: 'networkidle' })
let pending = 0
page.on('request', r => { if (r.url().includes('/api/')) pending++ })
page.on('requestfinished', r => { if (r.url().includes('/api/')) pending-- })
page.on('requestfailed', r => { if (r.url().includes('/api/')) pending-- })
const res = {}
for (let i = 0; i < ROUNDS; i++) for (const to of LINKS) {
  const a = page.locator(`aside a[href="${to}"]`).first()
  if (!(await a.count())) continue
  const t0 = Date.now()
  await a.click()
  await page.waitForURL(u => u.pathname === to)
  const shell = Date.now() - t0                       // URL + new route mounted
  await page.waitForFunction(() => !document.querySelector('[data-loading], .animate-spin'), null, { timeout: 15000 }).catch(() => {})
  const s = Date.now(); while (pending > 0 && Date.now() - s < 10000) await page.waitForTimeout(20)
  ;(res[to] ??= { shell: [], data: [] }).shell.push(shell); res[to].data.push(Date.now() - t0)
  await page.waitForTimeout(300)
}
await browser.close()
for (const [k, v] of Object.entries(res)) console.log(`${k.padEnd(18)} route ${q(v.shell, .5)} ms (p95 ${q(v.shell, .95)})   data ${q(v.data, .5)} ms (p95 ${q(v.data, .95)})`)
