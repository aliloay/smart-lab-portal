// Security page with two cameras in one lab: wall tile shows both; enlarge has Camera 1 / Camera 2 / Both.
//   node e2e/security_two_cams.mjs <baseUrl> <outDir>      (read-only; admin seed user)
import { chromium } from 'playwright-core'
const [BASE, OUT] = [process.argv[2] || 'http://127.0.0.1:5173', process.argv[3] || 'e2e-shots']
const b = await chromium.launch({ channel: 'chrome' })
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
await p.goto(`${BASE}/login`)
await p.fill('input[type=email]', 'admin@giu-uni.de'); await p.fill('input[type=password]', 'Admin#2026')
await p.click('form button[type=submit]'); await p.waitForURL(u => u.pathname === '/welcome')
await p.goto(`${BASE}/admin/security`); await p.waitForTimeout(9000)
await p.screenshot({ path: `${OUT}/security-wall.png` })
const tiles = await p.$$('[title="Click to enlarge"]')
console.log('camera tiles on the wall:', tiles.length)
await tiles[1].click(); await p.waitForTimeout(6000)
const tabs = await p.$$eval('[aria-label="Camera"] [role=tab]', els => els.map(e => e.textContent))
console.log('switcher:', tabs.join(' | ') || '(none)')
await p.screenshot({ path: `${OUT}/security-big-cam1.png` })
if (tabs.includes('Both')) { await p.click('[aria-label="Camera"] >> text=Both'); await p.waitForTimeout(6000); await p.screenshot({ path: `${OUT}/security-big-both.png` }) }
if (tabs.includes('Camera 2')) { await p.click('[aria-label="Camera"] >> text=Camera 2'); await p.waitForTimeout(6000); await p.screenshot({ path: `${OUT}/security-big-cam2.png` }) }
await b.close()
