/**
 * The assistant answers a period question with coloured charts, drawn in the chat.
 *   node e2e/ai_charts.mjs [base]      E2E_SHOTS=<folder> saves a screenshot.
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://localhost'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
let ok = true
try {
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 } })).newPage()
  await page.goto(`${BASE}/login`)
  await page.fill('#email', process.env.E2E_EMAIL || 'admin@giu-uni.de')
  await page.fill('#password', process.env.E2E_PASSWORD || 'Admin#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 })
  await page.click('button[aria-label="Open AI assistant"]')
  const box = '[aria-label="Question for the AI assistant"]'
  await page.fill(box, '15 sep till today')
  await page.press(box, 'Enter')
  await page.locator('svg.recharts-surface').nth(1).waitFor({ timeout: 20000 })
  await page.waitForTimeout(800)
  const n = await page.locator('[role=dialog][aria-label="AI assistant"] svg.recharts-surface').count()
  const bars = await page.locator('[role=dialog][aria-label="AI assistant"] .recharts-bar-rectangle').count()
  ok = n >= 2 && bars > 0
  console.log(`${ok ? 'ok  ' : 'FAIL'}  charts drawn in the chat: ${n} (bars: ${bars}), "Save image": ${await page.getByText('Save image').count()}`)
  if (process.env.E2E_SHOTS) await page.screenshot({ path: `${process.env.E2E_SHOTS}/ai_charts.png` })
} finally {
  await browser.close()
}
process.exit(ok ? 0 : 1)
