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

export default function LiveCameraFeed({ deviceId, intervalMs = 200, raw = false, className = '',
                                         fit = 'cover', children, onFrame }: {
  deviceId: number
  /** Pause between frames; ~200 ms = up to 5 frames a second. */
  intervalMs?: number
  /** The plain frame (no boxes), for drawing zones. */
  raw?: boolean
  className?: string
  fit?: 'cover' | 'contain'
  children?: ReactNode
  onFrame?: (w: number, h: number) => void
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [state, setState] = useState<'loading' | 'live' | 'nodata' | 'error'>('loading')
  const urlRef = useRef<string | null>(null)

  useEffect(() => {
    let stop = false, timer = 0
    async function tick() {
      try {
        const blob = await fetchBlob(`/security/cameras/${deviceId}/frame.jpg${raw ? '?raw=true' : ''}`)
        if (stop) return
        if (blob.size > 0) {
          const url = URL.createObjectURL(blob)
          if (urlRef.current) URL.revokeObjectURL(urlRef.current)
          urlRef.current = url
          setSrc(url)
          setState('live')
        } else setState('nodata')
      } catch {
        if (!stop) setState('error')
      }
      // Hidden tab: slow right down.
      if (!stop) timer = window.setTimeout(tick, document.hidden ? 2000 : intervalMs)
    }
    tick()
    return () => {
      stop = true
      window.clearTimeout(timer)
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
  }, [deviceId, intervalMs, raw])

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
              : 'Camera service not running'}
          </div>
        </div>)}
      {children}
    </div>
  )
}
