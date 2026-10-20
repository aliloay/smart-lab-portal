// Screenshots of the running portal for the paper (methodology / results figures).
// Live camera frames, event snapshots and face previews (blob: images, video) are BLURRED: pictures of people
// never leave the portal. Credentials from SMARTLAB_PASSWORD. Usage: node e2e/paper_shots.mjs <out-dir>
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'
const BASE = process.env.BASE || 'http://192.168.1.200'
const OUT = process.argv[2] || 'paper_shots'
mkdirSync(OUT, { recursive: true })
const PRIVACY_CSS = 'img[src^="blob:"], video, img[src*="frame"], img[src*="snapshot"], img[src*="preview"] { filter: blur(30px) saturate(0.4) !important; }'
const PAGES = [
  ['01_system_overview', '/'], ['02_laboratories', '/labs'], ['03_lab_robotics', '/labs/1'],
  ['04_iot_dashboard', '/command'], ['05_live_monitor', '/monitor'],
  ['06_security_cameras', '/admin/security'], ['07_operations_center', '/admin/operations'],
  ['08_access_audit', '/admin/access'], ['09_bookings', '/admin/bookings'], ['10_emergency', '/admin/emergency'],
  ['11_equipment_environment', '/admin/equipment?tab=environment'], ['12_equipment_robots_pcs', '/admin/equipment?tab=noncons'],
  ['13_equipment_consumables', '/admin/equipment?tab=consumables'], ['14_equipment_reusables', '/admin/equipment?tab=reusables'],
  ['15_equipment_register', '/admin/equipment?tab=register'], ['16_system_devices', '/admin/devices'],
  ['17_robot_ur5e_detail', '/robots/10'], ['18_maintenance', '/issues'], ['19_incidents', '/admin/incidents'],
  ['20_alerts', '/admin/alerts'], ['21_notifications', '/notifications'], ['22_system_analytics', '/admin/system'],
  ['23_reliability_briefing', '/admin/reliability?tab=briefing'], ['24_reliability_dependencies', '/admin/reliability?tab=graph'],
  ['25_reliability_drift', '/admin/reliability?tab=drift'], ['26_reliability_performance', '/admin/reliability?tab=performance'],
  ['27_reliability_alert_quality', '/admin/reliability?tab=quality'], ['28_reliability_backups', '/admin/reliability?tab=backups'],
  ['29_reliability_policy', '/admin/reliability?tab=policy'], ['30_reports', '/admin/reports'], ['31_users_roles', '/admin/users'],
  ['32_settings', '/admin/settings'],
]
const b = await chromium.launch({ channel: 'chrome' })
const ctx = await b.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1.5 })
const p = await ctx.newPage()
const shot = async (name, full = true) => {
  await p.addStyleTag({ content: PRIVACY_CSS }).catch(() => {})
  await p.waitForTimeout(400)
  await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: full })
  console.log('saved', name)
}
await p.goto(`${BASE}/login`); await p.waitForTimeout(2500); await shot('00a_sign_in', false)
await p.fill('#email', 'admin@giu-uni.de'); await p.fill('input[type=password]', process.env.SMARTLAB_PASSWORD || '')
await p.click('button[type=submit]'); await p.waitForURL(u => u.pathname.startsWith('/welcome'), { timeout: 20000 })
await p.waitForTimeout(3000); await shot('00b_welcome_top', false)
for (const [name, path] of PAGES) {
  try {
    await p.goto(BASE + path, { waitUntil: 'domcontentloaded' })
    await p.waitForFunction(() => !document.querySelector('[data-loading], .animate-spin'), null, { timeout: 15000 }).catch(() => {})
    await p.waitForTimeout(path.includes('equipment?tab=noncons') || path.startsWith('/robots') ? 7000 : 3500)
    await shot(name)
  } catch (e) { console.log('FAILED', name, String(e).slice(0, 120)) }
}
// search palette and the assistant answering a live status question
await p.goto(BASE + '/admin/devices'); await p.waitForTimeout(2500)
await p.keyboard.press('Control+k'); await p.fill('[role=dialog][aria-label=Search] input', 'UR5'); await p.waitForTimeout(1200)
await shot('33_global_search', false); await p.keyboard.press('Escape')
await p.goto('http://192.168.1.151/', { waitUntil: 'domcontentloaded' }).catch(() => {}); await p.waitForTimeout(3000)
await shot('34_door_tablet_station', false)
await b.close()
