// Robots & PCs tab: records what is on screen every ~80 ms after opening it, so a panel that disappears and
// comes back (owner 2026-10-27: "they disappear and then appear") shows up as a gap in the timeline.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/equipment_flicker.mjs <base> [shotDir]
import { chromium } from 'playwright-core'

const [BASE = 'http://127.0.0.1:5176', SHOTS] = process.argv.slice(2)
const b = await chromium.launch({ channel: 'chrome' })
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
await p.goto(`${BASE}/login`)
await p.fill('#email', process.env.E2E_EMAIL); await p.fill('#password', process.env.E2E_PASSWORD)
await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
await p.goto(`${BASE}/admin/equipment?tab=environment`); await p.waitForTimeout(1500)
const t0 = Date.now()
await p.click('text=2 · Robots & PCs')
const rows = []
for (let i = 0; i < 60; i++) {
  const s = await p.evaluate(() => {
    const vis = el => !!el && el.getBoundingClientRect().height > 4 && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).opacity !== '0'
    const q = sel => [...document.querySelectorAll(sel)]
    const twin = q('[data-twin]')
    return {
      panels: twin.length, panelsVisible: twin.filter(vis).length,
      canvas: q('[data-twin] canvas').filter(vis).length,
      picture: q('[data-twin] img').filter(vis).length,
      pcs: q('[data-pc]').filter(vis).length,
      text: document.querySelector('main')?.innerText.length ?? 0,
    }
  })
  rows.push({ ms: Date.now() - t0, ...s })
  if (SHOTS && i % 6 === 0) await p.screenshot({ path: `${SHOTS}/flk_${String(i).padStart(2, '0')}.png` })
  await p.waitForTimeout(80)
}
await b.close()
let prev = null
for (const r of rows) {
  const k = JSON.stringify({ ...r, ms: 0, text: Math.round(r.text / 200) })
  if (k !== prev) console.log(JSON.stringify(r))
  prev = k
}
