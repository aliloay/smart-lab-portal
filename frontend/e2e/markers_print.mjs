// Asset markers: the Print button must produce the PDF sheet (a new tab with the PDF, or a download when the
// browser blocks the tab). E2E_EMAIL=... E2E_PASSWORD=... node e2e/markers_print.mjs <base>
import { chromium } from 'playwright-core'

const [BASE = 'http://127.0.0.1:5176'] = process.argv.slice(2)
const b = await chromium.launch({ channel: 'chrome' })
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true })
const p = await ctx.newPage()
const out = { console: [] }
p.on('console', m => { if (m.type() === 'error') out.console.push(m.text().slice(0, 200)) })
p.on('response', r => { if (r.url().includes('markers.pdf')) out.pdf = { status: r.status(), type: r.headers()['content-type'] } })
await p.goto(`${BASE}/login`)
await p.fill('#email', process.env.E2E_EMAIL); await p.fill('#password', process.env.E2E_PASSWORD)
await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
await p.goto(`${BASE}/scan/markers`)
await p.waitForSelector('img[alt^="Marker"]', { timeout: 30000 })
const popup = ctx.waitForEvent('page', { timeout: 20000 }).catch(() => null)
const dl = p.waitForEvent('download', { timeout: 20000 }).catch(() => null)
await p.click('button:has-text("Print")')
const [tab, file] = await Promise.all([popup, dl])
if (tab) { await tab.waitForLoadState().catch(() => {}); await tab.waitForTimeout(1500); out.tab_url = tab.url().slice(0, 60) }
if (file) out.download = file.suggestedFilename()
out.page_error = await p.evaluate(() => document.querySelector('.text-bad-soft')?.textContent ?? null)
console.log(JSON.stringify(out, null, 1))
await b.close()
