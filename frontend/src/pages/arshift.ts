// 2026-11-21 (audit F-15): object boxes come from ONE frame sent to the server, so while the phone moves they stayed
// where the object WAS. A tiny grey copy of that frame is kept; ~8x a second the view's shift since then is estimated
// (sum of absolute differences over small offsets) and the boxes follow it. Past SHIFT_HIDE of the view, or for a
// poor match, the boxes are hidden instead of pointing at the wrong thing.
export const SHIFT_W = 64, SHIFT_H = 48, SHIFT_MAX_X = 10, SHIFT_MAX_Y = 8, SHIFT_HIDE = 0.3, SHIFT_EVERY_MS = 120
export function grayThumb(src: CanvasImageSource, sx: number, sy: number, sw: number, sh: number, c?: HTMLCanvasElement): Uint8Array | null {
  const g = c ?? document.createElement('canvas'); g.width = SHIFT_W; g.height = SHIFT_H
  const ctx = g.getContext('2d', { willReadFrequently: true }); if (!ctx) return null
  ctx.drawImage(src, sx, sy, sw, sh, 0, 0, SHIFT_W, SHIFT_H)
  const d = ctx.getImageData(0, 0, SHIFT_W, SHIFT_H).data, out = new Uint8Array(SHIFT_W * SHIFT_H)
  for (let i = 0, j = 0; i < out.length; i++, j += 4) out[i] = (d[j] * 77 + d[j + 1] * 150 + d[j + 2] * 29) >> 8
  return out
}
/** Shift (fractions of the view) that best maps the reference thumb onto the current one, and the match error. */
export function estimateShift(ref: Uint8Array, cur: Uint8Array): { dx: number; dy: number; err: number } {
  let best = { dx: 0, dy: 0, err: Infinity }
  for (let oy = -SHIFT_MAX_Y; oy <= SHIFT_MAX_Y; oy++) for (let ox = -SHIFT_MAX_X; ox <= SHIFT_MAX_X; ox++) {
    let s = 0, n = 0
    for (let y = Math.max(0, -oy); y < Math.min(SHIFT_H, SHIFT_H - oy); y += 2) {
      const r = y * SHIFT_W, c = (y + oy) * SHIFT_W
      for (let x = Math.max(0, -ox); x < Math.min(SHIFT_W, SHIFT_W - ox); x += 2) { s += Math.abs(ref[r + x] - cur[c + x + ox]); n++ }
    }
    const e = n ? s / n : Infinity
    if (e < best.err) best = { dx: ox / SHIFT_W, dy: oy / SHIFT_H, err: e }
  }
  return best
}
