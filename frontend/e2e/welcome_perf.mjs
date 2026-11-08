// Scroll-performance probe for /welcome: wheel-scrolls the whole page top->bottom->top
// and reports frame times (rAF), long frames and long tasks. Read-only.
//   node e2e/welcome_perf.mjs <baseUrl> [width] [height]
import { chromium } from 'playwright-core'
const BASE = process.argv[2] || 'http://127.0.0.1:4174'
const W = +(process.argv[3] || 1440), H = +(process.argv[4] || 900)
const b = await chromium.launch({ channel: 'chrome', args: ['--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--use-angle=d3d11'] })
const p = await (await b.newContext({ viewport: { width: W, height: H } })).newPage()
await p.goto(`${BASE}/login`)
await p.fill('#email', process.env.E2E_EMAIL || 'admin@giu-uni.de'); await p.fill('input[type=password]', process.env.E2E_PASSWORD || 'Admin#2026')
await p.click('form button[type=submit]'); await p.waitForSelector('#wl-end'); await p.waitForTimeout(2500)
await p.evaluate(() => {
  window.__f = []; window.__lt = []
  let last = performance.now()
  const sec = () => { const r = document.querySelector('.wl-root'); const y = r.scrollTop + r.clientHeight / 2; let id = '?'; document.querySelectorAll('.wl-sec').forEach(s => { if (s.offsetTop <= y) id = s.id }); return id }
  window.__slow = []
  const tick = t => { const d = t - last; window.__f.push(d); if (d > 50) window.__slow.push(`${sec()}:${Math.round(d)}`); last = t; if (window.__run) requestAnimationFrame(tick) }
  window.__run = true; requestAnimationFrame(tick)
  try { new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(e.duration))).observe({ type: 'longtask', buffered: false }) } catch {}
})
await p.mouse.move(W / 2, H / 2)
const total = await p.evaluate(() => document.querySelector('.wl-root').scrollHeight)
for (const dir of [1, -1]) for (let y = 0; y < total; y += 100) { await p.mouse.wheel(0, 100 * dir); await p.waitForTimeout(16) }
const r = await p.evaluate(() => { window.__run = false; return { f: window.__f.slice(2), lt: window.__lt, slow: window.__slow } })
const f = r.f.sort((a, b) => a - b), n = f.length
const avg = f.reduce((a, c) => a + c, 0) / n
console.log(JSON.stringify({
  viewport: `${W}x${H}`, frames: n, avgFps: +(1000 / avg).toFixed(1),
  p50ms: +f[Math.floor(n * .5)].toFixed(1), p95ms: +f[Math.floor(n * .95)].toFixed(1), maxMs: +f[n - 1].toFixed(1),
  over33ms: f.filter(x => x > 33.4).length, over50ms: f.filter(x => x > 50).length,
  slow: r.slow.join(' '), longTasks: r.lt.length, longTaskMs: Math.round(r.lt.reduce((a, c) => a + c, 0)),
}))
await b.close()
