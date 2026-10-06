/**
 * The report link in the assistant opens the report in a new tab, already
 * signed in (the sign-in lives in this tab's sessionStorage; a plain
 * target="_blank" link opens without it and asked to sign in again).
 *
 *   node e2e/report_link.mjs [base]      (default http://localhost - the Docker portal)
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://localhost'
const EMAIL = process.env.E2E_EMAIL || 'admin@giu-uni.de'
const PASSWORD = process.env.E2E_PASSWORD || 'Admin#2026'

const browser = await chromium.launch({ channel: 'chrome', headless: true })
let failed = false
try {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 860 } })
  const page = await ctx.newPage()
  await page.goto(`${BASE}/login`)
  await page.fill('#email', EMAIL)
  await page.fill('#password', PASSWORD)
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 })

  await page.click('button[aria-label="Open AI assistant"]')
  await page.fill('[aria-label="Question for the AI assistant"]', 'weekly report')
  await page.press('[aria-label="Question for the AI assistant"]', 'Enter')
  const link = page.getByText(/Open the full weekly report/).last()
  await link.waitFor({ timeout: 20000 })

  const [tab] = await Promise.all([ctx.waitForEvent('page'), link.click()])
  await tab.waitForLoadState('domcontentloaded')
  await tab.waitForTimeout(2500)                     // let the app route
  const path = new URL(tab.url()).pathname
  const heading = await tab.getByText('Weekly lab report').first().isVisible().catch(() => false)
  if (path.startsWith('/login') || !heading) {
    failed = true
    console.log(`FAIL  the report tab opened at ${path} (report visible: ${heading})`)
  } else {
    console.log(`ok    the report tab opened signed in at ${path}`)
  }
} finally {
  await browser.close()
}
process.exit(failed ? 1 : 0)
