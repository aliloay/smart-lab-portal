// IoT Dashboard wall layout check (2026-10-27): at 1664x920 the header <= ~12 % of the height, the twin ~45-50 % of
// the width, the camera preview large, no panel clipped or overlapping another; mobile stacks without overlap.
//   E2E_EMAIL=... E2E_PASSWORD=... node e2e/wall_layout.mjs <base> [shotDir]
import { chromium } from 'playwright-core'
const [BASE = 'http://127.0.0.1:5176', SHOTS] = process.argv.slice(2)
const b = await chromium.launch({ channel: 'chrome' })
let failed = false
for (const [w, h, name] of [[1664, 920, 'desktop'], [1920, 1080, 'fullhd'], [412, 915, 'phone']]) {
  const p = await (await b.newContext({ viewport: { width: w, height: h } })).newPage()
  await p.goto(`${BASE}/login`)
  await p.fill('#email', process.env.E2E_EMAIL); await p.fill('#password', process.env.E2E_PASSWORD)
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'))
  await p.goto(`${BASE}/wall`); await p.waitForSelector('.wall-floor-card', { timeout: 30000 }); await p.waitForSelector('svg[aria-label^="Robotics Lab floor plan"]', { timeout: 60000 }).catch(() => {}); await p.waitForTimeout(4000)
  const m = await p.evaluate(() => {
    const r = sel => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height } }
    const main = r('.wall-main'), boxes = ['.wall-header', '.wall-left-col', '.wall-floor-card', '.wall-right-stack', '.wall-camera-panel',
      '.wall-metrics', '.wall-environment-panel', '.wall-attention', '.wall-recent-panel', '.wall-robot-panel'].map(s => [s, r(s)])
    const ov = []
    const big = ['.wall-header', '.wall-left-col', '.wall-floor-card', '.wall-right-stack']
    for (let i = 0; i < big.length; i++) for (let j = i + 1; j < big.length; j++) {
      const a = r(big[i]), c = r(big[j]); if (!a || !c) continue
      const ix = Math.min(a.x + a.w, c.x + c.w) - Math.max(a.x, c.x), iy = Math.min(a.y + a.h, c.y + c.h) - Math.max(a.y, c.y)
      if (ix > 1 && iy > 1) ov.push(`${big[i]} x ${big[j]}`)
    }
    // children of the header must not overlap each other
    const hk = [...document.querySelectorAll('.wall-header > *')].map(e => e.getBoundingClientRect())
    for (let i = 0; i < hk.length; i++) for (let j = i + 1; j < hk.length; j++) {
      const a = hk[i], c = hk[j]; if (!a.width || !c.width) continue
      if (Math.min(a.right, c.right) - Math.max(a.left, c.left) > 1 && Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top) > 1) ov.push(`header child ${i} x ${j}`)
    }
    const clipped = [...document.querySelectorAll('.wall-subpanel, .wall-floor-card, .wall-attention')].filter(e => {
      const b = e.getBoundingClientRect(); return b.height > 0 && b.height < 60 })
      .map(e => e.className.split(' ').find(c => c.startsWith('wall-')))
    return { vw: innerWidth, vh: innerHeight, header_pct: Math.round(100 * r('.wall-header').h / innerHeight),
      twin_pct_of_main: main ? Math.round(100 * r('.wall-floor-card').w / main.w) : null,
      camera: r('.wall-camera-panel'), overlaps: ov, too_small: clipped, page_scroll: document.documentElement.scrollHeight > innerHeight + 2,
      boxes: Object.fromEntries(boxes.map(([s, v]) => [s, v && [Math.round(v.x), Math.round(v.y), Math.round(v.w), Math.round(v.h)]])) }
  })
  console.log(name, JSON.stringify(m))
  if (m.overlaps.length || m.too_small.length) failed = true
  if (name === 'desktop' && (m.header_pct > 12 || m.twin_pct_of_main < 44 || m.twin_pct_of_main > 51 || m.page_scroll)) failed = true
  if (SHOTS) await p.screenshot({ path: `${SHOTS}/wall_${name}.png`, fullPage: name === 'phone' })
}
await b.close()
console.log(failed ? 'FAIL' : 'PASS'); process.exit(failed ? 1 : 0)
