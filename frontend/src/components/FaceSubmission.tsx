/**
 * Face photos sent by the person, approved by staff.
 *
 * FaceSelfService (Profile): anyone with a door identity sends 5-10 photos - picked from the
 * phone / computer or taken right there with the camera. The face server checks each photo at
 * once (a clear face, not another registered person). Nothing is enrolled until staff check that
 * the photos show the account holder. FaceSubmissionReview (Users & roles -> Enroll): staff see
 * the photos and Approve, ask for a Retake, or Refuse (the person then comes to the lab staff).
 * The portal deletes its copies after any decision.
 */
import { ChangeEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Camera, Check, ImagePlus, RotateCcw, ScanFace, Send, X } from 'lucide-react'
import { FaceSubmission, api, fetchBlob } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDateTime } from '../lib/time'
import { ErrorBanner, Modal, ProgressBar } from './ui'

const MIN = 5, MAX = 10

/** The submission's photos, fetched with the login token (never public). */
function Thumbs({ id, count, size = 72 }: { id: number; count: number; size?: number }) {
  const [urls, setUrls] = useState<string[]>([])
  useEffect(() => {
    let made: string[] = [], stop = false
    Promise.all(Array.from({ length: count }, (_, n) =>
      fetchBlob(`/face-submissions/${id}/photos/${n}?variant=thumb`)
        .then(b => URL.createObjectURL(b)).catch(() => '')))
      .then(list => { made = list; if (!stop) setUrls(list) })
    return () => { stop = true; made.forEach(u => u && URL.revokeObjectURL(u)) }
  }, [id, count])
  return (
    <div className="flex flex-wrap gap-1.5">
      {Array.from({ length: count }, (_, n) => (
        <div key={n} style={{ width: size, height: size }}
             className="rounded-md overflow-hidden bg-ink-900 border border-ink-600/70">
          {urls[n] && <img src={urls[n]} alt={`Photo ${n + 1}`} className="w-full h-full object-cover" />}
        </div>))}
    </div>
  )
}

/** Selfies from this device's camera (front camera on a phone). Nothing leaves the browser until "Send". */
function SelfieCamera({ open, room, onShot, onClose }: { open: boolean; room: number; onShot: (f: File) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState('')
  const [taken, setTaken] = useState(0)
  useEffect(() => {
    if (!open) return
    let stream: MediaStream | null = null, stop = false
    setError(''); setTaken(0)
    if (!navigator.mediaDevices?.getUserMedia) { setError('This browser cannot open the camera here - use "Choose or take photos".'); return }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false })
      .then(s => { if (stop) { s.getTracks().forEach(t => t.stop()); return } stream = s; if (video.current) video.current.srcObject = s })
      .catch(() => setError('The camera could not be opened. Allow camera access for this site, or use "Choose or take photos".'))
    return () => { stop = true; stream?.getTracks().forEach(t => t.stop()) }
  }, [open])
  function shoot() {
    const v = video.current
    if (!v || !v.videoWidth) return
    const c = document.createElement('canvas')
    c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d')!.drawImage(v, 0, 0)
    c.toBlob(b => { if (b) { onShot(new File([b], `selfie-${Date.now()}.jpg`, { type: 'image/jpeg' })); setTaken(n => n + 1) } }, 'image/jpeg', 0.92)
  }
  return (
    <Modal open={open} onClose={onClose} title="Take Face ID photos"
           footer={<div className="flex gap-2 justify-end">
             <button type="button" className="btn-ghost btn-sm" onClick={onClose}>Done</button>
             <button type="button" className="btn-primary btn-sm" onClick={shoot} disabled={!!error || room - taken <= 0}>
               <Camera size={14} /> Take photo {taken ? `(${taken})` : ''}</button></div>}>
      {error ? <ErrorBanner message={error} />
        : <div className="space-y-2">
            <video ref={video} autoPlay playsInline muted className="w-full rounded-lg bg-black aspect-[4/3] object-cover -scale-x-100" />
            <p className="text-[12.5px] text-slate-400">Face the camera in good light; turn your head a little between
              photos. {room - taken > 0 ? `${room - taken} more can be added.` : 'That is the maximum.'}</p>
          </div>}
    </Modal>
  )
}

// --------------------------------------------------------------- person ---
export function FaceSelfService() {
  const { user } = useAuth()
  const [sub, setSub] = useState<FaceSubmission | null | undefined>(undefined)
  const [files, setFiles] = useState<File[]>([])
  const [previews, setPreviews] = useState<string[]>([])
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)          // registered people: the form opens on request
  const [camera, setCamera] = useState(false)

  const load = useCallback(() => {
    api.myFaceSubmission().then(setSub).catch(() => setSub(null))
  }, [])
  useEffect(load, [load])
  useEffect(() => () => previews.forEach(u => URL.revokeObjectURL(u)), [previews])

  if (!user?.auth_subject || sub === undefined) return null
  const registered = !!user.face_enrolled_at

  function add(chosen: File[]) {
    setFiles(f => {
      const all = [...f, ...chosen.filter(x => x.type.startsWith('image/'))].slice(0, MAX)
      setPreviews(p => { p.forEach(u => URL.revokeObjectURL(u)); return all.map(x => URL.createObjectURL(x)) })
      return all
    })
  }
  function pick(e: ChangeEvent<HTMLInputElement>) { add(Array.from(e.target.files ?? [])); e.target.value = '' }
  function remove(i: number) {
    URL.revokeObjectURL(previews[i])
    setFiles(f => f.filter((_, j) => j !== i))
    setPreviews(p => p.filter((_, j) => j !== i))
  }
  async function send() {
    setError(''); setProgress(0)
    try {
      setSub(await api.submitFacePhotos(files, setProgress))
      previews.forEach(u => URL.revokeObjectURL(u))
      setFiles([]); setPreviews([]); setOpen(false)
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed') }
    finally { setProgress(null) }
  }
  async function withdraw() {
    try { setSub(await api.withdrawFaceSubmission()) } catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
  }

  const pending = sub?.status === 'PENDING'
  const refused = !!sub?.refused_until_seen
  const showForm = !pending && !refused && (!registered || open || sub?.status === 'RETAKE')
  return (
    <div className="rounded-xl border border-ink-600/70 bg-ink-800/40 p-4 space-y-3" data-testid="face-self-service">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
        <ScanFace size={16} className="text-accent-300" /> {registered ? 'Update your Face ID photos' : 'Send your Face ID photos'}
      </div>
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {pending && <>
        <p className="text-[13px] text-slate-300">
          {sub!.photo_count} photos sent {fmtDateTime(sub!.created_at)} - waiting for lab staff to
          check them. You will get a notification when they decide.</p>
        <Thumbs id={sub!.id} count={sub!.photo_count} />
        <button type="button" className="btn-ghost btn-sm" onClick={withdraw}>Withdraw and send different photos</button>
      </>}
      {refused && <p className="text-[13px] text-warn-soft">Your last photos were not accepted: {sub!.reason} Please come
        to the lab staff - they will take your Face ID photos at the door camera.</p>}
      {sub?.status === 'RETAKE' && <p className="text-[13px] text-warn-soft">Lab staff asked you to retake your photos: {sub.reason}</p>}
      {sub?.status === 'APPROVED' && sub.reason && <p className="text-[13px] text-warn-soft">{sub.reason}</p>}
      {sub?.status === 'APPROVED' && !sub.reason && !showForm &&
        <p className="text-[12.5px] text-ok-soft">Your photos were approved {sub.reviewed_at ? fmtDateTime(sub.reviewed_at) : ''}.</p>}

      {!pending && !refused && registered && !showForm &&
        <button type="button" className="btn-ghost btn-sm" onClick={() => setOpen(true)}><ImagePlus size={14} /> Send new photos</button>}

      {showForm && <>
        <ul className="text-[12.5px] text-slate-400 list-disc pl-5 space-y-0.5">
          <li>{MIN}-{MAX} photos of your face, only you in each, looking at the camera.</li>
          <li>Good light, no sunglasses or mask; turn your head slightly between photos.</li>
          <li>Each photo is checked at once; lab staff then confirm they are you before they are used at the
            door and by the lab cameras, and the portal deletes them.</li>
        </ul>
        {previews.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {previews.map((u, i) => (
              <div key={u} className="relative w-[72px] h-[72px] rounded-md overflow-hidden border border-ink-600/70">
                <img src={u} alt={`Photo ${i + 1}`} className="w-full h-full object-cover" />
                <button type="button" onClick={() => remove(i)} aria-label="Remove photo"
                        className="absolute top-0.5 right-0.5 rounded bg-black/60 p-0.5 text-white"><X size={12} /></button>
              </div>))}
          </div>)}
        {progress !== null && <ProgressBar value={progress} />}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost btn-sm" onClick={() => setCamera(true)} disabled={files.length >= MAX}>
            <Camera size={14} /> Take selfies</button>
          <label className="btn-ghost btn-sm cursor-pointer">
            <ImagePlus size={14} /> {files.length ? 'Add more' : 'Choose or take photos'}
            <input type="file" accept="image/*" capture="user" multiple className="hidden" onChange={pick} />
          </label>
          <button type="button" className="btn-primary btn-sm" onClick={send}
                  disabled={files.length < MIN || progress !== null}>
            <Send size={14} /> {progress !== null ? 'Checking…' : `Send ${files.length || ''} photo${files.length === 1 ? '' : 's'}`}
          </button>
          {registered && sub?.status !== 'RETAKE' &&
            <button type="button" className="btn-quiet btn-sm" onClick={() => setOpen(false)}>Cancel</button>}
          {files.length > 0 && files.length < MIN &&
            <span className="text-[12px] text-slate-400 self-center">{MIN - files.length} more needed</span>}
        </div>
        <SelfieCamera open={camera} room={MAX - files.length} onShot={f => add([f])} onClose={() => setCamera(false)} />
      </>}
    </div>
  )
}

// ---------------------------------------------------------------- staff ---
type Decision = 'retake' | 'reject'
const DECISION: Record<Decision, { label: string; placeholder: string; done: string }> = {
  retake: { label: 'Ask to retake', placeholder: 'What to change (the person sees this)',
            done: 'Retake requested - the person was notified and can send new photos.' },
  reject: { label: 'Refuse', placeholder: 'Why (the person sees this and is asked to come to the lab staff)',
            done: 'Refused - the person was told to come to the lab staff to be enrolled in person.' },
}

export function FaceSubmissionReview({ userId, onEnrolled }: { userId: number; onEnrolled: () => void }) {
  const [sub, setSub] = useState<FaceSubmission | null>(null)
  const [reason, setReason] = useState('')
  const [deciding, setDeciding] = useState<Decision | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState('')

  useEffect(() => { api.pendingFaceSubmission(userId).then(setSub).catch(() => setSub(null)) }, [userId])
  if (!sub && !result) return null

  async function approve() {
    if (!sub) return
    setBusy(true); setError('')
    try {
      const r = await api.approveFaceSubmission(sub.id)
      const ok = (r.samples_saved ?? 0) >= r.min_samples
      setResult(ok ? `Approved: ${r.samples_saved} of ${r.photo_count} photos used. Face ID is registered.`
                   : (r.reason ?? 'Approved, but too few photos had a usable face.'))
      setSub(null)
      if (ok) onEnrolled()
    } catch (e) { setError(e instanceof Error ? e.message : 'Approval failed') }
    finally { setBusy(false) }
  }
  async function decide() {
    if (!sub || !deciding) return
    setBusy(true); setError('')
    try {
      await (deciding === 'retake' ? api.retakeFaceSubmission : api.rejectFaceSubmission)(sub.id, reason)
      setResult(DECISION[deciding].done)
      setSub(null)
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy(false) }
  }

  return (
    <div className="rounded-lg border border-accent-500/30 bg-accent-500/[0.05] p-3 space-y-2" data-testid="face-review">
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {result && <p className="text-[12.5px] text-slate-200">{result}</p>}
      {sub && <>
        <p className="text-[12.5px] text-slate-200">
          <b>{sub.photo_count} photos</b> sent by this person {fmtDateTime(sub.created_at)}.
          Approve only if they show <b>this account holder</b>.</p>
        <Thumbs id={sub.id} count={sub.photo_count} size={64} />
        {deciding ? (
          <div className="flex gap-2">
            <input className="input flex-1 !py-1.5 text-[13px]" placeholder={DECISION[deciding].placeholder}
                   value={reason} onChange={e => setReason(e.target.value)} maxLength={255} autoFocus />
            <button type="button" className="btn-ghost btn-sm" disabled={busy || reason.trim().length < 3}
                    onClick={decide}>Send</button>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setDeciding(null)}>Cancel</button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary btn-sm flex-1" disabled={busy} onClick={approve}>
              <Check size={14} /> {busy ? 'Sending to the face server…' : 'Approve'}</button>
            <button type="button" className="btn-ghost btn-sm flex-1" disabled={busy}
                    onClick={() => setDeciding('retake')}><RotateCcw size={14} /> {DECISION.retake.label}</button>
            <button type="button" className="btn-ghost btn-sm flex-1" disabled={busy}
                    onClick={() => setDeciding('reject')}><X size={14} /> {DECISION.reject.label}</button>
          </div>
        )}
      </>}
    </div>
  )
}

/** Users & roles: everyone whose photos wait for review, with a button that opens their enrollment. */
export function FaceReviewQueue({ onReview }: { onReview: (userId: number) => void }) {
  const [rows, setRows] = useState<FaceSubmission[]>([])
  useEffect(() => { api.waitingFaceSubmissions().then(setRows).catch(() => setRows([])) }, [])
  if (!rows.length) return null
  return (
    <div className="card p-4 mb-4 space-y-2" data-testid="face-review-queue">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
        <ScanFace size={16} className="text-accent-300" /> Face ID photos waiting for review ({rows.length})</div>
      {rows.map(s => (
        <div key={s.id} className="flex items-center justify-between gap-3 text-[13px]">
          <span className="text-slate-200">{s.user_name} <span className="mono text-accent-200">{s.auth_subject}</span>
            <span className="text-slate-400"> · {s.photo_count} photos · {fmtDateTime(s.created_at)}</span></span>
          <button type="button" className="btn-primary btn-sm" onClick={() => onReview(s.user_id)}>Review</button>
        </div>))}
    </div>
  )
}
