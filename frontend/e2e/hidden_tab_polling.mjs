// How many API requests a portal tab makes while it is HIDDEN (another tab in front / window minimised), per page.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/hidden_tab_polling.mjs <base> [seconds]
// Visible for 10 s (counted), then hidden for N s (counted) - the hidden state is emulated (document.hidden +
// visibilitychange), like a browser in the background.
import { chromium } from 'playwright-core'

const [BASE = 'http://127.0.0.1:5175', SECS = '40'] = process.argv.slice(2)
const PAGES = ['/admin/operations', '/monitor', '/admin/reliability', '/security']
const b = await chromium.launch({ channel: 'chrome' })
const out = {}
try {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } })
  const p = await ctx.newPage()
  await p.goto(`${BASE}/login`)
  await p.fill('#email', process.env.E2E_EMAIL); await p.fill('#password', process.env.E2E_PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  let n = 0
  p.on('request', r => { if (r.url().includes('/api/')) n++ })
  for (const path of PAGES) {
    await p.goto(BASE + path); await p.waitForTimeout(3000)
    n = 0; await p.waitForTimeout(10000)
    const visible = n / 10
    await p.evaluate(() => {
      Object.defineProperty(document, 'hidden', { value: true, configurable: true })
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })
    n = 0; await p.waitForTimeout(+SECS * 1000)
    const hidden = n / +SECS
    await p.evaluate(() => {
      Object.defineProperty(document, 'hidden', { value: false, configurable: true })
      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })
    out[path] = { visible_req_per_s: +visible.toFixed(2), hidden_req_per_s: +hidden.toFixed(2) }
  }
} finally { await b.close() }
console.log(JSON.stringify(out))
