/**
 * Report an issue: what, where, which equipment, how serious, describe,
 * photos. One page of numbered sections rather than a wizard, so a person
 * standing in a laboratory can finish in under a minute; anything the
 * context already knows (the lab, the equipment) arrives pre-filled.
 */
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  AlertOctagon, ArrowRight, Ban, Boxes, Bug, Check, Cpu, FileQuestion, Hammer,
  KeyRound, PackageX, ShieldAlert, Wifi, Wrench,
} from 'lucide-react'
import {
  Asset, Device, IssueCategory, IssueDetail, IssueSeverity, Lab, api,
} from '../../lib/api'
import { ISSUE_CATEGORIES, SEVERITIES } from '../../lib/labels'
import { fmtDateTime } from '../../lib/time'
import { isStaff, useAuth } from '../../lib/auth'
import {
  ErrorBanner, IssueStatusChip, KV, Notice, PageHeader, ProgressBar, SeverityBadge,
  SuccessMark,
} from '../../components/ui'
import { PhotoPicker, PickedFile } from '../../components/media'

const CAT_ICON: Record<IssueCategory, JSX.Element> = {
  DAMAGED: <Hammer size={18} />, MISSING: <PackageX size={18} />, MALFUNCTION: <Ban size={18} />,
  MAINTENANCE: <Wrench size={18} />, SAFETY: <ShieldAlert size={18} />, SOFTWARE: <Bug size={18} />,
  NETWORK: <Wifi size={18} />, ACCESS_CONTROL: <KeyRound size={18} />, OTHER: <FileQuestion size={18} />,
}

const SEV_STYLE: Record<IssueSeverity, string> = {
  LOW: 'border-slate-400/50 bg-slate-400/10',
  MEDIUM: 'border-accent-400/60 bg-accent-500/10',
  HIGH: 'border-warn/60 bg-warn/10',
  CRITICAL: 'border-bad/60 bg-bad/10',
}

/** Remounted with a new key to start a fresh report - no page reload. */
export default function ReportIssue() {
  const [k, setK] = useState(0)
  return <ReportIssueForm key={k} onAnother={() => { setK(n => n + 1); window.scrollTo(0, 0) }} />
}

function ReportIssueForm({ onAnother }: { onAnother: () => void }) {
  const [params] = useSearchParams()
  const { user } = useAuth()
  const [labs, setLabs] = useState<Lab[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [devices, setDevices] = useState<Device[]>([])

  const [category, setCategory] = useState<IssueCategory | null>(null)
  const [labId, setLabId] = useState<number | null>(Number(params.get('lab')) || null)
  const [assetId, setAssetId] = useState<number | null>(Number(params.get('asset')) || null)
  const [deviceId, setDeviceId] = useState<number | null>(Number(params.get('device')) || null)
  const eventId = Number(params.get('event')) || null
  const [severity, setSeverity] = useState<IssueSeverity | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [comments, setComments] = useState('')
  const [files, setFiles] = useState<PickedFile[]>([])

  const [touched, setTouched] = useState(false)
  const [error, setError] = useState('')
  const [phase, setPhase] = useState<'form' | 'saving' | 'uploading'>('form')
  const [progress, setProgress] = useState(0)
  const [done, setDone] = useState<{ issue: IssueDetail; photoError?: string } | null>(null)

  useEffect(() => { api.labs().then(setLabs).catch(() => {}) }, [])
  // An asset link implies its laboratory.
  useEffect(() => {
    const a = Number(params.get('asset'))
    if (a && !params.get('lab')) api.asset(a).then(d => setLabId(d.lab.id)).catch(() => {})
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!labId) { setAssets([]); setDevices([]); return }
    api.assets(labId).then(setAssets).catch(() => setAssets([]))
    if (isStaff(user)) api.devices(labId).then(setDevices).catch(() => setDevices([]))
    else api.lab(labId).then(s => setDevices(s.devices)).catch(() => setDevices([]))
  }, [labId, user])

  const lab = labs.find(l => l.id === labId)
  const asset = assets.find(a => a.id === assetId)
  const device = devices.find(d => d.id === deviceId)

  const problems = useMemo(() => {
    const p: string[] = []
    if (!category) p.push('choose what is wrong')
    if (!labId) p.push('choose the laboratory')
    if (!severity) p.push('choose how serious it is')
    if (title.trim().length < 5) p.push('give it a short title (5+ characters)')
    if (description.trim().length < 10) p.push('describe it (10+ characters)')
    return p
  }, [category, labId, severity, title, description])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (problems.length) return
    setError(''); setPhase('saving')
    let created: IssueDetail
    try {
      created = await api.createIssue({
        lab_id: labId!, asset_id: assetId, device_id: deviceId, access_event_id: eventId,
        category: category!, severity: severity!, title: title.trim(),
        description: description.trim(), additional_comments: comments.trim(),
      })
    } catch (err) {
      setPhase('form')
      setError(err instanceof Error ? err.message : 'Could not submit the report')
      return
    }
    if (files.length) {
      setPhase('uploading'); setProgress(0)
      try {
        await api.uploadIssuePhotos(created.id, files.map(f => f.file), 'REPORT', setProgress)
      } catch (err) {
        // The report exists; say exactly what did not make it.
        setDone({ issue: created, photoError: err instanceof Error ? err.message : 'Upload failed' })
        return
      }
    }
    setDone({ issue: created })
  }

  if (done) return <Submitted issue={done.issue} photoError={done.photoError}
                              assetName={asset?.name ?? device?.name}
                              onAnother={onAnother} />

  const busy = phase !== 'form'
  const sectionCls = 'card p-5'

  return (
    <form onSubmit={submit} className="max-w-3xl mx-auto space-y-4" noValidate>
      <PageHeader eyebrow="Maintenance & operations" title="Report an issue"
        sub="Broken, missing, unsafe or not working? Tell the laboratory team - it takes about a minute." />

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      <Section n={1} title="What is wrong?" done={!!category} className={sectionCls}>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {ISSUE_CATEGORIES.map(c => (
            <button type="button" key={c.value} onClick={() => setCategory(c.value)}
              aria-pressed={category === c.value}
              className={`text-left rounded-xl border p-3 transition-all ${category === c.value
                ? 'border-accent-400 bg-accent-500/10 ring-2 ring-accent-500/25'
                : 'border-ink-600 bg-ink-900/40 hover:border-ink-400'}`}>
              <div className="flex items-center gap-2 text-[13.5px] text-white">
                <span className="text-accent-300">{CAT_ICON[c.value]}</span>{c.label}
              </div>
              <div className="mt-1 text-[11.5px] text-slate-400 leading-snug">{c.hint}</div>
            </button>
          ))}
        </div>
      </Section>

      <Section n={2} title="Where?" done={!!labId} className={sectionCls}>
        <select className="input" value={labId ?? ''} aria-label="Laboratory"
                onChange={e => { setLabId(Number(e.target.value) || null); setAssetId(null); setDeviceId(null) }}>
          <option value="">Choose a laboratory…</option>
          {labs.map(l => <option key={l.id} value={l.id}>{l.code} · {l.name}</option>)}
        </select>
      </Section>

      <Section n={3} title="Which equipment?" done={!!labId} optional className={sectionCls}>
        {!labId ? <p className="text-[13px] text-slate-400">Choose the laboratory first.</p> : (
          <div className="grid sm:grid-cols-2 gap-2 max-h-72 overflow-y-auto pr-1">
            <Choice selected={!assetId && !deviceId} onClick={() => { setAssetId(null); setDeviceId(null) }}
                    icon={<Boxes size={15} />} title="General laboratory issue"
                    sub="Not tied to one item - the room, furniture, power…" />
            {assets.map(a => (
              <Choice key={`a${a.id}`} selected={assetId === a.id}
                      onClick={() => { setAssetId(a.id); setDeviceId(null) }}
                      icon={<Wrench size={15} />} title={a.name} sub={`${a.asset_tag} · ${a.category}`} />
            ))}
            {devices.map(d => (
              <Choice key={`d${d.id}`} selected={deviceId === d.id}
                      onClick={() => { setDeviceId(d.id); setAssetId(null) }}
                      icon={<Cpu size={15} />} title={d.name} sub={`Access device · ${d.device_uid}`} />
            ))}
          </div>
        )}
        {eventId && <div className="mt-3"><Notice>Linked to access event #{eventId}.</Notice></div>}
      </Section>

      <Section n={4} title="How serious?" done={!!severity} className={sectionCls}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {SEVERITIES.map(s => (
            <button type="button" key={s.value} onClick={() => setSeverity(s.value)}
              aria-pressed={severity === s.value}
              className={`text-left rounded-xl border p-3 transition-all ${severity === s.value
                ? SEV_STYLE[s.value] + ' ring-2 ring-white/10' : 'border-ink-600 bg-ink-900/40 hover:border-ink-400'}`}>
              <SeverityBadge severity={s.value} />
              <div className="mt-1.5 text-[11.5px] text-slate-400 leading-snug">{s.hint}</div>
            </button>
          ))}
        </div>
        {severity === 'CRITICAL' && (
          <div className="mt-3"><Notice tone="warn" icon={<AlertOctagon size={15} />}>
            If anyone is in danger, leave the area and contact the laboratory staff or security
            directly. This report notifies every staff member immediately.</Notice></div>
        )}
      </Section>

      <Section n={5} title="Describe it" done={title.trim().length >= 5 && description.trim().length >= 10}
               className={sectionCls}>
        <div className="space-y-3">
          <div>
            <label className="label block mb-1.5" htmlFor="title">Short title</label>
            <input id="title" className="input" value={title} maxLength={140}
                   placeholder={asset ? `${asset.name} not working` : 'e.g. PLC in LAB_03 is not powering on'}
                   onChange={e => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="label block mb-1.5" htmlFor="desc">What happened?</label>
            <textarea id="desc" className="input min-h-[110px]" value={description} maxLength={4000}
                      placeholder="What you saw, when it started, what you already tried."
                      onChange={e => setDescription(e.target.value)} />
            <div className="text-right text-[11px] text-slate-500">{description.length}/4000</div>
          </div>
          <div>
            <label className="label block mb-1.5" htmlFor="more">Anything else? <span className="normal-case tracking-normal text-slate-500">(optional)</span></label>
            <input id="more" className="input" value={comments} maxLength={2000}
                   placeholder="e.g. Workstation 4, near the window"
                   onChange={e => setComments(e.target.value)} />
          </div>
        </div>
      </Section>

      <Section n={6} title="Add photos" done={files.length > 0} optional className={sectionCls}>
        <PhotoPicker files={files} onChange={setFiles} disabled={busy} />
      </Section>

      <div className="sticky bottom-3 z-20 card p-4 flex flex-col sm:flex-row sm:items-center gap-3
                      !bg-ink-850/95 backdrop-blur">
        <div className="flex-1 text-[12.5px]">
          {phase === 'uploading' ? (
            <div>
              <div className="text-slate-200 mb-1.5">Uploading {files.length} photo{files.length > 1 ? 's' : ''}… {Math.round(progress * 100)}%</div>
              <ProgressBar value={progress} />
            </div>
          ) : touched && problems.length ? (
            <span className="text-warn-soft">Still needed: {problems.join(', ')}.</span>
          ) : (
            <span className="text-slate-400">
              {lab ? <>Reporting in <b className="text-slate-200">{lab.code}</b></> : 'Staff are notified as soon as you submit.'}
            </span>
          )}
        </div>
        <button type="submit" className="btn-primary !px-6" disabled={busy}>
          {phase === 'saving' ? 'Submitting…' : phase === 'uploading' ? 'Uploading…' : 'Submit report'}
          {!busy && <ArrowRight size={16} />}
        </button>
      </div>
    </form>
  )
}

function Section({ n, title, done, optional, className, children }: {
  n: number; title: string; done: boolean; optional?: boolean; className?: string
  children: React.ReactNode
}) {
  return (
    <section className={className}>
      <h2 className="flex items-center gap-2.5 mb-3.5 text-[15px] font-semibold text-white">
        <span className={`grid place-items-center w-7 h-7 rounded-full text-[12px] border
          ${done ? 'bg-ok/20 border-ok/45 text-ok-soft' : 'bg-ink-800 border-ink-500 text-slate-300'}`}>
          {done ? <Check size={13} strokeWidth={3} /> : n}
        </span>
        {title}
        {optional && <span className="text-[11.5px] font-normal text-slate-500">optional</span>}
      </h2>
      {children}
    </section>
  )
}

function Choice({ selected, onClick, icon, title, sub }: {
  selected: boolean; onClick: () => void; icon: JSX.Element; title: string; sub: string
}) {
  return (
    <button type="button" onClick={onClick} aria-pressed={selected}
      className={`text-left rounded-xl border p-3 flex gap-2.5 transition-all ${selected
        ? 'border-accent-400 bg-accent-500/10' : 'border-ink-600 bg-ink-900/40 hover:border-ink-400'}`}>
      <span className="text-accent-300 mt-0.5">{icon}</span>
      <span className="min-w-0">
        <span className="block text-[13px] text-white truncate">{title}</span>
        <span className="block text-[11.5px] text-slate-400 truncate">{sub}</span>
      </span>
    </button>
  )
}

function Submitted({ issue, photoError, assetName, onAnother }: {
  issue: IssueDetail; photoError?: string; assetName?: string; onAnother: () => void
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="max-w-lg mx-auto card p-7 text-center">
      <div className="inline-block"><SuccessMark /></div>
      <div className="mt-3 eyebrow !text-ok-soft">Issue reported</div>
      <h1 className="mt-1 font-display text-[26px] font-semibold text-white tnum">{issue.ticket_number}</h1>
      <p className="mt-1 text-[13.5px] text-slate-300">
        Issue {issue.ticket_number} has been submitted. Laboratory staff have been notified.
      </p>
      <dl className="mt-6 well p-4 text-left">
        <KV label="Laboratory">{issue.lab_name}</KV>
        <KV label="Equipment">{assetName ?? issue.asset_name ?? 'General laboratory issue'}</KV>
        <KV label="Severity"><SeverityBadge severity={issue.severity} /></KV>
        <KV label="Status"><IssueStatusChip status={issue.status} /></KV>
        <KV label="Reported">{fmtDateTime(issue.created_at)}</KV>
      </dl>
      {photoError && (
        <div className="mt-4 text-left"><ErrorBanner title="The photos were not attached"
          message={`${photoError} You can add them from the issue page.`} /></div>
      )}
      <div className="mt-6 flex flex-col sm:flex-row gap-2.5 justify-center">
        <Link to={`/issues/${issue.id}`} className="btn-primary">Follow this issue</Link>
        <button onClick={onAnother} className="btn-ghost">Report another</button>
        <Link to="/issues" className="btn-quiet">All reports</Link>
      </div>
    </motion.div>
  )
}
