/**
 * How long each sidebar tab takes to show its content (admin), measured in a
 * real browser: click -> no spinner left and the page has text. Read-only.
 *   node e2e/nav_timing.mjs [base] [rounds]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://localhost'
const ROUNDS = Number(process.argv[3] || 2)
const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 900 } })).newPage()
  const slow = new Map()
  page.on('requestfinished', async r => {
    const t = r.timing()
    const ms = t.responseEnd
    if (r.url().includes('/api/') && !r.url().includes('frame.jpg') && ms > 300)
      slow.set(r.url().replace(BASE, ''), Math.round(ms))
  })
  await page.goto(`${BASE}/login`)
  await page.fill('#email', process.env.E2E_EMAIL || 'admin@giu-uni.de')
  await page.fill('#password', process.env.E2E_PASSWORD || 'Admin#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 20000 })
  // Sign-in lands on the full-screen /welcome (no sidebar) since 2026-10-15: start from a framed page.
  await page.goto(`${BASE}/labs`)
  await page.waitForSelector('aside nav a[href^="/"]', { timeout: 20000 })
  await page.waitForTimeout(1500)
  // An alarm still on covers the page: CLEAR ALL must put this screen back to normal.
  if (await page.$('[role=alertdialog]')) {
    await page.getByRole('button', { name: 'CLEAR ALL' }).click()
    await page.waitForTimeout(300)
    const left = await page.$$eval('[role=alertdialog], .fixed.bottom-0.bg-bad', els => els.length)
    console.log(`${left ? 'FAIL' : 'ok  '}  alarm on screen: CLEAR ALL left ${left} alarm element(s)`)
  }
  const links = await page.$$eval('aside nav a[href^="/"]', as => as.map(a => a.getAttribute('href'))
    .filter(h => h && !h.startsWith('/monitor')))
  const rows = []
  for (let round = 0; round < ROUNDS; round++) {
    for (const href of links) {
      const t0 = Date.now()
      await page.click(`aside nav a[href="${href}"]`)
      await page.waitForFunction(() => {
        const main = document.querySelector('main')
        if (!main || main.innerText.trim().length < 40) return false
        return !main.querySelector('[role=status], .animate-spin')
      }, null, { timeout: 30000, polling: 25 }).catch(() => {})
      rows.push([round, href, Date.now() - t0])
    }
  }
  for (const [round, href, ms] of rows) console.log(`${String(ms).padStart(6)} ms  ${round ? 'again' : 'first'}  ${href}`)
  if (slow.size) {
    console.log('\nAPI calls over 300 ms:')
    for (const [u, ms] of [...slow].sort((a, b) => b[1] - a[1]).slice(0, 12)) console.log(`${String(ms).padStart(6)} ms  ${u}`)
  }
} finally {
  await browser.close()
}
