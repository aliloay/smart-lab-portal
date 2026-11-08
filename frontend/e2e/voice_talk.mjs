// Voice in the assistant, end to end in Chrome with a FAKE microphone (a WAV file of a spoken question):
//   bubble -> launcher "Talk" -> recording starts by itself -> stop -> local Whisper -> the question appears ->
//   the assistant answers -> the answer is spoken (local Piper, /api/voice/speak) -> the mic track is released.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/voice_talk.mjs <base> <question.wav> "<expected words>"
// Needs tools/voice/voice_service.py running. Proves the page logic with recorded audio - NOT a real microphone.
import { chromium } from 'playwright-core'

const [BASE = 'http://127.0.0.1:5175', WAV, EXPECT = 'temperature'] = process.argv.slice(2)
const b = await chromium.launch({ channel: 'chrome', args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
  `--use-file-for-fake-audio-capture=${WAV}`, '--autoplay-policy=no-user-gesture-required'] })
const out = {}
let failed = false
try {
  var p = await (await b.newContext({ viewport: { width: 1280, height: 860 } })).newPage()
  const t = {}
  p.on('request', r => { const u = r.url(); if (u.includes('/api/voice/') || u.includes('/api/ai/ask')) t[u.split('/api/')[1] + ':' + Date.now()] = 0 })
  await p.addInitScript(() => {
    const md = navigator.mediaDevices, orig = md.getUserMedia.bind(md)
    window.__mics = []
    md.getUserMedia = async c => { const s = await orig(c); window.__mics.push(s); return s }
  })
  await p.goto(`${BASE}/login`)
  await p.fill('#email', process.env.E2E_EMAIL); await p.fill('#password', process.env.E2E_PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  await p.goto(`${BASE}/labs`)
  await p.click('button[aria-label="Open AI assistant"]')
  await p.click('[role=menuitem]:has-text("Talk")')
  await p.waitForSelector('text=/Listening/', { timeout: 8000 })
  await p.waitForTimeout(4500)                                   // the fake mic plays the question
  const t0 = Date.now()
  await p.click('button[aria-label="Stop and send"]')
  const q = await p.waitForSelector(`div.justify-end >> text=/${EXPECT}/i`, { timeout: 20000 })
  out.question = (await q.textContent()).trim()
  out.speech_to_text_ms = Date.now() - t0
  const speak = p.waitForResponse(r => r.url().includes('/api/voice/speak'), { timeout: 60000 })
  await p.waitForSelector('text=/Stop speaking/', { timeout: 60000 })
  out.question_to_answer_ms = Date.now() - t0
  const sr = await speak
  out.first_audio_ms = Date.now() - t0
  out.speak_status = sr.status()
  out.mic_released = await p.evaluate(() => window.__mics.every(s => s.getAudioTracks().every(tr => tr.readyState === 'ended')))
  if (process.env.SHOT) await p.screenshot({ path: process.env.SHOT })
  if (!out.mic_released || out.speak_status !== 200) failed = true
} catch (e) { out.error = String(e).slice(0, 300); failed = true } finally { await b.close() }
console.log(JSON.stringify(out, null, 1))
console.log(failed ? 'FAIL' : 'PASS')
process.exit(failed ? 1 : 0)
