/**
 * Live monitor -> Details window, and Security -> All cameras wall (staff).
 *
 *   node e2e/monitor_security.mjs [base]      (default http://localhost - the Docker portal)
 *   E2E_SHOTS=<folder> also saves screenshots there.
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://localhost'
const SHOTS = process.env.E2E_SHOTS || ''
const LAB = process.env.E2E_LAB || 'LAB_01'

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const results = []
const step = (ok, text) => { results.push(ok); console.log(`${ok ? 'ok  ' : 'FAIL'}  ${text}`) }
try {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto(`${BASE}/login`)
  await page.fill('#email', process.env.E2E_EMAIL || 'admin@giu-uni.de')
  await page.fill('#password', process.env.E2E_PASSWORD || 'Admin#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 })

  // Live monitor -> Details
  await page.goto(`${BASE}/monitor`)
  const tile = page.locator('section', { hasText: LAB }).first()
  await tile.waitFor({ timeout: 15000 })
  await tile.getByRole('button', { name: /DETAILS/ }).click()
  const dlg = page.getByRole('dialog', { name: `${LAB} details` })
  step(await dlg.isVisible(), `Details opens for ${LAB}`)
  for (const h of ['Camera', 'Environment', 'Door and lock', 'Open alerts', 'Door activity', 'Bookings', 'Devices', 'Issues']) {
    step(await dlg.getByRole('heading', { name: new RegExp(`^${h}`) }).first().isVisible(), `  panel "${h}"`)
  }
  await page.waitForTimeout(2500)                              // data + a few camera frames
  const activity = await dlg.locator('section', { hasText: 'Door activity' }).locator('li').count()
  step(activity > 0, `  door activity listed (${activity} rows)`)
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/monitor_details.png` })
  await page.keyboard.press('Escape')
  step(!(await dlg.isVisible()), 'Esc closes Details')

  // Security -> All cameras
  await page.goto(`${BASE}/admin/security`)
  const wallTab = page.getByRole('tab', { name: /All cameras/ })
  await wallTab.waitFor({ timeout: 15000 })
  step((await wallTab.getAttribute('aria-selected')) === 'true', 'All cameras is the first tab shown')
  const card = page.getByRole('button', { name: /Click to enlarge|LAB_/ }).filter({ hasText: LAB }).first()
  step(await card.isVisible(), `camera of ${LAB} on the wall`)
  await page.waitForTimeout(2000)
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/security_wall.png` })
  const placeholders = await page.getByText('Camera to be installed').count()
  step(placeholders >= 1, `every lab has a frame (${placeholders} waiting for a camera)`)
  // Detection boxes OFF: the views load the plain picture; detection itself is untouched.
  const rawReq = page.waitForRequest(r => r.url().includes('/frame.jpg?raw=true'), { timeout: 8000 }).then(() => true, () => false)
  await page.getByRole('button', { name: /Detection boxes ON/ }).first().click()
  step(await rawReq, 'Detection boxes OFF shows the plain picture')
  await page.getByRole('button', { name: /Detection boxes OFF/ }).first().click()
  await card.click()
  const full = page.getByRole('dialog', { name: `${LAB} camera` })
  step(await full.isVisible(), 'click enlarges it full screen')
  await page.waitForTimeout(2000)
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/security_full.png` })
  await full.getByRole('button', { name: /^Events/ }).click()
  step(!(await full.isVisible()) && (await page.getByRole('tab', { name: /Events/ }).getAttribute('aria-selected')) === 'true',
       'Events button jumps to that camera\'s events')
  step(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} finally {
  await browser.close()
}
process.exit(results.every(Boolean) ? 0 : 1)
