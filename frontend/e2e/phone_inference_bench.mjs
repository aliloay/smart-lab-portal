/**
 * On-phone YOLO benchmark (2026-10-29): can the phone run the people model itself (ONNX Runtime Web) instead of
 * sending each frame to the laptop? SIMULATED - desktop Chrome with phone emulation and CPU throttling, not a real
 * iPhone/Android. Same model file as the camera service (yolo26s.onnx), same 640 frame, same letterbox.
 * Measures: model load, first inference, steady inference p50/p95, preprocessing, postprocessing, the JPEG encode the
 * server path needs, and which execution providers the browser really offers (WebGPU feature-detected).
 *   node e2e/phone_inference_bench.mjs <model.onnx> <test.jpg> [throttle=4] [runs=30] [device="Pixel 7"]
 */
import { chromium, devices } from 'playwright-core'
import fs from 'node:fs'
import path from 'node:path'

const [MODEL, IMG] = process.argv.slice(2, 4)
const THROTTLE = +(process.argv[4] || 4), RUNS = +(process.argv[5] || 30), DEV = process.argv[6] || 'Pixel 7'
const DIST = path.resolve('node_modules/onnxruntime-web/dist')
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--enable-unsafe-webgpu'] })
const ctx = await browser.newContext({ ...devices[DEV] })
const page = await ctx.newPage()
const types = { '.mjs': 'text/javascript', '.js': 'text/javascript', '.wasm': 'application/wasm' }
await page.route('http://bench.local/**', r => {
  const u = new URL(r.request().url()).pathname
  if (u === '/') return r.fulfill({ contentType: 'text/html', body: '<!doctype html><body></body>' })
  if (u === '/model.onnx') return r.fulfill({ contentType: 'application/octet-stream', body: fs.readFileSync(MODEL) })
  if (u === '/img.jpg') return r.fulfill({ contentType: 'image/jpeg', body: fs.readFileSync(IMG) })
  const f = path.join(DIST, path.basename(u))
  return fs.existsSync(f) ? r.fulfill({ contentType: types[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) }) : r.fulfill({ status: 404 })
})
await page.goto('http://bench.local/')
const cdp = await ctx.newCDPSession(page)
await cdp.send('Emulation.setCPUThrottlingRate', { rate: THROTTLE })

const result = await page.evaluate(async ({ RUNS }) => {
  const ort = await import('/ort.all.min.mjs')
  ort.env.wasm.wasmPaths = '/'
  ort.env.wasm.numThreads = self.crossOriginIsolated ? Math.min(4, navigator.hardwareConcurrency || 1) : 1
  const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return Math.round(s[Math.floor(p * (s.length - 1))]) }
  const img = new Image(); img.src = '/img.jpg'; await img.decode()
  const S = 640, cv = document.createElement('canvas'); cv.width = cv.height = S
  const g = cv.getContext('2d', { willReadFrequently: true })
  const pre = () => {             // letterbox to 640 (grey 114) + HWC uint8 -> CHW float32 0..1, like the server
    const k = S / Math.max(img.width, img.height)
    g.fillStyle = 'rgb(114,114,114)'; g.fillRect(0, 0, S, S); g.drawImage(img, 0, 0, img.width * k, img.height * k)
    const d = g.getImageData(0, 0, S, S).data, f = new Float32Array(3 * S * S), n = S * S
    for (let i = 0; i < n; i++) { f[i] = d[i * 4] / 255; f[n + i] = d[i * 4 + 1] / 255; f[2 * n + i] = d[i * 4 + 2] / 255 }
    return new ort.Tensor('float32', f, [1, 3, S, S])
  }
  const post = out => {           // YOLO26 end-to-end output (1, N, 6): x1 y1 x2 y2 score class - keep persons > 0.25
    const t = Object.values(out)[0], d = t.data, rows = t.dims[1], cols = t.dims[2], keep = []
    for (let i = 0; i < rows; i++) { const o = i * cols; if (d[o + 4] > 0.25) keep.push([...d.slice(o, o + 6)].map(v => Math.round(v * 100) / 100)) }
    return { dims: t.dims, boxes: keep }
  }
  // the server path needs a JPEG of the same frame
  const enc = []
  for (let i = 0; i < 10; i++) { const t0 = performance.now(); await new Promise(r => cv.toBlob(r, 'image/jpeg', 0.65)); enc.push(performance.now() - t0) }
  const report = { crossOriginIsolated: self.crossOriginIsolated, threads: ort.env.wasm.numThreads,
                   webgpu_api: !!navigator.gpu, jpeg_encode_ms_p50: q(enc, .5), eps: {} }
  let gpuOk = false
  if (navigator.gpu) { try { gpuOk = !!(await navigator.gpu.requestAdapter()) } catch { gpuOk = false } }
  report.webgpu_adapter = gpuOk
  const buf = await (await fetch('/model.onnx')).arrayBuffer()
  for (const ep of gpuOk ? ['webgpu', 'wasm'] : ['wasm']) {
    const r = {}
    try {
      let t0 = performance.now()
      const sess = await ort.InferenceSession.create(buf, { executionProviders: [ep], graphOptimizationLevel: 'all' })
      r.load_ms = Math.round(performance.now() - t0)
      const pr = [], inf = [], po = []
      let first, last
      for (let i = 0; i < RUNS; i++) {
        t0 = performance.now(); const x = pre(); const t1 = performance.now()
        const out = await sess.run({ [sess.inputNames[0]]: x }); const t2 = performance.now()
        last = post(out); const t3 = performance.now()
        if (i === 0) first = Math.round(t2 - t1); else { pr.push(t1 - t0); inf.push(t2 - t1); po.push(t3 - t2) }
      }
      Object.assign(r, { first_inference_ms: first, infer_p50: q(inf, .5), infer_p95: q(inf, .95), pre_p50: q(pre === null ? [] : pr, .5),
                         post_p50: q(po, .5), fps_model_only: Math.round(1000 / q(inf, .5) * 10) / 10, output: last })
      await sess.release()
    } catch (e) { r.error = String(e).slice(0, 200) }
    report.eps[ep] = r
  }
  return report
}, { RUNS })
console.log(JSON.stringify({ simulated: true, device: DEV, cpu_throttle: THROTTLE, model: path.basename(MODEL),
                             model_mb: Math.round(fs.statSync(MODEL).size / 1e5) / 10, ...result }, null, 1))
await browser.close()
