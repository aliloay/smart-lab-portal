// Stop sharing from ANOTHER tab must release the presenting tab's screen capture at once (2026-10-25).
// Tab A presents (browser capture, fake screen). Its frame uploads are held unanswered, so the old way out (a 409
// on the next upload - up to a minute later in a background tab, whose timers Chrome slows) cannot fire: only
// the share_state push can release it. Tab B (same admin) presses Stop through the API.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/share_stop_release.mjs [base]     (exit 1 = capture not released)
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || 'http://127.0.0.1:5174'
const EMAIL = process.env.E2E_EMAIL, PASSWORD = process.env.E2E_PASSWORD
if (!EMAIL || !PASSWORD) { console.error('set E2E_EMAIL and E2E_PASSWORD'); process.exit(2) }
const browser = await chromium.launch({ channel: 'chrome', args: [
  '--auto-select-desktop-capture-source=Entire screen', '--use-fake-ui-for-media-stream', '--enable-usermedia-screen-capturing'] })
let failed = false
try {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } })
  const a = await ctx.newPage()
  // Keep a handle on the captured stream to read its tracks' state.
  await a.addInitScript(() => {
    const md = navigator.mediaDevices
    if (!md?.getDisplayMedia) return
    const orig = md.getDisplayMedia.bind(md)
    md.getDisplayMedia = async (o) => { const s = await orig(o); window.__share = s; return s }
  })
  await a.goto(`${BASE}/login`)
  await a.fill('#email', EMAIL); await a.fill('#password', PASSWORD)
  await a.click('button[type=submit]'); await a.waitForURL(u => !u.pathname.startsWith('/login'))
  await a.goto(`${BASE}/admin/equipment?tab=noncons`, { waitUntil: 'networkidle' })
  await a.click('button:has-text("Choose screen or window")')
  await a.waitForSelector('text=Preview - only you can see this', { timeout: 15000 })
  await a.click('button:has-text("Go live")')
  await a.waitForFunction(() => window.__share?.getVideoTracks()[0]?.readyState === 'live', null, { timeout: 15000 })
  let uploads = 0
  await a.waitForTimeout(1200)                                   // a few real frames first
  await a.route('**/api/equipment/broadcast/frame', () => { uploads++ })   // held: never answered
  // Tab B: Stop, the way the Stop button of another tab / device does it.
  const b = await ctx.newPage()
  await b.goto(`${BASE}/labs`)
  const t0 = Date.now()
  const st = await b.evaluate(async () => {
    const t = localStorage.getItem('slp.token') || sessionStorage.getItem('slp.token')
    const r = await fetch('/api/equipment/broadcast/stop', { method: 'POST', headers: { Authorization: 'Bearer ' + t } })
    return r.status
  })
  const released = await a.waitForFunction(() => window.__share?.getVideoTracks()[0]?.readyState === 'ended',
    null, { timeout: 5000 }).then(() => Date.now() - t0).catch(() => null)
  const uploadsAtRelease = uploads
  await a.waitForTimeout(1500)
  console.log(JSON.stringify({ stop_status: st, capture_released_ms: released,
    uploads_after_release: uploads - uploadsAtRelease }))
  if (released == null || released > 2000 || uploads > uploadsAtRelease) failed = true
} finally {
  await browser.close()
}
console.log(failed ? 'FAIL: the presenting tab kept capturing after Stop' : 'PASS')
process.exit(failed ? 1 : 0)
