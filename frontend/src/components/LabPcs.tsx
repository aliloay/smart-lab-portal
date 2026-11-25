import { useEffect, useState } from 'react'
import { Monitor } from 'lucide-react'
import { SecurityCamera, api } from '../lib/api'
import { isStaff, useAuth } from '../lib/auth'
import { useLiveMessages } from '../lib/live'
import { pcStatus } from '../lib/pcStatus'
import { visibleInterval } from '../lib/visibleInterval'

/** The lab's PCs: on / off from the LAN check (tools/lan_presence, nothing installed on the PC) and
 *  the PC agent's heartbeat; whether someone works at it comes from the security camera's PC boxes. */
// Last answer kept for the page's lifetime (2026-10-27, owner: "the PCs disappear and then appear"): coming back
// to the tab shows the list at once, and a first visit draws it in one go once BOTH sources answered (no tiles
// popping in and re-sorting).
const PC_CACHE: { cams: SecurityCamera[] | null; pcs: Awaited<ReturnType<typeof api.equipment>> | null } = { cams: null, pcs: null }

export default function LabPcs() {
  const [cams, setCams0] = useState<SecurityCamera[] | null>(PC_CACHE.cams)
  const [pcs, setPcs0] = useState<Awaited<ReturnType<typeof api.equipment>> | null>(PC_CACHE.pcs)
  const setCams = (v: SecurityCamera[]) => { PC_CACHE.cams = v; setCams0(v) }
  const setPcs = (v: Awaited<ReturnType<typeof api.equipment>>) => { PC_CACHE.pcs = v; setPcs0(v) }
  const staff = isStaff(useAuth().user)
  useEffect(() => {
    const load = () => {
      api.securityCameras().then(setCams).catch(() => setCams(PC_CACHE.cams ?? []))
      if (staff) api.equipment().then(r => setPcs(r.filter(e => e.kind === 'PC'))).catch(() => setPcs(PC_CACHE.pcs ?? []))
      else setPcs([])
    }
    load(); const t = visibleInterval(load, 5000); return () => window.clearInterval(t)
  }, [staff])
  useLiveMessages(m => { if (m.type === 'pc_state' && staff) api.equipment().then(r => setPcs(r.filter(e => e.kind === 'PC'))).catch(() => {}) })
  const all = (cams ?? []).flatMap(c => c.zones ?? [])
  // The lab's real PCs (owner 2026-10-21: boxes named by the lab numbers, PC-03 removed from the lab):
  // every PC box on any camera plus every PC in the inventory. A PC seen by both cameras is "In use"
  // when either camera sees someone at it.
  const isPc = (n: string) => /^PC-\d+$/i.test(n)
  const names = Array.from(new Set([...all.map(z => String(z.name).toUpperCase()).filter(isPc),
                                    ...(pcs ?? []).map(e => String(e.asset_tag ?? e.name).toUpperCase()).filter(isPc)]))
    .sort((a, b) => Number(a.slice(3)) - Number(b.slice(3)))
  const rank = (s: string) => (s === 'IN_USE' ? 3 : s === 'CHANGED' || s === 'MOTION' ? 2 : s === 'OK' ? 1 : 0)
  const zones = all.filter(z => isPc(String(z.name))).map(z => ({ ...z, name: String(z.name).toUpperCase() }))
    .sort((a, b) => rank(b.status) - rank(a.status))
  const word: Record<string, [string, string]> = {
    IN_USE: ['In use', 'border-sky-400/50 bg-sky-500/15 text-sky-200'],
    OK: ['Free', 'border-ok/40 bg-ok/10 text-ok-soft'],
    MOTION: ['Moved?', 'border-warn/50 bg-warn/15 text-warn-soft'],
    CHANGED: ['Looks different', 'border-bad/50 bg-bad/15 text-bad-soft'],
    LEARNING: ['Learning', 'border-ink-500 text-slate-400'],
  }
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Monitor size={16} className="text-accent-300" />
        <span className="font-semibold text-white">Lab PCs</span>
        <span className="text-[12px] text-slate-400">on / off over the lab LAN · details from the PC agent · use seen by the security camera</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2">
        {(cams === null || pcs === null) && Array.from({ length: 12 }, (_, i) =>
          <div key={i} className="h-[66px] rounded-lg border border-ink-600/50 bg-ink-900/40 animate-pulse" />)}
        {cams !== null && pcs !== null && names.map(n => {
          const z = zones.find(x => x.name === n)
          const d = (pcs ?? []).find(e => (e.asset_tag ?? e.name) === n)
          const st = d ? pcStatus(d) : null
          const stCls = !st ? 'text-slate-500' : st.tone === 'ok' ? 'text-ok-soft' : st.tone === 'warn' ? 'text-warn-soft'
            : st.tone === 'bad' ? 'text-bad-soft' : 'text-slate-300'
          // Camera and LAN together (owner 2026-10-21): a PC that is off on the LAN is not "in use" - someone
          // is only sitting there; on and nobody seated = free; off and nobody = off.
          // 2026-11-18 lab: GIU-subnet PCs report through the relay and never answer the Smart_Lab LAN ping - a PC
          // whose agent reports right now is ON, whatever the ping says (it showed RUNNING + Off).
          const off = !!d?.lan && !d.lan.present && !d.online
          const [w, cls] = z?.status === 'IN_USE' && off ? ['Seated · PC off', 'border-warn/50 bg-warn/15 text-warn-soft']
            : off && (!z || z.status === 'OK') ? ['Off', 'border-ink-600 text-slate-400']
            : z ? (word[z.status] ?? [z.status, 'border-ink-500 text-slate-300']) : ['No camera box', 'border-ink-600 text-slate-500']
          return (
            <div key={n} className="rounded-lg border border-ink-600/70 bg-ink-900/40 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-white font-medium">{n}</span>
                <span className={`text-[10.5px] uppercase ${stCls}`} title={d?.lan?.ip ? `LAN ${d.lan.ip} (${d.lan.via})` : undefined}>
                  {st ? st.word : 'not checked'}</span>
              </div>
              <span className={`mt-1.5 inline-block rounded-md border px-1.5 py-0.5 text-[11px] ${cls}`}>{w}</span>
            </div>)
        })}
      </div>
    </div>)
}
