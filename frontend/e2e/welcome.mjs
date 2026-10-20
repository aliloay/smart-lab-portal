// Welcome story test: every role lands on /welcome after sign-in, it stays put,
// sections render with their real images, Skip / Enter go to "/", no console errors.
//
//   node e2e/welcome.mjs [baseUrl] [outDir]      (default http://127.0.0.1:5173)
//
// Needs the API with the seed users and Google Chrome (playwright-core).
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'

const BASE = process.argv[2] || 'http://127.0.0.1:5173'
const OUT = process.argv[3] || 'e2e-shots'
mkdirSync(OUT, { recursive: true })
const ROLES = [
  { name: 'admin', email: 'admin@giu-uni.de', password: 'Admin#2026' },
  { name: 'staff', email: 'ramy@giu-uni.de', password: 'Staff#2026' },
  { name: 'student', email: 'ali@giu-uni.de', password: 'Student#2026' },
]
const SECTIONS = ['wl-intro', 'wl-hero', 'wl-labs', 'wl-robots', 'wl-auto', 'wl-access', 'wl-end']
let failed = 0
const check = (ok, msg) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${msg}`); if (!ok) failed++ }

const browser = await chromium.launch({ channel: 'chrome', args: ['--enable-unsafe-swiftshader'] })

async function login(page, r) {
  await page.goto(`${BASE}/login`)
  await page.fill('input[type=email]', r.email)
  await page.fill('input[type=password]', r.password)
  await page.click('form button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 })
}

for (const [i, r] of ROLES.entries()) {
  for (const vp of i === 0 ? [{ n: 'desktop', w: 1440, h: 900 }, { n: 'mobile', w: 390, h: 844 }] : [{ n: 'desktop', w: 1440, h: 900 }]) {
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } })
    const page = await ctx.newPage()
    const errors = []
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
    page.on('pageerror', e => errors.push(String(e)))
    await login(page, r)
    check(new URL(page.url()).pathname === '/welcome', `${r.name}/${vp.n}: lands on /welcome (${page.url()})`)
    await page.waitForSelector('#wl-labs')
    // the lab cells fill in when the labs arrive: wait for them before counting
    await page.waitForFunction(() => document.querySelectorAll('.wl-cell-label b, .wl-mcell b').length > 0, null, { timeout: 15000 }).catch(() => {})
    const labels = await page.$$eval('.wl-cell-label b, .wl-mcell b', els => els.map(e => e.textContent))
    const codes = new Set(labels)
    // Compared with the database the page runs against (live: 10 active, LAB_10 inactive; the seeded test DB differs).
    const active = await page.evaluate(async () => {
      const r = await fetch('/api/labs', { headers: { Authorization: 'Bearer ' + (localStorage.getItem('slp.token') ?? sessionStorage.getItem('slp.token')) } })
      return (await r.json()).filter(l => l.is_active !== false).length
    })
    check(codes.size === active, `${r.name}/${vp.n}: ${codes.size} lab nodes = ${active} active labs in the DB`)
    for (const id of SECTIONS) {
      await page.evaluate(id => document.getElementById(id).scrollIntoView(), id)
      await page.waitForTimeout(id === 'wl-robots' ? 2500 : 1400)
      if (r.name === 'admin') await page.screenshot({ path: `${OUT}/${vp.n}-${id}.png` })
    }
    const broken = await page.$$eval('.wl-root img', imgs => imgs.filter(i => i.complete && i.naturalWidth === 0).map(i => i.src))
    check(broken.length === 0, `${r.name}/${vp.n}: all images load ${broken.join(' ')}`)
    const bottom = await page.evaluate(() => { const el = document.querySelector('.wl-root'); el.scrollTop = el.scrollHeight; return new Promise(res => setTimeout(() => res(sessionStorage.getItem('welcome.bottom')), 400)) })
    check(!!bottom && new URL(page.url()).pathname === '/welcome', `${r.name}/${vp.n}: bottom recorded once, page stays`)
    if (i === 0 && vp.n === 'desktop') {
      await page.evaluate(() => { document.querySelector('.wl-root').scrollTop = 0 })
      await page.waitForTimeout(30000)
      check(new URL(page.url()).pathname === '/welcome', 'admin: still on /welcome after 30 s idle')
      await page.reload(); await page.waitForSelector('#wl-hero')
      check(new URL(page.url()).pathname === '/welcome', 'admin: refresh keeps /welcome, no loop')
      await page.evaluate(() => document.getElementById('wl-auto').scrollIntoView())
      await page.click('.wl-head .wl-btn')                          // Skip from a middle section
    } else {
      await page.click('#wl-end .wl-btn-primary')                          // Enter Dashboard at the end
    }
    await page.waitForURL(u => u.pathname === '/', { timeout: 5000 }).catch(() => {})
    check(new URL(page.url()).pathname === '/', `${r.name}/${vp.n}: Skip/Enter goes to "/" (${page.url()})`)
    const real = errors.filter(e => !/WebGL|GPU stall|favicon|ResizeObserver|Cross-Origin-Opener-Policy/i.test(e))
    check(real.length === 0, `${r.name}/${vp.n}: no console errors ${real.slice(0, 3).join(' | ')}`)
    await ctx.close()
  }
}

// reduced motion: everything visible without animation
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
  const page = await ctx.newPage()
  await login(page, ROLES[0])
  await page.waitForSelector('#wl-end')
  await page.evaluate(() => document.getElementById('wl-end').scrollIntoView())
  const op = await page.$eval('#wl-end .wl-r', el => getComputedStyle(el).opacity)
  check(op === '1', `reduced motion: content visible (opacity ${op})`)
  await page.screenshot({ path: `${OUT}/reduced-end.png` })
  await ctx.close()
}
await browser.close()
console.log(failed ? `${failed} FAILED` : 'ALL PASSED')
process.exit(failed ? 1 : 0)
