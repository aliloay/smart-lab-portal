/**
 * Admin -> students screen sharing, and the wall of every lab PC's screen.
 *
 * Share: the admin presents from this browser (needs https) or from the master PC's agent; the
 * students' PCs get a notice and open /share. Wall: every PC's live screen at once; each PC shows
 * "Lab staff are viewing this screen" while it is watched; nothing is recorded.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Cast, LayoutGrid, MonitorPlay, MonitorUp, Square, X } from 'lucide-react'
import { BroadcastState, api, fetchBlob } from '../lib/api'
import { cancelPreview, canCaptureHere, goLive, isCapturing, onShareChange, pendingPreview, pickScreen, stopShare } from '../lib/screenShare'
import { PcScreenViewer } from './PcControls'
import { Chip } from './ui'

/** Live JPEG from an endpoint, refreshed every `ms` (object URLs revoked). */
export function useLiveJpeg(path: string | null, ms: number) {
  const [src, setSrc] = useState<string | null>(null)
  const [at, setAt] = useState<number | null>(null)
  const url = useRef<string | null>(null)
  useEffect(() => {
    if (!path) { setSrc(null); return }
    let stop = false
    let t = 0
    let got = false                       // until the first frame arrives, ask every 200 ms
    const tick = async () => {
      try {
        const b = await fetchBlob(path)
        if (!stop && b.size > 0) {
          const u = URL.createObjectURL(b)
          if (url.current) URL.revokeObjectURL(url.current)
          url.current = u
          setSrc(u)
          setAt(Date.now())
          got = true
        }
      } catch { /* shown as stale */ }
      if (!stop) t = window.setTimeout(tick, got ? ms : Math.min(ms, 200))
    }
    void tick()
    return () => {
      stop = true
      window.clearTimeout(t)
      if (url.current) URL.revokeObjectURL(url.current)
      url.current = null
    }
  }, [path, ms])
  return { src, stale: at === null || Date.now() - at > 5000 }
}

export function SharePanel({ hasMasterPc, pcs = [] }: { hasMasterPc: boolean; pcs?: { id: number; name: string; online: boolean }[] }) {
  const [st, setSt] = useState<BroadcastState | null>(null)
  const [title, setTitle] = useState('')
  const [all, setAll] = useState(true)
  const [chosen, setChosen] = useState<number[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [, force] = useState(0)
  const preview = useRef<HTMLVideoElement>(null)
  const load = useCallback(() => { api.broadcastStatus().then(setSt).catch(() => {}) }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 3000)
    const off = onShareChange(() => { force(n => n + 1); load() })
    return () => { window.clearInterval(t); off() }
  }, [load])
  const pending = pendingPreview()
  useEffect(() => { if (preview.current) preview.current.srcObject = pending }, [pending])
  const { src } = useLiveJpeg(st?.active ? '/equipment/broadcast/frame.jpg' : null, 1000)
  const targets = all ? null : chosen
  const go = async (fn: () => Promise<unknown>) => {
    if (busy) return                                   // no double starts
    setBusy(true)
    setError('')
    try { await fn() } catch (e) { setError(e instanceof Error ? e.message : 'Could not start sharing') }
    finally { setBusy(false); load() }
  }
  const secure = canCaptureHere()
  const noTargets = !all && chosen.length === 0
  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm">
        <Cast size={15} className="text-accent-300" />
        <span className="font-medium text-slate-200">Share my screen with the students</span>
        {st?.active
          ? <Chip tone="ok" dot className="ml-auto">presenting · {st.by} · {st.source === 'browser' ? 'browser' : 'master PC'} · {st.targets ? `${st.targets.length} PC(s)` : 'all lab PCs'}</Chip>
          : <Chip tone="idle" className="ml-auto">not sharing</Chip>}
      </div>
      {!st?.active && <>
        <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
          <span className="text-slate-400">Send to:</span>
          <label className="flex items-center gap-1"><input type="radio" checked={all} onChange={() => setAll(true)} /> all lab PCs</label>
          <label className="flex items-center gap-1"><input type="radio" checked={!all} onChange={() => setAll(false)} /> selected PCs</label>
          {!all && pcs.map(p => <label key={p.id} className={`flex items-center gap-1 px-2 py-0.5 rounded border ${chosen.includes(p.id) ? 'border-accent-400/60' : 'border-ink-600'}`}>
            <input type="checkbox" checked={chosen.includes(p.id)} onChange={e => setChosen(c => e.target.checked ? [...c, p.id] : c.filter(x => x !== p.id))} />
            {p.name}{!p.online && <span className="text-slate-500"> (offline)</span>}</label>)}
          {!all && pcs.length === 0 && <span className="text-slate-500">no PC agent has reported yet</span>}
        </div>
        {!pending ? (
          <div className="flex flex-wrap items-center gap-2">
            <input className="input !py-1.5 !text-[13px] w-56" placeholder="Title (optional), e.g. PLC demo" value={title}
                   maxLength={80} onChange={e => setTitle(e.target.value)} />
            <button className="btn-primary btn-sm" disabled={busy || !secure} onClick={() => go(pickScreen)}
                    title={secure ? '' : 'Screen capture needs the secure address: https://192.168.1.200'}>
              <MonitorUp size={14} /> Choose screen or window…</button>
            <button className="btn-ghost btn-sm" disabled={busy || !hasMasterPc || noTargets}
                    onClick={() => go(() => api.broadcastStart('master_pc', title, targets))}
                    title={hasMasterPc ? '' : 'Mark the admin PC as master PC first'}><MonitorPlay size={14} /> Share from master PC</button>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-[12.5px] text-warn-soft">Preview - only you can see this. Check it is the right screen or window and that nothing private
              (passwords, e-mail, chats) is visible, then go live.</p>
            <video ref={preview} autoPlay muted playsInline className="rounded-lg border border-warn/50 max-w-md w-full aspect-video bg-black object-contain" />
            <div className="flex gap-2">
              <button className="btn-primary btn-sm" disabled={busy || noTargets} onClick={() => go(() => goLive(title, targets))}><Cast size={13} /> Go live</button>
              <button className="btn-ghost btn-sm" disabled={busy} onClick={() => go(() => pickScreen())}>Choose another</button>
              <button className="btn-ghost btn-sm" disabled={busy} onClick={() => cancelPreview()}>Cancel</button>
            </div>
          </div>
        )}
      </>}
      {st?.active && (
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-ghost btn-sm text-bad-soft border border-bad/40" disabled={busy} onClick={() => go(stopShare)}>
            <Square size={13} /> Stop sharing</button>
          <a className="btn-ghost btn-sm" href="/share" target="_blank" rel="noreferrer">Open the students' view</a>
          {st.source === 'browser' && !isCapturing() &&
            <span className="text-[12px] text-warn-soft">This browser is not the one capturing (another tab or device started it).</span>}
        </div>
      )}
      {!secure && !st?.active && <div className="flex flex-wrap items-center gap-2 text-[11.5px] text-slate-400">
        <span>Browsers allow screen capture only on the secure address. Sharing from the master PC works from here.</span>
        <a className="btn-ghost btn-sm" href={`https://${window.location.hostname}${window.location.pathname}${window.location.search}`}>
          Switch to https://{window.location.hostname}</a>
        <span className="text-slate-500">(a warning there means this computer does not trust the lab certificate yet: import
          deploy/tls/smartlab-ca.crt once)</span></div>}
      {st?.active && <div className="rounded-lg overflow-hidden border border-ink-600 bg-black/40 max-w-md aspect-video grid place-items-center">
        {src ? <img src={src} alt="What the students see" className="w-full h-full object-contain" />
          : <span className="text-[12px] text-slate-400">Waiting for the first frame…</span>}</div>}
      <p className="text-[11px] text-slate-500">The chosen PCs (with the lab agent) get a notice and open the presentation in their browser;
        anyone signed in can also open /share. Nothing is recorded.</p>
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}
    </div>
  )
}

export type WallPc = { device_id: number; name: string; online: boolean | null; detail?: Record<string, unknown> | null }

function WallTile({ pc, onOpen }: { pc: WallPc; onOpen: () => void }) {
  const { src, stale } = useLiveJpeg(pc.online === false ? null : `/equipment/${pc.device_id}/screen.jpg`, 1000)
  const app = pc.detail?.foreground_app ? String(pc.detail.foreground_app).replace(/\.exe$/i, '') : null
  const user = pc.detail?.os_user ? String(pc.detail.os_user) : null
  return (
    <button type="button" onClick={onOpen} className="text-left rounded-xl border border-ink-600 bg-ink-900/60 overflow-hidden hover:border-accent-400/60">
      <div className="aspect-video bg-black/50 grid place-items-center">
        {pc.online === false ? <span className="text-[12px] text-slate-500">offline</span>
          : src ? <img src={src} alt={`Screen of ${pc.name}`} className={`w-full h-full object-contain ${stale ? 'opacity-50' : ''}`} />
          : <span className="text-[12px] text-slate-400">connecting…</span>}
      </div>
      <div className="px-2.5 py-1.5 text-[12px] flex items-center gap-2">
        <b className="text-slate-100 truncate">{pc.name}</b>
        <span className="text-slate-400 truncate">{user ?? 'nobody signed in'}{app ? ` · ${app}` : ''}</span>
        {stale && src && <Chip tone="warn" className="ml-auto">stale</Chip>}
      </div>
    </button>
  )
}

export function ScreenWall({ pcs, onClose }: { pcs: WallPc[]; onClose: () => void }) {
  const [open, setOpen] = useState<WallPc | null>(null)
  useEffect(() => {
    pcs.forEach(p => { if (p.online !== false) api.pcScreenStart(p.device_id).catch(() => {}) })
    return () => { pcs.forEach(p => api.pcScreenStop(p.device_id).catch(() => {})) }
  }, [pcs])
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape' && !open) onClose() }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose, open])
  return createPortal(
    <div className="fixed inset-0 z-50 bg-ink-950/95 backdrop-blur p-5 overflow-auto">
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <LayoutGrid size={18} className="text-accent-300" />
        <h2 className="text-white font-semibold text-lg">All lab PC screens</h2>
        <span className="text-[12px] text-slate-400">Each PC shows a notice while it is viewed · nothing is recorded · click a screen to enlarge</span>
        <button className="btn-ghost btn-sm ml-auto" onClick={onClose}><X size={14} /> Close</button>
      </div>
      {pcs.length === 0 ? <p className="text-slate-400">No lab PC is reporting.</p> :
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {pcs.map(p => <WallTile key={p.device_id} pc={p} onOpen={() => setOpen(p)} />)}
        </div>}
      {open && <PcScreenViewer deviceId={open.device_id} name={open.name} onClose={() => setOpen(null)} />}
    </div>, document.body)
}
