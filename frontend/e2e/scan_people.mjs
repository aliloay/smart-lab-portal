// "Scan the lab" people boxes: a fake phone camera playing real lab footage; the page sends ONE frame at a time to
// /api/scan/people (-> the camera service's /detect). Over 20 s: answered frames per second, round-trip and
// detector time, busy (429) skips, errors. A camera service must be running for the backend to reach.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/scan_people.mjs <base> <fake_cam.mjpeg>
import { chromium } from 'playwright-core'

const [BASE = 'http://127.0.0.1:5175', VIDEO] = process.argv.slice(2)
const b = await chromium.launch({ channel: 'chrome', args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
  `--use-file-for-fake-video-capture=${VIDEO}`] })
const res = []
try {
  const p = await (await b.newContext({ viewport: { width: 412, height: 915 }, isMobile: true })).newPage()
  p.on('requestfinished', async r => {
    if (!r.url().includes('/api/scan/people')) return
    const resp = await r.response()
    let body = null; try { body = resp && resp.status() === 200 ? await resp.json() : null } catch { /* */ }
    res.push({ t: Date.now(), status: resp?.status(), rtt: r.timing().responseEnd, ms: body?.ms, proxy: body?.proxy_ms, n: body?.boxes?.length })
  })
  await p.goto(`${BASE}/login`)
  await p.fill('#email', process.env.E2E_EMAIL); await p.fill('#password', process.env.E2E_PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  await p.goto(`${BASE}/scan`)
  if (await p.$('button:has-text("People boxes off")')) await p.click('button:has-text("People boxes off")')   // on by default since 2026-10-27
  await p.click('button:has-text("Start camera")')
  await p.waitForTimeout(20000)
  if (process.env.SHOT) await p.screenshot({ path: process.env.SHOT })
  await p.click('button:has-text("Stop")')
} finally { await b.close() }
const ok = res.filter(r => r.status === 200), q = (a, f) => { const s = [...a].sort((x, y) => x - y); return s.length ? Math.round(s[Math.min(s.length - 1, Math.floor(f * s.length))]) : null }
const span = ok.length > 1 ? (ok[ok.length - 1].t - ok[0].t) / 1000 : 1
console.log(JSON.stringify({ answered: ok.length, per_s: +(ok.length / span).toFixed(1), busy_429: res.filter(r => r.status === 429).length,
  errors: res.filter(r => r.status !== 200 && r.status !== 429).length, rtt_p50: q(ok.map(r => r.rtt), .5), rtt_p95: q(ok.map(r => r.rtt), .95),
  detector_p50: q(ok.map(r => r.ms), .5), people_p50: q(ok.map(r => r.n), .5) }))
