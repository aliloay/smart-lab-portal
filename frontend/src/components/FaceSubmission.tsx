/**
 * Face photos sent by the person, approved by staff.
 *
 * FaceSelfService (Profile): a person whose Face ID is not registered sends
 * 5-10 photos. Nothing is enrolled until staff check that the photos show
 * the account holder. FaceSubmissionReview (Users & roles -> Edit -> Face
 * ID): staff see the photos and approve or reject with a reason. The portal
 * deletes its copies after either decision.
 */
import { ChangeEvent, useCallback, useEffect, useState } from 'react'
import { Check, ImagePlus, ScanFace, Send, X } from 'lucide-react'
import { FaceSubmission, api, fetchBlob } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDateTime } from '../lib/time'
import { ErrorBanner, ProgressBar } from './ui'

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

// --------------------------------------------------------------- person ---
export function FaceSelfService() {
  const { user } = useAuth()
  const [sub, setSub] = useState<FaceSubmission | null | undefined>(undefined)
  const [files, setFiles] = useState<File[]>([])
  const [previews, setPreviews] = useState<string[]>([])
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.myFaceSubmission().then(setSub).catch(() => setSub(null))
  }, [])
  useEffect(load, [load])
  useEffect(() => () => previews.forEach(u => URL.revokeObjectURL(u)), [previews])

  if (!user?.auth_subject || user.face_enrolled_at || sub === undefined) return null

  function pick(e: ChangeEvent<HTMLInputElement>) {
    const chosen = Array.from(e.target.files ?? []).filter(f => f.type.startsWith('image/'))
    const all = [...files, ...chosen].slice(0, MAX)
    previews.forEach(u => URL.revokeObjectURL(u))
    setFiles(all)
    setPreviews(all.map(f => URL.createObjectURL(f)))
    e.target.value = ''
  }
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
      setFiles([]); setPreviews([])
    } catch (e) { setError(e instanceof Error ? e.message : 'Upload failed') }
    finally { setProgress(null) }
  }
  async function withdraw() {
    try { setSub(await api.withdrawFaceSubmission()) } catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
  }

  const pending = sub?.status === 'PENDING'
  return (
    <div className="rounded-xl border border-ink-600/70 bg-ink-800/40 p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
        <ScanFace size={16} className="text-accent-300" /> Send your Face ID photos
      </div>
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {pending ? (
        <>
          <p className="text-[13px] text-slate-300">
            {sub!.photo_count} photos sent {fmtDateTime(sub!.created_at)} - waiting for lab staff to
            check them. You will get a notification when they are approved.</p>
          <Thumbs id={sub!.id} count={sub!.photo_count} />
          <button type="button" className="btn-ghost btn-sm" onClick={withdraw}>Withdraw and send different photos</button>
        </>
      ) : (
        <>
          {sub?.status === 'REJECTED' && (
            <p className="text-[13px] text-warn-soft">Your last photos were not accepted: {sub.reason}</p>)}
          {sub?.status === 'APPROVED' && sub.reason && (
            <p className="text-[13px] text-warn-soft">{sub.reason}</p>)}
          <ul className="text-[12.5px] text-slate-400 list-disc pl-5 space-y-0.5">
            <li>{MIN}-{MAX} photos of your face, only you in each, looking at the camera.</li>
            <li>Good light, no sunglasses or mask; turn your head slightly between photos.</li>
            <li>Lab staff check the photos are you before they are used at the door, then delete them from the portal.</li>
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
            <label className="btn-ghost btn-sm cursor-pointer">
              <ImagePlus size={14} /> {files.length ? 'Add more' : 'Choose or take photos'}
              <input type="file" accept="image/*" capture="user" multiple className="hidden" onChange={pick} />
            </label>
            <button type="button" className="btn-primary btn-sm" onClick={send}
                    disabled={files.length < MIN || progress !== null}>
              <Send size={14} /> Send {files.length || ''} photo{files.length === 1 ? '' : 's'}
            </button>
            {files.length > 0 && files.length < MIN &&
              <span className="text-[12px] text-slate-400 self-center">{MIN - files.length} more needed</span>}
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- staff ---
export function FaceSubmissionReview({ userId, onEnrolled }: { userId: number; onEnrolled: () => void }) {
  const [sub, setSub] = useState<FaceSubmission | null>(null)
  const [reason, setReason] = useState('')
  const [rejecting, setRejecting] = useState(false)
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
  async function reject() {
    if (!sub) return
    setBusy(true); setError('')
    try {
      await api.rejectFaceSubmission(sub.id, reason)
      setResult('Rejected - the person has been told why and can send new photos.')
      setSub(null)
    } catch (e) { setError(e instanceof Error ? e.message : 'Reject failed') }
    finally { setBusy(false) }
  }

  return (
    <div className="rounded-lg border border-accent-500/30 bg-accent-500/[0.05] p-3 space-y-2">
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      {result && <p className="text-[12.5px] text-slate-200">{result}</p>}
      {sub && <>
        <p className="text-[12.5px] text-slate-200">
          <b>{sub.photo_count} photos</b> sent by this person {fmtDateTime(sub.created_at)}.
          Approve only if they show <b>this account holder</b>.</p>
        <Thumbs id={sub.id} count={sub.photo_count} size={64} />
        {rejecting ? (
          <div className="flex gap-2">
            <input className="input flex-1 !py-1.5 text-[13px]" placeholder="Reason the person will see"
                   value={reason} onChange={e => setReason(e.target.value)} maxLength={255} />
            <button type="button" className="btn-ghost btn-sm" disabled={busy || reason.trim().length < 3}
                    onClick={reject}>Send</button>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setRejecting(false)}>Cancel</button>
          </div>
        ) : (
          <div className="flex gap-2">
            <button type="button" className="btn-primary btn-sm flex-1" disabled={busy} onClick={approve}>
              <Check size={14} /> {busy ? 'Sending to the face server…' : 'Approve'}</button>
            <button type="button" className="btn-ghost btn-sm flex-1" disabled={busy}
                    onClick={() => setRejecting(true)}><X size={14} /> Reject</button>
          </div>
        )}
      </>}
    </div>
  )
}
