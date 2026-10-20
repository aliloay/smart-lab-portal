/** The students' view of a screen shared by lab staff (any signed-in user). Nothing is recorded. */
import { useEffect, useRef, useState } from 'react'
import { Cast, Maximize2 } from 'lucide-react'
import { BroadcastState, api } from '../lib/api'
import { useLiveJpeg } from '../components/ScreenShare'

export default function Share() {
  const [st, setSt] = useState<BroadcastState | null>(null)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const load = () => { api.broadcastStatus().then(setSt).catch(() => {}) }
    load()
    const t = window.setInterval(load, 3000)
    return () => window.clearInterval(t)
  }, [])
  const { src, stale } = useLiveJpeg(st?.active ? '/equipment/broadcast/frame.jpg' : null, 500)
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Cast size={18} className="text-accent-300" />
        <h1 className="text-white text-xl font-semibold">
          {st?.active ? `${st.by} is sharing their screen${st.title ? ` - ${st.title}` : ''}` : 'Shared screen'}</h1>
        {st?.active && <button className="btn-ghost btn-sm ml-auto" onClick={() => box.current?.requestFullscreen?.()}>
          <Maximize2 size={14} /> Full screen</button>}
      </div>
      <div ref={box} className="rounded-xl overflow-hidden border border-ink-600 bg-black aspect-video grid place-items-center">
        {!st ? <span className="text-slate-400">Loading…</span>
          : !st.active ? <span className="text-slate-400">Nothing is being shared right now. This page updates by itself.</span>
          : src ? <img src={src} alt="Shared screen" className={`w-full h-full object-contain ${stale ? 'opacity-60' : ''}`} />
          : <span className="text-slate-400">Connecting to the presenter…</span>}
      </div>
      {st?.active && stale && src && <p className="text-[12px] text-warn-soft">The picture is not updating - the presenter's connection may have dropped.</p>}
    </div>
  )
}
