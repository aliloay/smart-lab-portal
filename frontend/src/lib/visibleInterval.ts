/**
 * Polling for ordinary data views: a hidden tab asks the server nothing (audit 2026-11-04: 60+ timers kept polling from
 * background tabs), and a tab that comes back refreshes within 2 s instead of waiting a whole period. Returns a normal
 * interval id: clear it with window.clearInterval. NOT for anything that must keep running in a background tab:
 * alarms, emergency messages, the screen-share capture.
 */
export function visibleInterval(fn: () => void, ms: number): number {
  let last = Date.now()
  return window.setInterval(() => {
    if (document.hidden) return
    const now = Date.now()
    if (now - last >= ms - 50) {
      last = now
      fn()
    }
  }, Math.min(ms, 2000))
}
