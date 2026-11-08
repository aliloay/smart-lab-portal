/**
 * Scroll smoothness + start-up after the welcome page (2026-10-27, owner: "after skipping the welcome page it loads for a
 * bit, and when scrolling fast it does not respond immediately, it freezes and lags"). Real Chrome with the GPU (headed):
 *   - welcome -> Skip -> time until the dashboard shows its cards;
 *   - fast wheel scrolling on the heavy pages: frame intervals from requestAnimationFrame (a 60 Hz frame is 16.7 ms;
 *     > 50 ms = a visible stall) plus long tasks.
 *   node e2e/scroll_fps.mjs [base]   (E2E_EMAIL / E2E_PASSWORD)
 */
import { chromium } from 'playwright-core'
const BASE = process.argv[2] || 'http://localhost'
const browser = await chromium.launch({ channel: 'chrome', headless: false, args: ['--window-size=1600,950'] })
const pct = (a, p) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : 0 }
try {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } })
  await ctx.addInitScript(() => {
    window.__lt = []
    new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(e.duration))).observe({ type: 'longtask', buffered: true })
  })
  const page = await ctx.newPage()
  await page.goto(`${BASE}/login`)
  await page.fill('#email', process.env.E2E_EMAIL)
  await page.fill('#password', process.env.E2E_PASSWORD)
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 30000 })
  // welcome -> skip -> portal ready
  for (let run = 0; run < 3; run++) {
    await page.goto(`${BASE}/welcome`); await page.waitForSelector('#wl-end', { timeout: 30000 }); await page.waitForTimeout(1500)
    const skip = page.locator('button:has-text("Skip")').first()
    if (await skip.count()) {
      await skip.hover(); await page.waitForTimeout(250)
      const t0 = Date.now()
      await skip.click()
      await page.waitForSelector('aside nav', { timeout: 30000 })
      await page.waitForFunction(() => document.querySelectorAll('main .card').length >= 3 && !document.querySelector('main .animate-pulse'), null, { timeout: 30000 }).catch(() => {})
      console.log(`welcome skip -> dashboard ready: ${Date.now() - t0} ms`)
    }
  }
  const all = []
  for (const path of ['/', '/labs', '/admin/access', '/admin/equipment', '/admin/devices', '/robots']) {
    await page.goto(`${BASE}${path}`)
    await page.waitForTimeout(2500)
    await page.evaluate(() => {
      window.__lt = []; window.__fr = []
      let last = performance.now()
      const tick = t => { window.__fr.push(t - last); last = t; if (window.__fr.length < 2000 && !window.__stop) requestAnimationFrame(tick) }
      window.__stop = false; requestAnimationFrame(tick)
    })
    for (let r = 0; r < 2; r++) {
      for (let i = 0; i < 14; i++) { await page.mouse.wheel(0, 900); await page.waitForTimeout(40) }
      for (let i = 0; i < 14; i++) { await page.mouse.wheel(0, -900); await page.waitForTimeout(40) }
    }
    await page.waitForTimeout(300)
    const { fr, lt } = await page.evaluate(() => { window.__stop = true; return { fr: window.__fr.slice(2), lt: window.__lt } })
    all.push(...fr)
    const stalls = fr.filter(x => x > 50).length
    console.log(`${path.padEnd(18)} frames ${String(fr.length).padStart(4)}  median ${pct(fr, .5).toFixed(1)} ms  p95 ${pct(fr, .95).toFixed(1)} ms  worst ${Math.round(Math.max(0, ...fr))} ms  stalls>50ms ${stalls}  long tasks ${lt.length} (${Math.round(lt.reduce((a, b) => a + b, 0))} ms)`)
  }
  console.log(`ALL frames ${all.length} median ${pct(all, .5).toFixed(1)} ms p95 ${pct(all, .95).toFixed(1)} ms stalls>50ms ${all.filter(x => x > 50).length}`)
} finally { await browser.close() }
