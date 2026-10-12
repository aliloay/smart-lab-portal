/**
 * A lab's security camera, live, through the portal (staff only).
 *
 * Frames are fetched one after another (the next request only once the
 * previous frame arrived), so a slow link lowers the frame rate instead of
 * piling up requests. The stream itself is never exposed on the network: the
 * portal fetches each frame from the laptop's vision service.
 */
import { ReactNode, useEffect, useRef, useState } from 'react'
import { VideoOff } from 'lucide-react'
import { fetchBlob } from '../lib/api'
import { useBoxesShown } from '../lib/cameraView'

/** Pause for a big live view: one frame takes ~40 ms through the portal and
 *  the service draws 15 a second, so this shows ~12-15 pictures a second. */
export const LIVE_MS = 40

export default function LiveCameraFeed({ deviceId, intervalMs = 200, raw, className = '',
                                         fit = 'cover', children, onFrame }: {
  deviceId: number
  /** Pause between frames; ~200 ms = up to 5 frames a second. */
  intervalMs?: number
  /** true = always the plain frame (drawing zones); unset = the viewer's Detection boxes switch. */
  raw?: boolean
  className?: string
  fit?: 'cover' | 'contain'
  children?: ReactNode
  onFrame?: (w: number, h: number) => void
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [state, setState] = useState<'loading' | 'live' | 'nodata' | 'error'>('loading')
  const urlRef = useRef<string | null>(null)
  const [boxes] = useBoxesShown()
  const plain = raw ?? !boxes

  useEffect(() => {
    let stop = false, timer = 0
    async function tick() {
      let ok = false
      try {
        const blob = await fetchBlob(`/security/cameras/${deviceId}/frame.jpg${plain ? '?raw=true' : ''}`)
        if (stop) return
        if (blob.size > 0) {
          const url = URL.createObjectURL(blob)
          if (urlRef.current) URL.revokeObjectURL(urlRef.current)
          urlRef.current = url
          setSrc(url)
          setState('live')
          ok = true
        } else setState('nodata')
      } catch {
        if (!stop) setState('error')
      }
      // Hidden tab, or no picture (service down / camera offline): wait 3 s
      // between tries instead of hammering the portal 15 times a second.
      if (!stop) timer = window.setTimeout(tick, document.hidden ? 2000 : ok ? intervalMs : Math.max(intervalMs, 3000))
    }
    tick()
    return () => {
      stop = true
      window.clearTimeout(timer)
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
  }, [deviceId, intervalMs, plain])

  return (
    <div className={`relative overflow-hidden bg-black ${className}`}>
      {src && <img src={src} alt="Lab camera, live" draggable={false}
                   onLoad={e => onFrame?.(e.currentTarget.naturalWidth, e.currentTarget.naturalHeight)}
                   className={`absolute inset-0 w-full h-full ${fit === 'cover' ? 'object-cover' : 'object-contain'}
                               ${state === 'live' ? '' : 'opacity-40'}`} />}
      {state !== 'live' && (
        <div className="absolute inset-0 grid place-items-center text-center p-3 text-slate-400 text-[12.5px]">
          <div className="flex flex-col items-center gap-1.5">
            <VideoOff size={20} className="text-slate-500" />
            {state === 'loading' ? 'Connecting to the camera…'
              : state === 'nodata' ? 'Camera is not sending pictures'
              : 'Camera frame request failed'}
          </div>
        </div>)}
      {children}
    </div>
  )
}
