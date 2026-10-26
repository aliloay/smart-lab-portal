/// <reference lib="webworker" />
/**
 * QR decoding off the main thread for "Scan the lab" (browsers without the native BarcodeDetector,
 * e.g. iPhone Safari). One frame in, one answer out; the page never sends a new frame before the
 * answer, so frames cannot queue up here.
 */
import jsQR from 'jsqr'

type In = { id: number; data: Uint8ClampedArray; w: number; h: number }

self.onmessage = (e: MessageEvent<In>) => {
  const { id, data, w, h } = e.data
  const t0 = performance.now()
  const r = jsQR(data, w, h, { inversionAttempts: 'dontInvert' })
  postMessage({
    id, ms: performance.now() - t0,
    codes: r ? [{ text: r.data, corners: [r.location.topLeftCorner, r.location.topRightCorner,
                                         r.location.bottomRightCorner, r.location.bottomLeftCorner] }] : [],
  })
}
