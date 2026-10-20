/**
 * Robots & PCs / robot twin load benchmark (read-only). For each page: a COLD visit (fresh browser profile, empty
 * cache) and a REPEAT visit (in-app navigation away and back). Reports time until every robot model file has
 * arrived and the main thread has been quiet for 300 ms ("ready"), model bytes, model files, and long tasks.
 *   E2E_PASSWORD=... node e2e/robots_tab_perf.mjs [base] [runs]      (admin account; password never printed)
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || 'https://localhost'
const RUNS = Number(process.argv[3] || 3)
// [name, path, canvases the page shows when complete]
const PAGES = [['Robots & PCs tab', '/admin/equipment?tab=noncons', 2], ['UR5e page', '/robots/10', 1], ['FANUC page', '/robots/11', 1]]
const isModel = u => u.includes('/models/')

async function session() {
  const b = await chromium.launch({ channel: 'chrome', args: ['--ignore-certificate-errors'] })
  const ctx = await b.newContext({ viewport: { width: 1600, height: 1000 }, ignoreHTTPSErrors: true })
  await ctx.addInitScript(() => {
    window.__lt = []
    new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]) })
      .observe({ type: 'longtask', buffered: true })
  })
  const p = await ctx.newPage()
  await p.goto(BASE + '/login'); await p.fill('input[type=email]', process.env.E2E_EMAIL || 'admin@giu-uni.de')
  await p.fill('input[type=password]', process.env.E2E_PASSWORD); await p.click('button[type=submit]')
  await p.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 30000 })
  return { b, p }
}

/** Run `go` and wait until the page's canvases exist, model requests are done and no long task for 300 ms.
 *  fresh = `go` loads a new document (its timeline starts at 0). */
async function measure(p, go, canvases, fresh) {
  const pending = new Set(); let bytes = 0, files = 0
  const onReq = r => { if (isModel(r.url())) pending.add(r) }
  const onDone = async r => {
    if (!isModel(r.url())) return
    pending.delete(r); files++
    try { bytes += (await r.sizes()).responseBodySize } catch { /* ignore */ }
  }
  const onFail = r => pending.delete(r)
  p.on('request', onReq); p.on('requestfinished', onDone); p.on('requestfailed', onFail)
  const t0 = fresh ? 0 : await p.evaluate(() => performance.now())
  const w0 = Date.now()
  await go()
  let ready = 0
  for (;;) {
    await p.waitForTimeout(50)
    const s = await p.evaluate(() => {
      const ends = window.__lt.map(([st, d]) => st + d)
      return { now: performance.now(), lastEnd: ends.length ? Math.max(...ends) : 0, canvas: document.querySelectorAll('canvas').length }
    })
    // a fresh document must fetch its models (empty cache): not ready before at least one has arrived
    const modelsIn = !fresh || files > 0 || Date.now() - w0 > 8000
    if (modelsIn && pending.size === 0 && s.canvas >= canvases && s.now - s.lastEnd > 300 && Date.now() - w0 > 400) { ready = Date.now() - w0 - 300; break }
    if (Date.now() - w0 > 30000) { ready = -1; break }
  }
  const lt = await p.evaluate(t => window.__lt.filter(([st]) => st >= t).map(([, d]) => Math.round(d)), t0)
  p.off('request', onReq); p.off('requestfinished', onDone); p.off('requestfailed', onFail)
  return { ready, files, kb: Math.round(bytes / 1024), longTasks: lt.length, longMs: lt.reduce((a, d) => a + d, 0), maxLong: Math.max(0, ...lt) }
}

const rows = []
for (let run = 0; run < RUNS; run++) {
  for (const [name, path, canvases] of PAGES) {
    const { b, p } = await session()
    try {
      const cold = await measure(p, () => p.goto(BASE + path), canvases, true)
      // away (another sidebar page) and back, in-app
      await p.click('aside nav a[href="/labs"]').catch(() => p.goto(BASE + '/labs'))
      await p.waitForTimeout(1200)
      const warm = await measure(p, () => p.evaluate(u => { history.pushState({}, '', u); dispatchEvent(new PopStateEvent('popstate')) }, path), canvases, false)
      rows.push({ run, name, cold, warm })
      console.log(`${name.padEnd(18)} run ${run}  cold ${String(cold.ready).padStart(5)} ms  ${String(cold.kb).padStart(6)} KB in ${cold.files} files  long ${cold.longMs} ms (max ${cold.maxLong})` +
        `  |  repeat ${String(warm.ready).padStart(5)} ms  ${warm.kb} KB  long ${warm.longMs} ms (max ${warm.maxLong})`)
    } finally { await b.close() }
  }
}
const med = a => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)] }
console.log('\nmedians:')
for (const [name] of PAGES) {
  const r = rows.filter(x => x.name === name)
  console.log(`${name.padEnd(18)} cold ${med(r.map(x => x.cold.ready))} ms, ${med(r.map(x => x.cold.kb))} KB, long ${med(r.map(x => x.cold.longMs))} ms  |  repeat ${med(r.map(x => x.warm.ready))} ms, long ${med(r.map(x => x.warm.longMs))} ms`)
}
