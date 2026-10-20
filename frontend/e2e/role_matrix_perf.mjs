/**
 * Role x route x cold/warm navigation matrix + search latency (2026-10-20, owner: "full speed for
 * every role"). Read-only: opens pages and types into search, never presses an action.
 *   node e2e/role_matrix_perf.mjs <dir with tok_admin.txt, tok_staff.txt, tok_student.txt> [trials] [base]
 * Tokens (short-lived, minted for the run) are read from files and never printed.
 *
 * Per visit:  shell   = ms from the click (warm) / navigation start (cold) until the URL is the target and
 *                       <main> shows the new page (route rendered);
 *             content = until <main> has real content and no skeleton / spinner / role=status left.
 * warm = in-app click with the pointer arriving 250 ms before it (as a person does); cold = a new browser
 * context opening the URL directly (document, code and data from scratch, HTTP cache empty).
 * Also: API requests started, refused (401/403), failed / 5xx, console errors - per visit.
 * Search: the palette, once its index is loaded: keystroke -> first result row for each query.
 */
import { chromium } from 'playwright-core'
import fs from 'node:fs'
import path from 'node:path'

const [, , tokDir, trialsArg = '3', BASE = 'https://localhost'] = process.argv
const TRIALS = Number(trialsArg)
const ROLES = ['admin', 'staff', 'student']
const QUERIES = ['lab1', 'robot', 'fanuc', 'fanuk', 'door', 'temperature too high', 'booking access denied', 'oscilloscope', 'camera']
const pct = (a, q) => { const s = [...a].filter(x => x != null).sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(q * (s.length - 1) + 0.5))] : null }

async function newCtx(b, tok) {
  const ctx = await b.newContext({ viewport: { width: 1600, height: 1000 }, ignoreHTTPSErrors: true })
  await ctx.addInitScript(t => { try { localStorage.setItem('slp.token', t) } catch {} }, tok)
  return ctx
}
function watch(p) {
  const s = { api: 0, refused: 0, failed: 0, errors: 0, refusedUrls: [] }
  p.on('request', r => { if (r.url().includes('/api/') && !r.url().includes('frame.jpg')) s.api++ })
  p.on('response', r => {
    if (!r.url().includes('/api/')) return
    if (r.status() === 401 || r.status() === 403) { s.refused++; s.refusedUrls.push(r.status() + ' ' + r.url().replace(BASE, '')) }
    if (r.status() >= 500) s.failed++
  })
  p.on('requestfailed', r => { if (r.url().includes('/api/') && !/frame\.jpg|\/ws/.test(r.url())) s.failed++ })
  p.on('console', m => { if (m.type() === 'error' && !/frame\.jpg|503|camera/i.test(m.text())) s.errors++ })
  p.on('pageerror', () => s.errors++)
  return s
}
const SHELL = (target) => {
  const u = new URL(location.href); const t = new URL(target, location.origin)
  return u.pathname === t.pathname && !!document.querySelector('main') && (document.querySelector('main')?.children.length ?? 0) > 0
}
const CONTENT = () => {
  const m = document.querySelector('main'); if (!m || m.innerText.trim().length < 30) return false
  return !m.querySelector('[role=status], .animate-spin, .skeleton, [class*="animate-pulse"]')
}
async function timed(p, t0, href) {
  const shell = await p.waitForFunction(SHELL, href, { polling: 8, timeout: 15000 }).then(() => Date.now() - t0).catch(() => null)
  const content = await p.waitForFunction(CONTENT, null, { polling: 8, timeout: 15000 }).then(() => Date.now() - t0).catch(() => null)
  return { shell, content }
}

const b = await chromium.launch({ channel: 'chrome', args: ['--ignore-certificate-errors'] })
const out = { at: new Date().toISOString(), base: BASE, trials: TRIALS, roles: {} }
for (const role of ROLES) {
  const tok = fs.readFileSync(path.join(tokDir, `tok_${role}.txt`), 'utf8').trim()
  // the role's own sidebar
  const c0 = await newCtx(b, tok); const p0 = await c0.newPage()
  await p0.goto(BASE + '/labs'); await p0.waitForSelector('aside nav a[href^="/"]', { timeout: 30000 })
  const routes = (await p0.$$eval('aside nav a[href^="/"]', as => [...new Set(as.map(a => a.getAttribute('href')))])).filter(h => h !== '/monitor')
  await c0.close()
  const rows = {}
  for (const href of routes) rows[href] = { cold: [], warm: [], api: [], refused: 0, failed: 0, errors: 0, refusedUrls: [] }
  for (let t = 0; t < TRIALS; t++) {
    // cold: a fresh context per route, direct URL
    for (const href of routes) {
      const ctx = await newCtx(b, tok); const p = await ctx.newPage(); const s = watch(p)
      const t0 = Date.now(); await p.goto(BASE + href, { waitUntil: 'commit' }).catch(() => {})
      rows[href].cold.push(await timed(p, t0, href))
      await p.waitForTimeout(400)
      rows[href].refused += s.refused; rows[href].failed += s.failed; rows[href].errors += s.errors; rows[href].refusedUrls.push(...s.refusedUrls)
      await ctx.close()
    }
    // warm: one session, in-app clicks
    const ctx = await newCtx(b, tok); const p = await ctx.newPage(); const s = watch(p)
    await p.goto(BASE + '/labs'); await p.waitForSelector('aside nav a[href^="/"]'); await p.waitForTimeout(2500)
    for (const href of routes) {
      const from = href === '/labs' ? '/' : '/labs'
      await p.click(`aside nav a[href="${from}"]`).catch(() => {}); await p.waitForTimeout(700)
      const a0 = s.api, r0 = s.refused, f0 = s.failed, e0 = s.errors
      await p.hover(`aside nav a[href="${href}"]`).catch(() => {}); await p.waitForTimeout(250)
      const t0 = Date.now(); await p.click(`aside nav a[href="${href}"]`).catch(() => {})
      rows[href].warm.push(await timed(p, t0, href))
      await p.waitForTimeout(500)
      rows[href].api.push(s.api - a0); rows[href].refused += s.refused - r0; rows[href].failed += s.failed - f0; rows[href].errors += s.errors - e0
    }
    rows['__refused_urls_warm'] = s.refusedUrls
    // search latency (warm index)
    if (t === 0 && role !== 'student') {
      await p.keyboard.press('Control+k'); await p.waitForSelector('[role=dialog][aria-label=Search] input'); await p.waitForTimeout(1500)
      out.roles[role + ' search'] = []
      for (const q of QUERIES) {
        await p.fill('[role=dialog][aria-label=Search] input', '')
        await p.waitForTimeout(150)
        const r = await p.evaluate(async q => {
          const inp = document.querySelector('[role=dialog][aria-label=Search] input')
          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
          const t0 = performance.now(); setter.call(inp, q); inp.dispatchEvent(new Event('input', { bubbles: true }))
          return await new Promise(res => {
            const tick = () => { const li = document.querySelector('[role=dialog][aria-label=Search] ul li button'); if (li) res({ ms: performance.now() - t0, first: li.innerText.replace(/\s+/g, ' ').trim() }); else if (performance.now() - t0 > 3000) res({ ms: null, first: '' }); else requestAnimationFrame(tick) }
            tick()
          })
        }, q)
        out.roles[role + ' search'].push({ q, ms: r.ms == null ? null : +r.ms.toFixed(1), first: r.first.slice(0, 70) })
      }
      await p.keyboard.press('Escape')
    }
    await ctx.close()
  }
  out.roles[role] = Object.fromEntries(Object.entries(rows).filter(([k]) => !k.startsWith('__')).map(([href, r]) => [href, {
    cold_shell_p50: pct(r.cold.map(x => x.shell), 0.5), cold_shell_p95: pct(r.cold.map(x => x.shell), 0.95),
    cold_content_p50: pct(r.cold.map(x => x.content), 0.5), cold_content_p95: pct(r.cold.map(x => x.content), 0.95),
    warm_shell_p50: pct(r.warm.map(x => x.shell), 0.5), warm_shell_p95: pct(r.warm.map(x => x.shell), 0.95),
    warm_content_p50: pct(r.warm.map(x => x.content), 0.5), warm_content_p95: pct(r.warm.map(x => x.content), 0.95),
    api_per_visit: pct(r.api, 0.5), refused: r.refused, failed: r.failed, console_errors: r.errors,
    refused_urls: [...new Set(r.refusedUrls)].slice(0, 5),
  }]))
  out.roles[role + ' refused (warm session)'] = [...new Set(rows['__refused_urls_warm'] || [])]
  console.log(`${role}: ${routes.length} routes done`)
}
await b.close()
fs.writeFileSync(path.join(tokDir, 'role_matrix.json'), JSON.stringify(out, null, 1))
console.log('wrote', path.join(tokDir, 'role_matrix.json'))
