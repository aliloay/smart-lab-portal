/**
 * Workcell editor for one robot twin: named setups (saved on the server, versioned), the table
 * (present / height / position) and box obstacles. Everything here is MANUAL unless marked
 * CAMERA_ESTIMATE - the panel says so; nothing is ever shown as physically verified.
 * Planning aid only: no robot is read from or commanded here.
 */
import { memo, useEffect, useState } from 'react'
import { Box, Plus, Save, Trash2, TriangleAlert } from 'lucide-react'
import { api } from '../../lib/api'
import { isAdmin, useAuth } from '../../lib/auth'
import { Hit, Obstacle, Workcell, defaultWorkcell } from './workcell'

const num = (v: string, f: number) => { const n = parseFloat(v); return Number.isFinite(n) ? n : f }
const F = ({ label, value, on, step = 0.01 }: { label: string; value: number; on: (n: number) => void; step?: number }) => (
  <label className="flex items-center gap-1 text-[11px] text-slate-400">{label}
    <input type="number" step={step} value={Number(value.toFixed(3))} onChange={e => on(num(e.target.value, value))}
           className="input !py-0.5 !px-1.5 !text-[11.5px] w-[68px]" /></label>)

function WorkcellEditor({ robotKey, cell, onChange, hits, selected, onSelect, poseKnown }: {
  robotKey: 'UR5E' | 'FANUC'; cell: Workcell; onChange: (c: Workcell) => void; hits: Hit[]
  selected: string | null; onSelect: (id: string | null) => void; poseKnown: boolean
}) {
  const { user } = useAuth()
  const admin = isAdmin(user)
  const [setups, setSetups] = useState<{ name: string; data: Workcell }[]>([])
  const [name, setName] = useState('default')
  const [msg, setMsg] = useState('')
  useEffect(() => { api.workcells(robotKey).then(setSetups).catch(() => setSetups([])) }, [robotKey])

  const t = cell.table
  const setO = (id: string, patch: Partial<Obstacle>) => onChange({ ...cell, obstacles: cell.obstacles.map(o => o.id === id ? { ...o, ...patch } : o) })
  const add = () => {
    const id = `b${Date.now().toString(36)}`
    const z = (t?.present ? t.height : 0) + 0.075
    onChange({ ...cell, obstacles: [...cell.obstacles, { id, label: `Box ${cell.obstacles.length + 1}`, x: 0, y: 0, z, w: 0.15, d: 0.15, h: 0.15, source: 'MANUAL' }] })
    onSelect(id)
  }
  const save = async () => {
    try { await api.saveWorkcell(robotKey, name, cell); setMsg(`Saved "${name}"`); setSetups(await api.workcells(robotKey)) }
    catch (e) { setMsg(e instanceof Error ? e.message : 'Save failed') }
  }
  const sel = cell.obstacles.find(o => o.id === selected)

  return (
    <div className="border-t border-ink-700/60 p-4 space-y-3 text-[12px]">
      <div className="flex flex-wrap items-center gap-2">
        <Box size={14} className="text-amber-300" /><span className="font-medium text-slate-200">Workcell (virtual)</span>
        <span className="text-[10.5px] px-1.5 py-0.5 rounded border border-amber-400/40 text-amber-200">MANUAL · not verified</span>
        <select className="input !py-0.5 !text-[12px] w-auto ml-auto" value=""
                onChange={e => { const s = setups.find(x => x.name === e.target.value); if (s) { onChange(s.data); setName(s.name); setMsg(`Loaded "${s.name}"`) } }}>
          <option value="">Load setup…</option>{setups.map(s => <option key={s.name}>{s.name}</option>)}
        </select>
        <button type="button" className="btn-ghost btn-sm" onClick={() => onChange(defaultWorkcell(robotKey))}>Defaults</button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-1.5 text-slate-300">
          <input type="checkbox" checked={!!t?.present} onChange={e => onChange({ ...cell, table: { ...(t ?? defaultWorkcell('UR5E').table!), present: e.target.checked } })} /> Table</label>
        {t?.present && <>
          <F label="height" value={t.height} on={v => onChange({ ...cell, table: { ...t, height: v } })} />
          <F label="x0" value={t.x0} on={v => onChange({ ...cell, table: { ...t, x0: v } })} />
          <F label="x1" value={t.x1} on={v => onChange({ ...cell, table: { ...t, x1: v } })} />
          <F label="y0" value={t.y0} on={v => onChange({ ...cell, table: { ...t, y0: v } })} />
          <F label="y1" value={t.y1} on={v => onChange({ ...cell, table: { ...t, y1: v } })} />
        </>}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {cell.obstacles.map(o => (
          <button key={o.id} type="button" onClick={() => onSelect(o.id === selected ? null : o.id)}
                  className={`px-2 py-0.5 rounded-md border text-[11.5px] ${o.id === selected ? 'border-white/70 text-white' : 'border-ink-600 text-slate-300'}
                    ${hits.some(h => h.obstacle === o.id) ? '!border-bad/70 !text-bad-soft' : ''}`}>
            {o.label}{o.source === 'CAMERA_ESTIMATE' && ' (est.)'}</button>))}
        <button type="button" className="btn-ghost btn-sm" onClick={add}><Plus size={12} /> Box</button>
      </div>

      {sel && <div className="flex flex-wrap items-center gap-2 rounded-md bg-ink-900/50 p-2">
        <input className="input !py-0.5 !text-[12px] w-28" value={sel.label} maxLength={48} onChange={e => setO(sel.id, { label: e.target.value })} />
        {(['x', 'y', 'z', 'w', 'd', 'h'] as const).map(k => <F key={k} label={k} value={sel[k]} on={v => setO(sel.id, { [k]: k === 'w' || k === 'd' || k === 'h' ? Math.max(0.01, v) : v })} />)}
        {sel.source === 'CAMERA_ESTIMATE' && <span className="text-violet-300 text-[11px]">camera estimate ±{sel.uncertainty_m ?? '?'} m - correct it here</span>}
        <button type="button" className="btn-ghost btn-sm text-bad-soft ml-auto" title="Remove from this setup (saved versions are kept)"
                onClick={() => { onChange({ ...cell, obstacles: cell.obstacles.filter(o => o.id !== sel.id) }); onSelect(null) }}><Trash2 size={12} /> Remove</button>
      </div>}

      <div className={`rounded-md p-2 text-[11.5px] ${hits.length ? 'bg-bad/10 border border-bad/40 text-bad-soft' : 'bg-ink-900/40 text-slate-400'}`}>
        {!poseKnown ? 'No current pose - collision check paused (nothing is claimed).'
          : hits.length ? <><TriangleAlert size={12} className="inline mr-1" />MODELLED contact (prediction, not a measured collision):{' '}
              {hits.map(h => `${h.link} ↔ ${h.label}`).filter((v, i, a) => a.indexOf(v) === i).join(', ')}</>
          : 'Model: no contact between the robot links and the virtual objects.'}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {admin ? <>
          <input className="input !py-0.5 !text-[12px] w-40" value={name} maxLength={64} onChange={e => setName(e.target.value)} aria-label="Setup name" />
          <button type="button" className="btn-ghost btn-sm" onClick={save}><Save size={12} /> Save setup</button>
        </> : <span className="text-[11px] text-slate-500">Only administrators can save setups.</span>}
        {msg && <span className="text-[11px] text-slate-400">{msg}</span>}
        <span className="ml-auto text-[10.5px] text-slate-500">Planning aid - not a safety system. Metres; +x front, z up, floor = 0.</span>
      </div>
    </div>)
}

export default memo(WorkcellEditor)
