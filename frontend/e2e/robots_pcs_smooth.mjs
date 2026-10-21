/**
 * Robots & PCs tab smoothness, measured the way the owner uses it (read-only):
 *   1. open the tab, 2. sit still 12 s (live data arriving), 3. scroll down and up with the wheel for ~8 s.
 * Per phase: frames slower than 50 ms (janky) and 200 ms (a freeze), worst frame, long tasks, DOM nodes
 * changed per second (re-render churn) and requests per second. A CPU profile of the whole run gives the
 * functions that took the most time.
 *   E2E_TOKEN_FILE=<file with an admin token> node e2e/robots_pcs_smooth.mjs [base] [out.json]
 */
import { chromium } from 'playwright-core'
import fs from 'node:fs'

const BASE = process.argv[2] || 'http://192.168.1.200'
const OUT = process.argv[3] || ''
// LIVE_ROBOT=1: the UR5e as when it is live in the lab - robot_state at 5/s (the server's rate) is added
// to this test browser's own WebSocket only. Made-up joint values; nothing is sent anywhere.
const LIVE = process.env.LIVE_ROBOT === '1'
const token = fs.readFileSync(process.env.E2E_TOKEN_FILE, 'utf8').trim()

const b = await chromium.launch({ channel: 'chrome', headless: process.env.HEADFUL !== '1' })
const ctx = await b.newContext({ viewport: { width: 1600, height: 950 } })
if (LIVE) {
  const r = await fetch(BASE + '/api/robots', { headers: { Authorization: `Bearer ${token}` } })
  const ur = (await r.json()).find(x => !x.demo && /UR5/i.test(`${x.model} ${x.device_uid}`))
  await ctx.routeWebSocket(/\/ws\/activity/, ws => {
    ws.connectToServer()
    let k = 0
    const t = setInterval(() => {
      k++
      const q = [-0.26 + 0.3 * Math.sin(k / 10), -2.2, 2.04, -1.4, 1.59, 1.66]
      try {
        ws.send(JSON.stringify({ type: 'robot_state', device_id: ur.device_id, lab_id: ur.lab_id, state: 'MOVING', q,
          qd: [0.1, 0, 0, 0, 0, 0], joints_moving: [true, false, false, false, false, false], home: 'NOT_HOME',
          source: 'test', telemetry_age_ms: 20 }))
      } catch { clearInterval(t) }
    }, 200)
    ws.onClose(() => clearInterval(t))
  })
}
await ctx.addInitScript(t => {
  try { localStorage.setItem('slp.token', t) } catch { /* */ }
  window.__lt = []; window.__fr = []; window.__mut = 0; window.__req = 0
  // every WebGL context ever created, and whether it was released (lost) afterwards
  window.__gl = []
  const orig = HTMLCanvasElement.prototype.getContext
  HTMLCanvasElement.prototype.getContext = function (kind, ...a) {
    const c = orig.call(this, kind, ...a)
    if (c && /webgl/.test(kind) && !window.__gl.includes(c)) window.__gl.push(c)
    return c
  }
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]) })
    .observe({ type: 'longtask', buffered: true })
  let last = performance.now()
  const tick = now => { window.__fr.push([now, now - last]); last = now; requestAnimationFrame(tick) }
  requestAnimationFrame(tick)
  new MutationObserver(m => { window.__mut += m.length }).observe(document, { subtree: true, childList: true, attributes: true, characterData: true })
}, token)
const p = await ctx.newPage()
const paths = new Map()
p.on('request', r => {
  p.evaluate(() => { window.__req++ }).catch(() => {})
  const u = new URL(r.url()); if (u.pathname.startsWith('/api/')) paths.set(u.pathname, (paths.get(u.pathname) || 0) + 1)
})
p.on('response', async r => {
  const u = new URL(r.url()); if (!u.pathname.startsWith('/api/')) return
  try { const n = (await r.body()).length; paths.set(u.pathname + ' bytes', (paths.get(u.pathname + ' bytes') || 0) + n) } catch { /* */ }
})
const cdp = await ctx.newCDPSession(p)
await cdp.send('Profiler.enable'); await cdp.send('Profiler.setSamplingInterval', { interval: 500 })

const t0 = Date.now()
await p.goto(BASE + '/admin/equipment?tab=noncons', { waitUntil: 'domcontentloaded' })
await p.waitForSelector('text=Robots', { timeout: 30000 })
const loadMs = Date.now() - t0
// CYCLES=n: leave the tab and come back n times first (in-app, as a long session does), pointing at both
// robot views each time so their 3D starts - then measure. Reports WebGL contexts still alive.
for (let i = 0; i < Number(process.env.CYCLES || 0); i++) {
  await p.getByText('1 · ', { exact: false }).first().click(); await p.waitForTimeout(700)
  await p.getByText('2 · Robots & PCs').first().click(); await p.waitForTimeout(1500)
  for (const el of await p.locator('button[aria-label$="open the 3D view"]').all()) await el.click().catch(() => {})
  await p.waitForTimeout(1500)
}
await p.waitForTimeout(3000)                       // settle
await cdp.send('Profiler.start')

async function phase(name, run) {
  const s = await p.evaluate(() => ({ t: performance.now(), m: window.__mut, r: window.__req }))
  await run()
  return p.evaluate(([name, s]) => {
    const e = performance.now(), dur = (e - s.t) / 1000
    const fr = window.__fr.filter(([t]) => t > s.t && t <= e).map(([, d]) => d)
    const lt = window.__lt.filter(([t]) => t > s.t && t <= e).map(([, d]) => Math.round(d))
    return { phase: name, seconds: +dur.toFixed(1), frames: fr.length, fps: +(fr.length / dur).toFixed(1),
             janky_over_50ms: fr.filter(d => d > 50).length, freezes_over_200ms: fr.filter(d => d > 200).length,
             worst_frame_ms: Math.round(Math.max(0, ...fr)), long_tasks: lt.length, long_task_ms: lt.sort((a, b) => b - a).slice(0, 8),
             dom_changes_per_s: Math.round((window.__mut - s.m) / dur), requests_per_s: +((window.__req - s.r) / dur).toFixed(1) }
  }, [name, s])
}

const gl = await p.evaluate(() => ({ created: window.__gl.length, alive: window.__gl.filter(c => !c.isContextLost()).length,
  on_page: document.querySelectorAll('canvas').length }))
const res = [{ load_ms: loadMs, cycles: Number(process.env.CYCLES || 0), webgl: gl }]
res.push(await phase('idle 12 s', () => p.waitForTimeout(12000)))
await p.mouse.move(800, 500)
res.push(await phase('scroll down + up', async () => {
  for (let i = 0; i < 25; i++) { await p.mouse.wheel(0, 240); await p.waitForTimeout(140) }
  for (let i = 0; i < 25; i++) { await p.mouse.wheel(0, -240); await p.waitForTimeout(140) }
}))
const { profile } = await cdp.send('Profiler.stop')
// self time per function (top 15)
const dt = profile.timeDeltas, byId = new Map(profile.nodes.map(n => [n.id, n])), self = new Map()
profile.samples.forEach((id, i) => {
  const n = byId.get(id), f = n.callFrame
  const k = `${f.functionName || '(anon)'} ${f.url.split('/').pop()}:${f.lineNumber}`
  self.set(k, (self.get(k) || 0) + (dt[i] || 0) / 1000)
})
res.push({ top_self_ms: [...self.entries()].filter(([k]) => !k.startsWith('(idle)') && !k.startsWith('(program)'))
  .sort((a, b) => b[1] - a[1]).slice(0, 15).map(([k, v]) => [k, Math.round(v)]) })
res.push({ api_requests_whole_run: Object.fromEntries([...paths.entries()].sort((a, b) => b[1] - a[1])) })
console.log(JSON.stringify(res, null, 1))
if (OUT) fs.writeFileSync(OUT, JSON.stringify(res, null, 1))
await b.close()
