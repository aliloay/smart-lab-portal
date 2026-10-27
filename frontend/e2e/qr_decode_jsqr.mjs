// Independent decoder check for the asset markers: jsQR (the decoder the phone page uses when the browser has no
// BarcodeDetector, e.g. iPhone Safari) reads every rendered variant listed in <variants.json>.
//   node e2e/qr_decode_jsqr.mjs <dir with variants.json and the PNGs>
import { readFileSync, writeFileSync } from 'node:fs'
import sharp from 'sharp'
import jsQR from 'jsqr'
const dir = process.argv[2]
const list = JSON.parse(readFileSync(`${dir}/variants.json`, 'utf8'))
for (const v of list) {
  const { data, info } = await sharp(`${dir}/${v.file}`).ensureAlpha().raw().toBuffer({ resolveWithObject: true })
  const r = jsQR(new Uint8ClampedArray(data), info.width, info.height, { inversionAttempts: 'dontInvert' })
  v.jsqr = r?.data === v.code
}
writeFileSync(`${dir}/variants.json`, JSON.stringify(list, null, 1))
const by = {}
for (const v of list) { const k = v.cat; by[k] ??= { n: 0, cv2: 0, jsqr: 0, either: 0, fails: [] }; const b = by[k]; b.n++; b.cv2 += v.cv2; b.jsqr += v.jsqr; b.either += (v.cv2 || v.jsqr); if (!v.jsqr) b.fails.push(v.variant) }
let t = { n: 0, cv2: 0, jsqr: 0, either: 0 }
for (const [k, b] of Object.entries(by)) { console.log(`${k.padEnd(12)} cv2 ${b.cv2}/${b.n}  jsQR ${b.jsqr}/${b.n}  either ${b.either}/${b.n}  jsQR misses: ${b.fails.join(',') || '-'}`); for (const x of ['n', 'cv2', 'jsqr', 'either']) t[x] += b[x] }
console.log(`TOTAL cv2 ${t.cv2}/${t.n} (${(100 * t.cv2 / t.n).toFixed(1)}%)  jsQR ${t.jsqr}/${t.n} (${(100 * t.jsqr / t.n).toFixed(1)}%)  either ${t.either}/${t.n}`)
