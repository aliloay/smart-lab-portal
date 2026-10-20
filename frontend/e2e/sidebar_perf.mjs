/**
 * Every sidebar entry, measured in a real browser (read-only; 2026-10-20 sidebar speed audit).
 * For each run a FRESH browser profile (empty cache) signs in, then for every sidebar item:
 *   first   - first click in this session (route code + data fetched for the first time)
 *   repeat  - a second click later in the same session (in-app navigation back to it)
 *   direct  - the address typed / refreshed (full document load, scripts from cache)
 * Per visit: ms to the route change, ms until usable (main has content, no spinner / skeleton /
 * role=status left, and no /api request started by the visit still open), long main-thread tasks,
 * API requests, duplicate GETs, failed requests, console errors.
 *   E2E_PASSWORD=... node e2e/sidebar_perf.mjs [base] [runs] [email]     (password never printed)
 * Window entries (Live monitor opens its own window) are measured as a direct load; "Ask the lab"
 * opens the chat panel (measured until its input is usable).
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || 'https://localhost'
const RUNS = Number(process.argv[3] || 3)
const EMAIL = process.argv[4] || process.env.E2E_EMAIL || 'admin@giu-uni.de'
const STREAMS = /frame\.jpg|\.mjpg|\/ws\b|\/events\/stream|\/sse/   // long-lived by design: never "open work"

async function session() {
  const b = await chromium.launch({ channel: 'chrome', args: ['--ignore-certificate-errors'] })
  const ctx = await b.newContext({ viewport: { width: 1600, height: 1000 }, ignoreHTTPSErrors: true })
  await ctx.addInitScript(() => {
    window.__lt = []
    new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]) })
      .observe({ type: 'longtask', buffered: true })
  })
  const p = await ctx.newPage()
  const errors = []
  p.on('console', m => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)) })
  p.on('pageerror', e => errors.push(String(e).slice(0, 160)))
  p.on('crash', () => { errors.push('PAGE CRASHED'); console.log('    PAGE CRASHED at ' + p.url()) })
  await p.goto(BASE + '/login'); await p.fill('input[type=email]', EMAIL)
  await p.fill('input[type=password]', process.env.E2E_PASSWORD); await p.click('button[type=submit]')
  await p.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 30000 })
  await p.goto(BASE + '/labs'); await p.waitForSelector('aside nav a[href^="/"]', { timeout: 30000 })
  await p.waitForTimeout(1500)
  if (await p.$('[role=alertdialog]')) await p.getByRole('button', { name: 'CLEAR ALL' }).click().catch(() => {})
  return { b, p, errors }
}

/** Wait until the visit is usable; returns timings and counters for the window since `go`. */
async function visit(p, errors, go, path, ready = 'main') {
  const w0 = Date.now()
  const reqs = [], open = new Map()           // request -> ms after the click it started
  const onReq = r => { const u = r.url(); if (u.includes('/api/') && !STREAMS.test(u)) { reqs.push(r); open.set(r, Date.now() - w0) } }
  const onEnd = r => open.delete(r)
  p.on('request', onReq); p.on('requestfinished', onEnd); p.on('requestfailed', onEnd)
  const e0 = errors.length
  const t0lt = await p.evaluate(() => performance.now()).catch(() => 0)
  const fresh = await go()
  let route = -1, usable = -1, okAt = 0
  for (;;) {
    await p.waitForTimeout(20)
    const now = Date.now() - w0
    const s = await p.evaluate(([path, ready]) => {
      const atRoute = location.pathname === path.split('?')[0]
      if (ready === 'chat') {
        const box = document.querySelector('[role=dialog][aria-label="AI assistant"][aria-hidden="false"] input[aria-label^="Question"]')
        return { atRoute: true, ok: !!box && !box.disabled && getComputedStyle(box.closest('[role=dialog]')).opacity === '1' }
      }
      const main = document.querySelector('main') || document.body
      const ok = main.innerText.trim().length >= 40 &&
        !main.querySelector('[role=status], .animate-spin, .skeleton')
      return { atRoute, ok }
    }, [path, ready]).catch(() => ({ atRoute: false, ok: false }))
    if (route < 0 && s.atRoute) route = now
    // Usable = content shown (no spinner / skeleton) AND every API request that started before the
    // content appeared has finished. Polls that start later (live pages refresh every few s) do not count.
    if (!s.ok) { okAt = 0 } else if (!okAt) okAt = now
    // a request with no finish event 5 s after the content appeared is reported as stuck, not waited for
    const waiting = okAt ? [...open.values()].some(st => st <= okAt) && now - okAt < 5000 : true
    if (okAt && !waiting) { usable = Math.max(okAt, now - 20); break }
    if (now > 30000) break
  }
  if (usable < 0) console.log(`    not usable in 30 s: ${path || 'chat'}; open: ${[...open.keys()].map(r => r.url().replace(BASE, '')).slice(0, 4).join(' ')}`)
  const lts = await p.evaluate(([t, fresh]) => window.__lt.filter(([st]) => fresh || st >= t).map(([, d]) => Math.round(d)), [t0lt, fresh]).catch(() => [])
  p.off('request', onReq); p.off('requestfinished', onEnd); p.off('requestfailed', onEnd)
  const gets = reqs.filter(r => r.method() === 'GET').map(r => r.url().replace(BASE, ''))
  const dup = gets.length - new Set(gets).size
  let failed = 0
  for (const r of reqs) { const res = await r.response().catch(() => null); if (!res || res.status() >= 400) failed++ }
  const stuck = [...open.entries()].filter(([, st]) => okAt && st <= okAt).map(([r]) => r.url().replace(BASE, ''))
  if (stuck.length) console.log(`    ${path || 'chat'}: no finish event for ${stuck.slice(0, 3).join(' ')}`)
  return { route, usable, stuck: stuck.length, lt: lts.length, ltMs: lts.reduce((a, d) => a + d, 0), ltMax: Math.max(0, ...lts),
           api: reqs.length, dup, failed, errors: errors.slice(e0) }
}

const rows = []
let items = []
for (let run = 0; run < RUNS; run++) {
  const { b, p, errors } = await session()
  try {
    if (!items.length) {
      items = await p.$$eval('aside nav a[href^="/"]', as => as.map(a => ({
        label: a.innerText.trim().split('\n')[0], href: a.getAttribute('href'),
        window: !!a.querySelector('svg.lucide-external-link') || a.getAttribute('href') === '/monitor' })))
      // the same page listed twice (e.g. Notifications) is measured once
      items = items.filter((x, i) => items.findIndex(y => y.href === x.href) === i)
      const chat = await p.getByRole('button', { name: /Ask (the lab|Smart Lab)/ }).count()
      if (chat) items.push({ label: 'Ask the lab', href: null, chat: true })
      console.log(`${items.length} sidebar entries: ${items.map(i => i.label).join(', ')}`)
    }
    for (const pass of ['first', 'repeat']) {
      for (const it of items) {
        if (it.window) continue
        if (it.chat) {
          const r = await visit(p, errors, async () => { await p.getByRole('button', { name: /Ask (the lab|Smart Lab)/ }).click(); return false }, '', 'chat')
          rows.push({ run, label: it.label, kind: pass, ...r })
          await p.keyboard.press('Escape').catch(() => {})
          await p.goto(BASE + '/labs').catch(() => {}); await p.waitForSelector('aside nav a[href^="/"]').catch(() => {})
          continue
        }
        const r = await visit(p, errors, async () => { await p.click(`aside nav a[href="${it.href}"]`); return false }, it.href)
        rows.push({ run, label: it.label, kind: pass, ...r })
        if (process.env.PERF_VERBOSE) console.log(`  run ${run} ${pass.padEnd(6)} ${it.href.padEnd(22)} route ${r.route} usable ${r.usable} long ${r.ltMs} api ${r.api}`)
      }
    }
    for (const it of items) {
      if (it.chat) continue
      const r = await visit(p, errors, async () => { await p.goto(BASE + it.href); return true }, it.href)
      rows.push({ run, label: it.label, kind: 'direct', ...r })
      if (it.window) await p.goto(BASE + '/labs').catch(() => {})
    }
  } finally { await b.close() }
}

const q = (a, f) => { const s = a.filter(x => x >= 0).sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(f * s.length))] : -1 }
const pad = (v, n = 6) => String(v).padStart(n)
console.log(`\n${RUNS} runs, ${BASE}, ${EMAIL.split('@')[0]}; ms = median (p95 over runs where ${RUNS} >= 5). usable -1 = not usable in 30 s`)
console.log('entry'.padEnd(20) + ' | first: route usable  long(ms) api dup fail | repeat: usable long | direct: usable long api | errors')
const summary = []
for (const it of items) {
  const of = k => rows.filter(r => r.label === it.label && r.kind === k)
  const f = of('first'), r = of('repeat'), d = of('direct')
  const m = (a, k) => a.length ? q(a.map(x => x[k]), 0.5) : '-'
  const p95 = (a, k) => a.length >= 5 ? '/' + q(a.map(x => x[k]), 0.95) : ''
  const errs = [...new Set([...f, ...r, ...d].flatMap(x => x.errors))]
  summary.push({ label: it.label, href: it.href, first: m(f, 'usable'), repeat: m(r, 'usable'), direct: m(d, 'usable'),
                 firstLong: m(f, 'ltMs'), api: m(f, 'api'), dup: m(f, 'dup'), failed: m(f, 'failed'), errors: errs.length })
  console.log(it.label.slice(0, 20).padEnd(20) + ` | ${pad(m(f, 'route'))} ${pad(m(f, 'usable'))}${p95(f, 'usable')} ${pad(m(f, 'ltMs'))} ${pad(m(f, 'api'), 3)} ${pad(m(f, 'dup'), 3)} ${pad(m(f, 'failed'), 3)}` +
              ` | ${pad(m(r, 'usable'))}${p95(r, 'usable')} ${pad(m(r, 'ltMs'))} | ${pad(m(d, 'usable'))}${p95(d, 'usable')} ${pad(m(d, 'ltMs'))} ${pad(m(d, 'api'), 3)} | ${errs.length}`)
}
const allErr = [...new Set(rows.flatMap(r => r.errors))]
if (allErr.length) { console.log('\nconsole / page errors:'); allErr.slice(0, 15).forEach(e => console.log('  ' + e)) }
if (process.env.PERF_JSON) { const fs = await import('node:fs'); fs.writeFileSync(process.env.PERF_JSON, JSON.stringify({ base: BASE, runs: RUNS, at: new Date().toISOString(), summary, rows }, null, 1)) }
