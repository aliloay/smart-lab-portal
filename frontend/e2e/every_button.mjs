// Every control of every page, for every role, on an ISOLATED COPY (2026-11-25): is it clickable, does it do something, does
// the backend answer? Never clicked, only checked for presence: door, robot, emergency, alarm, relay, PC control, sign out.
// Browser confirm() questions are always answered "no".
//   E2E_PW=... node e2e/every_button.mjs <out.json>
import { chromium } from 'playwright-core'
import { writeFileSync } from 'node:fs'
const BASE = 'http://127.0.0.1:5176', API = 'http://127.0.0.1:8100/api'
const WHO = { ADMIN: 'nav-admin@test.local', LAB_STAFF: 'nav-staff@test.local', STUDENT: 'nav-student@test.local' }
const ST = ['/', '/labs', '/labs/1', '/book', '/bookings', '/share', '/robots', '/issues', '/issues/new', '/notifications', '/profile']
const OP = ['/', '/labs', '/labs/1', '/book', '/robots', '/issues', '/issues/new', '/notifications', '/profile', '/command', '/admin/security', '/admin/operations',
  '/admin/access', '/admin/alerts', '/admin/incidents', '/admin/bookings', '/admin/equipment?tab=environment', '/admin/equipment?tab=noncons',
  '/admin/equipment?tab=share', '/admin/equipment?tab=consumables', '/admin/equipment?tab=reusables', '/admin/equipment?tab=register',
  '/admin/devices', '/admin/health', '/admin/sensors', '/admin/system', '/admin/reliability', '/admin/users', '/admin/experiments', '/demo',
  '/scan', '/scan/markers', '/phone-setup', '/monitor', '/wall', '/exhibit', '/report']
const PAGES = { ADMIN: [...OP, '/admin/reports', '/admin/settings', '/admin/emergency'], LAB_STAFF: OP, STUDENT: ST }
const PHYSICAL = /door|unlock|lock(ed|down)?\b|relay|robot.*(move|jog|home|stop)|\bjog\b|move|emergency|evacuat|alarm|siren|buzzer|sign out|log ?out|shut ?down|restart|reboot|exam|wake|kill|release lock|commission|arm\b|send home|stop all|calibrat|tare|open lid|test sound|speak|announce|fire|hazard/i
const ONLY = process.argv[3]
const browser = await chromium.launch({ channel: 'chrome' })
const rep = { controls: [], api: {}, errors: [] }
const t00 = Date.now()
for (const role of Object.keys(WHO)) {
  if (ONLY && ONLY !== role) continue
  const r = await fetch(API + '/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: WHO[role], password: process.env.E2E_PW }) })
  const tok = (await r.json()).access_token
  if (!tok) throw new Error('no sign-in ' + role)
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', acceptDownloads: true })
  await ctx.addInitScript(t => {
    if (!sessionStorage.getItem('nb')) { localStorage.setItem('slp.token', t); sessionStorage.setItem('nb', '1') }
    window.__mut = 0; window.__open = 0
    new MutationObserver(() => { window.__mut++ }).observe(document, { subtree: true, childList: true, attributes: true, characterData: true })
    window.open = () => { window.__open++; return null }
    window.print = () => { window.__open++ }
  }, tok)
  const p = await ctx.newPage()
  let req = 0, where = ''
  p.on('dialog', d => { req++; d.dismiss().catch(() => {}) })
  p.on('download', () => { req++ })
  p.on('filechooser', () => { req++ })
  p.on('request', q => { if (/\/api\//.test(q.url())) req++ })
  p.on('response', q => {
    const u = new URL(q.url())
    if (!u.pathname.startsWith('/api/')) return
    const k = `${q.request().method()} ${u.pathname.replace(/\/\d+/g, '/{id}')}`
    const e = rep.api[k] ??= {}
    e[q.status()] = (e[q.status()] || 0) + 1
    if (q.status() >= 500 || q.status() === 405) rep.errors.push({ role, page: where, api: k, status: q.status() })
  })
  p.on('pageerror', e => rep.errors.push({ role, page: where, text: 'PAGEERROR ' + e.message.slice(0, 160) }))
  p.on('console', m => { if (m.type() === 'error' && !/WebSocket|Failed to load resource|favicon|getUserMedia|permission/i.test(m.text())) rep.errors.push({ role, page: where, text: m.text().slice(0, 160) }) })
  const load = async u => { await p.goto(BASE + u, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1300) }
  const list = () => p.evaluate(() => [...document.querySelectorAll('button, a[href], [role=tab], select, summary, input[type=checkbox]')]
    .filter(e => e.offsetParent !== null && !e.closest('aside')).map(e => ({ tag: e.tagName.toLowerCase(), href: e.getAttribute('href'),
      label: (e.innerText || e.getAttribute('aria-label') || e.title || e.value || '').trim().replace(/\s+/g, ' ').slice(0, 60), dis: !!e.disabled,
      ctx: (e.closest('[data-danger]') ? 'danger ' : '') })))
  for (const url of PAGES[role]) {
    where = url
    await load(url)
    let items = await list()
    const seen = {}
    let n = 0
    for (let k = 0; k < items.length && n < 70; k++) {
      const c = items[k]
      const key = `${c.tag}|${c.label}|${c.href || ''}`
      seen[key] = (seen[key] || 0) + 1
      if (seen[key] > 2) continue                        // the same control on many rows: two of them
      const rec = { role, page: url, tag: c.tag, label: c.label, href: c.href }
      rep.controls.push(rec)
      if (c.dis) { rec.result = 'disabled'; continue }
      if (PHYSICAL.test(c.label) && c.tag !== 'a' && c.tag !== 'select') { rec.result = 'present (not clicked: physical or sign-out)'; continue }
      if (/^\/admin\/emergency/.test(url) && c.tag !== 'a') { rec.result = 'present (not clicked: emergency page)'; continue }
      n++
      if (c.tag === 'a') {                               // links: opened one by one below
        rec.result = 'link'
        continue
      }
      const now = await list()
      if (!now[k] || `${now[k].tag}|${now[k].label}|${now[k].href || ''}` !== key) { await load(url); items = await list(); if (!items[k] || items[k].label !== c.label) { rec.result = 'moved (live page)'; continue } }
      const h = (await p.$$('button, a[href], [role=tab], select, summary, input[type=checkbox]'))
      const vis = []
      for (const e of h) if (await e.evaluate(x => x.offsetParent !== null && !x.closest('aside')).catch(() => false)) vis.push(e)
      const el = vis[k]
      if (!el) { rec.result = 'moved (live page)'; continue }
      const before = await p.evaluate(() => ({ m: window.__mut, o: window.__open, u: location.href, a: document.activeElement?.tagName, v: document.body.innerText.length }))
      const r0 = req
      try {
        if (c.tag === 'select') {
          const vals = await el.$$eval('option', os => os.filter(o => !o.disabled).map(o => o.value))
          if (vals.length < 2) { rec.result = 'select with one choice'; continue }
          await el.selectOption(vals[vals.length - 1])
        } else await el.click({ timeout: 2500 })
      } catch (e) {
        rec.result = /intercepts pointer/.test(String(e)) ? 'COVERED by another element' : 'click failed: ' + String(e).split('\n')[0].slice(0, 90)
        await p.keyboard.press('Escape').catch(() => {})
        continue
      }
      await p.waitForTimeout(450)
      const after = await p.evaluate(() => ({ m: window.__mut, o: window.__open, u: location.href, v: document.body.innerText.length,
        crash: /could not be displayed|Something went wrong/i.test(document.body.innerText) })).catch(() => ({ m: 1e9, u: '' }))
      rec.result = after.crash ? 'PAGE CRASH' : after.u !== before.u ? 'navigates' : req > r0 ? 'talks to the backend' : after.o > before.o ? 'opens a window' : after.m > before.m ? 'changes the page' : 'NOTHING'
      if (after.u !== before.u || after.crash || await p.locator('[role=dialog]:visible, .fixed.inset-0:visible').count()) { await load(url) }
    }
  }
  const links = [...new Set(rep.controls.filter(c => c.role === role && c.href?.startsWith('/') && !c.href.startsWith('/api')).map(c => c.href.split('#')[0]))].filter(Boolean)
  const pat = {}
  for (const l of links) {
    const g = l.replace(/\d+/g, '#')
    if ((pat[g] = (pat[g] || 0) + 1) > 2) continue
    where = l
    await load(l)
    const s = await p.evaluate(() => ({ at: location.pathname, n: document.body.innerText.length, bad: /could not be displayed|Something went wrong|not found/i.test((document.querySelector('main') ?? document.body).innerText.slice(0, 400)) }))
    rep.controls.push({ role, page: 'link target', tag: 'a', label: l, href: l, result: s.n < 40 ? 'BLANK PAGE' : s.bad ? 'ERROR PAGE' : 'opens' })
  }
  await ctx.close()
  writeFileSync(process.argv[2], JSON.stringify(rep, null, 1))
  console.log(role, 'done', Math.round((Date.now() - t00) / 1000), 's')
}
await browser.close()
const by = {}
rep.controls.forEach(c => { const k = c.result?.startsWith('click failed') ? 'click failed' : c.result; by[k] = (by[k] || 0) + 1 })
console.log(by, 'api', Object.keys(rep.api).length, 'errors', rep.errors.length)
