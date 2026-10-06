/**
 * Security camera recording, end to end (admin): Record -> ~6 s -> Stop ->
 * the file is listed -> Play loads it in the page (duration read by the
 * browser) -> the download link answers. Writes ONE short real recording on
 * the laptop (and two audit-log entries); nothing else.
 *   node e2e/recording.mjs [base]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://localhost'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
let failed = 0
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'}  ${what}`); if (!ok) failed++ }
try {
  const page = await (await browser.newContext({ viewport: { width: 1500, height: 950 } })).newPage()
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  page.on('dialog', d => d.accept())
  await page.goto(`${BASE}/login`)
  await page.fill('#email', 'admin@giu-uni.de')
  await page.fill('#password', 'Admin#2026')
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 20000 })
  if (await page.$('[role=alertdialog]')) await page.getByRole('button', { name: 'CLEAR ALL' }).click()
  await page.goto(`${BASE}/admin/security`)
  await page.getByRole('tab', { name: /Recordings/ }).or(page.locator('[role=tablist] button', { hasText: 'Recordings' })).first().click()
  const record = page.getByRole('button', { name: /^Record$/ })
  await record.waitFor({ timeout: 15000 })
  const before = await page.locator('[data-testid=recordings] > div').count()
  await record.click()
  await page.getByText(/REC \d\d:\d\d/).waitFor({ timeout: 10000 })
  check(true, 'Record pressed: REC timer shown')
  await page.waitForTimeout(6000)
  await page.getByRole('button', { name: /Stop/ }).first().click()
  await page.getByRole('button', { name: /^Record$/ }).waitFor({ timeout: 15000 })
  await page.waitForTimeout(1500)
  await page.reload()
  await page.locator('[role=tablist] button', { hasText: 'Recordings' }).first().click()
  await page.locator('[data-testid=recordings] > div').first().waitFor({ timeout: 15000 })
  const rows = await page.locator('[data-testid=recordings] > div').count()
  const first = await page.locator('[data-testid=recordings] > div').first().innerText()
  check(rows === before + 1, `listed: ${rows} recording(s) (was ${before}) - newest: ${first.replace(/\s+/g, ' ').slice(0, 90)}`)
  await page.locator('[data-testid=recordings] > div').first().getByRole('button', { name: /Play/ }).click()
  const video = page.locator('video')
  await video.waitFor({ timeout: 10000 })
  const dur = await page.waitForFunction(() => {
    const v = document.querySelector('video')
    return v && v.readyState >= 1 && isFinite(v.duration) && v.duration > 0 ? v.duration : null
  }, null, { timeout: 20000 }).then(h => h.jsonValue()).catch(() => null)
  check(dur !== null && dur > 4, `plays in the page: the browser reads a ${dur ? dur.toFixed(1) : '?'} s video`)
  const src = await video.getAttribute('src')
  const head = await page.request.get(`${BASE}${src}&download=true`, { headers: { Range: 'bytes=0-15' } })
  check([200, 206].includes(head.status()) && (head.headers()['content-disposition'] || '').includes('attachment'),
        `download link answers ${head.status()} (${head.headers()['content-range'] || head.headers()['content-length']})`)
  const expired = await page.request.get(`${BASE}/api/security/recordings/play?t=not-a-token`)
  check(expired.status() === 401, `a bad link is refused (${expired.status()})`)
  check(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`)
} finally {
  await browser.close()
}
process.exit(failed ? 1 : 0)
