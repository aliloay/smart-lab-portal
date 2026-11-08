// CPU profile of one portal page - READ-ONLY. Prints the functions that used the most main-thread time.
//   node e2e/profile_page.mjs <base> <route> [seconds]      E2E_EMAIL / E2E_PASSWORD from the environment
import { chromium } from 'playwright-core'

const [BASE = 'http://localhost', ROUTE = '/command', SECS = '15'] = process.argv.slice(2)
const EMAIL = process.env.E2E_EMAIL, PASSWORD = process.env.E2E_PASSWORD
if (!EMAIL || !PASSWORD) { console.error('set E2E_EMAIL and E2E_PASSWORD'); process.exit(2) }
const b = await chromium.launch({ channel: 'chrome', headless: true })
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
await p.goto(BASE + '/login'); await p.fill('#email', EMAIL); await p.fill('#password', PASSWORD)
await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
await p.waitForTimeout(3500)
await p.goto(BASE + ROUTE); await p.waitForTimeout(4000)
const cdp = await p.context().newCDPSession(p)
await cdp.send('Profiler.enable'); await cdp.send('Profiler.setSamplingInterval', { interval: 500 })
await cdp.send('Profiler.start')
await p.waitForTimeout(Number(SECS) * 1000)
const { profile } = await cdp.send('Profiler.stop')
const dt = (profile.endTime - profile.startTime) / 1000 / profile.samples.length   // ms per sample
const self = new Map(), byId = new Map(profile.nodes.map(n => [n.id, n]))
for (const id of profile.samples) {
  const n = byId.get(id); const f = n.callFrame
  const key = `${f.functionName || '(anon)'} @ ${(f.url || '').split('/').pop().split('?')[0]}:${f.lineNumber + 1}`
  self.set(key, (self.get(key) || 0) + dt)
}
const total = [...self.values()].reduce((a, c) => a + c, 0)
const idle = (self.get('(idle) @ :0') || 0) + (self.get('(program) @ :0') || 0)
console.log(`${ROUTE}: ${SECS} s profiled, busy ${Math.round(total - (self.get('(idle) @ :0') || 0))} ms of ${Math.round(total)} ms`)
for (const [k, v] of [...self.entries()].filter(([k]) => !k.startsWith('(idle)')).sort((a, c) => c[1] - a[1]).slice(0, 18))
  console.log(`${String(Math.round(v)).padStart(6)} ms  ${k}`)
await b.close()
