/**
 * Responsive audit (2026-10-28): every sidebar route per role at phone / tablet / laptop / desktop sizes (Chromium
 * device emulation with touch + mobile UA for phones/tablets - SIMULATED, not a real device). Per page:
 *   overflow      the page scrolls sideways (document wider than the viewport)
 *   wide          visible elements sticking out past the right edge (selector + px)
 *   tiny          tappable controls smaller than 32 px on touch profiles
 *   open_ms       click -> content drawn; long tasks; layout shift (CLS); console errors
 *   E2E_ADMIN_PW / E2E_PW   node e2e/responsive_audit.mjs <base> <out.json> [profiles=all]
 */
import { chromium, devices } from 'playwright-core'
import fs from 'node:fs'

const BASE = process.argv[2] || 'http://127.0.0.1:5176'
const OUT = process.argv[3] || 'responsive.json'
const PROFILES = {
  phone_small: { ...devices['iPhone SE'] },                         // 375 x 667
  phone_large: { ...devices['iPhone 15 Pro Max'] ?? devices['iPhone 14 Pro Max'] },
  android: { ...devices['Pixel 7'] },
  phone_landscape: { ...devices['iPhone 13 landscape'] },
  tablet_portrait: { ...devices['iPad (gen 7)'] },
  tablet_landscape: { ...devices['iPad (gen 7) landscape'] },
  laptop: { viewport: { width: 1366, height: 768 } },
  desktop: { viewport: { width: 1920, height: 1080 } },
}
const want = (process.argv[4] || Object.keys(PROFILES).join(',')).split(',')
const ROLES = [['admin', 'perf-admin@giu-uni.de', process.env.E2E_ADMIN_PW], ['staff', 'perf-staff@giu-uni.de', process.env.E2E_PW],
               ['student', 'perf-student@giu-uni.de', process.env.E2E_PW]]
const roleFilter = (process.env.ROLES || 'admin,staff,student').split(',')
const API = process.env.API || 'http://127.0.0.1:8100/api'
const TOKEN_KEY = 'slp.token'
const TOKENS = {}
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const report = { base: BASE, at: new Date().toISOString(), simulated: true, profiles: {} }

async function settle(page, t0) {
  await page.waitForFunction(() => {
    const m = document.querySelector('main') || document.body
    return (m.innerText || '').trim().length > 30 && !m.querySelector('.animate-pulse, .animate-spin, [aria-busy="true"]')
  }, null, { timeout: 8000 }).catch(() => {})
  return Date.now() - t0
}

for (const pname of want) {
  const prof = PROFILES[pname]
  report.profiles[pname] = {}
  for (const [role, email, pw] of ROLES) {
    if (!pw || !roleFilter.includes(role)) continue
    const ctx = await browser.newContext({ ...prof })
    await ctx.addInitScript(() => {
      window.__lt = []; window.__cls = 0
      try { new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(Math.round(e.duration)))).observe({ type: 'longtask', buffered: true }) } catch {}
      try { new PerformanceObserver(l => l.getEntries().forEach(e => { if (!e.hadRecentInput) window.__cls += e.value })).observe({ type: 'layout-shift', buffered: true }) } catch {}
      try { sessionStorage.setItem('welcome.seen', '1') } catch {}
    })
    const page = await ctx.newPage()
    const errs = []
    page.on('console', m => { if (m.type() === 'error' && !/favicon|ERR_ABORTED|net::|401|503/.test(m.text())) errs.push(m.text().slice(0, 140)) })
    page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 140)))
    // one API sign-in per role (repeated UI logins hit the login rate limit); the token goes where the portal keeps it
    if (!TOKENS[role]) {
      const r = await fetch(API + '/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password: pw }) })
      TOKENS[role] = (await r.json()).access_token
    }
    await page.goto(`${BASE}/login`)
    await page.evaluate(([k, t]) => { localStorage.setItem(k, t) }, [TOKEN_KEY, TOKENS[role]])
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await page.waitForSelector('aside nav a[href]', { state: 'attached', timeout: 30000 })
    // the sidebar's links (on phones the menu is closed: read them from the DOM anyway)
    const links = [...new Set(await page.$$eval('aside nav a[href]', as => as.map(a => a.getAttribute('href')).filter(h => h && h.startsWith('/'))))]
    const rows = []
    for (const href of [...links, '/scan', '/scan/markers'].filter((v, i, a) => a.indexOf(v) === i)) {
      const e0 = errs.length
      await page.evaluate(() => { window.__lt = []; window.__cls = 0 })
      const t0 = Date.now()
      await page.goto(BASE + href, { waitUntil: 'domcontentloaded' })
      const open_ms = await settle(page, t0)
      await page.waitForTimeout(400)
      const m = await page.evaluate(touch => {
        const W = document.documentElement.clientWidth
        const overflow = document.documentElement.scrollWidth - W
        const wide = [], tiny = []
        const desc = el => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : '')).slice(0, 90)
        for (const el of document.querySelectorAll('main *, header *, aside *')) {
          const r = el.getBoundingClientRect()
          if (!r.width || !r.height) continue
          const cs = getComputedStyle(el)
          if (cs.visibility === 'hidden' || cs.display === 'none' || cs.position === 'fixed') continue
          // inside a horizontal scroller is fine (tables, chip rows)
          let p = el.parentElement, scroller = false
          while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') { scroller = true; break } p = p.parentElement }
          if (!scroller && r.right > W + 2 && wide.length < 8) wide.push(`${desc(el)} +${Math.round(r.right - W)}px`)
          if (touch && r.right > 0 && r.left < W && el.matches('button, a[href], [role=button], input:not([type=hidden]), select') && r.top < innerHeight * 3
              && (r.width < 32 || r.height < 32) && tiny.length < 400) tiny.push(desc(el))
        }
        // text squeezed to a letter or two per line ("N e t w o r k" - 2026-10-28 regression)
        const stacked = []
        for (const el of document.querySelectorAll('main *')) {
          const txt = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('')
          if (txt.length < 5 || el.closest('svg')) continue            // chart axis titles are rotated on purpose
          const r = el.getBoundingClientRect(), fs = parseFloat(getComputedStyle(el).fontSize) || 14
          if (r.width > 0 && r.width < fs * 2.2 && r.height > fs * 4 && stacked.length < 5) stacked.push(desc(el) + ' "' + txt.slice(0, 20) + '"')
        }
        return { overflow, wide, stacked, tiny: tiny.length, tinyEx: [...new Set(tiny)].slice(0, 4) }
      }, !!prof.hasTouch)
      const perf = await page.evaluate(() => ({ lt: window.__lt, cls: Math.round(window.__cls * 1000) / 1000 }))
      const row = { href, open_ms, ...m, long_tasks: perf.lt.length, worst_task: Math.max(0, ...perf.lt), cls: perf.cls, errors: errs.slice(e0) }
      rows.push(row)
      const flag = (m.overflow > 2 ? ` OVERFLOW+${m.overflow}` : '') + (m.wide.length ? ` WIDE(${m.wide.length})` : '') + (m.stacked.length ? ` STACKED ${m.stacked[0]}` : '') + (row.errors.length ? ' ERR' : '')
      console.log(`${pname.padEnd(16)} ${role.padEnd(7)} ${href.padEnd(22)} ${String(open_ms).padStart(5)} ms  tiny ${String(m.tiny).padStart(3)}  cls ${perf.cls}  lt ${perf.lt.length}${flag}`)
    }
    report.profiles[pname][role] = rows
    await ctx.close()
  }
}
fs.writeFileSync(OUT, JSON.stringify(report, null, 1))
await browser.close()
