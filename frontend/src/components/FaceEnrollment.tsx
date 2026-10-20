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
import { Camera, CheckCircle2, ExternalLink, ImagePlus, Pause, Play, RotateCcw, ScanFace } from 'lucide-react'
import { FaceStatus, api, fetchBlob } from '../lib/api'
import { fmtDateTime } from '../lib/time'
import { ErrorBanner, ProgressBar, Spinner } from './ui'
import { FaceSubmissionReview } from './FaceSubmission'

// Progress of automatic capture is read this often (the face server spaces and
// varies the samples itself: steady face, a new look, >= 0.35 s apart).
const AUTO_POLL_MS = 500

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
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState<number | null>(null)

  const load = useCallback(() => {
    api.faceStatus(userId).then(setSt).catch(e => setError(e.message))
  }, [userId])
  useEffect(load, [load])

  // Live view: a frame about every 0.4 s while the panel is open - the frame the door camera
  // already sent to the face server, so the camera does no extra work (its own snapshot only
  // as a fallback, in the portal backend).
  // When an error occurs, the stale frame is cleared so an offline camera
  // never masquerades as a live preview.
  useEffect(() => {
    if (!open) return
    let stop = false, url: string | null = null, timer: number | undefined, misses = 0
    const tick = async () => {
      try {
        const blob = await fetchBlob('/enrollment/camera/snapshot')
        if (stop) return
        const next = URL.createObjectURL(blob)
        setFrame(next)
        if (url) URL.revokeObjectURL(url)
        url = next
        misses = 0
        setCameraError('')
      } catch (e) {
        // One missed frame (a Wi-Fi hiccup of the door camera, seen 2026-10-18) is not an outage:
        // keep the last frame and only report the camera unreachable after 3 misses in a row.
        if (!stop && ++misses >= 3) {
          setCameraError(e instanceof Error ? e.message : 'Camera not reachable')
          // Clear stale frame on connection loss:
          setFrame(null)
          if (url) {
            URL.revokeObjectURL(url)
            url = null
          }
        }
      }
      if (!stop) timer = window.setTimeout(tick, 400)
    }
    tick()
    return () => { stop = true; window.clearTimeout(timer); if (url) URL.revokeObjectURL(url) }
  }, [open])

  // Leaving the page or closing the panel ends a running automatic capture on the face server too.
  useEffect(() => () => {
    if (autoRef.current) api.faceAutoStop(userId).catch(() => undefined)
    autoRef.current = false
  }, [userId])

  async function captureOnce(): Promise<boolean> {
    if (busy) return false
    try {
      const r = await api.faceCapture(userId)
      setMsg(r.message)
      setError('')
      if (r.samples !== null) setSt(s => s && { ...s, samples: r.samples ?? s.samples,
                                                  has_photo: s.has_photo || r.saved })
      return r.saved
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Capture failed')
      return false
    }
  }

  async function resetSamples() {
    if (!st || !confirm(`Stop using the ${st.samples} saved face photos of this person and start again?\n` +
                        'They are moved to the face server\'s archive (kept, not deleted).')) return
    setBusy(true); setError('')
    try {
      await api.faceReset(userId)
      setSt(await api.faceStatus(userId))
      setMsg('Old photos set aside - capture new ones, then Finish.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset failed')
    } finally { setBusy(false) }
  }

  async function capture() {
    setBusy(true)
    await captureOnce()
    setBusy(false)
  }

  // Automatic capture (2026-10-14): the face server keeps every steady, sharp, new-looking frame
  // of this person from the door camera's normal stream - no camera round trip per sample, and a
  // rejected frame (blurred, moving, same look) just waits for the next one instead of stopping.
  async function startAuto() {
    if (!st) return
    const want = Math.max(1, st.target_samples - st.samples)
    autoRef.current = true
    setAuto(true); setError(''); setDone(false)
    try {
      let s = await api.faceAutoStart(userId, want)
      while (autoRef.current && s.active) {
        await new Promise(r => window.setTimeout(r, AUTO_POLL_MS))
        s = await api.faceAuto(userId)
        if (s.samples != null) setSt(prev => prev && { ...prev, samples: s.samples ?? prev.samples,
                                                         has_photo: prev.has_photo || (s.saved ?? 0) > 0 })
        setMsg(s.active ? `${s.saved ?? 0} / ${s.target ?? want} new samples - ${s.hint ?? ''}`
                        : `${s.saved ?? 0} new samples saved${s.ended ? ` (${s.ended})` : ''}.`)
      }
      if (!autoRef.current) await api.faceAutoStop(userId).catch(() => undefined)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Automatic capture failed')
    } finally {
      autoRef.current = false
      setAuto(false)
      load()
    }
  }

  // Photos staff already have (e.g. from a phone): straight to the face server.
  async function uploadPhotos(list: FileList | null) {
    if (!list?.length) return
    setUploading(0); setError(''); setDone(false)
    try {
      const r = await api.faceUpload(userId, Array.from(list), f => setUploading(f))
      setMsg(r.message)
      setDone(r.face_enrolled)
      load()
      if (r.face_enrolled) onEnrolled()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(null)
      if (fileRef.current) fileRef.current.value = ''
    }
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

      {/* Photos the person sent themselves, waiting for staff approval. */}
      <FaceSubmissionReview userId={userId} onEnrolled={() => { load(); onEnrolled() }} />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {msg && !error && (
        <p className={`text-[12px] ${done ? 'text-ok-soft' : 'text-slate-300'} flex items-center gap-1.5`}>
          {done && <CheckCircle2 size={13} />}{msg}</p>
      )}

      {!open ? (
        <div className="grid grid-cols-2 gap-2">
          <button type="button" className="btn-ghost btn-sm" onClick={() => { setOpen(true); setDone(false); setMsg('') }}>
            <Camera size={14} /> {samples ? 'Add at the camera' : 'Enroll at the camera'}
          </button>
          <button type="button" className="btn-ghost btn-sm" disabled={uploading !== null || !st?.face_server_online}
                  title="Clear, front-facing photos of this person (JPEG/PNG), up to 20"
                  onClick={() => fileRef.current?.click()}>
            <ImagePlus size={14} /> {uploading !== null ? `Uploading ${Math.round(uploading * 100)}%` : 'Upload photos'}
          </button>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden
                 onChange={e => uploadPhotos(e.target.files)} />
          {samples > 0 && (
            <button type="button" className="btn-ghost btn-sm col-span-2 text-warn-soft border border-warn/40"
                    disabled={busy || !st?.face_server_online} onClick={resetSamples}>
              <RotateCcw size={14} /> Remove saved face photos ({samples}) and start again</button>)}
        </div>
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
          {samples > 0 && (
            <button type="button" className="btn-ghost btn-sm text-warn-soft" disabled={busy || auto}
                    onClick={resetSamples}><RotateCcw size={14} /> Remove saved face photos ({samples}) and start again</button>)}
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
