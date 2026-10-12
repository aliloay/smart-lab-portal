/**
 * Networked equipment (robots, PCs) as their collector / agent reports them.
 *
 * Robots are monitored read-only (no command exists). For PCs, staff set
 * the mode (NORMAL / EXAM / MAINTENANCE); in exam mode the agent reports
 * prohibited programs, listed here for staff - nothing is decided
 * automatically about a student. FANUC appears once its controller has been
 * identified and a collector exists.
 *
 * Admin master PC (System 1): from here staff remove / give access to a PC
 * (mode LOCKED keeps it locked), view its screen while they watch, and send
 * a message - per PC or to all PCs at once. Every action is audited.
 *
 * The lab engineer's master PC is controlled by an administrator only: lab
 * staff see it, but not its controls, and "Lock all" leaves it alone.
 */
import { useCallback, useEffect, useState } from 'react'
import { Bot, Crown, Lock, MessageSquare, Monitor, MonitorPlay, ShieldAlert, Unlock } from 'lucide-react'
import { api, type PcMode } from '../lib/api'
import { isAdmin, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import { PcMessageModal, PcScreenViewer } from './PcControls'
import { Chip, SectionTitle } from './ui'

type Equip = Awaited<ReturnType<typeof api.equipment>>[number]
type Violation = Awaited<ReturnType<typeof api.equipmentViolations>>[number]

function hours(s: number) {
  return s >= 3600 ? `${(s / 3600).toFixed(1)} h` : `${Math.round(s / 60)} min`
}

export default function NetworkedEquipment() {
  const [items, setItems] = useState<Equip[] | null>(null)
  const [violations, setViolations] = useState<Violation[]>([])
  const [viewing, setViewing] = useState<Equip | null>(null)
  const [messaging, setMessaging] = useState<Equip | null>(null)
  const [busy, setBusy] = useState(false)
  const admin = isAdmin(useAuth().user)
  const closeViewer = useCallback(() => setViewing(null), [])
  const load = useCallback(() => {
    // Robots have their own panels above (live twin); this list is the PCs' agents.
    api.equipment().then(r => setItems(r.filter(e => e.kind === 'PC'))).catch(() => setItems([]))
    api.equipmentViolations().then(setViolations).catch(() => setViolations([]))
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 10000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => { if (m.type === 'access_event' || m.type === 'staff') load() })

  if (!items || !items.length) return null          // no PC agent yet: the Lab PCs card says so
  async function setMode(id: number, mode: PcMode) {
    await api.setEquipmentMode(id, mode).catch(() => {})
    load()
  }
  async function setMaster(e: Equip) {
    const what = e.is_master_pc
      ? `${e.name} is no longer the master PC: lab staff can control it again.`
      : `Make ${e.name} the lab engineer's master PC? Only administrators can control it then.`
    if (!window.confirm(what)) return
    await api.setMasterPc(e.device_id, !e.is_master_pc).catch(err => window.alert(err.message))
    load()
  }
  // Bulk actions never touch the master PC.
  const pcs = items.filter(e => e.kind === 'PC' && !e.is_master_pc)
  async function setAll(mode: 'LOCKED' | 'NORMAL') {
    const what = mode === 'LOCKED' ? 'Remove access on ALL lab PCs? They lock now and stay locked.'
      : 'Give access back on all locked PCs?'
    if (!window.confirm(what)) return
    setBusy(true)
    await Promise.all(pcs.filter(e => mode === 'LOCKED' ? e.mode !== 'LOCKED' : e.mode === 'LOCKED')
      .map(e => api.setEquipmentMode(e.device_id, mode).catch(() => {})))
    setBusy(false)
    load()
  }

  return (
    <section className="mb-6">
      <SectionTitle icon={<Bot size={15} />}
        sub="Robots read-only over the lab LAN; PCs through the lab agent."
        action={pcs.length > 0 ? (
          <div className="flex gap-2">
            <button className="btn-ghost btn-sm" disabled={busy} onClick={() => setAll('LOCKED')}>
              <Lock size={13} /> Lock all PCs</button>
            <button className="btn-ghost btn-sm" disabled={busy || !pcs.some(e => e.mode === 'LOCKED')}
                    onClick={() => setAll('NORMAL')}><Unlock size={13} /> Unlock all</button>
          </div>) : undefined}>Networked equipment</SectionTitle>
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
                  {e.is_master_pc && <Chip tone="violet" className="ml-auto shrink-0"><Crown size={11} /> Master PC</Chip>}
                  <Chip tone={tone} dot className={e.is_master_pc ? 'shrink-0' : 'ml-auto'}>
                    {e.online === false ? 'offline' : (e.state ?? 'no data').toLowerCase()}</Chip>
                </div>
                <div className="text-[12.5px] text-slate-300 space-y-0.5">
                  {e.user_name && <div>Booking: <b className="text-white">{e.user_name}</b></div>}
                  {e.kind === 'PC' && e.detail?.os_user ? <div>Signed in: <span className="mono">{String(e.detail.os_user)}</span></div> : null}
                  <div>Running today: {hours(e.running_today_s)}</div>
                  {e.since && e.online !== false && <div className="text-slate-500">In this state since {relative(e.since)}</div>}
                  <div className="text-slate-500">Last report {e.last_seen_at ? relative(e.last_seen_at) : 'never'}</div>
                </div>
                {e.kind === 'PC' && e.is_master_pc && !admin && (
                  <div className="text-[12px] text-slate-400 pt-1">
                    The lab engineer's master PC: controlled by an administrator.</div>)}
                {e.kind === 'PC' && (admin || !e.is_master_pc) && (
                  <div className="flex items-center gap-2 pt-1">
                    <span className="text-[11.5px] text-slate-400">Mode</span>
                    {e.mode === 'LOCKED'
                      ? <Chip tone="bad" dot>Access removed</Chip>
                      : <select className="input !py-1 !text-[12.5px] w-auto" value={e.mode}
                                onChange={ev => setMode(e.device_id, ev.target.value as PcMode)}>
                          <option value="NORMAL">Normal</option><option value="EXAM">Exam</option>
                          <option value="MAINTENANCE">Maintenance</option></select>}
                    {e.open_violations > 0 && <Chip tone="warn">{e.open_violations} violation{e.open_violations > 1 ? 's' : ''}</Chip>}
                  </div>)}
                {e.kind === 'PC' && (admin || !e.is_master_pc) && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {e.mode === 'LOCKED'
                      ? <button className="btn-ghost btn-sm" onClick={() => setMode(e.device_id, 'NORMAL')}>
                          <Unlock size={13} /> Give access</button>
                      : <button className="btn-ghost btn-sm" onClick={() => {
                          if (window.confirm(`Remove access on ${e.name}? It locks now and stays locked until you give access.`))
                            setMode(e.device_id, 'LOCKED')
                        }}><Lock size={13} /> Remove access</button>}
                    <button className="btn-ghost btn-sm" disabled={e.online === false} onClick={() => setViewing(e)}>
                      <MonitorPlay size={13} /> View screen</button>
                    <button className="btn-ghost btn-sm" disabled={e.online === false} onClick={() => setMessaging(e)}>
                      <MessageSquare size={13} /> Message</button>
                    {admin && <button className="btn-ghost btn-sm" onClick={() => setMaster(e)}>
                      <Crown size={13} /> {e.is_master_pc ? 'Not master PC' : 'Make master PC'}</button>}
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
      {viewing && <PcScreenViewer deviceId={viewing.device_id} name={viewing.name} onClose={closeViewer} />}
      <PcMessageModal deviceId={messaging?.device_id ?? 0} name={messaging?.name ?? ''}
                      open={messaging !== null} onClose={() => setMessaging(null)} />
    </section>
  )
}
