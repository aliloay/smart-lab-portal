// Independent jsQR check of the 10 delivered marker PNGs (2026-10-27): every file at several sizes and with phone-like
// distortions (blur, rotation, dim light, JPEG). node e2e/qr10_check.mjs <dir with manifest.json + out/*.png>
import { readFileSync, writeFileSync } from 'node:fs'
import sharp from 'sharp'
import jsQR from 'jsqr'
const dir = process.argv[2]
const man = JSON.parse(readFileSync(`${dir}/manifest.json`, 'utf8'))
const V = {
  w1600: s => s.resize(1600), w800: s => s.resize(800), w480: s => s.resize(480), w320: s => s.resize(320),
  blur: s => s.resize(640).blur(1.2), rot12: s => s.resize(640).rotate(12, { background: '#fff' }),
  dim: s => s.resize(640).linear(0.55, 20), jpeg40: s => s.resize(640).jpeg({ quality: 40 }),
}
let ok = 0, n = 0
for (const m of man) {
  const res = {}
  for (const [k, f] of Object.entries(V)) {
    const buf = await f(sharp(`${dir}/out/${m.file}`).flatten({ background: '#fff' })).png().toBuffer()
    const { data, info } = await sharp(buf).ensureAlpha().raw().toBuffer({ resolveWithObject: true })
    const r = jsQR(new Uint8ClampedArray(data), info.width, info.height)
    res[k] = r?.data === m.payload; n++; ok += res[k]
  }
  m.jsqr = res
  console.log(m.file.padEnd(22), m.payload.padEnd(24), Object.entries(res).map(([k, v]) => `${k}:${v ? 'ok' : 'FAIL'}`).join(' '))
}
writeFileSync(`${dir}/manifest.json`, JSON.stringify(man, null, 1))
console.log(`jsQR TOTAL ${ok}/${n}`)
