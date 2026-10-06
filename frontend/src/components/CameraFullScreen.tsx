/**
 * One lab camera full screen, live with its person boxes. Used by the Live
 * monitor tiles, the monitor's Details window and the Security camera wall.
 * Click the picture or press Esc to close; `actions` (buttons) do not close it.
 */
import { ReactNode, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Maximize, X } from 'lucide-react'
import { BoxesToggle } from '../lib/cameraView'
import LiveCameraFeed, { LIVE_MS } from './LiveCameraFeed'

export default function CameraFullScreen({ deviceId, title, sub, badges, actions, onClose }: {
  deviceId: number
  title: string
  sub?: string | null
  badges?: ReactNode
  actions?: ReactNode
  onClose: () => void
}) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  return createPortal(
    <div ref={box} className="fixed inset-0 z-[64] bg-black flex flex-col" onClick={onClose}
         role="dialog" aria-modal="true" aria-label={`${title} camera`}>
      <div className="flex flex-wrap items-center gap-3 px-5 py-3 text-white">
        <span className="text-xl font-extrabold">{title}</span>
        {sub && <span className="text-slate-400 truncate">{sub}</span>}
        {badges && <div className="ml-2" onClick={e => e.stopPropagation()}>{badges}</div>}
        <div className="ml-auto flex items-center gap-2" onClick={e => e.stopPropagation()}>
          <BoxesToggle dark />
          {actions}
          <button onClick={() => document.fullscreenElement ? document.exitFullscreen().catch(() => {})
                                  : box.current?.requestFullscreen().catch(() => {})}
                  className="inline-flex items-center gap-1 rounded-lg border border-white/30 px-3 py-1.5 text-[13px] text-slate-200 hover:bg-white/10">
            <Maximize size={14} /> Full screen</button>
          <button onClick={onClose}
                  className="inline-flex items-center gap-1 rounded-lg border border-white/30 px-3 py-1.5 text-[13px] text-slate-200 hover:bg-white/10">
            <X size={15} /> Close (Esc)</button>
        </div>
      </div>
      <LiveCameraFeed deviceId={deviceId} intervalMs={LIVE_MS} fit="contain" className="flex-1" />
    </div>,
    document.body)
}
