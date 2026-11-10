// Renders architecture.html to docs/images/smart-lab-architecture.png (2400 x 1350) with the system Chrome.
//   cd frontend && node e2e/render_architecture.mjs
import { chromium } from 'playwright-core'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const src = path.join(here, '..', '..', 'docs', 'images', 'src', 'architecture.html')
const out = path.join(here, '..', '..', 'docs', 'images', 'smart-lab-architecture.png')
const browser = await chromium.launch({ channel: 'chrome' })
const page = await browser.newPage({ viewport: { width: 2400, height: 1350 } })
await page.goto(pathToFileURL(src).href)
await page.waitForLoadState('networkidle')
const broken = await page.evaluate(() => [...document.images].filter((i) => !i.naturalWidth).map((i) => i.src))
if (broken.length) { console.error('Missing images:', broken); process.exit(1) }
await page.screenshot({ path: out })
await browser.close()
console.log('wrote', out)
