/**
 * Main-thread freezes (long tasks > 50 ms) while opening and scrolling the
 * heavy admin pages. Read-only.   node e2e/jank.mjs [base]
 */
import { chromium } from 'playwright-core'
const BASE = process.argv[2] || 'http://localhost'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } })
  await ctx.addInitScript(() => {
    window.__lt = []
    new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(e.duration))).observe({ type: 'longtask', buffered: true })
  })
  const page = await ctx.newPage()
  await page.goto(`${BASE}/login`)
  await page.fill('#email', process.env.E2E_EMAIL || 'admin@giu-uni.de')
  await page.fill('#password', process.env.E2E_PASSWORD || 'Admin#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'))
  for (const path of ['/', '/labs', '/labs/1', '/admin/access', '/admin/operations', '/command', '/admin/devices']) {
    await page.click(`aside nav a[href="${path}"]`).catch(() => page.goto(`${BASE}${path}`))
    await page.evaluate(() => { window.__lt = [] })
    await page.waitForTimeout(1500)
    for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, 700); await page.waitForTimeout(150) }
    await page.waitForTimeout(500)
    const lt = await page.evaluate(() => window.__lt)
    const tot = Math.round(lt.reduce((a, b) => a + b, 0))
    console.log(`${path.padEnd(18)} long tasks: ${String(lt.length).padStart(3)}  total ${String(tot).padStart(5)} ms  worst ${Math.round(Math.max(0, ...lt))} ms`)
  }
} finally { await browser.close() }
