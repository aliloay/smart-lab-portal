/**
 * The admin's own screen, captured in this browser and sent to the portal ~2 times a second while
 * presenting. Two steps, so the wrong monitor or a private window is never shared by accident:
 *   pickScreen()  - the browser's own picker (screen / window / tab), then a LOCAL preview only;
 *                   nothing leaves this browser yet.
 *   goLive()      - the admin has seen the preview and confirms; only now do frames go out.
 * Module-level, so it keeps running while the admin moves around the portal; it stops on Stop,
 * on "Stop sharing" in the browser bar, or when the tab closes.
 * Screen capture needs a secure page (https://...); on plain http the master-PC source is used.
 */
import { api, getToken, uploadBroadcastFrame } from './api'

const FRAME_MS = 500
const MAX_W = 1280
let stream: MediaStream | null = null
let live = false
let timer = 0
let video: HTMLVideoElement | null = null      // the hidden player frames are drawn from (released on stop)
let sentAt = 0                                  // last frame actually uploaded (0 = none yet)
let liveSince = 0
const listeners = new Set<() => void>()
const notify = () => listeners.forEach(f => f())

export const canCaptureHere = () => window.isSecureContext && !!navigator.mediaDevices?.getDisplayMedia
export const isCapturing = () => live
export const pendingPreview = () => (stream && !live ? stream : null)
/** Live but no picture yet after a few seconds: the chosen window gives none (minimized / closed / blocked). */
export const noPictureYet = () => live && sentAt === 0 && Date.now() - liveSince > 6000
export function onShareChange(f: () => void) { listeners.add(f); return () => { listeners.delete(f) } }

/** Step 1: choose what to share; returns the stream for a local preview. Nothing is sent. */
export async function pickScreen(): Promise<MediaStream> {
  stopTracks()
  // monitorTypeSurfaces / selfBrowserSurface: hint the picker towards windows/tabs, never this portal tab.
  const s = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: 5 }, audio: false, selfBrowserSurface: 'exclude', surfaceSwitching: 'include',
  } as DisplayMediaStreamOptions)
  stream = s
  s.getVideoTracks()[0]?.addEventListener('ended', () => { void stopShare() })
  notify()
  return s
}

/** Step 2: after the admin has seen the preview. */
export async function goLive(title: string, targets: number[] | null): Promise<void> {
  if (!stream) throw new Error('Choose a screen or window first')
  await api.broadcastStart('browser', title, targets)
  live = true
  sentAt = 0
  liveSince = Date.now()
  const v = document.createElement('video')
  video = v
  v.muted = true
  v.playsInline = true
  v.srcObject = stream
  // 2026-10-27: "Waiting for the first frame" forever - `await v.play()` never resolves while the shared
  // window gives no picture (e.g. minimized), so no frame loop ever started. Never block on it: the loop
  // starts at once and uploads as soon as the player has a picture.
  void v.play().catch(() => { /* retried by the loop below */ })
  const canvas = document.createElement('canvas')
  const tick = async () => {
    if (!stream || !live || video !== v) return              // stopped (or a newer share replaced this one)
    if (v.readyState < 2 || !v.videoWidth) {                 // no picture yet: try again shortly
      if (v.paused) void v.play().catch(() => {})
      if (live) { notify(); timer = window.setTimeout(tick, FRAME_MS) }
      return
    }
    const vw = v.videoWidth, vh = v.videoHeight              // follows resolution changes
    const w = Math.min(MAX_W, vw), h = Math.round(w * vh / vw)
    canvas.width = w
    canvas.height = h
    canvas.getContext('2d')?.drawImage(v, 0, 0, w, h)
    const blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/jpeg', 0.6))
    if (blob && live && video === v) {                       // never upload a frame taken before Stop
      const st = await uploadBroadcastFrame(blob).catch(() => 0)
      if (st === 409) { stopTracks(); notify(); return }       // stopped elsewhere
      if (st >= 200 && st < 300) { if (!sentAt) notify(); sentAt = Date.now() }
    }
    if (live) timer = window.setTimeout(tick, FRAME_MS)
  }
  notify()
  void tick()
}

function stopTracks() {
  window.clearTimeout(timer)
  stream?.getTracks().forEach(t => t.stop())
  if (video) { video.pause(); video.srcObject = null }      // release the decoder / last frame too
  video = null
  stream = null
  live = false
}

/** A share_state push (live socket - delivered at once even in a background tab, whose timers Chrome
 *  slows to ~1/min): if this tab is capturing but the portal no longer shows OUR browser share (Stop
 *  pressed in another tab / device, an admin ended it, a new share replaced it), release the screen
 *  now instead of on the next frame upload (409) - up to a minute later in a background tab. */
export async function syncShare(myId: number | null | undefined): Promise<void> {
  if (!live) return
  const st = await api.broadcastStatus().catch(() => null)
  if (!st || !live) return                                   // no answer: keep going (the 409 still stops it)
  if (!st.active || st.source !== 'browser' || (myId != null && st.by_id !== myId)) {
    stopTracks()
    notify()
  }
}

export function cancelPreview() { stopTracks(); notify() }

// Closing / reloading the presenting tab: stop the capture and end the share in the portal right away
// (keepalive lets the request finish while the page unloads), instead of viewers seeing a frozen picture.
window.addEventListener('pagehide', () => {
  if (!live) return
  stopTracks()
  const token = getToken()
  try {
    void fetch('/api/equipment/broadcast/stop', { method: 'POST', keepalive: true,
      headers: token ? { Authorization: `Bearer ${token}` } : {} })
  } catch { /* the portal also ends a silent share by itself */ }
})

/** force: the admin pressed Stop - end the share in the portal even when THIS tab is not the one
 *  capturing (another tab / device, or the master PC). Without it Stop did nothing there (2026-10-21).
 *  The capturing tab learns it from the share_state push (syncShare) or its next frame (409). */
export async function stopShare(force = false): Promise<void> {
  const wasLive = live
  stopTracks()
  if (wasLive || force) await api.broadcastStop().catch(() => {})
  notify()
}
