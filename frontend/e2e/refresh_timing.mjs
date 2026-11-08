// What a browser refresh of a page costs: every request (size, time), long tasks, time until quiet.
// Usage: SMARTLAB_PASSWORD=... node e2e/refresh_timing.mjs [path]
import { chromium } from 'playwright-core'
const BASE = process.env.BASE || 'http://192.168.1.200'
const PATH = process.argv[2] || '/'
const b = await chromium.launch({ channel: 'chrome' })
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } })
await p.addInitScript(() => { window.__lt = []; new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)) }).observe({ type: 'longtask', buffered: true }) })
await p.goto(`${BASE}/login`)
await p.fill('#email', 'admin@giu-uni.de'); await p.fill('input[type=password]', process.env.SMARTLAB_PASSWORD || '')
await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
await p.goto(BASE + PATH, { waitUntil: 'networkidle' })
const reqs = new Map()
p.on('request', r => reqs.set(r, { url: r.url().replace(BASE, ''), t0: Date.now() }))
p.on('requestfinished', async r => { const e = reqs.get(r); if (e) { e.ms = Date.now() - e.t0; try { e.kb = Math.round(((await r.sizes()).responseBodySize) / 1024) } catch { e.kb = '?' } } })
const t0 = Date.now()
await p.reload({ waitUntil: 'domcontentloaded' })
const dom = Date.now() - t0
await p.waitForLoadState('networkidle').catch(() => {})
const idle = Date.now() - t0
const lt = await p.evaluate(() => window.__lt)
console.log(`refresh ${PATH}: DOM ${dom} ms, network quiet ${idle} ms, long tasks ${lt.length} (sum ${lt.reduce((a, c) => a + c, 0)} ms, max ${Math.max(0, ...lt)} ms)`)
const rows = [...reqs.values()].filter(e => e.ms != null).sort((a, c) => c.ms - a.ms)
for (const e of rows.slice(0, 14)) console.log(String(e.ms).padStart(6), 'ms', String(e.kb).padStart(5), 'KB', e.url.slice(0, 90))
console.log('requests:', rows.length, '| api:', rows.filter(e => e.url.startsWith('/api/')).length)
await b.close()
