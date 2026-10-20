// Login page screenshots (desktop, mobile, reduced motion) + horizontal-overflow check. Read-only.
//   node e2e/login_shots.mjs <baseUrl> <outDir>
import { chromium } from 'playwright-core'
const [BASE, OUT] = [process.argv[2], process.argv[3]]
const b = await chromium.launch({ channel: 'chrome' })
for (const [n, w, h, rm] of [['desktop', 1440, 900, 'no-preference'], ['mobile', 390, 844, 'no-preference'], ['reduced', 1440, 900, 'reduce']]) {
  const c = await b.newContext({ viewport: { width: w, height: h }, reducedMotion: rm }); const p = await c.newPage()
  const errs = []; p.on('pageerror', e => errs.push(String(e)))
  await p.goto(`${BASE}/login`); await p.waitForTimeout(1500)
  const ow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  console.log(`${n}: overflow ${ow}px, page errors ${errs.length}`)
  await p.screenshot({ path: `${OUT}/login-${n}.png` }); await c.close()
}
await b.close()
