/**
 * Robot page in a real browser (admin): live tool trail, a recorded movement
 * replayed in 3D, wall mode. Screenshots to the folder given. Read-only.
 *   node e2e/robots_replay.mjs [base] [shots-dir] [robot-id]
 */
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || 'http://localhost'
const OUT = process.argv[3] || '.'
const ID = process.argv[4] || '6'
const b = await chromium.launch({ channel: 'chrome', headless: true })
const errors = []
try {
  const p = await (await b.newContext({ viewport: { width: 1600, height: 1000 } })).newPage()
  p.on('console', m => { if (m.type() === 'error' && !m.text().includes('503')) errors.push(m.text()) })
  p.on('pageerror', e => errors.push(String(e)))
  await p.goto(`${BASE}/login`)
  await p.fill('#email', 'admin@giu-uni.de'); await p.fill('#password', 'Admin#2026')
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  await p.goto(`${BASE}/robots/${ID}`); await p.waitForSelector('canvas'); await p.waitForTimeout(9000)
  await p.screenshot({ path: `${OUT}/robot_live.png` })
  const item = p.locator('text=Replay a movement').locator('..').locator('li button').first()
  await item.click()
  await p.waitForSelector('text=REPLAY', { timeout: 5000 })
  await p.waitForTimeout(1800)
  console.log('replay chip:', await p.locator('text=REPLAY').count() > 0, '| slider:', await p.locator('input[type=range]').count())
  await p.screenshot({ path: `${OUT}/robot_replay.png` })
  await p.goto(`${BASE}/wall`); await p.waitForSelector('canvas'); await p.waitForTimeout(4000)
  console.log('wall mode sidebar present:', await p.locator('aside nav').count() > 0)
  await p.screenshot({ path: `${OUT}/wall.png` })
} finally {
  await b.close()
}
console.log(errors.length ? `CONSOLE ERRORS:\n${errors.join('\n')}` : 'no console errors')
