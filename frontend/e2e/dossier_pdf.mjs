// Render docs/reports/dossier/*.html to PDF with page numbers (headless Chrome, no network needed).
// usage: node e2e/dossier_pdf.mjs <input.html> <output.pdf>
import { chromium } from 'playwright-core'
import { pathToFileURL } from 'node:url'
import path from 'node:path'

const [, , input, output] = process.argv
if (!input || !output) { console.error('usage: node e2e/dossier_pdf.mjs <input.html> <output.pdf>'); process.exit(2) }
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage()
await page.goto(pathToFileURL(path.resolve(input)).href, { waitUntil: 'load' })
await page.pdf({
  path: output, format: 'A4', printBackground: true, preferCSSPageSize: true,
  displayHeaderFooter: true,
  headerTemplate: '<div style="font-size:7pt;color:#888;width:100%;padding:0 16mm;text-align:right">ALIoT Smart Lab - engineering dossier</div>',
  footerTemplate: '<div style="font-size:7.5pt;color:#666;width:100%;text-align:center">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
  outline: true, tagged: true,
})
await browser.close()
console.log('wrote', output)
