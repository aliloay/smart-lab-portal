/**
 * Thesis experiments (staff).
 *
 * Plan an experiment (what, on which device and firmware, under which
 * condition, what is expected), START it - every new door event, reading,
 * alert, booking, session, ticket and camera event is then stamped with its
 * data mode (normally PHYSICAL_TEST) and its code - record each repeat as a
 * trial with its measurement, STOP it with the actual result.
 *
 * The current data mode (what new records are stamped with when no
 * experiment runs) is shown here and changed by an administrator under
 * Settings. Nothing on this page edits or deletes recorded data.
 */
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { FlaskConical, Play, Plus, Square } from 'lucide-react'
import { Experiment, Provenance, api } from '../lib/api'
import { isAdmin, useAuth } from '../lib/auth'
import { fmtDateTime } from '../lib/time'
import { Chip, Drawer, EmptyState, ErrorBanner, Field, Modal, Notice, PageHeader, Skeleton } from '../components/ui'

const MODES: Provenance[] = ['REAL_OPERATION', 'PHYSICAL_TEST', 'BENCH_TEST', 'SOFTWARE_TEST', 'DEMO_DATA',
  'UNKNOWN_PROVENANCE']
const STATUS_TONE = { PLANNED: 'idle', RUNNING: 'ok', FINISHED: 'info' } as const
const RESULT_TONE = { PASS: 'ok', FAIL: 'bad', PARTIAL: 'warn', INCONCLUSIVE: 'idle', NA: 'idle' } as const
const SUBSYSTEMS = ['DOOR', 'ENVIRONMENT', 'CAMERA', 'INVENTORY', 'NETWORK', 'PC', 'ROBOT', 'AI', 'N8N', 'POWER']

export default function Experiments() {
  const { user } = useAuth()
  const [list, setList] = useState<Experiment[] | null>(null)
  const [mode, setMode] = useState<{ mode: Provenance; experiment_id: number | null } | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.experiments().then(setList).catch(e => { setError(e.message); setList([]) })
    api.dataMode().then(setMode).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load])

  async function changeMode(m: Provenance) {
    try { await api.setDataMode(m); load() } catch (e) { setError(e instanceof Error ? e.message : 'Failed') }
  }

  return (
    <div>
      <PageHeader eyebrow="Thesis" title="Experiments"
        sub="Controlled physical experiments: every record made while one runs is stamped with its code."
        actions={<button className="btn-primary" onClick={() => setCreating(true)}><Plus size={16} />Plan experiment</button>} />
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}

      <div className="card p-4 mb-4 flex flex-wrap items-center gap-3">
        <div>
          <div className="label">New records are stamped</div>
          <div className="text-white font-semibold mono" data-testid="data-mode">{mode ? mode.mode : '…'}
            {mode?.experiment_id && <span className="ml-2 text-ok-soft text-[12px]">(an experiment is running)</span>}</div>
        </div>
        {isAdmin(user) && !mode?.experiment_id && (
          <label className="ml-auto text-[12.5px] text-slate-300 flex items-center gap-2">Data mode
            <select className="input w-auto" value={mode?.mode ?? ''} onChange={e => changeMode(e.target.value as Provenance)}>
              {MODES.map(m => <option key={m} value={m}>{m}</option>)}</select></label>)}
        <p className="basis-full text-[12px] text-slate-500">Changing the mode affects new records only. Existing
          records keep their provenance; history that cannot be proven stays UNKNOWN_PROVENANCE.</p>
      </div>

      <div className="card overflow-hidden">
        {list === null ? <div className="p-4"><Skeleton className="h-40" /></div>
          : !list.length ? <EmptyState icon={<FlaskConical size={20} />} title="No experiments yet"
              detail="Plan one, start it, run the trials on the real hardware, record each result, then stop it." />
          : (
            <table className="w-full">
              <thead><tr><th className="th">Code</th><th className="th">Experiment</th><th className="th">Subsystem</th>
                <th className="th">Status</th><th className="th">Result</th><th className="th">Started</th></tr></thead>
              <tbody>{list.map(e => (
                <tr key={e.id} className="tr cursor-pointer" onClick={() => setOpen(e.id)}>
                  <td className="td mono text-accent-200">{e.code}</td>
                  <td className="td text-slate-100">{e.name}</td>
                  <td className="td text-slate-300">{e.subsystem}</td>
                  <td className="td"><Chip tone={STATUS_TONE[e.status]} dot>{e.status.toLowerCase()}</Chip></td>
                  <td className="td">{e.result ? <Chip tone={RESULT_TONE[e.result]}>{e.result}</Chip> : '—'}</td>
                  <td className="td text-slate-400 text-[12.5px]">{e.started_at ? fmtDateTime(e.started_at) : '—'}</td>
                </tr>))}</tbody>
            </table>)}
      </div>

      <Drawer open={open !== null} onClose={() => { setOpen(null); load() }} title="Experiment" width="sm:w-[620px]">
        {open !== null && <ExperimentDetail id={open} onChange={load} />}
      </Drawer>
      {creating && <PlanExperiment onClose={() => setCreating(false)} onSaved={() => { setCreating(false); load() }} />}
    </div>
  )
}

function PlanExperiment({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: '', subsystem: 'DOOR', firmware_version: '', hardware_configuration: '',
    environment: '', network_state: '', test_condition: '', expected_result: '', notes: '',
    data_mode: 'PHYSICAL_TEST' as Provenance })
  const [error, setError] = useState('')
  async function save(e: FormEvent) {
    e.preventDefault()
    try { await api.createExperiment({ ...f, firmware_version: f.firmware_version || null }); onSaved() }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed') }
  }
  const text = (k: keyof typeof f, label: string, hint?: string) => (
    <Field label={label} hint={hint}><textarea className="input min-h-[52px]" value={f[k]}
      onChange={e => setF({ ...f, [k]: e.target.value })} /></Field>)
  return (
    <Modal open onClose={onClose} title="Plan an experiment">
      <form onSubmit={save} className="space-y-3">
        {error && <ErrorBanner message={error} />}
        <Field label="Name"><input className="input" required value={f.name} placeholder="Door: valid RFID card x 20"
          onChange={e => setF({ ...f, name: e.target.value })} /></Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Subsystem"><select className="input" value={f.subsystem}
            onChange={e => setF({ ...f, subsystem: e.target.value })}>{SUBSYSTEMS.map(s => <option key={s}>{s}</option>)}</select></Field>
          <Field label="Firmware"><input className="input" value={f.firmware_version} placeholder="env-0.1.0"
            onChange={e => setF({ ...f, firmware_version: e.target.value })} /></Field>
          <Field label="Records stamped"><select className="input" value={f.data_mode}
            onChange={e => setF({ ...f, data_mode: e.target.value as Provenance })}>
            {(['PHYSICAL_TEST', 'BENCH_TEST', 'SOFTWARE_TEST', 'DEMO_DATA'] as Provenance[]).map(m => <option key={m}>{m}</option>)}</select></Field>
        </div>
        {text('test_condition', 'Test condition', 'What exactly is done, e.g. card held 2 cm from the reader, 20 times')}
        {text('expected_result', 'Expected result')}
        {text('hardware_configuration', 'Hardware configuration', 'Wiring, supply, positions')}
        <div className="grid grid-cols-2 gap-3">
          {text('environment', 'Environment', 'Lighting, temperature, people present')}
          {text('network_state', 'Network', 'Smart_Lab, Wi-Fi signal')}
        </div>
        <button className="btn-primary w-full">Plan</button>
      </form>
    </Modal>
  )
}

function ExperimentDetail({ id, onChange }: { id: number; onChange: () => void }) {
  const [e, setE] = useState<Experiment | null>(null)
  const [t, setT] = useState({ input: '', expected: '', actual: '', measurement: '', unit: '', result: 'PASS', notes: '' })
  const [stop, setStop] = useState({ actual_result: '', result: 'PASS' })
  const [error, setError] = useState('')
  const load = useCallback(() => api.experiment(id).then(setE).catch(err => setError(err.message)), [id])
  useEffect(() => { load() }, [load])
  const run = async (f: () => Promise<unknown>) => {
    setError('')
    try { await f(); await load(); onChange() } catch (err) { setError(err instanceof Error ? err.message : 'Failed') }
  }
  if (!e) return error ? <ErrorBanner message={error} /> : <Skeleton className="h-60" />
  const next = (e.trials?.length ?? 0) + 1
  return (
    <div className="space-y-4">
      {error && <ErrorBanner message={error} />}
      <div className="flex items-center gap-2">
        <span className="mono text-accent-200">{e.code}</span><span className="text-white font-semibold">{e.name}</span>
        <Chip tone={STATUS_TONE[e.status]} dot className="ml-auto">{e.status.toLowerCase()}</Chip></div>
      <div className="text-[12.5px] text-slate-300 space-y-1">
        <div><span className="text-slate-500">Condition:</span> {e.test_condition || '—'}</div>
        <div><span className="text-slate-500">Expected:</span> {e.expected_result || '—'}</div>
        <div><span className="text-slate-500">Stamps records as:</span> <span className="mono">{e.data_mode}</span>
          {e.firmware_version && <> · firmware {e.firmware_version}</>}</div>
        {e.started_at && <div><span className="text-slate-500">Ran:</span> {fmtDateTime(e.started_at)}
          {e.ended_at && ` - ${fmtDateTime(e.ended_at)}`}</div>}
      </div>
      {e.status === 'PLANNED' && <button className="btn-primary w-full" onClick={() => run(() => api.startExperiment(e.id))}>
        <Play size={14} />Start - new records get {e.data_mode} and {e.code}</button>}

      {e.records && <Notice>Records stamped with {e.code}: {Object.entries(e.records).filter(([, n]) => n)
        .map(([k, n]) => `${n} ${k.replace(/_/g, ' ')}`).join(', ') || 'none yet'}.</Notice>}

      <div>
        <div className="label mb-2">Trials ({e.trials?.length ?? 0})</div>
        {!!e.trials?.length && (
          <table className="w-full text-[12.5px] mb-3"><thead><tr className="text-slate-500 text-left">
            <th>#</th><th>Input</th><th>Actual</th><th>Measurement</th><th>Result</th></tr></thead>
            <tbody>{e.trials.map(x => (
              <tr key={x.id} className="border-t border-ink-600/50"><td className="py-1 tnum">{x.repeat_number}</td>
                <td>{x.input}</td><td>{x.actual}</td>
                <td className="tnum">{x.measurement ?? '—'} {x.unit ?? ''}</td>
                <td>{x.result && <Chip tone={RESULT_TONE[x.result]}>{x.result}</Chip>}</td></tr>))}</tbody></table>)}
        {e.status === 'RUNNING' && (
          <form className="grid grid-cols-2 gap-2" onSubmit={ev => { ev.preventDefault(); run(() => api.addTrial(e.id, {
            repeat_number: next, input: t.input, expected: t.expected, actual: t.actual,
            measurement: t.measurement === '' ? null : Number(t.measurement), unit: t.unit || null,
            result: t.result as 'PASS' | 'FAIL' | 'NA', notes: t.notes })).then(() => setT({ ...t, actual: '', measurement: '', notes: '' })) }}>
            <input className="input" placeholder={`Trial ${next}: input`} value={t.input} onChange={x => setT({ ...t, input: x.target.value })} />
            <input className="input" placeholder="Expected" value={t.expected} onChange={x => setT({ ...t, expected: x.target.value })} />
            <input className="input" placeholder="Actual (observed)" required value={t.actual} onChange={x => setT({ ...t, actual: x.target.value })} />
            <div className="flex gap-2"><input className="input" placeholder="Measurement" inputMode="decimal" value={t.measurement}
              onChange={x => setT({ ...t, measurement: x.target.value })} />
              <input className="input w-20" placeholder="Unit" value={t.unit} onChange={x => setT({ ...t, unit: x.target.value })} /></div>
            <select className="input" value={t.result} onChange={x => setT({ ...t, result: x.target.value })}>
              <option>PASS</option><option>FAIL</option><option>NA</option></select>
            <button className="btn-ghost"><Plus size={14} />Record trial {next}</button>
          </form>)}
      </div>

      {e.status === 'RUNNING' && (
        <div className="card p-3 space-y-2">
          <div className="label">Stop and record the result</div>
          <textarea className="input min-h-[52px]" placeholder="Actual result (what was observed overall)"
            value={stop.actual_result} onChange={x => setStop({ ...stop, actual_result: x.target.value })} />
          <div className="flex gap-2">
            <select className="input" value={stop.result} onChange={x => setStop({ ...stop, result: x.target.value })}>
              <option>PASS</option><option>FAIL</option><option>PARTIAL</option><option>INCONCLUSIVE</option></select>
            <button className="btn-primary" onClick={() => run(() => api.stopExperiment(e.id, stop))}><Square size={14} />Stop</button>
          </div>
        </div>)}
      {e.status === 'FINISHED' && (
        <div className="text-[13px]"><span className="text-slate-500">Result:</span>{' '}
          {e.result ? <Chip tone={RESULT_TONE[e.result]}>{e.result}</Chip> : '—'} {e.actual_result}</div>)}
    </div>
  )
}
