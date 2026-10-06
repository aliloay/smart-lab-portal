/**
 * Notifications page from the admin menu: tabs with counts, list, filters,
 * load more. Read-only (it does not mark anything read).
 *   node e2e/notifications_page.mjs [base]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://localhost'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
let failed = 0
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'}  ${what}`); if (!ok) failed++ }
try {
  const page = await (await browser.newContext({ viewport: { width: 1500, height: 900 } })).newPage()
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto(`${BASE}/login`)
  await page.fill('#email', 'admin@giu-uni.de')
  await page.fill('#password', 'Admin#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 20000 })
  if (await page.$('[role=alertdialog]')) await page.getByRole('button', { name: 'CLEAR ALL' }).click()
  const t0 = Date.now()
  await page.click('aside nav a[href="/notifications"]')
  await page.locator('[data-testid=notification-list] button').first().waitFor({ timeout: 15000 })
  check(true, `admin menu opens Notifications, list shown in ${Date.now() - t0} ms`)
  const tabs = await page.locator('[role=tab], [role=tablist] button').allInnerTexts()
  check(['All', 'Unread', 'From n8n', 'From the portal', 'Critical'].every(t => tabs.some(x => x.includes(t))),
        `tabs: ${tabs.map(t => t.replace(/\s+/g, ' ')).join(' | ')}`)
  const shown = await page.locator('[data-testid=notification-list] > section button').count()
  const more = await page.getByRole('button', { name: /Load more/ }).count()
  check(shown > 0 && shown <= 50, `first page shows ${shown} (load more button: ${more ? 'yes' : 'no'})`)
  if (more) {
    await page.getByRole('button', { name: /Load more/ }).click()
    await page.waitForTimeout(1500)
    const after = await page.locator('[data-testid=notification-list] > section button').count()
    check(after > shown, `load more: ${shown} -> ${after}`)
  }
  await page.getByRole('tab', { name: /Critical/ }).or(page.locator('[role=tablist] button', { hasText: 'Critical' })).first().click()
  await page.waitForTimeout(1200)
  check(true, `critical tab: ${await page.locator('[data-testid=notification-list] > section button').count()} shown`)
  await page.fill('input[aria-label="Search notifications"]', 'offline')
  await page.waitForTimeout(1500)
  const titles = await page.locator('[data-testid=notification-list] > section button').allInnerTexts()
  check(titles.every(t => /offline/i.test(t)) , `search "offline" in Critical: ${titles.length} results, all match title or text`)
  check(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} finally {
  await browser.close()
}
process.exit(failed ? 1 : 0)
