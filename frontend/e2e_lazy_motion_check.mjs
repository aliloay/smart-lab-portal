// 2026-11-17 optimisation check: the lean framer-motion build renders without errors (login + a 404 route).
import { chromium } from 'playwright-core'
const base = process.argv[2] || 'http://localhost:5177'
const b = await chromium.launch({ channel: 'chrome' }).catch(() => chromium.launch({ executablePath: 'C://Program Files (x86)//Microsoft//Edge//Application//msedge.exe' })); const p = await b.newPage()
const errors = []
p.on('pageerror', e => errors.push('pageerror: ' + e.message))
p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource|401|ERR_CONNECTION|fetch/i.test(m.text())) errors.push(m.text()) })
for (const path of ['/login', '/']) {
  await p.goto(base + path, { waitUntil: 'networkidle', timeout: 20000 }).catch(e => errors.push('goto ' + path + ': ' + e.message))
  await p.waitForTimeout(1500)
  const pw = await p.locator('input[type="password"]').count()
  const text = (await p.locator('body').innerText()).slice(0, 80).replace(/\s+/g, ' ')
  console.log(path, 'password inputs:', pw, '| text:', text)
}
console.log('errors:', errors.length ? errors : 'none')
await b.close()
