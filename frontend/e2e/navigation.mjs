// Navigation regression test: no route may ever render blank or need a refresh.
//
//   node e2e/navigation.mjs [baseUrl]        (default http://127.0.0.1:5173)
//
// Needs the API running with the seed users, and Google Chrome installed
// (playwright-core drives the system Chrome; no browser download).
// Exits non-zero on any blank page, invisible page, error screen, or
// console error.
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://127.0.0.1:5173'

const ROLES = [
  { name: 'student', email: 'ali@giu-uni.de', password: 'Student#2026',
    // Dashboard -> Laboratories -> Laboratory details -> New booking ->
    // My bookings -> Booking details -> QR -> Dashboard
    journey: async page => {
      await clickNav(page, '/labs')
      await clickFirst(page, 'main a[href^="/labs/"]', 'laboratory card')
      await clickNav(page, '/book')
      await clickNav(page, '/bookings')
      if (await page.$('main a[href^="/bookings/"]:not([href$="/qr"])')) {
        await clickFirst(page, 'main a[href^="/bookings/"]:not([href$="/qr"])', 'booking details')
        if (await page.$('main a[href$="/qr"]')) await clickFirst(page, 'main a[href$="/qr"]', 'QR')
      }
      await clickNav(page, '/')
    } },
  { name: 'staff', email: 'ramy@giu-uni.de', password: 'Staff#2026',
    journey: async page => {
      for (const p of ['/labs', '/admin/bookings', '/admin/access', '/admin/devices',
                       '/admin/equipment', '/admin/alerts', '/issues', '/']) await clickNav(page, p)
    } },
  { name: 'admin', email: 'admin@giu-uni.de', password: 'Admin#2026',
    journey: async page => {
      for (const p of ['/labs', '/admin/bookings', '/admin/access', '/admin/reports',
                       '/admin/users', '/admin/devices', '/admin/equipment', '/admin/alerts',
                       '/admin/settings', '/']) await clickNav(page, p)
    } },
]

const problems = []
let checks = 0
let current = ''

async function state(page) {
  return page.evaluate(() => {
    const main = document.querySelector('main')
    if (!main) return { text: 0, opacity: 1, err: false, heading: null }
    // The page wrapper (keyed per route) and its direct content. Decorative
    // layers inside cards are translucent by design and are not measured.
    let op = 1
    const wrapper = main.querySelector('.animate-page-in')
    for (const el of [main, main.firstElementChild, wrapper, wrapper?.firstElementChild]) {
      if (el) op = Math.min(op, parseFloat(getComputedStyle(el).opacity))
    }
    const h = main.querySelector('h1, h2')
    return { text: main.innerText.trim().length, opacity: op,
             err: main.innerText.includes('could not be displayed'),
             heading: h ? h.innerText.trim().slice(0, 50) : null }
  })
}

async function check(page, label) {
  await page.waitForTimeout(250)
  let s = await state(page)
  // Give data a moment, but never forever: a page that is still empty or
  // invisible after 2.5 s is the bug this test exists for.
  for (let i = 0; i < 10 && (s.text < 20 || s.opacity < 0.95) && !s.err; i++) {
    await page.waitForTimeout(250)
    s = await state(page)
  }
  checks++
  const bad = s.err ? 'ERROR SCREEN' : s.text < 20 ? 'BLANK'
    : s.opacity < 0.95 ? `INVISIBLE (opacity ${s.opacity.toFixed(2)})` : null
  const line = `${current.padEnd(8)} ${label.padEnd(34)} ${page.url().replace(BASE, '').padEnd(28)} ${bad ?? 'ok'}  "${s.heading ?? ''}"`
  console.log(line)
  if (bad) problems.push(line)
}

async function clickNav(page, href) {
  const link = await page.$(`aside nav a[href="${href}"]`)
  if (!link) { problems.push(`${current}: no sidebar link ${href}`); return }
  await link.click()
  await check(page, `nav ${href}`)
}

async function clickFirst(page, selector, label) {
  await page.waitForSelector(selector, { timeout: 8000 }).catch(() => {})
  const el = await page.$(selector)
  if (!el) { problems.push(`${current}: nothing to click for ${label}`); return }
  await el.click()
  await check(page, `click ${label}`)
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  for (const role of ROLES) {
    current = role.name
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 860 } })
    const page = await ctx.newPage()
    // E2E_CPU_THROTTLE=6 emulates a slow laptop, where animation timing bugs show.
    if (process.env.E2E_CPU_THROTTLE) {
      const cdp = await ctx.newCDPSession(page)
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: Number(process.env.E2E_CPU_THROTTLE) })
    }
    const consoleErrors = []
    page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()) })
    page.on('pageerror', e => consoleErrors.push(String(e)))

    await page.goto(`${BASE}/login`)
    await page.fill('#email', role.email)
    await page.fill('#password', role.password)
    await page.click('button[type=submit]')
    await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 })
    await check(page, 'after sign-in')

    await role.journey(page)

    const hrefs = await page.$$eval('aside nav a', as => as.map(a => a.getAttribute('href')))
    for (const h of hrefs) {           // rapid clicking, no waiting
      await page.click(`aside nav a[href="${h}"]`)
      await page.waitForTimeout(40)
    }
    await check(page, 'after rapid clicking')
    for (let i = 0; i < 3; i++) { await page.goBack(); await check(page, `back ${i + 1}`) }
    for (let i = 0; i < 2; i++) { await page.goForward(); await check(page, `forward ${i + 1}`) }
    for (const h of hrefs) { await page.goto(BASE + h); await check(page, `direct ${h}`) }
    await page.reload(); await check(page, 'reload')

    const real = consoleErrors.filter(e => !/WebSocket|ERR_CONNECTION_REFUSED/.test(e))
    if (real.length) problems.push(`${role.name}: console errors: ${[...new Set(real)].join(' | ').slice(0, 400)}`)
    await ctx.close()
  }

  // Expired session: must land on sign-in, never a blank screen.
  current = 'expired'
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  await page.goto(`${BASE}/login`)
  await page.evaluate(() => sessionStorage.setItem('slp.token', 'expired.bogus.token'))
  await page.goto(`${BASE}/admin/devices`)
  await page.waitForSelector('#email', { timeout: 8000 }).catch(() => {})
  checks++
  if (!(await page.$('#email'))) problems.push('expired session did not reach the sign-in form')
  else console.log('expired  session -> sign-in form                                        ok')
  await ctx.close()
} finally {
  await browser.close()
}

console.log(`\n${checks} checks, ${problems.length} problems`)
problems.forEach(p => console.log('  ! ' + p))
process.exit(problems.length ? 1 : 0)
