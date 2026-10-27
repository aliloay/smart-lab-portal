// Live Smart Lab camera (2026-10-27): fake phone camera showing a marker + fake microphone.
//   start -> the marker's live chip is pinned in the picture -> tap it (target selected, live panel open)
//   -> typed "Is anything wrong?" answered from the live record -> spoken "Tell me more" transcribed by the local
//   speech service and answered about the SAME target -> Stop releases camera and microphone.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/live_camera.mjs <base> <fake_cam.mjpeg> <question.wav> "<asset name>"
// Fake devices prove the page logic and the real backend path - NOT a real phone, camera or microphone.
import { chromium } from 'playwright-core'

const [BASE = 'http://127.0.0.1:5176', VIDEO, WAV, NAME = 'Environment node'] = process.argv.slice(2)
const b = await chromium.launch({ channel: 'chrome', args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
  `--use-file-for-fake-video-capture=${VIDEO}`, `--use-file-for-fake-audio-capture=${WAV}`, '--autoplay-policy=no-user-gesture-required'] })
const out = {}
let failed = false
let p
try {
  p = await (await b.newContext({ viewport: { width: 412, height: 915 }, isMobile: true, hasTouch: true })).newPage()
  const asks = []
  p.on('request', r => { if (r.url().includes('/api/scan/ask')) asks.push(JSON.parse(r.postData() || '{}')) })
  await p.addInitScript(() => {
    const md = navigator.mediaDevices, orig = md.getUserMedia.bind(md)
    window.__streams = []
    md.getUserMedia = async c => { const s = await orig(c); window.__streams.push(s); return s }
  })
  await p.goto(`${BASE}/login`)
  await p.fill('#email', process.env.E2E_EMAIL); await p.fill('#password', process.env.E2E_PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  await p.goto(`${BASE}/scan`)
  const t0 = Date.now()
  await p.click('button:has-text("Start camera")')
  const pin = p.locator(`button.absolute:has-text("${NAME}")`).first()
  await pin.waitFor({ state: 'visible', timeout: 20000 })
  out.pin_ms = Date.now() - t0
  out.pin_moves_with_marker = (await pin.getAttribute('style'))?.includes('translate(') ?? false
  await pin.click()
  await p.waitForSelector('text=/Last report/', { timeout: 10000 })
  out.panel_open = true
  // typed question about the selected target
  await p.fill('input[placeholder^="e.g."]', 'Is anything wrong?')
  const t1 = Date.now()
  await p.click('button[aria-label="Ask"]')
  await p.waitForSelector('text=/from the live record/', { timeout: 30000 })
  out.typed_answer_ms = Date.now() - t1
  out.typed_target = asks[0]?.code ?? null
  // spoken question - same target, local speech service
  await p.click('button[aria-label="Ask by voice"]')
  await p.waitForSelector('text=/Listening/', { timeout: 8000 })
  await p.waitForTimeout(3500)
  const t2 = Date.now()
  await p.click('button[aria-label="Stop and ask"]')
  await p.waitForFunction(() => document.querySelectorAll('div.space-y-1 > div.text-\\[12\\.5px\\]').length >= 2, null, { timeout: 60000 })
  await p.waitForFunction(() => !/Looking it up|Transcribing/.test(document.body.innerText), null, { timeout: 120000 })
  out.voice_total_ms = Date.now() - t2
  out.transcript = await p.evaluate(() => [...document.querySelectorAll('div.space-y-1 > div.text-\\[12\\.5px\\]')].pop()?.textContent ?? '')
  out.voice_target = asks[1]?.code ?? null
  out.same_target = !!out.typed_target && out.typed_target === out.voice_target
  if (process.env.SHOT) await p.screenshot({ path: process.env.SHOT, fullPage: true })
  await p.click('button:has-text("Stop")')
  await p.waitForTimeout(500)
  out.camera_released = await p.evaluate(() => window.__streams.filter(s => s.getVideoTracks().length).every(s => s.getVideoTracks().every(t => t.readyState === 'ended')))
  out.mic_released = await p.evaluate(() => window.__streams.filter(s => s.getAudioTracks().length).every(s => s.getAudioTracks().every(t => t.readyState === 'ended')))
  if (!out.panel_open || !out.same_target || !out.camera_released || !out.mic_released) failed = true
} catch (e) {
  out.error = String(e).slice(0, 300); failed = true
  try { out.page_text = (await p.evaluate(() => document.body.innerText)).slice(0, 600) } catch { /* closed */ }
} finally { await b.close() }
console.log(JSON.stringify(out, null, 1))
console.log(failed ? 'FAIL' : 'PASS')
process.exit(failed ? 1 : 0)
