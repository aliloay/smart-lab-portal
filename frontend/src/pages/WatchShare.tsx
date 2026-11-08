/** A shared screen on a lab PC without a portal sign-in (2026-11-03). The PC agent opens /share?t=<watch
 *  token> (from its device key); the token only reads the share's status and picture - nothing else. */
import { useEffect, useRef, useState } from 'react'
import { Cast, Maximize2 } from 'lucide-react'

type St = { active: boolean; by?: string | null; title?: string; since?: number | null }

export default function WatchShare({ token }: { token: string }) {
  const [st, setSt] = useState<St | null>(null)
  const [err, setErr] = useState('')
  const [n, setN] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const q = `t=${encodeURIComponent(token)}`
  useEffect(() => {
    let alive = true
    const load = () => fetch(`/api/equipment/broadcast/watch/status?${q}`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error(r.status === 401 ? 'This watch link expired - it renews by itself with the next share.' : `status ${r.status}`)))
      .then(s => { if (alive) { setSt(s); setErr('') } })
      .catch(e => { if (alive) setErr(e.message) })
    load()
    const t = window.setInterval(load, 1500)
    return () => { alive = false; window.clearInterval(t) }
  }, [q])
  useEffect(() => {                                     // the picture: a new frame twice a second
    if (!st?.active) return
    const t = window.setInterval(() => setN(x => x + 1), 500)
    return () => window.clearInterval(t)
  }, [st?.active])
  return (
    <div className="min-h-screen p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Cast size={18} className="text-accent-300" />
        <h1 className="text-white text-xl font-semibold">
          {st?.active ? `${st.by ?? 'Lab staff'} is sharing their screen${st.title ? ` - ${st.title}` : ''}` : 'Shared screen'}</h1>
        {st?.active && <button className="btn-ghost btn-sm ml-auto" onClick={() => box.current?.requestFullscreen?.()}>
          <Maximize2 size={14} /> Full screen</button>}
      </div>
      <div ref={box} className="rounded-xl overflow-hidden border border-ink-600 bg-black h-[calc(100vh-120px)] min-h-[320px] grid place-items-center">
        {err ? <span className="text-warn-soft">{err}</span>
          : !st ? <span className="text-slate-400">Loading...</span>
          : !st.active ? <span className="text-slate-400">Nothing is being shared right now. This page updates by itself.</span>
          : <img src={`/api/equipment/broadcast/watch/frame.jpg?${q}&s=${st.since ?? 0}&n=${n}`} alt="Shared screen"
                 className="w-full h-full object-contain" />}
      </div>
    </div>
  )
}
