/**
 * Security camera recording (administrators). The video is recorded and kept
 * on the laptop by the camera service (FFmpeg): the camera's own H.264
 * video, audio converted to AAC. A recording runs until Stop and is split
 * into 1-hour MP4 files (no gap between them). Nothing is deleted automatically.
 *
 *   RecordButton    Record / ● REC mm:ss + Stop, for one camera
 *   RecordingsPanel every recording of a camera: play in the page, download
 */
import { useCallback, useEffect, useState } from 'react'
import { Circle, Download, Play, Square, X } from 'lucide-react'
import { Recording, RecordingStatus, api } from '../lib/api'
import { isAdmin, useAuth } from '../lib/auth'
import { EmptyState, ErrorBanner, Spinner } from './ui'

const hms = (s: number) => s >= 3600 ? `${Math.floor(s / 3600)}:${mmss(s % 3600)}` : mmss(s)
const mmss = (s: number) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${Math.floor(s % 60).toString().padStart(2, '0')}`
const size = (b: number) => b >= 1e9 ? `${(b / 1e9).toFixed(2)} GB` : `${(b / 1e6).toFixed(1)} MB`

export function RecordButton({ deviceId, onChange }: { deviceId: number; onChange?: () => void }) {
  const { user } = useAuth()
  const [st, setSt] = useState<RecordingStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)

  const load = useCallback(() => {
    api.recordingStatus(deviceId).then(s => { setSt(s); setTick(0) }).catch(() => setSt(null))
  }, [deviceId])
  useEffect(() => {
    if (!isAdmin(user)) return
    load()
    const t = window.setInterval(load, 5000)
    return () => window.clearInterval(t)
  }, [load, user])
  useEffect(() => {                         // the timer runs between status checks
    if (!st?.recording) return
    const t = window.setInterval(() => setTick(x => x + 1), 1000)
    return () => window.clearInterval(t)
  }, [st?.recording])

  if (!isAdmin(user)) return null
  if (!st) return <span className="text-[12px] text-slate-500" title="The camera service does not answer">Recording unavailable</span>

  async function flip(action: 'start' | 'stop') {
    if (action === 'start' && !window.confirm('Start recording this camera? The video is saved on the laptop.')) return
    setBusy(true); setError('')
    try { await api.recordingSwitch(deviceId, action); load(); onChange?.() }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy(false) }
  }

  return (
    <span className="inline-flex items-center gap-2">
      {st.recording ? (<>
        <span className="inline-flex items-center gap-1.5 rounded-lg bg-bad/15 border border-bad/50 px-2.5 py-1 text-[12.5px] font-bold text-bad-soft"
              title={`Started by ${st.started_by || '?'} - runs until Stop, a new file every ${Math.round(st.segment_s / 60)} min`}>
          <Circle size={10} className="fill-current animate-pulse" /> REC {hms((st.elapsed_s ?? 0) + tick)}
          {st.parts > 1 && <span className="font-normal text-[11px]">· part {st.parts}</span>}</span>
        <button className="btn-ghost btn-sm" disabled={busy} onClick={() => flip('stop')}>
          <Square size={13} /> Stop</button>
      </>) : (
        <button className="btn-ghost btn-sm text-bad-soft" disabled={busy || !st.ffmpeg || st.free_gb < st.min_free_gb}
          onClick={() => flip('start')}
          title={!st.ffmpeg ? 'FFmpeg is not installed on the laptop'
            : st.free_gb < st.min_free_gb ? `Only ${st.free_gb} GB free on the laptop` : `${st.free_gb} GB free on the laptop`}>
          <Circle size={12} className="fill-current" /> Record</button>
      )}
      {error && <span className="text-[12px] text-bad-soft">{error}</span>}
    </span>
  )
}

/** Pictures for teaching the camera the robots: one every few seconds, only when the scene changed. */
export function TrainingPictures({ deviceId }: { deviceId: number }) {
  const [st, setSt] = useState<Awaited<ReturnType<typeof api.datasetStatus>> | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(() => { api.datasetStatus(deviceId).then(setSt).catch(() => setSt(null)) }, [deviceId])
  useEffect(() => { load(); const t = window.setInterval(load, 3000); return () => window.clearInterval(t) }, [load])
  if (!st) return null
  async function flip(action: 'start' | 'stop') {
    setError('')
    try { await api.datasetSwitch(deviceId, action); load() } catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
  }
  return (
    <div className="card p-4 space-y-2" data-testid="training-pictures">
      <div className="flex flex-wrap items-center gap-3">
        <div className="text-white font-semibold text-[14px]">Robot training pictures</div>
        {st.collecting
          ? <span className="text-[12px] font-bold text-bad-soft inline-flex items-center gap-1.5">
              <Circle size={9} className="fill-current animate-pulse" /> collecting · {st.saved_this_run} this run</span>
          : <span className="text-[12px] text-slate-400">{st.total} saved</span>}
        <span className="ml-auto">
          {st.collecting
            ? <button className="btn-ghost btn-sm" onClick={() => flip('stop')}><Square size={13} /> Stop</button>
            : <button className="btn-ghost btn-sm" onClick={() => flip('start')}><Circle size={12} className="fill-current" /> Start collecting</button>}
        </span>
      </div>
      <p className="text-[12px] text-slate-400">
        Point the camera at the robots, then collect while they move and people work around them. A picture is kept
        every {st.interval_s} s, only when the scene changed ({st.skipped_unchanged} unchanged skipped). Aim for
        100-200 per robot; {st.total} of {st.max_pictures} so far. They stay on the laptop; labelling comes next.</p>
      {error && <p className="text-[12px] text-bad-soft">{error}</p>}
    </div>
  )
}

export function RecordingsPanel({ deviceId }: { deviceId: number }) {
  const [items, setItems] = useState<Recording[] | null>(null)
  const [free, setFree] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [playing, setPlaying] = useState<{ file: string; url: string } | null>(null)

  const load = useCallback(() => {
    api.recordings(deviceId).then(r => { setItems(r.items); setFree(r.free_gb) })
      .catch(e => { setError(e instanceof Error ? e.message : 'Failed'); setItems([]) })
  }, [deviceId])
  useEffect(() => { load() }, [load])

  async function open(r: Recording, download = false) {
    try {
      const { url } = await api.recordingLink(deviceId, r.file)
      if (download) window.location.href = `${url}&download=true`
      else setPlaying({ file: r.file, url })
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
  }

  if (items === null) return <Spinner label="Loading recordings" />
  return (
    <div className="space-y-3">
      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
      <TrainingPictures deviceId={deviceId} />
      <div className="flex items-center gap-3">
        <RecordButton deviceId={deviceId} onChange={load} />
        <span className="ml-auto text-[12px] text-slate-400">
          Saved on the laptop in 1-hour files{free !== null ? ` · ${free} GB free` : ''} · never deleted automatically</span>
      </div>
      {playing && (
        <div className="card p-3 space-y-2">
          <div className="flex items-center gap-2 text-[13px] text-slate-200">
            <Play size={14} /> {playing.file}
            <button className="ml-auto btn-ghost btn-sm" onClick={() => setPlaying(null)}><X size={13} /> Close</button>
          </div>
          <video key={playing.url} src={playing.url} controls autoPlay className="w-full max-h-[70vh] bg-black rounded-lg" />
        </div>)}
      {!items.length ? (
        <div className="card"><EmptyState icon={<Circle size={18} />} title="No recordings yet"
          detail="Press Record to save this camera's video on the laptop." /></div>
      ) : (
        <div className="card divide-y divide-ink-700/60 overflow-hidden" data-testid="recordings">
          {items.map(r => (
            <div key={r.file} className="px-4 py-3 flex flex-wrap items-center gap-3 text-[13px]">
              <div className="min-w-0">
                <div className="text-white font-medium">
                  {r.started_at ? new Date(r.started_at).toLocaleString() : r.file}
                  {r.recording && <span className="ml-2 text-bad-soft font-bold text-[11px]">● RECORDING</span>}</div>
                <div className="text-slate-400 text-[12px]">
                  {r.parts && r.parts > 1 ? `part ${r.part} of ${r.parts} · ` : ''}
                  {r.duration_s != null ? hms(r.duration_s) : r.recording ? 'recording…' : '–'} · {size(r.size_bytes)}
                  {r.started_by ? ` · started by ${r.started_by}` : ''}
                  {r.stop_reason && r.stop_reason !== 'stopped' ? ` · ${r.stop_reason === 'disk_low' ? 'stopped: laptop disk nearly full'
                    : r.stop_reason === 'max_length' ? 'stopped at the maximum length' : 'camera stream ended'}` : ''}
                </div>
              </div>
              <div className="ml-auto flex gap-2">
                <button className="btn-ghost btn-sm" disabled={r.recording} onClick={() => open(r)}><Play size={13} /> Play</button>
                <button className="btn-ghost btn-sm" disabled={r.recording} onClick={() => open(r, true)}><Download size={13} /> Download</button>
              </div>
            </div>))}
        </div>)}
    </div>
  )
}
