/**
 * Networked equipment (robots, PCs) as their collector / agent reports them.
 *
 * Robots are monitored read-only (no command exists). For PCs, staff set
 * the mode (NORMAL / EXAM / MAINTENANCE); in exam mode the agent reports
 * prohibited programs, listed here for staff - nothing is decided
 * automatically about a student. FANUC appears once its controller has been
 * identified and a collector exists.
 */
import { useCallback, useEffect, useState } from 'react'
import { Bot, Monitor, ShieldAlert } from 'lucide-react'
import { api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import { Chip, SectionTitle } from './ui'

type Equip = Awaited<ReturnType<typeof api.equipment>>[number]
type Violation = Awaited<ReturnType<typeof api.equipmentViolations>>[number]

function hours(s: number) {
  return s >= 3600 ? `${(s / 3600).toFixed(1)} h` : `${Math.round(s / 60)} min`
}

export default function NetworkedEquipment() {
  const [items, setItems] = useState<Equip[] | null>(null)
  const [violations, setViolations] = useState<Violation[]>([])
  const load = useCallback(() => {
    api.equipment().then(setItems).catch(() => setItems([]))
    api.equipmentViolations().then(setViolations).catch(() => setViolations([]))
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 10000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => { if (m.type === 'access_event' || m.type === 'staff') load() })

  if (!items) return null
  async function setMode(id: number, mode: 'NORMAL' | 'EXAM' | 'MAINTENANCE') {
    await api.setEquipmentMode(id, mode).catch(() => {})
    load()
  }

  return (
    <section className="mb-6">
      <SectionTitle icon={<Bot size={15} />}
        sub="Robots read-only over the lab LAN; PCs through the lab agent.">Networked equipment</SectionTitle>
      {!items.length ? (
        <div className="card p-4 text-[13px] text-slate-400">
          No robot or PC is reporting yet. Start the UR5e collector (tools/ur5e_collector) or the PC agent
          (tools/pc_agent) on the lab network; each appears here on its first report. FANUC: identify the
          controller model first (see docs/ROBOTICS_LAB_ARCHITECTURE.md §N).
        </div>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map(e => {
            const tone = e.online === false ? 'bad' : e.state === 'FAULT' ? 'bad'
              : e.state === 'RUNNING' ? 'ok' : 'idle'
            return (
              <div key={e.device_id} className="card p-4 space-y-2">
                <div className="flex items-center gap-2">
                  {e.kind === 'ROBOT' ? <Bot size={16} className="text-accent-300" /> : <Monitor size={16} className="text-accent-300" />}
                  <div className="min-w-0">
                    <div className="text-white font-semibold truncate">{e.name}</div>
                    <div className="mono text-[11px] text-slate-400">{e.asset_tag ?? e.device_uid} · {e.lab_code}</div>
                  </div>
                  <Chip tone={tone} dot className="ml-auto">
                    {e.online === false ? 'offline' : (e.state ?? 'no data').toLowerCase()}</Chip>
                </div>
                <div className="text-[12.5px] text-slate-300 space-y-0.5">
                  {e.user_name && <div>Booking: <b className="text-white">{e.user_name}</b></div>}
                  {e.kind === 'PC' && e.detail?.os_user ? <div>Signed in: <span className="mono">{String(e.detail.os_user)}</span></div> : null}
                  <div>Running today: {hours(e.running_today_s)}</div>
                  {e.since && e.online !== false && <div className="text-slate-500">In this state since {relative(e.since)}</div>}
                  <div className="text-slate-500">Last report {e.last_seen_at ? relative(e.last_seen_at) : 'never'}</div>
                </div>
                {e.kind === 'PC' && (
                  <div className="flex items-center gap-2 pt-1">
                    <span className="text-[11.5px] text-slate-400">Mode</span>
                    <select className="input !py-1 !text-[12.5px] w-auto" value={e.mode}
                            onChange={ev => setMode(e.device_id, ev.target.value as 'NORMAL' | 'EXAM' | 'MAINTENANCE')}>
                      <option value="NORMAL">Normal</option><option value="EXAM">Exam</option>
                      <option value="MAINTENANCE">Maintenance</option></select>
                    {e.open_violations > 0 && <Chip tone="warn">{e.open_violations} violation{e.open_violations > 1 ? 's' : ''}</Chip>}
                  </div>)}
              </div>)
          })}
        </div>
      )}
      {violations.length > 0 && (
        <div className="card mt-4 p-4">
          <div className="label mb-2 flex items-center gap-1.5"><ShieldAlert size={13} /> Exam-mode reports</div>
          <ul className="space-y-1 text-[12.5px]">
            {violations.slice(0, 8).map(v => (
              <li key={v.id} className="flex gap-2">
                <span className="mono text-slate-300">{v.device_uid}</span>
                <span className="text-warn-soft">{v.detail}</span>
                {v.os_user && <span className="text-slate-400">({v.os_user})</span>}
                <span className="ml-auto text-slate-500">{relative(v.created_at)}</span>
              </li>))}
          </ul>
          <p className="mt-2 text-[11px] text-slate-500">A report is what the agent saw running; staff decide what it means.</p>
        </div>
      )}
    </section>
  )
}
