// End-to-end workflow test: the things people actually do, through the UI.
//
//   node e2e/workflows.mjs [baseUrl]         (default http://127.0.0.1:5173)
//
// Needs the API running with the seed users, and Google Chrome installed.
// It WRITES to the database it runs against (a booking, a booking made by
// staff for a student, one issue report with a photo) - run it against the
// CI / QA database, never against a database whose history matters.
//
//   1. student books a laboratory through the wizard and opens the QR
//   2. staff books on behalf of a student
//   3. student reports an issue with a photo and gets an ISS- ticket;
//      staff acknowledge, assign, add an internal note and an "after" photo,
//      resolve; the admin closes and reopens; the student never sees the
//      internal note and is notified of the resolution
//   4. staff opens the simulation page and runs a scenario (no API writes)
//   5. phone width: key pages have no horizontal page scroll
import { deflateSync } from 'node:zlib'
import { chromium } from 'playwright-core'

const BASE = process.argv[2] || process.env.E2E_BASE || 'http://127.0.0.1:5173'
const STUDENT = { email: 'ali@giu-uni.de', password: 'Student#2026' }
const STAFF = { email: 'ramy@giu-uni.de', password: 'Staff#2026' }
const ADMIN = { email: 'admin@giu-uni.de', password: 'Admin#2026' }
const INTERNAL = 'E2E internal - ordered replacement probe'

const problems = []
let passed = 0
let issueUrl = null

function ok(label) { passed++; console.log(`ok    ${label}`) }
function fail(label, why) { problems.push(`${label}: ${why}`); console.log(`FAIL  ${label}: ${why}`) }

async function step(label, fn) {
  try { await fn(); ok(label) } catch (e) { fail(label, String(e?.message ?? e).split('\n')[0]) }
}

async function signIn(browser, who, viewport = { width: 1366, height: 860 }) {
  const ctx = await browser.newContext({ viewport })
  const page = await ctx.newPage()
  const errors = []
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  page.on('pageerror', e => errors.push(String(e)))
  await page.goto(`${BASE}/login`)
  await page.fill('#email', who.email)
  await page.fill('#password', who.password)
  await page.click('button[type=submit]')
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 })
  return { ctx, page, errors }
}

function consoleCheck(label, errors) {
  const real = errors.filter(e => !/WebSocket|ERR_CONNECTION_REFUSED/.test(e))
  if (real.length) fail(`${label} console`, [...new Set(real)].join(' | ').slice(0, 300))
}

/** A real 64x48 PNG (gradient), so the server's image decoder accepts it. */
function png(w = 64, h = 48) {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    return c >>> 0
  })
  const crc = buf => {
    let c = 0xffffffff
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8)
    return (c ^ 0xffffffff) >>> 0
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length)
    const body = Buffer.concat([Buffer.from(type), data])
    const c = Buffer.alloc(4); c.writeUInt32BE(crc(body))
    return Buffer.concat([len, body, c])
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4)
  ihdr[8] = 8; ihdr[9] = 2                      // 8-bit RGB
  const raw = Buffer.alloc((w * 3 + 1) * h)
  for (let y = 0; y < h; y++) {
    const row = y * (w * 3 + 1)
    for (let x = 0; x < w; x++) {
      raw[row + 1 + x * 3] = (x * 4) & 255
      raw[row + 2 + x * 3] = (y * 5) & 255
      raw[row + 3 + x * 3] = 160
    }
  }
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))])
}

/** Walk the booking wizard. Picks a door-equipped lab, a day two weeks out,
 *  and the first free hour, so repeated runs do not collide. */
async function bookThroughWizard(page, { forUserIndex } = {}) {
  await page.goto(`${BASE}/book`)
  const cont = page.getByRole('button', { name: 'Continue' })
  // 0: laboratory
  await page.locator('main button[aria-pressed]', { hasText: 'Door access' }).first().click()
  await cont.click()
  // 1: date - the last of the 14 day buttons
  await page.getByText('Which day?').waitFor({ timeout: 4000 })
  await page.locator('main .grid button[aria-pressed]').last().click()
  await cont.click()
  // 2: hours - first free hour, tapped twice = one hour. (The previous step
  // animates out, so match hour buttons by their "HH:00" label.)
  await page.getByText('Which hours?').waitFor({ timeout: 4000 })
  const free = page.locator('main button[aria-pressed]:not([disabled])', { hasText: /^\d\d:00/ }).first()
  await free.waitFor({ timeout: 8000 })
  const hour = (await free.innerText()).trim().slice(0, 5)
  await free.click(); await free.click()
  await page.getByText(/→.*\(1 h\)/).first().waitFor({ timeout: 4000 })
  await cont.click()
  // 3: purpose (and, for staff, the person)
  await page.getByRole('button', { name: 'Thesis experiment' }).click()
  if (forUserIndex !== undefined) {
    await page.selectOption('#for', { index: forUserIndex })
  }
  await cont.click()
  // 4: review
  await page.getByText('Review and confirm').waitFor({ timeout: 4000 })
  await page.getByRole('button', { name: /Confirm booking/ }).click()
  await page.getByText(/Booking confirmed|Request submitted/).waitFor({ timeout: 10000 })
  return hour
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
try {
  // ---------------------------------------------------------------- 1
  {
    const { ctx, page, errors } = await signIn(browser, STUDENT)
    await step('student books a laboratory through the wizard', async () => {
      const hour = await bookThroughWizard(page)
      console.log(`      (booked ${hour}, two weeks out)`)
    })
    await step('student opens the booking QR', async () => {
      const qr = page.getByRole('button', { name: 'Open QR' })
      if (!(await qr.count())) {
        // Lab requires approval: the QR is correctly withheld until staff approve.
        await page.getByText('Awaiting approval').waitFor({ timeout: 3000 })
        console.log('      (booking pending approval - QR correctly withheld)')
        return
      }
      await qr.click()
      await page.waitForURL(/\/bookings\/\d+\/qr$/, { timeout: 8000 })
      await page.locator('main svg, main canvas, main img').first().waitFor({ timeout: 8000 })
    })
    await step('the new booking is listed under My bookings', async () => {
      await page.goto(`${BASE}/bookings`)
      await page.locator('main a[href^="/bookings/"]').first().waitFor({ timeout: 8000 })
    })
    consoleCheck('student booking', errors)
    await ctx.close()
  }

  // ---------------------------------------------------------------- 2
  {
    const { ctx, page, errors } = await signIn(browser, STAFF)
    await step('staff books on behalf of a user', async () => {
      await bookThroughWizard(page, { forUserIndex: 1 })
      await page.getByText('Booked for').first().waitFor({ timeout: 4000 })
    })
    // ------------------------------------------------------------ 4
    await step('staff runs a simulation scenario (no API writes)', async () => {
      const writes = []
      const onReq = r => { if (r.url().includes('/api/') && r.method() !== 'GET') writes.push(r.url()) }
      page.on('request', onReq)
      await page.goto(`${BASE}/demo`)
      await page.getByText(/simulation/i).first().waitFor({ timeout: 8000 })
      const before = (await page.locator('main').innerText()).length
      await page.getByRole('button', { name: /Run simulation/ }).click()
      await page.getByRole('button', { name: /Run again/ }).waitFor({ timeout: 20000 })
      const after = (await page.locator('main').innerText()).length
      page.off('request', onReq)
      if (after <= before) throw new Error('the simulated timeline did not appear')
      if (writes.length) throw new Error(`simulation called the API: ${writes.join(', ')}`)
    })
    await step('an access session page opens from the monitor (if any session exists)', async () => {
      await page.goto(`${BASE}/admin/access`)
      await page.locator('main h1').first().waitFor({ timeout: 8000 })
      await page.getByRole('tab', { name: /Sessions/ }).click()
      const link = page.locator('main a[href^="/sessions/"]').first()
      await link.waitFor({ timeout: 6000 }).catch(() => {})
      if (!(await link.count())) { console.log('      (no sessions recorded in this database - skipped)'); return }
      await link.click()
      await page.waitForURL(/\/sessions\/\d+$/)
      await page.getByText('Live access session').first().waitFor({ timeout: 8000 })
    })
    consoleCheck('staff', errors)
    await ctx.close()
  }

  // ---------------------------------------------------------------- 3
  {
    const { ctx, page, errors } = await signIn(browser, STUDENT)
    await step('student reports an issue with a photo and gets a ticket', async () => {
      await page.goto(`${BASE}/issues/new`)
      await page.getByRole('button', { name: /Malfunction/ }).click()
      await page.selectOption('select[aria-label="Laboratory"]', { index: 1 })
      await page.getByRole('button', { name: /^low/i }).click()
      await page.fill('#title', 'E2E - oscilloscope channel 2 flat')
      await page.fill('#desc', 'Automated browser test report. Channel 2 shows no signal.')
      await page.setInputFiles('input[type=file]',
        { name: 'e2e-photo.png', mimeType: 'image/png', buffer: png() })
      await page.locator('main img').first().waitFor({ timeout: 5000 })   // preview
      await page.getByRole('button', { name: /Submit report/ }).click()
      const ticket = page.locator('h1', { hasText: /^ISS-/ })
      await ticket.waitFor({ timeout: 20000 })
      if (await page.getByText('The photos were not attached').count())
        throw new Error('report created but the photo upload failed')
      console.log(`      (${(await ticket.innerText()).trim()})`)
    })
    await step('the issue page shows the uploaded photo', async () => {
      await page.getByRole('link', { name: 'Follow this issue' }).click()
      await page.waitForURL(/\/issues\/\d+$/)
      await page.locator('main img').first().waitFor({ timeout: 10000 })
      const loaded = await page.locator('main img').first()
        .evaluate(img => img.complete && img.naturalWidth > 0)
      if (!loaded) throw new Error('photo element present but the image did not load')
      issueUrl = page.url()
    })
    consoleCheck('student issue', errors)
    await ctx.close()
  }

  // ---------------------------------------------------------------- 3b
  if (issueUrl) {
    const { ctx, page, errors } = await signIn(browser, STAFF)
    const status = t => page.locator('main').getByText(t, { exact: true }).first()
    await page.goto(issueUrl)
    await step('staff acknowledges the issue', async () => {
      await page.getByRole('button', { name: 'Acknowledge', exact: true }).click()
      await page.getByRole('button', { name: 'Acknowledge', exact: true }).waitFor({ state: 'detached', timeout: 8000 })
    })
    await step('staff assigns it to themselves', async () => {
      await page.getByRole('button', { name: 'Assign to me' }).click()
      await page.getByRole('button', { name: 'Assign to me' }).waitFor({ state: 'detached', timeout: 8000 })
    })
    await step('staff adds an internal note', async () => {
      await page.fill('textarea[placeholder^="Update for the reporter"]', INTERNAL)
      await page.getByLabel('Internal note').check()
      await page.getByRole('button', { name: 'Post' }).click()
      await page.getByText(INTERNAL).first().waitFor({ timeout: 8000 })
    })
    await step('staff adds an "after" maintenance photo', async () => {
      const before = await page.locator('main button[aria-label^="Open photo"]').count()
      await page.getByRole('button', { name: /Add maintenance photos/ }).click()
      await page.getByRole('button', { name: 'After maintenance', exact: true }).click()
      await page.locator('input[type=file]').last().setInputFiles(
        { name: 'after.png', mimeType: 'image/png', buffer: png(80, 60) })
      await page.getByRole('button', { name: /^Upload/ }).click()
      await page.waitForFunction(n =>
        document.querySelectorAll('main button[aria-label^="Open photo"]').length > n, before, { timeout: 10000 })
    })
    await step('staff resolves it with notes', async () => {
      await page.fill('textarea[placeholder^="What was done"]', 'Replaced the channel 2 probe; verified with the calibrator.')
      await page.getByRole('button', { name: /Mark resolved/ }).click()
      await status('Resolved').waitFor({ timeout: 8000 })
    })
    consoleCheck('staff maintenance', errors)
    await ctx.close()

    const a = await signIn(browser, ADMIN)
    await a.page.goto(issueUrl)
    await step('admin closes the resolved issue', async () => {
      await a.page.getByRole('button', { name: /Close issue/ }).click()
      await a.page.locator('main').getByText('Closed', { exact: true }).first().waitFor({ timeout: 8000 })
    })
    await step('admin reopens it, and the history records every step', async () => {
      await a.page.getByRole('button', { name: /Reopen/ }).click()
      await a.page.getByRole('button', { name: /Reopen/ }).waitFor({ state: 'detached', timeout: 8000 })
      const text = await a.page.locator('main').innerText()
      for (const w of [/acknowledged/i, /assigned/i, /resolved/i, /closed/i, /reopened/i])
        if (!w.test(text)) throw new Error(`history is missing ${w}`)
    })
    consoleCheck('admin maintenance', a.errors)
    await a.ctx.close()

    const st = await signIn(browser, STUDENT)
    await step('the reporter never sees the internal note', async () => {
      await st.page.goto(issueUrl)
      await st.page.locator('main h1').first().waitFor({ timeout: 8000 })
      await st.page.waitForTimeout(500)
      if (await st.page.getByText(INTERNAL).count()) throw new Error('internal note visible to the student')
    })
    await step('the reporter was notified of the resolution', async () => {
      await st.page.goto(`${BASE}/notifications`)
      await st.page.getByText(/resolved/i).first().waitFor({ timeout: 8000 })
    })
    consoleCheck('student follow-up', st.errors)
    await st.ctx.close()
  }

  // ---------------------------------------------------------------- 5
  for (const [who, paths] of [
    [STUDENT, ['/', '/labs', '/book', '/bookings', '/issues', '/issues/new', '/notifications']],
    [STAFF, ['/', '/admin/bookings', '/admin/access', '/admin/equipment', '/issues', '/demo']],
  ]) {
    const { ctx, page, errors } = await signIn(browser, who, { width: 390, height: 844 })
    for (const p of paths) {
      await step(`phone width ${who === STAFF ? 'staff  ' : 'student'} ${p}`, async () => {
        await page.goto(BASE + p)
        await page.locator('main h1, main h2').first().waitFor({ timeout: 8000 })
        await page.waitForTimeout(300)
        const { sw, w } = await page.evaluate(() =>
          ({ sw: document.documentElement.scrollWidth, w: window.innerWidth }))
        if (sw > w + 1) throw new Error(`page scrolls sideways (${sw}px content in ${w}px)`)
      })
    }
    consoleCheck(`phone ${who.email}`, errors)
    await ctx.close()
  }
} finally {
  await browser.close()
}

console.log(`\n${passed} passed, ${problems.length} problems`)
problems.forEach(p => console.log('  ! ' + p))
process.exit(problems.length ? 1 : 0)
