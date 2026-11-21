/**
 * Door photo (2026-11-21, owner): the photo the ACCESS GRANTED screen shows for this person, on the door's LCD and the
 * tablet. Pick one of their face-enrollment frames, take one now at the door camera, or upload one. A chosen photo is
 * never replaced by a later enrollment. The door picks it up at the person's next entry (within 5 minutes).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, CheckCircle2, ImagePlus, UserSquare } from 'lucide-react'
import { api, fetchBlob } from '../lib/api'
import { Spinner } from './ui'

type Info = Awaited<ReturnType<typeof api.doorPhotoInfo>>

/** An image that needs the sign-in token: fetched as a blob, shown through an object URL. */
function AuthedImg({ path, alt, className }: { path: string; alt: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let url: string | null = null, alive = true
    fetchBlob(path).then(b => { if (alive) { url = URL.createObjectURL(b); setSrc(url) } }).catch(() => setSrc(null))
    return () => { alive = false; if (url) URL.revokeObjectURL(url) }
  }, [path])
  return src ? <img src={src} alt={alt} className={className} />
    : <div className={`${className ?? ''} grid place-items-center bg-ink-800 text-slate-500 text-[11px]`}>…</div>
}

export default function DoorPhoto({ userId, savedSubject }: { userId: number; savedSubject: string | null }) {
  const [info, setInfo] = useState<Info | null>(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState('')
  const [bump, setBump] = useState(0)            // re-fetch the current photo after a change
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    setErr('')
    api.doorPhotoInfo(userId).then(setInfo).catch(e => setErr(e instanceof Error ? e.message : 'Could not load'))
  }, [userId])
  useEffect(() => { if (savedSubject) load() }, [load, savedSubject])

  async function run(label: string, fn: () => Promise<unknown>, done: string) {
    setBusy(label); setErr(''); setMsg('')
    try { await fn(); setMsg(done); setBump(b => b + 1); load() }
    catch (e) { setErr(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy('') }
  }

  if (!savedSubject) return null
  return (
    <section className="space-y-3 rounded-xl border border-ink-600/70 p-4">
      <div className="flex items-center gap-2">
        <UserSquare size={16} className="text-accent-300" />
        <div className="label !mb-0">Door photo</div>
        {info?.source === 'chosen' && <span className="ml-auto text-[11px] text-ok-soft flex items-center gap-1">
          <CheckCircle2 size={12} />chosen{info.how ? ` (${info.how})` : ''}</span>}
      </div>
      <p className="text-[12px] text-slate-400">Shown on the door screen and the tablet when this person is let in.
        Pick the best one; it appears from their next entry.</p>
      {err && <p className="text-[12px] text-warn-soft">{err}</p>}
      {!info && !err && <Spinner label="Loading photos" />}
      {info && (
        <>
          <div className="flex items-start gap-3">
            {info.has_photo
              ? <AuthedImg key={bump} path={`/users/${userId}/door-photo/current.jpg`} alt="Current door photo"
                           className="w-32 h-24 object-cover rounded-lg border border-accent-500/40" />
              : <div className="w-32 h-24 rounded-lg border border-dashed border-ink-500 grid place-items-center text-[11px] text-slate-500">no photo yet</div>}
            <div className="flex flex-col gap-2">
              <button type="button" className="btn-ghost btn-sm" disabled={!!busy || !info.camera_live}
                      title={info.camera_live ? 'The person looks at the door camera, then press' : 'The door camera is not sending pictures'}
                      onClick={() => run('camera', () => api.doorPhotoChoose(userId, { from: 'camera' }), 'Photo taken at the door camera.')}>
                <Camera size={14} />{busy === 'camera' ? 'Taking…' : 'Take photo now (door camera)'}</button>
              <button type="button" className="btn-ghost btn-sm" disabled={!!busy} onClick={() => fileRef.current?.click()}>
                <ImagePlus size={14} />{busy === 'upload' ? 'Uploading…' : 'Upload a photo'}</button>
              <input ref={fileRef} type="file" accept="image/jpeg,image/png" className="hidden"
                     onChange={e => { const f = e.target.files?.[0]; e.target.value = ''
                       if (f) run('upload', () => api.doorPhotoUpload(userId, f), 'Photo uploaded.') }} />
            </div>
          </div>
          {info.candidates.length > 0 ? (
            <div>
              <div className="text-[11.5px] text-slate-400 mb-1.5">Or pick one from their face enrollment:</div>
              <div className="grid grid-cols-4 gap-2">
                {info.candidates.map(c => (
                  <button key={c} type="button" disabled={!!busy} title="Use this photo on the door"
                          className="rounded-lg overflow-hidden border border-ink-600 hover:border-accent-400 focus:border-accent-400"
                          onClick={() => run(`c${c}`, () => api.doorPhotoChoose(userId, { from: 'candidate', candidate: c }), 'Door photo chosen.')}>
                    <AuthedImg path={`/users/${userId}/door-photo/candidate/${c}.jpg`} alt="Enrollment frame"
                               className="w-full aspect-[4/3] object-cover" />
                  </button>))}
              </div>
            </div>
          ) : <p className="text-[11.5px] text-slate-500">Full photos from the door camera appear here after this person
              is recognised at the door a few times (or after the next face enrollment).</p>}
          {(info.training ?? []).length > 0 && (
            <div>
              <div className="text-[11.5px] text-slate-400 mb-1.5">From face training ({info.training!.length}) - face-only
                crops, small; <span className="text-slate-300">colour</span> ones look best on the door screen:</div>
              <div className="grid grid-cols-6 gap-1.5 max-h-56 overflow-y-auto pr-1">
                {info.training!.map(c => (
                  <button key={c} type="button" disabled={!!busy}
                          title={c.startsWith('s') ? 'Training photo (colour crop)' : 'Training photo (grey crop)'}
                          className="relative rounded-md overflow-hidden border border-ink-600 hover:border-accent-400 focus:border-accent-400"
                          onClick={() => run(`c${c}`, () => api.doorPhotoChoose(userId, { from: 'candidate', candidate: c }), 'Door photo chosen.')}>
                    <AuthedImg path={`/users/${userId}/door-photo/candidate/${c}.jpg`} alt="Training photo"
                               className="w-full aspect-square object-cover" />
                    <span className={`absolute bottom-0 inset-x-0 text-[9px] text-center ${c.startsWith('s')
                      ? 'bg-accent-600/70 text-white' : 'bg-ink-900/70 text-slate-300'}`}>{c.startsWith('s') ? 'colour' : 'grey'}</span>
                  </button>))}
              </div>
            </div>)}
          {msg && <p className="text-[12px] text-ok-soft">{msg}</p>}
        </>
      )}
    </section>
  )
}
