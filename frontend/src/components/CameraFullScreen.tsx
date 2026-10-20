/**
 * One lab camera full screen, live with its person boxes. Used by the Live
 * monitor tiles, the monitor's Details window and the Security camera wall.
 * Click the picture or press Esc to close; `actions` (buttons) do not close it.
 * `cameras`: every camera of the same lab - a switcher shows each one, or all side by side.
 */
import { ReactNode, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Maximize, X } from 'lucide-react'
import { BoxesToggle } from '../lib/cameraView'
import LiveCameraFeed, { LIVE_MS } from './LiveCameraFeed'

export default function CameraFullScreen({ deviceId, title, sub, badges, actions, onClose, cameras }: {
  deviceId: number
  cameras?: { id: number; label: string }[]
  title: string
  sub?: string | null
  badges?: ReactNode
  actions?: ReactNode
  onClose: () => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState<number | 'all'>(deviceId)
  useEffect(() => setShown(deviceId), [deviceId])
  const multi = (cameras?.length ?? 0) > 1
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
          {multi && <div className="flex rounded-lg border border-white/30 overflow-hidden text-[13px]" role="tablist" aria-label="Camera">
            {[...cameras!.map(c => ({ k: c.id as number | 'all', l: c.label })), { k: 'all' as const, l: 'Both' }].map(o => (
              <button key={String(o.k)} role="tab" aria-selected={shown === o.k} onClick={() => setShown(o.k)}
                      className={`px-3 py-1.5 ${shown === o.k ? 'bg-cyan-500/30 text-white' : 'text-slate-300 hover:bg-white/10'}`}>{o.l}</button>))}
          </div>}
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
      {shown === 'all' && multi
        ? <div className="flex-1 grid grid-rows-1 md:grid-cols-2 gap-1 min-h-0">
            {cameras!.map(c => <div key={c.id} className="relative h-full min-h-0">
              <LiveCameraFeed deviceId={c.id} intervalMs={LIVE_MS} fit="contain" className="!absolute inset-0" />
              <span className="absolute left-2 top-2 rounded-md bg-black/70 px-2 py-0.5 text-[12px] font-semibold text-white">{c.label}</span>
            </div>)}
          </div>
        : <LiveCameraFeed deviceId={shown === 'all' ? deviceId : shown} intervalMs={LIVE_MS} fit="contain" className="flex-1" />}
    </div>,
    document.body)
}
