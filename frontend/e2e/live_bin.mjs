// Smart-bin live update (reusable_update), isolated copy only. 2026-11-16.
//   E2E_BASE=http://127.0.0.1:5176 E2E_API=http://127.0.0.1:8100/api E2E_DEVICE_KEY=... SEED_STAFF_PASSWORD=... \
//   E2E_DB_CONTAINER=smartlab-e2e-db node e2e/live_bin.mjs [trials]
// Checks, in a real browser, WITHOUT a page reload: the Smart-bin card goes Offline -> Online when the node reports (a
// SYNTHETIC scan of an unknown tag, not a real node), a stale node shows Offline, every accepted report is pushed exactly
// once, a rejected report pushes nothing. Latency = request sent -> card text changed (same PC, same clock; includes the
// HTTP round trip) - NOT device-sample-to-portal. Refuses anything that is not 127.0.0.1:5176 / :8100.
import { chromium } from 'playwright-core'
import { execFileSync } from 'node:child_process'

const BASE = process.env.E2E_BASE || 'http://127.0.0.1:5176'
const API = process.env.E2E_API || 'http://127.0.0.1:8100/api'
if (!BASE.startsWith('http://127.0.0.1:5176') || !API.startsWith('http://127.0.0.1:8100')) throw new Error('isolated copy only')
const need = k => process.env[k] ?? (() => { throw new Error(`Set ${k}`) })()
const KEY = need('E2E_DEVICE_KEY'), PW = need('SEED_STAFF_PASSWORD'), DB = process.env.E2E_DB_CONTAINER || 'smartlab-e2e-db'
const N = Number(process.argv[2] || 20)
const problems = []
const bad = m => { problems.push(m); console.log('FAIL', m) }
const ok = m => console.log('ok  ', m)

const post = (path, body, key = KEY) => fetch(API + path, { method: 'POST', headers: { 'content-type': 'application/json', 'x-device-key': key }, body: JSON.stringify(body) })
const staleNode = () => execFileSync('docker', ['exec', DB, 'psql', '-U', 'smartlab', '-d', 'smartlab_e2e_test', '-c',
  "update devices set last_seen_at = now() - interval '1 hour' where device_uid='REUSE_BIN_1'"], { stdio: 'ignore' })
const hint = () => post('/reusable/weight-change', { device_uid: 'REUSE_BIN_1', delta_g: 0, mass_g: 0 })   // below MIN_ITEM_G: no DB write, only the push
const scan = () => post('/reusable/scan', { device_uid: 'REUSE_BIN_1', nfc_uid: '04 11 22 33 44 55 66' })  // unknown tag; marks the node seen

const browser = await chromium.launch({ channel: process.env.E2E_CHANNEL || 'chrome', headless: true })
try {
  const page = await (await browser.newContext({ viewport: { width: 1366, height: 860 } })).newPage()
  let frames = 0
  page.on('websocket', ws => ws.on('framereceived', f => { if (String(f.payload).includes('"reusable_update"')) frames++ }))
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto(`${BASE}/login`)
  await page.fill('#email', 'ramy@giu-uni.de'); await page.fill('#password', PW); await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 })
  staleNode()
  await page.goto(`${BASE}/labs/1`)
  await page.waitForFunction(() => document.body.innerText.includes('Smart bin'), null, { timeout: 15000 })
  await page.evaluate(() => { window.__noReload = 'same-page' })
  await page.waitForFunction(() => document.body.innerText.includes('Bin offline'), null, { timeout: 5000 }).then(() => ok('stale node shows "Bin offline"'), () => bad('stale node did not show Bin offline'))
  await page.waitForTimeout(1500)

  // rejected report: nothing pushed, card unchanged
  const f0 = frames
  const r = await post('/reusable/scan', { device_uid: 'REUSE_BIN_1', nfc_uid: '04 11 22 33 44 55 66' }, 'wrong-key')
  await page.waitForTimeout(800)
  r.status >= 400 && frames === f0 ? ok(`rejected report (HTTP ${r.status}) pushed nothing`) : bad(`rejected report: status ${r.status}, frames +${frames - f0}`)
  if (!(await page.evaluate(() => document.body.innerText.includes('Bin offline')))) bad('card changed after a rejected report')

  const lat = [], rtt = []
  for (let i = 0; i < N; i++) {
    staleNode()
    let f = frames
    await hint()                                                    // push -> card refetches -> Offline
    await page.waitForFunction(() => document.body.innerText.includes('Bin offline'), null, { timeout: 5000 })
    if (frames - f !== 1) bad(`trial ${i + 1}: hint delivered ${frames - f} times`)
    await page.evaluate(() => { window.__t = null; window.__obs?.disconnect()
      window.__obs = new MutationObserver(() => { if (!window.__t && document.body.innerText.includes('Bin online')) window.__t = Date.now() })
      window.__obs.observe(document.body, { subtree: true, childList: true, characterData: true }) })
    f = frames
    const t0 = Date.now(); const res = await scan(); const t1 = Date.now()
    if (res.status !== 200) { bad(`trial ${i + 1}: scan HTTP ${res.status}`); continue }
    await page.waitForFunction(() => window.__t, null, { timeout: 5000, polling: 5 }).catch(async () => {
      const card = await page.evaluate(() => [...document.body.innerText.matchAll(/Bin (online|offline)/g)].map(m => m[0]).join(','))
      bad(`trial ${i + 1}: card did not turn online in 5 s (card: ${card}, pushes so far: ${frames})`)
    })
    if (!(await page.evaluate(() => window.__t))) continue
    const tr = await page.evaluate(() => window.__t)
    lat.push(tr - t0); rtt.push(t1 - t0)
    await page.waitForTimeout(150)
    if (frames - f !== 1) bad(`trial ${i + 1}: scan delivered ${frames - f} pushes (expected exactly 1)`)
  }
  if (await page.evaluate(() => window.__noReload) !== 'same-page') bad('page was reloaded')
  else ok('page never reloaded; card updated in place')
  if (errors.length) bad('page errors: ' + errors.slice(0, 2).join(' | '))
  const st = a => { const s = [...a].sort((x, y) => x - y); const q = p => s[Math.min(s.length - 1, Math.ceil(p * s.length) - 1)]; return `n=${s.length} min=${s[0]} median=${q(0.5)} p95=${q(0.95)} max=${s[s.length - 1]} ms` }
  console.log('SYNTHETIC latency, request sent -> card rendered:', st(lat))
  console.log('  of which HTTP round trip (request -> response):', st(rtt))
} finally { await browser.close() }
console.log(problems.length ? `${problems.length} problem(s)` : 'live bin: 0 problems')
process.exit(problems.length ? 1 : 0)
