/**
 * Admin master PC controls for one lab PC (System 1): live screen view and a
 * message to the person at it. Lock / unlock (remove / give access) is the
 * PC's mode, set in NetworkedEquipment.
 *
 * The screen view exists only while this viewer is open: each frame request
 * tells the portal someone is watching; the agent on the PC shows a notice
 * and sends frames until ~6 s after the viewer closes. Nothing is recorded.
 */
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { MessageSquare, MonitorPlay, X } from 'lucide-react'
import { api, fetchBlob } from '../lib/api'
import { Modal } from './ui'

const FRAME_MS = 500

export function PcScreenViewer({ deviceId, name, onClose }: {
  deviceId: number; name: string; onClose: () => void
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [updated, setUpdated] = useState<number | null>(null)
  const urlRef = useRef<string | null>(null)

  useEffect(() => {
    let stop = false
    let timer = 0
    api.pcScreenStart(deviceId).catch(e => setError(String(e.message ?? e)))
    async function tick() {
      try {
        const blob = await fetchBlob(`/equipment/${deviceId}/screen.jpg`)
        if (!stop && blob.size > 0) {
          const url = URL.createObjectURL(blob)
          if (urlRef.current) URL.revokeObjectURL(urlRef.current)
          urlRef.current = url
          setSrc(url)
          setUpdated(Date.now())
          setError(null)
        }
      } catch (e) {
        if (!stop) setError(e instanceof Error ? e.message : String(e))
      }
      if (!stop) timer = window.setTimeout(tick, FRAME_MS)
    }
    tick()
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', k)
    return () => {
      stop = true
      window.clearTimeout(timer)
      window.removeEventListener('keydown', k)
      api.pcScreenStop(deviceId).catch(() => {})
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    }
  }, [deviceId, onClose])

  const stale = updated !== null && Date.now() - updated > 4000
  // Portal to <body>: an animated page wrapper (transform) would otherwise
  // pin this "fixed" overlay to the page area instead of the whole window.
  return createPortal(
    <div className="fixed inset-0 z-[60] bg-ink-950 flex flex-col" role="dialog" aria-modal="true">
      <div className="flex items-center gap-3 px-5 py-3 border-b border-ink-600">
        <MonitorPlay size={16} className="text-accent-300" />
        <div className="text-white font-semibold">{name}: screen</div>
        <span className="text-[12px] text-slate-400">
          View only. The person at the PC sees a notice; nothing is recorded.</span>
        <button onClick={onClose} className="btn-ghost btn-sm ml-auto"><X size={14} /> Close</button>
      </div>
      <div className="flex-1 grid place-items-center p-4 min-h-0">
        {src ? (
          <img src={src} alt={`Screen of ${name}`}
               className={`max-w-full max-h-full object-contain rounded-lg border border-ink-600 ${stale ? 'opacity-50' : ''}`} />
        ) : (
          <div className="text-slate-400 text-[14px] text-center max-w-md">
            {error ?? <>Waiting for {name}… The agent on the PC starts sending within about 2 seconds.
              If nothing appears, the agent is not running in the signed-in session or the PC is locked.</>}
          </div>
        )}
      </div>
      {stale && <div className="text-center text-warn-soft text-[12.5px] pb-3">
        No new frame for a few seconds: the PC may be locked, asleep or off.</div>}
    </div>,
    document.body)
}

const PRESETS = [
  'Please save your work: your session ends in 5 minutes.',
  'The exam starts now. Close all other programs.',
  'Please come to the lab desk.',
]

export function PcMessageModal({ deviceId, name, open, onClose }: {
  deviceId: number; name: string; open: boolean; onClose: () => void
}) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)
  useEffect(() => { if (open) { setText(''); setResult(null) } }, [open])

  async function send() {
    setBusy(true)
    try {
      await api.pcMessage(deviceId, text.trim())
      setResult({ ok: true, text: 'Sent. It pops up on the PC within about 2 seconds.' })
      setText('')
    } catch (e) {
      setResult({ ok: false, text: e instanceof Error ? e.message : String(e) })
    } finally { setBusy(false) }
  }

  return (
    <Modal open={open} onClose={onClose} title={<span className="flex items-center gap-2">
      <MessageSquare size={15} /> Message to {name}</span>}
      footer={<>
        <button className="btn-ghost" onClick={onClose}>Close</button>
        <button className="btn-primary" disabled={busy || !text.trim()} onClick={send}>Send</button>
      </>}>
      <div className="space-y-3">
        <textarea className="input w-full min-h-[90px]" maxLength={200} value={text}
                  placeholder="Shown in a pop-up on the PC" onChange={e => setText(e.target.value)} />
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map(p => (
            <button key={p} className="btn-quiet btn-sm !text-[11.5px]" onClick={() => setText(p)}>{p}</button>))}
        </div>
        {result && <div className={`text-[12.5px] ${result.ok ? 'text-ok-soft' : 'text-bad-soft'}`}>{result.text}</div>}
      </div>
    </Modal>
  )
}
