/**
 * Command Center + robot pages in a real browser (admin): they load, show
 * live robot telemetry, and the browser console has no errors (incl. CSP).
 * Screenshots go to the folder given as 2nd argument. Read-only.
 *   node e2e/command_center.mjs [base] [shots-dir]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || 'http://localhost'
const OUT = process.argv[3] || '.'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const errors = []
try {
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage()
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto(`${BASE}/login`)
  await page.fill('#email', process.env.E2E_EMAIL || 'admin@giu-uni.de')
  await page.fill('#password', process.env.E2E_PASSWORD || 'Admin#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'))
  for (const [path, name] of [['/command', 'command'], ['/robots', 'robots']]) {
    const t0 = Date.now()
    await page.goto(`${BASE}${path}`)
    await page.waitForSelector('canvas', { timeout: 15000 })
    await page.waitForTimeout(1500)
    console.log(`${path}: canvas after ${Date.now() - t0} ms`)
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  }
  const href = await page.locator('a[href^="/robots/"]').first().getAttribute('href')
  await page.goto(`${BASE}${href}`)
  await page.waitForSelector('table')
  await page.waitForTimeout(1500)
  const q1 = await page.locator('tbody tr').first().innerText()
  await page.waitForTimeout(1200)
  const q2 = await page.locator('tbody tr').first().innerText()
  console.log('J1 row updates live:', q1 !== q2, '|', q1.replace(/\s+/g, ' '), '->', q2.replace(/\s+/g, ' '))
  await page.screenshot({ path: `${OUT}/robot.png`, fullPage: true })
} finally {
  await browser.close()
}
console.log(errors.length ? `CONSOLE ERRORS:\n${errors.join('\n')}` : 'no console errors')
