/**
 * Reliability centre + incident investigation + global search in a real browser (admin) - READ-ONLY:
 * opens every Reliability tab, runs one sandboxed what-if, opens an incident's investigation, uses the
 * Ctrl+K palette, and checks the regrouped sidebar still lists every former page. Screenshots to [shots].
 *   node e2e/reliability.mjs [base] [shots-dir]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || 'http://localhost'
const OUT = process.argv[3] || '.'
// Credentials from the environment only - never written into the repository (public).
const EMAIL = process.env.SMARTLAB_EMAIL || 'admin@giu-uni.de'
const PASSWORD = process.env.SMARTLAB_PASSWORD
if (!PASSWORD) { console.error('Set SMARTLAB_PASSWORD (and SMARTLAB_EMAIL) first.'); process.exit(2) }
const b = await chromium.launch({ channel: 'chrome', headless: true })
const errors = []
let failed = 0
const check = (ok, msg) => { console.log(`${ok ? 'PASS' : 'FAIL'} ${msg}`); if (!ok) failed++ }
try {
  const p = await (await b.newContext({ viewport: { width: 1500, height: 1000 } })).newPage()
  p.on('pageerror', e => errors.push(String(e)))
  await p.goto(`${BASE}/login`)
  await p.fill('#email', EMAIL); await p.fill('#password', PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  // every page that was in the admin menu before the regrouping is still there (a normal page: the
  // welcome screen after login has no sidebar)
  await p.goto(`${BASE}/admin/system`)
  await p.waitForSelector('nav[aria-label=Main] a')
  const nav = await p.locator('nav[aria-label=Main] a').evaluateAll(as => as.map(a => a.getAttribute('href')))
  for (const r of ['/', '/labs', '/admin/bookings', '/admin/access', '/command', '/admin/operations', '/admin/system', '/monitor',
    '/admin/security', '/admin/reports', '/issues', '/admin/devices', '/admin/equipment', '/admin/alerts', '/admin/incidents',
    '/notifications', '/admin/users', '/admin/settings', '/admin/emergency', '/admin/reliability'])
    check(nav.includes(r), `menu still has ${r}`)
  check(!nav.includes('/robots'), 'Robots only under Lab Equipment (owner, 2026-10-18)')
  for (const t of ['briefing', 'graph', 'drift', 'performance', 'quality', 'backups', 'policy']) {
    const t0 = Date.now()
    await p.goto(`${BASE}/admin/reliability?tab=${t}`)
    await p.waitForSelector('[role=tablist]')
    await p.waitForFunction(() => !document.body.innerText.includes('Loading…'), null, { timeout: 15000 })
    check(true, `tab ${t} rendered in ${Date.now() - t0} ms`)
    await p.screenshot({ path: `${OUT}/rel_${t}.png` })
  }
  await p.goto(`${BASE}/admin/reliability?tab=graph`)
  await p.waitForFunction(() => !document.body.innerText.includes('Loading…'))
  await p.locator('button', { hasText: 'PostgreSQL' }).first().click()
  await p.getByText('What if this fails? (simulation)').click()
  await p.waitForSelector('text=SIMULATED - nothing was changed', { timeout: 8000 })
  check(await p.getByText('Backend API').count() > 0, 'what-if lists the backend as affected by the database')
  await p.screenshot({ path: `${OUT}/rel_whatif.png` })
  await p.goto(`${BASE}/admin/incidents`)
  await p.waitForSelector('text=INC-')
  await p.locator('button:has-text("INC-")').first().click()
  await p.getByRole('button', { name: 'Investigate' }).click()
  await p.waitForSelector('text=correlation, not proof', { timeout: 15000 })
  check(true, 'incident investigation shown with its correlation-not-proof statement')
  await p.screenshot({ path: `${OUT}/incident_investigation.png` })
  await p.keyboard.press('Escape')
  await p.goto(`${BASE}/admin/system`)
  await p.waitForSelector('nav[aria-label=Main] a')
  await p.keyboard.press('Control+k')
  await p.fill('[role=dialog] input', 'camera')
  await p.waitForSelector('[role=dialog] li button:has-text("device")', { timeout: 8000 })
  check(await p.locator('[role=dialog] li button').count() > 1, 'search palette finds pages and devices')
  await p.screenshot({ path: `${OUT}/palette.png` })
} finally {
  await b.close()
}
console.log(errors.length ? `PAGE ERRORS:\n${errors.join('\n')}` : 'no page errors')
console.log(failed ? `${failed} FAILED` : 'ALL PASS')
