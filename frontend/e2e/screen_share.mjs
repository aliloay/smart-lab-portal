// Admin -> students screen share, end to end on the live portal:
// admin (https, screen capture) presses "Share this screen"; a student on /share must receive frames;
// Stop must end it for the student. Usage: node e2e/screen_share.mjs [screenshot dir]
import { chromium } from 'playwright-core'
const out = process.argv[2]
const browser = await chromium.launch({ channel: 'chrome', args: [
  '--auto-select-desktop-capture-source=Entire screen', '--use-fake-ui-for-media-stream', '--enable-usermedia-screen-capturing'] })
async function login(base, email, pw) {
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1400, height: 900 } })
  const p = await ctx.newPage()
  await p.goto(`${base}/login`)
  await p.fill('input[type=email]', email); await p.fill('input[type=password]', pw)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  return p
}
const admin = await login('https://192.168.1.200', 'admin@giu-uni.de', 'Admin#2026')
const student = await login('http://192.168.1.200', process.env.VIEWER || 'ramy@giu-uni.de', process.env.VIEWER_PW || 'Staff#2026')
await admin.goto('https://192.168.1.200/admin/equipment?tab=noncons', { waitUntil: 'networkidle' })
const btn = admin.locator('button:has-text("Choose screen or window")')
console.log('share button enabled (https):', await btn.isEnabled())
await admin.fill('input[placeholder^="Title"]', 'E2E test')
await btn.click()
await admin.waitForSelector('text=Preview - only you can see this', { timeout: 15000 })
console.log('local preview shown before going live: true')
const before = await student.evaluate(() => fetch('/api/equipment/broadcast/status', { headers: { Authorization: 'Bearer ' + (localStorage.getItem('token') || sessionStorage.getItem('token') || '') } }).then(r => r.json()).catch(() => null))
await admin.click('button:has-text("Go live")')
await admin.waitForSelector('text=presenting', { timeout: 15000 })
await student.goto('http://192.168.1.200/share')
const t0 = Date.now()
await student.waitForSelector('img[alt="Shared screen"]', { timeout: 20000 })
const ms = Date.now() - t0
const w = await student.$eval('img[alt="Shared screen"]', i => i.naturalWidth)
console.log('student sees the shared screen:', w > 0, `(${w}px wide, first frame after ${ms} ms)`)
console.log('heading:', await student.locator('h1').innerText())
if (out) await student.screenshot({ path: `${out}/share_student.png` })
await admin.click('button:has-text("Stop sharing")')
await student.waitForSelector('text=Nothing is being shared right now', { timeout: 10000 })
console.log('stop ends it for the student: true')
await browser.close()
