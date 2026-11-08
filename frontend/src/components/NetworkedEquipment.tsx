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
import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot, Crown, GraduationCap, LayoutGrid, Lock, MessageSquare, Monitor, MonitorPlay, Power, RotateCw, ShieldAlert, Unlock, Wrench } from 'lucide-react'
import { api, type PcMode } from '../lib/api'
import { isAdmin, isStaff, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { pcStatus } from '../lib/pcStatus'
import { relative } from '../lib/time'
import { PcMessageModal, PcScreenViewer } from './PcControls'
import PcActions from './PcActions'
import { ScreenWall, SharePanel } from './ScreenShare'
import { Chip, SectionTitle } from './ui'
import { visibleInterval } from '../lib/visibleInterval'

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
  const [wall, setWall] = useState(false)
  const closeWall = useCallback(() => setWall(false), [])
  const me = useAuth().user
  const admin = isAdmin(me)
  // Owner 2026-11-03: the lab engineer (staff) is a master too - share screen, view, modes, messages on every
  // lab PC - except the admin's own PC (the portal laptop runs every service) and the current master PC.
  const staff = isStaff(me)
  const adminPc = (e: Equip) => /ADMIN/i.test(e.device_uid ?? '')
  const canCtl = (e: Equip) => admin || (staff && !adminPc(e))      // ACT-02: the engineer controls his own master PC too
  const closeViewer = useCallback(() => setViewing(null), [])
  const load = useCallback(() => {
    // Robots have their own panels above (live twin); this list is the PCs' agents.
    api.equipment().then(r => setItems(r.filter(e => e.kind === 'PC'))).catch(() => setItems([]))
    api.equipmentViolations().then(setViolations).catch(() => setViolations([]))
  }, [])
  useEffect(() => {
    load()
    const t = visibleInterval(load, 10000)
    return () => window.clearInterval(t)
  }, [load])
  const soon = useRef(0)
  useLiveMessages(m => {
    if (m.type === 'access_event' || m.type === 'staff') load()
    if (m.type === 'pc_state') { window.clearTimeout(soon.current); soon.current = window.setTimeout(load, 150) }
  })

  // No PC agent yet: the Lab PCs card says so; the admin can still share their screen.
  if (!items || !items.length) return staff ? <section className="mb-6"><SharePanel hasMasterPc={false} /></section> : null
  async function setMode(id: number, mode: PcMode) {
    let url: string | undefined
    if (mode === 'EXAM') {
      // Exam lockdown (2026-10-21): the PC closes other programs and shows only this page in a kiosk
      // Chrome window; anything else opened is closed and reported at once. Empty = report-only exam mode.
      let last = ''
      try { last = localStorage.getItem('smartlab.examUrl') ?? '' } catch { /* ignore */ }
      const answer = window.prompt('Exam page for the lockdown (the PC closes other programs and opens only this page). '
        + 'Leave empty to lock the PC down on the portal page.', last)
      if (answer === null) return
      url = answer.trim() || undefined
      if (url && !/^https?:\/\//i.test(url)) url = 'https://' + url
      try { if (url) localStorage.setItem('smartlab.examUrl', url) } catch { /* ignore */ }
    }
    await api.setEquipmentMode(id, mode, url).catch(err => window.alert(err.message))
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
  // Bulk actions also skip the old test cards (renamed "TEST - ..." on 2026-11-04).
  const pcs = items.filter(e => e.kind === 'PC' && !e.is_master_pc && !adminPc(e) && !/^TEST\b/i.test(e.name))
  async function setAll(mode: PcMode) {
    let url: string | undefined
    if (mode === 'EXAM') {
      let last = ''
      try { last = localStorage.getItem('smartlab.examUrl') ?? '' } catch { /* ignore */ }
      const answer = window.prompt(`Exam mode on ALL ${pcs.length} lab PCs. Exam page (every PC closes other programs `
        + 'and opens only this page). Leave empty for the portal page.', last)
      if (answer === null) return
      url = answer.trim() || undefined
      if (url && !/^https?:\/\//i.test(url)) url = 'https://' + url
      try { if (url) localStorage.setItem('smartlab.examUrl', url) } catch { /* ignore */ }
    } else {
      const what = mode === 'LOCKED' ? `Remove access on ALL ${pcs.length} lab PCs? Each signs out after a short countdown.`
        : mode === 'MAINTENANCE' ? `Maintenance (OUT OF ORDER) on ALL ${pcs.length} lab PCs? Mouse and keyboard stop working.`
        : 'Set every lab PC back to Normal (ends exam, maintenance and removed access)?'
      if (!window.confirm(what)) return
    }
    setBusy(true)
    await Promise.all(pcs.filter(e => e.mode !== mode)
      .map(e => api.setEquipmentMode(e.device_id, mode, url).catch(() => {})))
    setBusy(false)
    load()
  }
  async function unlockAll() {             // only the PCs whose access was removed; exam / maintenance stay
    const locked = pcs.filter(e => e.mode === 'LOCKED')
    if (!window.confirm(`Give access back to the ${locked.length} locked lab PC(s)?`)) return
    setBusy(true)
    await Promise.all(locked.map(e => api.setEquipmentMode(e.device_id, 'NORMAL').catch(() => {})))
    setBusy(false)
    load()
  }
  async function clearAllMessages() {
    if (!window.confirm(`Close the open messages on all ${pcs.length} lab PCs?`)) return
    setBusy(true)
    await Promise.all(pcs.map(e => api.pcMessageClear(e.device_id).catch(() => {})))
    setBusy(false)
  }
  async function powerAll(action: 'restart' | 'shutdown') {
    const what = action === 'restart'
      ? `RESTART all ${pcs.length} lab PCs? Every user gets a 1-minute warning to save.`
      : `SHUT DOWN all ${pcs.length} lab PCs? Every user gets a 1-minute warning. Turning them back on needs someone at each PC.`
    if (!window.confirm(what)) return
    setBusy(true)
    await Promise.all(pcs.map(e => api.pcAction(e.device_id, { action, confirmed: true }).catch(() => {})))
    setBusy(false)
    load()
  }
  async function messageAll() {
    const text = window.prompt(`Message to ALL ${pcs.length} lab PCs (shown big on top of every screen):`)
    if (!text || !text.trim()) return
    const t = window.prompt('Close by itself after how many minutes? Leave empty: stays until OK.', '')
    if (t === null) return
    const minutes = Math.min(240, Math.max(0, Math.round(Number(t) || 0)))
    setBusy(true)
    await Promise.all(pcs.map(e => api.pcMessage(e.device_id, text.trim(), minutes).catch(() => {})))
    setBusy(false)
    load()
  }

  return (
    <section className="mb-6">
      <SectionTitle icon={<Bot size={15} />}
        sub="Robots read-only over the lab LAN; PCs through the lab agent."
        action={(pcs.length > 0 || (admin && items.some(e => e.kind === 'PC'))) ? (
          <div className="flex flex-wrap gap-2 justify-end">
            <button className="btn-ghost btn-sm" onClick={() => setWall(true)}><LayoutGrid size={13} /> View all screens</button>
            {pcs.length > 0 && <>
            <button className="btn-ghost btn-sm" disabled={busy} onClick={messageAll}>
              <MessageSquare size={13} /> Message all</button>
            <button className="btn-ghost btn-sm" disabled={busy} onClick={clearAllMessages}>
              <MessageSquare size={13} /> Clear messages</button>
            <button className="btn-ghost btn-sm" disabled={busy} onClick={() => setAll('EXAM')}>
              <GraduationCap size={13} /> Exam all</button>
            <button className="btn-ghost btn-sm" disabled={busy} onClick={() => setAll('MAINTENANCE')}>
              <Wrench size={13} /> Maintenance all</button>
            <button className="btn-ghost btn-sm" disabled={busy} onClick={() => setAll('LOCKED')}>
              <Lock size={13} /> Lock all PCs</button>
            <button className="btn-ghost btn-sm" disabled={busy || !pcs.some(e => e.mode === 'LOCKED')} onClick={unlockAll}>
              <Unlock size={13} /> Unlock all</button>
            <button className="btn-ghost btn-sm" disabled={busy || !pcs.some(e => e.mode !== 'NORMAL')}
                    onClick={() => setAll('NORMAL')}><Unlock size={13} /> All normal</button>
            <button className="btn-ghost btn-sm" disabled={busy} onClick={() => powerAll('restart')}>
              <RotateCw size={13} /> Restart all</button>
            <button className="btn-ghost btn-sm text-bad-soft" disabled={busy} onClick={() => powerAll('shutdown')}>
              <Power size={13} /> Power off all</button></>}
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
            const st = e.kind === 'PC' ? pcStatus(e) : null
            const tone = st ? st.tone : e.online === false ? 'bad' : e.state === 'FAULT' ? 'bad'
              : e.state === 'RUNNING' ? 'ok' : 'idle'
            const usable = st ? st.agent : e.online !== false
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
                    {st ? st.word : e.online === false ? 'offline' : (e.state ?? 'no data').toLowerCase()}</Chip>
                </div>
                <div className="text-[12.5px] text-slate-300 space-y-0.5">
                  {e.user_name && <div>Booking: <b className="text-white">{e.user_name}</b></div>}
                  {e.kind === 'PC' && e.detail?.os_user ? <div>Signed in: <span className="mono">{String(e.detail.os_user)}</span></div> : null}
                  {e.kind === 'PC' && e.detail?.foreground_app ? <div>Using: <b className="text-white">{String(e.detail.foreground_app).replace(/\.exe$/i, '')}</b></div> : null}
                  {e.kind === 'PC' && (e.detail?.hostname || e.detail?.ips) ? <div className="text-slate-400">
                    <span className="mono">{String(e.detail?.hostname ?? '')}</span>
                    {Array.isArray(e.detail?.ips) && (e.detail.ips as string[]).length > 0 && <span className="mono"> · {(e.detail.ips as string[]).join(', ')}</span>}
                    {e.detail?.agent_version ? <span> · agent {String(e.detail.agent_version)}</span> : null}</div> : null}
                  {/* A minute or two between the university's clocks and the offline laptop is normal: only a real drift is worth a line, and only from a PC that reports now. */}
                  {e.kind === 'PC' && e.online !== false && typeof e.detail?.clock_offset_s === 'number' && Math.abs(e.detail.clock_offset_s as number) >= 300
                    ? <div className="text-warn-soft">Clock {(e.detail.clock_offset_s as number) > 0 ? 'behind' : 'ahead of'} the server by {Math.abs(e.detail.clock_offset_s as number).toFixed(0)} s</div> : null}
                  <div>Running today: {hours(e.running_today_s)}</div>
                  {e.since && e.online !== false && <div className="text-slate-500">In this state since {relative(e.since)}</div>}
                  {/* Lab PCs behind the relay are on the university's network: the laptop's LAN scan cannot see them, and a red
                      "not on the LAN" next to a PC whose agent reports right now was simply wrong (lab, 2026-11-04). */}
                  {e.lan && (e.lan.present || e.online === false) && <div className={e.lan.present ? 'text-slate-400' : 'text-bad-soft'}>
                    Network: {e.lan.present ? 'connected' : 'not on the LAN'} since {relative(e.lan.since)}
                    {e.lan.ip ? <span className="mono"> · {e.lan.ip}</span> : null} ({e.lan.via === 'ping' ? 'ping' : 'ARP'})</div>}
                  <div className="text-slate-500">Last agent report {e.last_seen_at ? relative(e.last_seen_at) : 'never'}</div>
                </div>
                {e.kind === 'PC' && !canCtl(e) && (
                  <div className="text-[12px] text-slate-400 pt-1">
                    {adminPc(e) ? "The administrator's PC (it runs the portal's services): controlled by an administrator only."
                      : 'The current master PC: controlled by an administrator.'}</div>)}
                {e.kind === 'PC' && canCtl(e) && (
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
                {e.kind === 'PC' && canCtl(e) && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {e.mode === 'LOCKED'
                      ? <button className="btn-ghost btn-sm" onClick={() => setMode(e.device_id, 'NORMAL')}>
                          <Unlock size={13} /> Give access</button>
                      : <button className="btn-ghost btn-sm" onClick={() => {
                          if (window.confirm(`Remove access on ${e.name}? It locks now and stays locked until you give access.`))
                            setMode(e.device_id, 'LOCKED')
                        }}><Lock size={13} /> Remove access</button>}
                    <button className="btn-ghost btn-sm" disabled={!usable} onClick={() => setViewing(e)}>
                      <MonitorPlay size={13} /> View screen</button>
                    <button className="btn-ghost btn-sm" disabled={!usable} onClick={() => setMessaging(e)}>
                      <MessageSquare size={13} /> Message</button>
                    {staff && <button className="btn-ghost btn-sm" onClick={() => setMaster(e)}>
                      <Crown size={13} /> {e.is_master_pc ? 'Not master PC' : 'Make master PC'}</button>}
                  </div>)}
                {e.kind === 'PC' && canCtl(e) && (
                  <PcActions deviceId={e.device_id} name={e.name} admin={admin} online={usable} />)}
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
      {staff && <div className="mt-4"><SharePanel hasMasterPc={items.some(e => e.kind === 'PC' && e.is_master_pc)}
        pcs={pcs.map(e => ({ id: e.device_id, name: e.name, online: pcStatus(e).agent }))} /></div>}
      {wall && <ScreenWall pcs={admin ? items.filter(e => e.kind === 'PC') : pcs} onClose={closeWall} />}
      {viewing && <PcScreenViewer deviceId={viewing.device_id} name={viewing.name} onClose={closeViewer}
        monitors={Array.isArray(viewing.detail?.monitors) ? viewing.detail!.monitors as { index: number; width: number; height: number; primary: boolean }[] : []} />}
      <PcMessageModal deviceId={messaging?.device_id ?? 0} name={messaging?.name ?? ''}
                      open={messaging !== null} onClose={() => setMessaging(null)} />
    </section>
  )
}
