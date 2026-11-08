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
import { Camera, Check, ChevronLeft, ChevronRight, ImagePlus, RotateCcw, ScanFace, Send, SkipForward, X } from 'lucide-react'
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

type PhotoDecision = 'accept' | 'refuse' | 'retake' | 'auto'
const PD: Record<PhotoDecision, { label: string; tone: string; hint: string }> = {
  accept: { label: 'Accept', tone: 'bg-emerald-500/20 text-emerald-200 border-emerald-400/40', hint: 'use this photo' },
  retake: { label: 'Retake', tone: 'bg-amber-500/15 text-amber-200 border-amber-400/40', hint: 'not used - the person is asked for a new one' },
  refuse: { label: 'Refuse', tone: 'bg-rose-500/15 text-rose-200 border-rose-400/40', hint: 'never used' },
  auto: { label: 'Skip', tone: 'bg-ink-700 text-slate-300 border-ink-500', hint: 'the system decides - used only if the face server confirms it is this person' },
}

/** Open the photos and decide each one (owner 2026-10-20). Skip leaves that photo to the system. */
function PhotoByPhoto({ sub, onClose, onDone }: { sub: FaceSubmission; onClose: () => void; onDone: (text: string, enrolled: boolean) => void }) {
  const [urls, setUrls] = useState<string[]>([])
  const [at, setAt] = useState(0)
  const [dec, setDec] = useState<PhotoDecision[]>(() => Array(sub.photo_count).fill('auto'))
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let made: string[] = [], stop = false
    Promise.all(Array.from({ length: sub.photo_count }, (_, n) =>
      fetchBlob(`/face-submissions/${sub.id}/photos/${n}`).then(b => URL.createObjectURL(b)).catch(() => '')))
      .then(list => { made = list; if (!stop) setUrls(list) })
    return () => { stop = true; made.forEach(u => u && URL.revokeObjectURL(u)) }
  }, [sub.id, sub.photo_count])
  const last = sub.photo_count - 1
  const set = useCallback((d: PhotoDecision) => {
    setDec(x => x.map((v, i) => (i === at ? d : v)))
    setAt(a => Math.min(last, a + 1))
  }, [at, last])
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === 'INPUT') return
      if (e.key === 'ArrowRight') setAt(a => Math.min(last, a + 1))
      if (e.key === 'ArrowLeft') setAt(a => Math.max(0, a - 1))
      const m: Record<string, PhotoDecision> = { a: 'accept', r: 'retake', x: 'refuse', s: 'auto' }
      if (m[e.key]) set(m[e.key])
    }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [set, last])
  async function send() {
    setBusy(true); setError('')
    try {
      const r = await api.reviewFaceSubmission(sub.id, dec, note.trim())
      const lines = r.photos.map(p => `${p.n}: ${p.used ? 'used' : 'not used'} (${p.why})`).join(' · ')
      const enrolled = (r.samples_saved ?? 0) >= r.min_samples
      onDone(`${r.status === 'RETAKE' ? 'Asked for new photos. ' : 'Approved. '}${r.samples_saved ?? 0} of ${r.photo_count} used${enrolled ? ' - Face ID is registered' : ''}. ${lines}`, enrolled)
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed') } finally { setBusy(false) }
  }
  const count = (d: PhotoDecision) => dec.filter(x => x === d).length
  return (
    <Modal open onClose={onClose} title={`Review photo by photo${sub.user_name ? ` - ${sub.user_name}` : ''}`}>
      <div className="space-y-3" data-testid="photo-review">
        {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
        <div className="relative rounded-lg overflow-hidden bg-ink-950 border border-ink-600 aspect-[4/3] grid place-items-center">
          {urls[at] ? <img src={urls[at]} alt={`Photo ${at + 1}`} className="max-h-full max-w-full object-contain" />
            : <span className="text-[12.5px] text-slate-500">Loading photo {at + 1}…</span>}
          <button type="button" aria-label="Previous photo" disabled={at === 0} onClick={() => setAt(at - 1)}
                  className="absolute left-2 top-1/2 -translate-y-1/2 btn-ghost btn-sm !px-2 disabled:opacity-30"><ChevronLeft size={18} /></button>
          <button type="button" aria-label="Next photo" disabled={at === last} onClick={() => setAt(at + 1)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 btn-ghost btn-sm !px-2 disabled:opacity-30"><ChevronRight size={18} /></button>
          <span className={`absolute top-2 left-2 text-[11.5px] px-2 py-0.5 rounded-md border ${PD[dec[at]].tone}`}>
            Photo {at + 1} of {sub.photo_count}: {PD[dec[at]].label}</span>
        </div>
        <div className="grid grid-cols-4 gap-2">
          <button type="button" className="btn-primary btn-sm" onClick={() => set('accept')}><Check size={14} /> Accept</button>
          <button type="button" className="btn-ghost btn-sm" onClick={() => set('retake')}><RotateCcw size={14} /> Retake</button>
          <button type="button" className="btn-ghost btn-sm" onClick={() => set('refuse')}><X size={14} /> Refuse</button>
          <button type="button" className="btn-ghost btn-sm" onClick={() => set('auto')}><SkipForward size={14} /> Skip</button>
        </div>
        <p className="text-[11.5px] text-slate-500">{PD[dec[at]].label}: {PD[dec[at]].hint}. Keys: A accept · R retake · X refuse · S skip · arrows.</p>
        <div className="flex flex-wrap gap-1.5">
          {dec.map((d, i) => (
            <button key={i} type="button" onClick={() => setAt(i)} aria-label={`Photo ${i + 1}: ${PD[d].label}`}
                    className={`relative w-14 h-14 rounded-md overflow-hidden border-2 ${i === at ? 'border-accent-400' : 'border-transparent'}`}>
              {urls[i] && <img src={urls[i]} alt="" className="w-full h-full object-cover" />}
              <span className={`absolute bottom-0 inset-x-0 text-[9.5px] text-center border-t ${PD[d].tone}`}>{PD[d].label}</span>
            </button>))}
        </div>
        <div className="flex flex-wrap gap-3 text-[11.5px]">
          <span className="text-slate-400">All photos:</span>
          {(['accept', 'retake', 'refuse', 'auto'] as PhotoDecision[]).map(d => (
            <button key={d} type="button" className="link" onClick={() => setDec(Array(sub.photo_count).fill(d))}>{PD[d].label}</button>))}
        </div>
        <input className="input !py-1.5 text-[13px]" maxLength={255} value={note} onChange={e => setNote(e.target.value)}
               placeholder="Optional note to the person (e.g. less light behind you)" />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-[12px] text-slate-400">{count('accept')} accept · {count('auto')} system decides · {count('retake')} retake · {count('refuse')} refuse</span>
          <div className="flex gap-2">
            <button type="button" className="btn-quiet" onClick={onClose}>Cancel</button>
            <button type="button" className="btn-primary" disabled={busy} onClick={send}>{busy ? 'Sending to the face server…' : 'Apply decisions'}</button>
          </div>
        </div>
      </div>
    </Modal>
  )
}

export function FaceSubmissionReview({ userId, onEnrolled }: { userId: number; onEnrolled: () => void }) {
  const [sub, setSub] = useState<FaceSubmission | null>(null)
  const [reason, setReason] = useState('')
  const [deciding, setDeciding] = useState<Decision | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState('')
  const [byPhoto, setByPhoto] = useState(false)

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
            <button type="button" className="btn-ghost btn-sm w-full" disabled={busy} onClick={() => setByPhoto(true)}>
              <ScanFace size={14} /> Open the photos and decide each one</button>
          </div>
        )}
        {byPhoto && <PhotoByPhoto sub={sub} onClose={() => setByPhoto(false)}
          onDone={(text, enrolled) => { setByPhoto(false); setResult(text); setSub(null); if (enrolled) onEnrolled() }} />}
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
