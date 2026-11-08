/**
 * Robot master-control panels in a real browser (admin) - READ-ONLY: opens each robot page, checks the
 * readiness checklist, the DRY RUN / SIMULATED labels and the software-STOP wording, takes screenshots.
 * It never presses Home, STOP or Request control.
 *   node e2e/robot_readiness.mjs [base] [shots-dir] [ids comma-separated]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || 'http://localhost'
const OUT = process.argv[3] || '.'
const IDS = (process.argv[4] || '10,11').split(',')
// Credentials from the environment only - never written into the repository (public).
const EMAIL = process.env.SMARTLAB_EMAIL || 'admin@giu-uni.de'
const PASSWORD = process.env.SMARTLAB_PASSWORD
if (!PASSWORD) { console.error('Set SMARTLAB_PASSWORD (and SMARTLAB_EMAIL) first.'); process.exit(2) }
const b = await chromium.launch({ channel: 'chrome', headless: true })
const errors = []
let failed = 0
const check = (ok, msg) => { console.log(`${ok ? 'PASS' : 'FAIL'} ${msg}`); if (!ok) failed++ }
try {
  const p = await (await b.newContext({ viewport: { width: 1500, height: 1100 } })).newPage()
  p.on('pageerror', e => errors.push(String(e)))
  await p.goto(`${BASE}/login`)
  await p.fill('#email', EMAIL); await p.fill('#password', PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  for (const id of IDS) {
    await p.goto(`${BASE}/robots/${id}`)
    // 2026-10-18: Home + STOP up front, the readiness checklist behind "Details" (owner's layout).
    const summary = p.locator('summary', { hasText: 'Details: readiness' }).first()
    await summary.waitFor({ timeout: 15000 })
    await summary.click()
    const panel = p.locator('text=Physical test readiness').first()
    await panel.waitFor({ timeout: 15000 })
    await p.waitForTimeout(1500)
    const box = p.locator('div.card', { has: p.locator('text=Physical test readiness') }).first()
    const text = await box.innerText()
    if (process.env.DUMP) console.log(`--- robot ${id}
${text.slice(0, 900)}`)
    check(/DRY RUN/.test(text), `robot ${id}: DRY RUN label shown`)
    check(/Blocked|Ready for supervised physical test|Ready \(live\)/i.test(text), `robot ${id}: readiness state shown`)
    check(/A real robot \(not the simulator\)/.test(text), `robot ${id}: real-vs-simulator check listed`)
    if (/STOP/.test(text) && !/Needed before any command can exist/.test(text))
      check(/Software stop - not an emergency stop/.test(text), `robot ${id}: STOP labelled software stop`)
    else check(/Needed before any command can exist/.test(text), `robot ${id}: FANUC dependencies listed`)
    await box.screenshot({ path: `${OUT}/robot_${id}_control.png` })
  }
} finally {
  await b.close()
}
console.log(errors.length ? `PAGE ERRORS:\n${errors.join('\n')}` : 'no page errors')
console.log(failed ? `${failed} FAILED` : 'ALL PASS')
