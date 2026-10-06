/**
 * Experiments page opens for staff/admin and shows the current data mode.
 * Read-only on purpose: creating an experiment here would write test data into
 * the live database (the backend tests cover creating and running them).
 *   node e2e/experiments_page.mjs [base]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://localhost'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
let ok = true
try {
  const page = await (await browser.newContext()).newPage()
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto(`${BASE}/login`)
  await page.fill('#email', process.env.E2E_EMAIL || 'admin@giu-uni.de')
  await page.fill('#password', process.env.E2E_PASSWORD || 'Admin#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 })
  await page.click('aside nav a[href="/admin/experiments"]')
  await page.getByText('New records are stamped').waitFor({ timeout: 15000 })
  await page.waitForTimeout(800)
  const mode = (await page.getByTestId('data-mode').textContent())?.trim()
  ok = /^(REAL_OPERATION|PHYSICAL_TEST|BENCH_TEST|SOFTWARE_TEST|DEMO_DATA|UNKNOWN_PROVENANCE)/.test(mode ?? '') && errors.length === 0
  console.log(`${ok ? 'ok  ' : 'FAIL'}  Experiments page opens from the menu; new records stamped: ${mode}${errors.length ? ' | errors: ' + errors.join(' | ') : ''}`)
} finally {
  await browser.close()
}
process.exit(ok ? 0 : 1)
