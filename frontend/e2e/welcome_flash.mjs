// Sign-in must go login -> dark -> welcome, never through the dashboard frame.  node e2e/welcome_flash.mjs <base> <outDir>
import { chromium } from 'playwright-core'
const [BASE, OUT] = [process.argv[2], process.argv[3]]
const b = await chromium.launch({ channel: 'chrome' })
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
await p.goto(`${BASE}/login`); await p.waitForTimeout(1200)
await p.screenshot({ path: `${OUT}/login-desktop.png` })
await p.fill('#email', 'admin@giu-uni.de'); await p.fill('input[type=password]', 'Admin#2026')
await p.click('form button[type=submit]')
const seen = []
for (let i = 0; i < 40; i++) {
  seen.push(await p.evaluate(() => {
    const el = document.elementFromPoint(innerWidth / 2, innerHeight / 2)
    return `${location.pathname}:${el?.closest('.wl-root') ? 'welcome' : el?.closest('.login-stage') ? 'login' : el?.closest('aside,nav,main') ? 'PORTAL' : 'other'}`
  }))
  await p.waitForTimeout(50)
}
console.log([...new Set(seen)].join(' -> '))
console.log(seen.some(s => s.includes('PORTAL')) ? 'FAIL dashboard flashed' : 'PASS no dashboard flash')
await b.close()
