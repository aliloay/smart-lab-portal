/**
 * Freezes as the staff's real browsers see them (2026-10-22, owner: "Robots & PCs still freezes" while every
 * test browser measured it smooth). Chrome's Long Animation Frames API names the script and function behind
 * each long frame and how much of it was style / layout. Frames over MIN_MS are sent every FLUSH_MS with what
 * was on screen (page, DOM size, heap, 3D views, camera feeds). Nothing is sent when nothing froze. Browsers
 * without the API (old Chrome, Firefox) do nothing.
 */
import { api } from './api'

const MIN_MS = 150
const FLUSH_MS = 15000

type LoafScript = { invoker?: string; invokerType?: string; sourceFunctionName?: string; sourceURL?: string
  sourceCharPosition?: number; duration: number; forcedStyleAndLayoutDuration?: number }
type Loaf = PerformanceEntry & { blockingDuration?: number; renderStart?: number; styleAndLayoutStart?: number
  scripts?: LoafScript[] }

let started = false

export function startJankProbe() {
  if (started || typeof PerformanceObserver === 'undefined'
      || !PerformanceObserver.supportedEntryTypes?.includes('long-animation-frame')) return
  started = true
  let frames: unknown[] = []
  let count = 0, since = performance.now()
  // frame rate over the window, from requestAnimationFrame (paused by the browser in a hidden tab)
  const tick = () => { count++; requestAnimationFrame(tick) }
  requestAnimationFrame(tick)
  new PerformanceObserver(list => {
    for (const e of list.getEntries() as Loaf[]) {
      if (e.duration < MIN_MS || frames.length >= 60) continue
      const end = e.startTime + e.duration
      frames.push({
        at: Math.round(performance.timeOrigin + e.startTime) / 1000,
        ms: Math.round(e.duration),
        blocking_ms: Math.round(e.blockingDuration ?? 0),
        render_ms: e.renderStart ? Math.round(end - e.renderStart) : 0,
        style_layout_ms: e.styleAndLayoutStart ? Math.round(end - e.styleAndLayoutStart) : 0,
        scripts: (e.scripts ?? []).slice().sort((a, b) => b.duration - a.duration).slice(0, 8).map(s => ({
          invoker: (s.invoker ?? '').slice(0, 200), type: s.invokerType ?? '', fn: (s.sourceFunctionName ?? '').slice(0, 120),
          url: (s.sourceURL ?? '').split('/').pop()?.slice(0, 200) ?? '', char: s.sourceCharPosition ?? 0,
          ms: Math.round(s.duration), forced_layout_ms: Math.round(s.forcedStyleAndLayoutDuration ?? 0) })),
      })
    }
  }).observe({ type: 'long-animation-frame', buffered: false })
  window.setInterval(() => {
    const now = performance.now(), window_s = (now - since) / 1000
    const fps = document.hidden ? null : Math.round((count / Math.max(window_s, 0.001)) * 10) / 10
    const out = frames
    frames = []; count = 0; since = now
    if (!out.length) return
    const mem = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory
    api.uiperfReport({
      page: (location.pathname + location.search).slice(0, 200), build: document.querySelector('script[type=module]')?.getAttribute('src')?.split('/').pop()?.slice(0, 40) ?? '',
      ua: navigator.userAgent.slice(0, 200), dom_nodes: document.getElementsByTagName('*').length,
      heap_mb: mem ? Math.round(mem.usedJSHeapSize / 1e5) / 10 : null,
      canvases: document.querySelectorAll('canvas').length, feeds: document.querySelectorAll('img[alt="Lab camera, live"]').length,
      hidden: document.hidden, window_s: Math.round(window_s * 10) / 10, frames: out, fps,
    }).catch(() => { /* never disturb the page */ })
  }, FLUSH_MS)
}
