// "Scan the lab" end to end in Chrome with a FAKE camera (a video file that shows a real asset marker):
//   start -> the marker is decoded on the page -> the live card of THAT record appears (time measured);
//   Stop -> the camera track ends and no further /api/scan request is made; 5 start/stop cycles;
//   the launcher in the AI bubble offers the four entries.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/scan_lab.mjs <base> <fake_cam.mjpeg> <expected card name>
// The fake camera proves the page logic (decode, lookup, overlay, cleanup) - NOT a real phone. Exit 1 = failure.
import { chromium } from 'playwright-core'

const [BASE = 'http://127.0.0.1:5175', VIDEO, NAME = 'Environment node'] = process.argv.slice(2)
const EMAIL = process.env.E2E_EMAIL, PASSWORD = process.env.E2E_PASSWORD
if (!EMAIL || !PASSWORD || !VIDEO) { console.error('usage: E2E_EMAIL/E2E_PASSWORD node e2e/scan_lab.mjs <base> <video.mjpeg> [name]'); process.exit(2) }
const b = await chromium.launch({ channel: 'chrome', args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
  `--use-file-for-fake-video-capture=${VIDEO}`] })
const out = { cycles: [] }
let failed = false
try {
  const ctx = await b.newContext({ viewport: { width: 412, height: 915 }, isMobile: true, hasTouch: true })   // a phone-sized screen
  const p = await ctx.newPage()
  const scanReqs = []
  p.on('request', r => { if (r.url().includes('/api/scan/')) scanReqs.push({ t: Date.now(), url: r.url() }) })
  await p.addInitScript(() => {                         // keep the camera stream reachable for the checks
    const md = navigator.mediaDevices
    const orig = md.getUserMedia.bind(md)
    md.getUserMedia = async c => { const s = await orig(c); window.__cam = s; return s }
  })
  await p.goto(`${BASE}/login`)
  await p.fill('#email', EMAIL); await p.fill('#password', PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  // the launcher (bubble -> 4 entries)
  await p.goto(`${BASE}/labs`)
  await p.click('button[aria-label="Open AI assistant"]')
  out.launcher = await p.$$eval('[role=menu] [role=menuitem]', els => els.map(e => e.textContent.trim().split(/(?=[A-Z][a-z]+ [a-z])/)[0]))
  await p.click('[role=menuitem]:has-text("Scan the lab")')
  await p.waitForURL(u => u.pathname === '/scan')
  for (let i = 0; i < 5; i++) {
    const t0 = Date.now()
    await p.click('button:has-text("Start camera")')
    await p.waitForSelector(`text=${NAME}`, { timeout: 15000 })
    const cardMs = Date.now() - t0
    const decoder = await p.textContent('text=/Markers: /').catch(() => '')
    if (i === 0 && process.env.SHOT) { await p.waitForTimeout(600); await p.screenshot({ path: process.env.SHOT, fullPage: true }) }
    await p.click('button:has-text("Stop")')
    const tStop = Date.now()
    await p.waitForTimeout(1500)
    const ended = await p.evaluate(() => window.__cam?.getVideoTracks().every(t => t.readyState === 'ended'))
    const after = scanReqs.filter(r => r.t > tStop + 100).length
    out.cycles.push({ card_ms: cardMs, track_ended: ended, scan_requests_after_stop: after })
    if (!ended || after > 0) failed = true
    if (i === 0) out.decoder = decoder
  }
  out.heap_mb = await p.evaluate(() => performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null)
  // a hidden tab never keeps the camera
  await p.click('button:has-text("Start camera")')
  await p.waitForSelector(`text=${NAME}`, { timeout: 15000 })
  await p.evaluate(() => { Object.defineProperty(document, 'hidden', { value: true, configurable: true }); document.dispatchEvent(new Event('visibilitychange')) })
  await p.waitForTimeout(500)
  out.hidden_tab_released = await p.evaluate(() => window.__cam?.getVideoTracks().every(t => t.readyState === 'ended'))
  if (!out.hidden_tab_released) failed = true
  if (!out.launcher || out.launcher.length !== 4) failed = true
} finally { await b.close() }
console.log(JSON.stringify(out, null, 1))
console.log(failed ? 'FAIL' : 'PASS')
process.exit(failed ? 1 : 0)
