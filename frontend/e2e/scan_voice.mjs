// Voice while scanning (2026-10-27): fake phone camera showing a marker + fake microphone asking a question.
//   start camera -> the asset card appears -> tap the mic -> speak -> tap -> the question is transcribed and
//   answered WITH the card as context; the camera keeps running; mic released afterwards.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/scan_voice.mjs <base> <fake_cam.mjpeg> <question.wav> "<card name>"
// Fake devices prove the page logic - NOT a real phone or microphone.
import { chromium } from 'playwright-core'

const [BASE = 'http://127.0.0.1:5175', VIDEO, WAV, NAME = 'Environment node'] = process.argv.slice(2)
const b = await chromium.launch({ channel: 'chrome', args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
  `--use-file-for-fake-video-capture=${VIDEO}`, `--use-file-for-fake-audio-capture=${WAV}`, '--autoplay-policy=no-user-gesture-required'] })
const out = {}
let failed = false
let p
try {
  p = await (await b.newContext({ viewport: { width: 412, height: 915 }, isMobile: true, hasTouch: true })).newPage()
  const asks = []
  p.on('request', r => { if (r.url().includes('/api/ai/ask')) asks.push(JSON.parse(r.postData() || '{}')) })
  await p.addInitScript(() => {
    const md = navigator.mediaDevices, orig = md.getUserMedia.bind(md)
    window.__streams = []
    md.getUserMedia = async c => { const s = await orig(c); window.__streams.push(s); return s }
  })
  await p.goto(`${BASE}/login`)
  await p.fill('#email', process.env.E2E_EMAIL); await p.fill('#password', process.env.E2E_PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  await p.goto(`${BASE}/scan`)
  await p.click('button:has-text("Start camera")')
  await p.waitForSelector(`text=${NAME}`, { timeout: 20000 })
  await p.waitForSelector(`text=/Ask about/`, { timeout: 10000 })
  await p.click('button[aria-label="Ask by voice"]')
  await p.waitForSelector('text=/Listening/', { timeout: 8000 })
  await p.waitForTimeout(4500)
  const t0 = Date.now()
  await p.click('button[aria-label="Stop and ask"]')
  await p.waitForSelector('text=/^You: /', { timeout: 30000 })
  out.question = (await p.textContent('text=/^You: /')).slice(5)
  await p.waitForFunction(() => !document.body.innerText.includes('Thinking…'), null, { timeout: 240000 })
  out.answer_ms = Date.now() - t0
  out.context_sent = asks.length > 0 && JSON.stringify(asks[asks.length - 1].history || []).includes(NAME)
  out.camera_still_running = await p.evaluate(() => window.__streams.some(s => s.getVideoTracks().some(t => t.readyState === 'live')))
  out.mic_released = await p.evaluate(() => window.__streams.filter(s => s.getAudioTracks().length).every(s => s.getAudioTracks().every(t => t.readyState === 'ended')))
  if (process.env.SHOT) await p.screenshot({ path: process.env.SHOT, fullPage: true })
  if (!out.context_sent || !out.camera_still_running || !out.mic_released) failed = true
} catch (e) {
  out.error = String(e).slice(0, 300); failed = true
  try { out.page_error = await p.evaluate(() => [...document.querySelectorAll('.text-bad-soft')].map(e => e.textContent).join(' / ')) } catch { /* closed */ }
} finally { await b.close() }
console.log(JSON.stringify(out, null, 1))
console.log(failed ? 'FAIL' : 'PASS')
process.exit(failed ? 1 : 0)
