// PC screen preview + sharing, end to end on the live portal with a REAL agent running
// (tools/pc_agent on this laptop as PC_ADMIN_LAPTOP). Usage: node e2e/pc_screen.mjs <screenshot dir> [device_uid]
import { chromium } from 'playwright-core'
const out = process.argv[2]
const UID = process.argv[3] || 'PC_ADMIN_LAPTOP'
const BASE = 'https://192.168.1.200'
const browser = await chromium.launch({ channel: 'chrome', args: ['--auto-select-desktop-capture-source=Entire screen', '--use-fake-ui-for-media-stream'] })
const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1500, height: 950 } })
const page = await ctx.newPage()
await page.goto(`${BASE}/login`)
await page.fill('#email', 'admin@giu-uni.de'); await page.fill('input[type=password]', 'Admin#2026')
await page.click('button[type=submit]'); await page.waitForURL(u => !u.pathname.startsWith('/login'))
const token = await page.evaluate(() => localStorage.getItem('token') || sessionStorage.getItem('token') ||
  Object.values(localStorage).find(v => typeof v === 'string' && v.split('.').length === 3))
const api = (p, init = {}) => page.evaluate(async ([p, init, t]) => {
  const r = await fetch('/api' + p, { ...init, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t } })
  const ct = r.headers.get('content-type') || ''
  return { status: r.status, body: ct.includes('json') ? await r.json() : null, size: Number(r.headers.get('content-length') || 0) }
}, [p, init, token])
const eq = (await api('/equipment')).body
const pc = eq.find(e => e.device_uid === UID)
console.log('PC listed:', !!pc, pc && { online: pc.online, monitors: pc.detail?.monitors?.length, using: pc.detail?.foreground_app })

// 1. Live preview through the UI, first frame latency
await page.goto(`${BASE}/admin/equipment?tab=noncons`, { waitUntil: 'networkidle' })
const card = page.locator('div.card', { hasText: pc.name }).first()
let t0 = Date.now()
await card.locator('button:has-text("View screen")').click()
await page.waitForSelector(`img[alt="Screen of ${pc.name}"]`, { timeout: 20000 })
console.log(`preview: first frame after ${Date.now() - t0} ms`)
const w1 = await page.$eval(`img[alt="Screen of ${pc.name}"]`, i => i.naturalWidth + 'x' + i.naturalHeight)
// 2. Monitor 2 + High quality
const sel = page.locator('select[aria-label="Monitor"]')
if (await sel.count()) {
  await sel.selectOption('2'); await page.waitForTimeout(4500)
  const w2 = await page.$eval(`img[alt="Screen of ${pc.name}"]`, i => i.naturalWidth + 'x' + i.naturalHeight)
  await sel.selectOption('0'); await page.waitForTimeout(4500)
  const w0 = await page.$eval(`img[alt="Screen of ${pc.name}"]`, i => i.naturalWidth + 'x' + i.naturalHeight)
  console.log('monitor switch (frame size): monitor1', w1, '| monitor2', w2, '| all screens', w0)
}
if (out) await page.screenshot({ path: `${out}/pc_preview.png` })
// frame cadence over 6 s
let frames = 0, last = ''
const tEnd = Date.now() + 6000
while (Date.now() < tEnd) { const s = await page.$eval(`img[alt="Screen of ${pc.name}"]`, i => i.src); if (s !== last) { frames++; last = s }; await page.waitForTimeout(100) }
console.log(`preview cadence: ${(frames / 6).toFixed(1)} new frames/s (Standard = 2 fps target)`)
await page.click('[role=dialog] button:has-text("Close")')
await page.waitForTimeout(8000)
const after = await api(`/equipment/${pc.device_id}/screen.jpg`)
console.log('after Close: agent stopped sending (frame endpoint) ->', after.status)

// 3. Wall
await page.click('button:has-text("View all screens")')
t0 = Date.now()
await page.waitForSelector(`img[alt="Screen of ${pc.name}"]`, { timeout: 20000 })
console.log(`wall: tile frame after ${Date.now() - t0} ms; tiles:`, await page.locator('text=All lab PC screens').count())
if (out) await page.screenshot({ path: `${out}/pc_wall.png` })
await page.keyboard.press('Escape'); await page.waitForTimeout(1000)

// 4. Share to the selected PC only (browser source over https). The master PC presents, it never receives.
if (pc.is_master_pc) { console.log('share-to-selected skipped: this PC is the master PC'); await browser.close(); process.exit(0) }
await page.goto(`${BASE}/admin/equipment?tab=noncons`, { waitUntil: 'networkidle' })
await page.click('text=selected PCs')
await page.locator('label', { hasText: pc.name }).locator('input[type=checkbox]').check()
await page.click('button:has-text("Choose screen or window")')
await page.waitForSelector('text=Preview - only you can see this')
await page.click('button:has-text("Go live")')
await page.waitForSelector('text=presenting', { timeout: 15000 })
const st = (await api('/equipment/broadcast/status')).body
console.log('share status:', { active: st.active, targets: st.targets, source: st.source })
await page.waitForTimeout(5000)
const fr = await api('/equipment/broadcast/frame.jpg')
console.log('share frame served:', fr.status)
await page.click('button:has-text("Stop sharing")')
await page.waitForTimeout(2000)
console.log('after Stop: frame ->', (await api('/equipment/broadcast/frame.jpg')).status, '| active:', (await api('/equipment/broadcast/status')).body.active)
await browser.close()
