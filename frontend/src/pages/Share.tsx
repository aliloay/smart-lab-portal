/** The students' view of a screen shared by lab staff (any signed-in user). Nothing is recorded. */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Cast, Maximize2, MonitorUp, Square } from 'lucide-react'
import { BroadcastState, api } from '../lib/api'
import { useLiveJpeg } from '../components/ScreenShare'
import { useLiveMessages } from '../lib/live'
import { agentProof } from '../lib/master'

export default function Share() {
  const [st, setSt] = useState<BroadcastState | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const load = useCallback(() => { api.broadcastStatus().then(setSt).catch(() => {}) }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 1500)            // a new share appears within 1.5 s
    return () => window.clearInterval(t)
  }, [load])
  // A student asks to share their lab PC's screen; an admin accepts first (2026-10-21).
  const [mine, setMine] = useState<Awaited<ReturnType<typeof api.shareMine>> | null>(null)
  const [askErr, setAskErr] = useState('')
  const loadMine = useCallback(() => { api.shareMine().then(setMine).catch(() => {}) }, [])
  useEffect(() => { loadMine(); const t = window.setInterval(loadMine, 3000); return () => window.clearInterval(t) }, [loadMine])
  useLiveMessages(m => { if (m.type === 'share_state') { load(); loadMine() } })
  const ask = async () => {
    setAskErr('')
    try {
      const { nonce } = await api.shareNonce()
      await api.shareAsk({ nonce, ...(await agentProof(nonce)) })
      loadMine()
    } catch (e) { setAskErr(e instanceof Error ? e.message : 'Could not send the request') }
  }
  const myReq = mine?.request
  // the frame stream itself says when the share ended (410): the picture goes within ~0.5 s
  const ended = useCallback(() => { setSt(s => (s ? { ...s, active: false } : s)); load() }, [load])
  const { src, stale } = useLiveJpeg(st?.active ? `/equipment/broadcast/frame.jpg?s=${st.since ?? 0}` : null, 500, ended)
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
      <div className="card p-3 flex flex-wrap items-center gap-2 text-[13px]">
        <MonitorUp size={15} className="text-violet-300" />
        {mine?.presenting
          ? <><span className="text-white">You are presenting this PC's screen.</span>
              <button className="btn-ghost btn-sm text-bad-soft border border-bad/40 ml-auto"
                      onClick={() => api.shareStopMine().then(() => { load(); loadMine() })}><Square size={13} /> Stop presenting</button></>
          : myReq?.status === 'PENDING'
            ? <span className="text-slate-300">Waiting for the administrator to accept your request to share <b className="text-white">{myReq.pc_name}</b>...</span>
            : <><span className="text-slate-300">Want to show your screen to the class or the administrator?</span>
                <button className="btn-ghost btn-sm ml-auto" onClick={ask}><MonitorUp size={13} /> Ask to share my screen</button>
                {myReq?.status === 'REJECTED' && <span className="text-[12px] text-bad-soft w-full">Your last request was declined.</span>}</>}
        {askErr && <span className="text-[12px] text-bad-soft w-full">{askErr}</span>}
      </div>
    </div>
  )
}
