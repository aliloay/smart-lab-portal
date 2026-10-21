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
const listeners = new Set<() => void>()
const notify = () => listeners.forEach(f => f())

export const canCaptureHere = () => window.isSecureContext && !!navigator.mediaDevices?.getDisplayMedia
export const isCapturing = () => live
export const pendingPreview = () => (stream && !live ? stream : null)
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
  const video = document.createElement('video')
  video.muted = true
  video.srcObject = stream
  await video.play()
  const canvas = document.createElement('canvas')
  const tick = async () => {
    if (!stream || !live) return
    const vw = video.videoWidth || 1280, vh = video.videoHeight || 720      // follows resolution changes
    const w = Math.min(MAX_W, vw), h = Math.round(w * vh / vw)
    canvas.width = w
    canvas.height = h
    canvas.getContext('2d')?.drawImage(video, 0, 0, w, h)
    const blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/jpeg', 0.6))
    if (blob && live) {
      const st = await uploadBroadcastFrame(blob).catch(() => 0)
      if (st === 409) { stopTracks(); notify(); return }       // stopped elsewhere
    }
    if (live) timer = window.setTimeout(tick, FRAME_MS)
  }
  notify()
  void tick()
}

function stopTracks() {
  window.clearTimeout(timer)
  stream?.getTracks().forEach(t => t.stop())
  stream = null
  live = false
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
 *  The capturing tab learns it on its next frame (409) and releases the screen. */
export async function stopShare(force = false): Promise<void> {
  const wasLive = live
  stopTracks()
  if (wasLive || force) await api.broadcastStop().catch(() => {})
  notify()
}
