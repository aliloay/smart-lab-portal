/**
 * The emergency message on a STUDENT's screen: shown, read aloud, repeated,
 * Stop voice silences only this screen, CLEAR ALL hides it, and "voice off
 * by the administrator" stops the speech. The portal's answer is faked in the
 * browser (no record is written to the live database).
 *   node e2e/emergency_message.mjs [base]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://localhost'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
let failed = 0
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'}  ${what}`); if (!ok) failed++ }
try {
  const page = await (await browser.newContext()).newPage()
  await page.addInitScript(() => {
    window.__said = []
    const fake = { speaking: false, cancel() {}, getVoices: () => [],
                   speak(u) { window.__said.push(u.text) } }
    Object.defineProperty(window, 'speechSynthesis', { value: fake })
  })
  let state = { lab_id: 2, lab_code: 'LAB_02', message: 'Leave by the stairs', speak: true, alarm: false,
                version: 7, active: true, at: new Date().toISOString() }
  await page.route('**/api/emergency/active', r => r.fulfill({ json: state.message ? [state] : [] }))

  await page.goto(`${BASE}/login`)
  await page.fill('#email', 'ali@giu-uni.de')
  await page.fill('#password', 'Student#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 20000 })
  await page.getByTestId('emergency-message').waitFor({ timeout: 15000 })
  check((await page.getByTestId('emergency-message').innerText()).includes('Leave by the stairs'),
        'student sees the message')
  await page.waitForTimeout(1500)
  let said = await page.evaluate(() => window.__said)
  check(said.length === 1 && said[0].includes('Leave by the stairs'), `read aloud once at first (${said.length})`)

  await page.getByRole('button', { name: 'Stop voice' }).click()
  const before = (await page.evaluate(() => window.__said)).length
  await page.waitForTimeout(1500)
  check((await page.evaluate(() => window.__said)).length === before
        && await page.getByTestId('emergency-message').isVisible(), 'Stop voice: silent, message still shown')

  // A NEW message (new version) is read aloud again.
  state = { ...state, message: 'Meet at gate 2', version: 8 }
  await page.evaluate(() => { window.__said = [] })
  await page.reload()
  await page.getByText('Meet at gate 2').waitFor({ timeout: 15000 })
  await page.waitForTimeout(1500)
  said = await page.evaluate(() => window.__said)
  check(said.length === 1 && said[0].includes('Meet at gate 2'), 'a new message is read aloud again')

  // Clear sound from the administrator: shown, not spoken.
  state = { ...state, speak: false, version: 9 }
  await page.evaluate(() => { window.__said = [] })
  await page.reload()
  await page.getByText('Voice switched off by the administrator').waitFor({ timeout: 15000 })
  await page.waitForTimeout(1500)
  check((await page.evaluate(() => window.__said)).length === 0, 'Clear sound: message shown, nothing read aloud')

  // Clear all by the administrator: gone.
  state = { ...state, message: '', version: 10 }
  await page.reload()
  await page.waitForTimeout(2500)
  check(await page.getByTestId('emergency-message').count() === 0, 'Clear all: the message disappears')
} finally {
  await browser.close()
}
process.exit(failed ? 1 : 0)
