// Portal responsiveness under camera load - READ-ONLY measurement, one browser session.
//   node e2e/perf_portal.mjs [base] [seconds]      (default http://localhost, 30 s per page)
// Measures per page: requests/s by kind, frame fetch time p50/p95 (browser side), server proxy
// time (X-Proxy-Ms), frame age when served (X-Frame-Age-Ms), long tasks (>50 ms main-thread
// blocks), JS heap growth, and the latency of an unrelated API call while the feed runs.
// Credentials: E2E_EMAIL / E2E_PASSWORD from the environment (never printed).
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || 'http://localhost'
const SECS = Number(process.argv[3] || 30)
const EMAIL = process.env.E2E_EMAIL, PASSWORD = process.env.E2E_PASSWORD
if (!EMAIL || !PASSWORD) { console.error('set E2E_EMAIL and E2E_PASSWORD'); process.exit(2) }

const pct = (a, p) => a.length ? Math.round([...a].sort((x, y) => x - y)[Math.min(a.length - 1, Math.floor(p * a.length))]) : null
const b = await chromium.launch({ channel: 'chrome', headless: true })
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } })
const p = await ctx.newPage()
const errors = []
p.on('pageerror', e => errors.push(String(e).slice(0, 160)))
await p.goto(BASE + '/login'); await p.fill('#email', EMAIL); await p.fill('#password', PASSWORD)
await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
await p.waitForTimeout(3500)                                   // past the welcome intro

for (const route of ['/admin/security', '/command', '/']) {
  const reqs = {}, frameMs = [], proxyMs = [], ageMs = [], starts = new Map()
  const onReq = r => { starts.set(r, Date.now()); const k = r.url().replace(BASE, '').replace(/\?.*$/, '').replace(/\/\d+/g, '/:id'); reqs[k] = (reqs[k] || 0) + 1 }
  const onFin = async r => {
    if (!r.url().includes('/frame.jpg')) return
    const t = starts.get(r); if (t) frameMs.push(Date.now() - t)
    try { const h = (await r.response())?.headers() || {}; if (h['x-proxy-ms']) proxyMs.push(+h['x-proxy-ms']); if (h['x-frame-age-ms']) ageMs.push(+h['x-frame-age-ms']) } catch {}
  }
  p.on('request', onReq); p.on('requestfinished', onFin)
  await p.goto(BASE + route)
  await p.evaluate(() => { window.__lt = []; new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(e.duration))).observe({ type: 'longtask', buffered: false }) })
  const heap0 = await p.evaluate(() => performance.memory?.usedJSHeapSize || 0)
  const apiMs = []
  for (let s = 0; s < SECS; s += 5) {
    await p.waitForTimeout(5000)
    apiMs.push(await p.evaluate(async () => { const t = performance.now(); await fetch('/api/health'); return performance.now() - t }))
  }
  const lt = await p.evaluate(() => window.__lt)
  const heap1 = await p.evaluate(() => performance.memory?.usedJSHeapSize || 0)
  p.off('request', onReq); p.off('requestfinished', onFin)
  const total = Object.values(reqs).reduce((a, c) => a + c, 0)
  const top = Object.entries(reqs).sort((a, c) => c[1] - a[1]).slice(0, 5).map(([k, v]) => `${k} ${(v / SECS).toFixed(1)}/s`)
  console.log(`\n== ${route}  (${SECS} s)`)
  console.log(`requests ${(total / SECS).toFixed(1)}/s: ${top.join(' | ')}`)
  console.log(`frame fetch ms p50/p95 ${pct(frameMs, .5)}/${pct(frameMs, .95)} (n ${frameMs.length}) | proxy ms p50/p95 ${pct(proxyMs, .5)}/${pct(proxyMs, .95)} | frame age at serve ms p50/p95 ${pct(ageMs, .5)}/${pct(ageMs, .95)}`)
  console.log(`long tasks ${lt.length} (total ${Math.round(lt.reduce((a, c) => a + c, 0))} ms, max ${Math.round(Math.max(0, ...lt))} ms) | heap ${(heap0 / 1e6).toFixed(1)} -> ${(heap1 / 1e6).toFixed(1)} MB | /api/health while loaded ms ${apiMs.map(Math.round).join(',')}`)
}
console.log('\npage errors:', errors.length ? errors.join(' | ') : 'none')
await b.close()
