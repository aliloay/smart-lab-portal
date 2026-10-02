/**
 * Face ID enrollment inside Users & roles -> Edit user.
 *
 * Staff stand the person in front of the door camera, watch the live view
 * here and capture samples (one at a time, or automatically). "Finish"
 * retrains the face server and marks Face ID as registered. The portal only
 * relays to the camera and the face server; it stores no biometric. The
 * camera's own page is linked for anything done there by hand.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, CheckCircle2, ExternalLink, Pause, Play, ScanFace } from 'lucide-react'
import { FaceStatus, api, fetchBlob } from '../lib/api'
import { fmtDateTime } from '../lib/time'
import { ErrorBanner, ProgressBar, Spinner } from './ui'

// Pause between automatic captures: time to turn the head slightly, so the
// samples differ (angle, expression) instead of being one frame 20 times.
const AUTO_GAP_MS = 900

export default function FaceEnrollment({ userId, savedSubject, onEnrolled }: {
  userId: number
  /** The door identity as saved on the server; captures need one. */
  savedSubject: string | null
  onEnrolled: () => void
}) {
  const [st, setSt] = useState<FaceStatus | null>(null)
  const [open, setOpen] = useState(false)
  const [frame, setFrame] = useState<string | null>(null)
  const [cameraError, setCameraError] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [auto, setAuto] = useState(false)
  const [done, setDone] = useState(false)
  const autoRef = useRef(false)

  const load = useCallback(() => {
    api.faceStatus(userId).then(setSt).catch(e => setError(e.message))
  }, [userId])
  useEffect(load, [load])

  // Live view: one frame about every 0.8 s while the panel is open.
  useEffect(() => {
    if (!open) return
    let stop = false, url: string | null = null, timer: number | undefined
    const tick = async () => {
      try {
        const blob = await fetchBlob('/enrollment/camera/snapshot')
        if (stop) return
        const next = URL.createObjectURL(blob)
        setFrame(next)
        if (url) URL.revokeObjectURL(url)
        url = next
        setCameraError('')
      } catch (e) {
        if (!stop) setCameraError(e instanceof Error ? e.message : 'Camera not reachable')
      }
      if (!stop) timer = window.setTimeout(tick, 800)
    }
    tick()
    return () => { stop = true; window.clearTimeout(timer); if (url) URL.revokeObjectURL(url) }
  }, [open])

  useEffect(() => () => { autoRef.current = false }, [])

  async function captureOnce(): Promise<boolean> {
    try {
      const r = await api.faceCapture(userId)
      setMsg(r.message)
      setError('')
      if (r.samples !== null) setSt(s => s && { ...s, samples: r.samples ?? s.samples,
                                                  has_photo: s.has_photo || r.saved })
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Capture failed')
      return false
    }
  }

  async function capture() {
    setBusy(true)
    await captureOnce()
    setBusy(false)
  }

  async function startAuto() {
    if (!st) return
    autoRef.current = true
    setAuto(true)
    let samples = st.samples
    while (autoRef.current && samples < st.target_samples) {
      const ok = await captureOnce()
      if (!ok) break
      samples = await api.faceStatus(userId).then(s => { setSt(s); return s.samples })
        .catch(() => samples + 1)
      await new Promise(r => window.setTimeout(r, AUTO_GAP_MS))
    }
    autoRef.current = false
    setAuto(false)
  }

  async function finish() {
    autoRef.current = false
    setBusy(true); setError('')
    try {
      const r = await api.faceFinish(userId)
      setDone(true)
      setMsg(`Trained with ${r.samples} samples. Face ID is registered${
        r.has_photo ? ' and the photo will show on ACCESS GRANTED' : ''}.`)
      setOpen(false)
      load()
      onEnrolled()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Training failed')
    } finally { setBusy(false) }
  }

  if (!savedSubject) {
    return <p className="text-[12px] text-slate-500">
      Face ID: save a door identity (USERn) first, then reopen this to enroll the face.
    </p>
  }

  const target = st?.target_samples ?? 20
  const samples = st?.samples ?? 0
  const enough = samples >= (st?.min_samples ?? 8)

  return (
    <div className="rounded-lg border border-ink-600/70 bg-ink-800/40 p-3 space-y-2.5">
      <div className="flex items-center gap-2 text-sm text-slate-200">
        <ScanFace size={15} className="text-accent-300" />
        <span className="font-medium">Face ID</span>
        <span className="mono text-[11px] text-slate-400">{savedSubject}</span>
        <a href={st?.camera_page_url ?? 'http://192.168.1.150'} target="_blank" rel="noreferrer"
           className="ml-auto inline-flex items-center gap-1 text-[12px] text-accent-300 hover:underline">
          Camera page <ExternalLink size={12} /></a>
      </div>

      {st && (
        <p className="text-[12px] text-slate-400">
          {st.face_server_online
            ? <>{st.samples} sample{st.samples === 1 ? '' : 's'} on the face server
                {' · '}{st.has_photo ? 'photo for the grant screen ✓' : 'no grant-screen photo yet'}</>
            : <span className="text-warn-soft">Face server not reachable - start it with launch.bat.</span>}
          {st.face_enrolled_at && <> · registered {fmtDateTime(st.face_enrolled_at)}</>}
        </p>
      )}

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {msg && !error && (
        <p className={`text-[12px] ${done ? 'text-ok-soft' : 'text-slate-300'} flex items-center gap-1.5`}>
          {done && <CheckCircle2 size={13} />}{msg}</p>
      )}

      {!open ? (
        <button type="button" className="btn-ghost btn-sm w-full" onClick={() => { setOpen(true); setDone(false); setMsg('') }}>
          <Camera size={14} /> {samples ? 'Add face samples' : 'Enroll face'}
        </button>
      ) : (
        <div className="space-y-2.5">
          <div className="relative aspect-[4/3] rounded-lg overflow-hidden bg-ink-900 border border-ink-600/70">
            {frame && <img src={frame} alt="Door camera live view" className="w-full h-full object-cover" />}
            {!frame && !cameraError && <div className="absolute inset-0 grid place-items-center"><Spinner label="Connecting to the camera" /></div>}
            {cameraError && <div className="absolute inset-0 grid place-items-center p-4 text-center text-[12px] text-warn-soft">{cameraError}</div>}
          </div>
          <p className="text-[11.5px] text-slate-400">
            The person looks at the door camera from about 50 cm. Between captures they turn
            their head slightly and change expression, so the samples differ.
          </p>
          <div>
            <div className="flex justify-between text-[11.5px] text-slate-400 mb-1">
              <span>{samples} / {target} samples</span>
              {!enough && <span>at least {st?.min_samples ?? 8} to finish</span>}
            </div>
            <ProgressBar value={samples / target} tone={samples >= target ? 'ok' : 'info'} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" className="btn-ghost btn-sm" disabled={busy || auto || !!cameraError}
                    onClick={capture}><Camera size={14} /> Capture</button>
            {auto
              ? <button type="button" className="btn-ghost btn-sm" onClick={() => { autoRef.current = false }}>
                  <Pause size={14} /> Stop auto</button>
              : <button type="button" className="btn-ghost btn-sm" disabled={busy || !!cameraError || samples >= target}
                        onClick={startAuto}><Play size={14} /> Auto-capture</button>}
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn-ghost btn-sm flex-1"
                    onClick={() => { autoRef.current = false; setOpen(false) }}>Close</button>
            <button type="button" className="btn-primary btn-sm flex-1" disabled={busy || auto || !enough}
                    onClick={finish}>{busy ? 'Training…' : 'Finish & train'}</button>
          </div>
        </div>
      )}
    </div>
  )
}
