/**
 * Click-through of the whole portal per role (2026-10-27, owner: "press each and every button as admin, staff and
 * student; navigation must be super fast with no freezing"). Real Chrome (GPU), against the isolated copy.
 *   For every sidebar page: click -> time until the content is drawn (no spinner/skeleton, text in <main>).
 *   On every page: every SAFE control - tabs, toggles, expand/collapse, details / view / full view / open buttons,
 *   selects - is clicked; each click is timed the same way; any dialog is closed with Escape.
 *   Skipped by design: anything that changes data or touches hardware (delete, cancel, approve, reject, send, save,
 *   submit, confirm, start, stop, home, unlock, door, emergency, logout, print, download).
 *   Flags: freezes (frames > 200 ms), long tasks, console errors, error screens, blank pages.
 *   E2E_PW=<pw> node e2e/click_everything.mjs <base> <out.json>      (accounts perf-admin / perf-staff / perf-student)
 */
import { chromium, devices } from 'playwright-core'
import fs from 'node:fs'

const BASE = process.argv[2] || 'http://127.0.0.1:5176'
const OUT = process.argv[3] || 'click_everything.json'
const ROLES = [['admin', 'perf-admin@giu-uni.de', process.env.E2E_ADMIN_PW], ['staff', 'perf-staff@giu-uni.de', process.env.E2E_PW],
               ['student', 'perf-student@giu-uni.de', process.env.E2E_PW]]
const UNSAFE = /delete|remove|cancel|reject|revoke|approve|confirm|send|save|submit|start|stop|home|unlock|lock|door|relay|emergency|sign out|log ?out|print|download|reset|disable|deactivate|enable|activate|run|move|jog|clear|resolve|acknowledge|assign|close issue|claim|release|book |create|add |new |upload|import|export|restore|backup|test alarm|mute|record|mic|camera|share|scan|enrol|play|replay|broadcast|apply|publish|generate/i
const SAFE = /tab|details?|more|view|full|open|show|expand|collapse|hide|less|week|month|day|hours?|all|filter|next|prev|chart|table|list|grid|map|history|overview|summary|analytics|trend|live|robots?|pcs?|environment|consumables|reusable|events?|boxes|people|devices?|labs?/i

// DEVICE=<playwright device name> runs the same click-through as that phone / tablet (simulated, touch + its screen)
const DEV = process.env.DEVICE ? devices[process.env.DEVICE] : null
const browser = await chromium.launch({ channel: 'chrome', headless: !!process.env.HEADLESS, args: ['--window-size=1600,950'] })
const report = { base: BASE, at: new Date().toISOString(), roles: {} }
const pct = (a, p) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : 0 }

async function settle(page, t0, limit = 8000) {
  // drawn = main has text, no spinner/skeleton/"Loading" left, and two quiet animation frames
  await page.waitForFunction(() => {
    const m = document.querySelector('main') || document.body
    const busy = m.querySelector('.animate-pulse, .animate-spin, [aria-busy="true"]')
    return (m.innerText || '').trim().length > 40 && !busy
  }, null, { timeout: limit }).catch(() => {})
  await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))
  return Date.now() - t0
}

for (const [role, email, pw] of ROLES) {
  if (!pw) { console.log(`skip ${role}: no password`); continue }
  const ctx = await browser.newContext(DEV ? { ...DEV } : { viewport: { width: +(process.env.VW || 1600), height: +(process.env.VH || 900) } })
  await ctx.addInitScript(() => {
    window.__lt = []; window.__fz = 0
    try { new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(Math.round(e.duration)))).observe({ type: 'longtask', buffered: true }) } catch {}
    let last = performance.now()
    const tick = t => { if (t - last > 200) window.__fz++; last = t; requestAnimationFrame(tick) }
    requestAnimationFrame(tick)
  })
  const page = await ctx.newPage()
  const errors = []
  page.on('console', m => { if (m.type() === 'error' && !/favicon|ERR_ABORTED|401|net::/.test(m.text())) errors.push(m.text().slice(0, 160)) })
  page.on('pageerror', e => errors.push('pageerror: ' + String(e).slice(0, 160)))
  await page.goto(`${BASE}/login`)
  await page.fill('#email', email); await page.fill('#password', pw); await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 30000 })
  if (new URL(page.url()).pathname.startsWith('/welcome')) {
    const skip = page.locator('button:has-text("Skip")').first()
    const t0 = Date.now(); await skip.click(); report.roles[role] = { welcome_skip_ms: await settle(page, t0) }
  } else report.roles[role] = {}
  const R = report.roles[role]
  const links = [...new Set(await page.$$eval('aside nav a[href]', as => as.map(a => a.getAttribute('href')).filter(h => h && h.startsWith('/'))))]
  R.pages = []
  for (const href of links) {
    const errs0 = errors.length
    await page.evaluate(() => { window.__lt = []; window.__fz = 0 })
    const t0 = Date.now()
    await page.click(`aside nav a[href="${href}"]`).catch(() => page.goto(BASE + href))
    const open_ms = await settle(page, t0)
    const blank = await page.evaluate(() => ((document.querySelector('main') || document.body).innerText || '').trim().length < 20)
    const crashed = await page.locator('text=/Something went wrong|This page crashed|Unexpected Application Error/i').count()
    // every safe control on the page
    const clicks = []
    const handles = await page.$$('main button:visible, main [role=tab]:visible, main select:visible, main summary:visible')
    for (const h of handles.slice(0, 40)) {
      const label = ((await h.innerText().catch(() => '')) || (await h.getAttribute('aria-label')) || (await h.getAttribute('title')) || '').trim().replace(/\s+/g, ' ').slice(0, 40)
      const tag = await h.evaluate(e => e.tagName.toLowerCase()).catch(() => '')
      const isTab = (await h.getAttribute('role')) === 'tab' || (await h.getAttribute('aria-pressed')) !== null || (await h.getAttribute('aria-expanded')) !== null
      if (!label || UNSAFE.test(label) || (!isTab && tag !== 'select' && tag !== 'summary' && !SAFE.test(label))) continue
      if (!(await h.isVisible().catch(() => false)) || await h.isDisabled().catch(() => true)) continue
      const c0 = Date.now()
      try {
        if (tag === 'select') {
          const vals = await h.$$eval('option', os => os.map(o => o.value))
          if (vals.length > 1) await h.selectOption(vals[1])
        } else await h.click({ timeout: 2000 })
      } catch { continue }
      const ms = await settle(page, c0, 5000)
      clicks.push({ label, ms })
      if (await page.locator('[role=dialog]:visible').count()) { await page.keyboard.press('Escape'); await page.waitForTimeout(150) }
      if (!new URL(page.url()).pathname.startsWith(href.split('?')[0])) { await page.goBack().catch(() => {}); await settle(page, Date.now(), 4000) }
    }
    const { lt, fz } = await page.evaluate(() => ({ lt: window.__lt, fz: window.__fz }))
    const row = { href, open_ms, controls: clicks.length, click_p50: pct(clicks.map(c => c.ms), .5), click_max: Math.max(0, ...clicks.map(c => c.ms)),
                  slowest: clicks.sort((a, b) => b.ms - a.ms).slice(0, 2), long_tasks: lt.length, worst_task: Math.max(0, ...lt),
                  freezes_200ms: fz, blank, crashed: !!crashed, errors: errors.slice(errs0) }
    R.pages.push(row)
    console.log(`${role.padEnd(7)} ${href.padEnd(26)} open ${String(open_ms).padStart(5)} ms  controls ${String(row.controls).padStart(2)}  click p50 ${String(row.click_p50).padStart(4)} max ${String(row.click_max).padStart(5)}  long tasks ${row.long_tasks} (worst ${row.worst_task})  freezes ${fz}${blank ? '  BLANK' : ''}${crashed ? '  CRASH' : ''}${row.errors.length ? '  ERR ' + row.errors[0] : ''}`)
  }
  await ctx.close()
}
fs.writeFileSync(OUT, JSON.stringify(report, null, 1))
await browser.close()
