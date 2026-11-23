/** Which live-socket frame hints belong to a picture path (2026-11-23). */
export function hintMatches(path: string, m: { scope: 'pc' | 'broadcast'; device_id?: number }): boolean {
  if (m.scope === 'broadcast') return path.includes('/broadcast/')
  const id = /\/equipment\/(\d+)\/screen\.jpg/.exec(path)
  return !!id && Number(id[1]) === m.device_id
}

/** Wait before the next ask: 200 ms until the first picture; then `ms`, or a slow safety poll while the live
 *  socket announces new pictures (a hint seen in the last 3 s) - the hint itself triggers the fetch. */
export function nextDelay(got: boolean, ms: number, sinceHintMs: number): number {
  if (!got) return Math.min(ms, 200)
  return sinceHintMs < 3000 ? Math.max(ms, 2500) : ms
}
