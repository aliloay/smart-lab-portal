// Screenshots of the welcome finale while the ABB writes the heading.  node e2e/welcome_writer_shots.mjs <outDir>
import { chromium } from 'playwright-core'
const OUT = process.argv[2]
const b = await chromium.launch({ channel: 'chrome' }); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
p.on('pageerror', e => console.log('ERR', String(e).slice(0, 200)))
await p.goto('http://192.168.1.200/login'); await p.fill('input[type=email]', 'admin@giu-uni.de'); await p.fill('input[type=password]', 'Admin#2026')
await p.click('form button[type=submit]'); await p.waitForSelector('#wl-end'); await p.waitForTimeout(5000)
await p.evaluate(() => document.getElementById('wl-end').scrollIntoView())
for (const [n, w] of [['w1', 500], ['w2', 1700], ['w3', 1500], ['w4', 2000], ['w5', 1000], ['w6', 1500]]) { await p.waitForTimeout(w); await p.screenshot({ path: `${OUT}/${n}.png` }) }
await b.close()
