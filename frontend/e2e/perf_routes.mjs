// Performance baseline: per-route time to network-idle + every /api request's duration.
// Usage: node e2e/perf_routes.mjs [label] [runs]   (writes docs/reports/perf_<label>.json)
import { chromium } from 'playwright-core'
import fs from 'node:fs'

const BASE = process.env.BASE || 'http://192.168.1.200'
const label = process.argv[2] || 'run'
const RUNS = Number(process.argv[3] || 3)
const ROUTES = ['/', '/labs', '/labs/1', '/bookings', '/admin/access', '/admin/reports', '/admin/system',
  '/admin/equipment', '/admin/security', '/admin/devices', '/admin/alerts', '/admin/operations']

const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : null }
const browser = await chromium.launch({ channel: 'chrome', args: ['--enable-unsafe-swiftshader'] })
const page = await browser.newPage()
const api = {}
page.on('requestfinished', async r => {
  const u = new URL(r.url()); if (!u.pathname.startsWith('/api/')) return
  const t = r.timing(); const ms = t.responseEnd > 0 ? t.responseEnd : null
  if (ms == null) return
  const k = r.method() + ' ' + u.pathname.replace(/\/\d+(?=\/|$)/g, '/:id');
  (api[k] ??= []).push(ms)
})
await page.goto(`${BASE}/login`)
await page.fill('input[type=email]', 'admin@giu-uni.de'); await page.fill('input[type=password]', 'Admin#2026')
const t0 = Date.now(); await page.click('button[type=submit]')
await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 30000 })
const loginToApp = Date.now() - t0
const routes = {}
for (let i = 0; i < RUNS; i++) {
  for (const r of ROUTES) {
    const s = Date.now()
    await page.goto(BASE + r, { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {})
    ;(routes[r] ??= []).push(Date.now() - s)
  }
}
await browser.close()
const out = { label, at: new Date().toISOString(), base: BASE, runs: RUNS, login_to_app_ms: loginToApp,
  routes: Object.fromEntries(Object.entries(routes).map(([k, v]) => [k, { median: q(v, .5), p95: q(v, .95) }])),
  api: Object.fromEntries(Object.entries(api).sort((a, b) => q(b[1], .5) - q(a[1], .5))
    .map(([k, v]) => [k, { n: v.length, median: Math.round(q(v, .5)), p95: Math.round(q(v, .95)) }])) }
fs.mkdirSync('../docs/reports', { recursive: true })
fs.writeFileSync(`../docs/reports/perf_${label}.json`, JSON.stringify(out, null, 1))
console.log(JSON.stringify({ login_to_app_ms: out.login_to_app_ms, routes: out.routes }, null, 0))
console.log(Object.entries(out.api).slice(0, 15).map(([k, v]) => `${v.median}\t${v.p95}\t${v.n}\t${k}`).join('\n'))
