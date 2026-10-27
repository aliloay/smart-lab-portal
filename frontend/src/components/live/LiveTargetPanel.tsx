/**
 * The expanded live panel of the selected camera target (2026-10-27). Every number comes from the card's `live`
 * block (backend services/live_target.py) with its age and quality; nothing is estimated from the image.
 * Robot: six joint bars in the twin's own joint limits, velocity, TCP, controller modes, LIVE/STALE/OFFLINE.
 */
import { Link } from 'react-router-dom'
import { LiveBlock, ScanCard, ScanPerson } from '../../lib/api'
import { MODELS } from '../robot/kinematics'
import { Chip } from '../ui'

export const fmtAge = (s: number | null | undefined) => s == null ? 'never' : s < 90 ? `${Math.round(s)} s ago`
  : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`

const CONN_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle'> = { LIVE: 'ok', STALE: 'warn', OFFLINE: 'bad', NO_TELEMETRY: 'idle' }

export function RobotBars({ live, compact = false }: { live: Extract<LiveBlock, { type: 'robot' }>; compact?: boolean }) {
  const limits = (MODELS[(live.model ?? '').toUpperCase().includes('FANUC') ? 'FANUC' : 'UR5E'] ?? MODELS.UR5E).limitsDeg
  const dim = live.connection !== 'LIVE'
  if (!live.joints.length) return <div className="text-[12px] text-slate-400">No joint telemetry in the robot's record.</div>
  return (
    <div className={`space-y-1 ${dim ? 'opacity-60 grayscale' : ''}`}>
      {live.joints.map(j => {
        const [lo, hi] = limits[j.index - 1] ?? [-360, 360]
        const pct = Math.max(0, Math.min(100, ((j.deg - lo) / (hi - lo)) * 100))
        const zero = ((0 - lo) / (hi - lo)) * 100
        const moving = j.vel_deg_s != null && Math.abs(j.vel_deg_s) >= 0.3
        return (
          <div key={j.index} className={`grid ${compact ? 'grid-cols-[52px_1fr_48px]' : 'grid-cols-[70px_1fr_58px_62px]'} items-center gap-1.5 text-[11.5px]`}>
            <span className={moving ? 'text-ok-soft font-semibold' : 'text-slate-300'}>{compact ? `J${j.index}` : `J${j.index} ${j.name}`}</span>
            <div className="relative h-2 rounded-full bg-ink-700 overflow-hidden" title={`${lo}° … ${hi}°`}>
              <div className="absolute top-0 bottom-0 w-px bg-slate-500/70" style={{ left: `${zero}%` }} />
              <div className={`absolute top-0 bottom-0 ${moving ? 'bg-ok' : 'bg-accent-400'} transition-[left,right] duration-300 ease-out`}
                   style={pct >= zero ? { left: `${zero}%`, right: `${100 - pct}%` } : { left: `${pct}%`, right: `${100 - zero}%` }} />
            </div>
            <span className="tnum text-right text-slate-100">{j.deg.toFixed(1)}°</span>
            {!compact && <span className={`tnum text-right ${moving ? 'text-ok-soft' : 'text-slate-500'}`}>
              {j.vel_deg_s == null ? '—' : `${j.vel_deg_s >= 0 ? '+' : ''}${j.vel_deg_s.toFixed(1)}°/s`}</span>}
          </div>)
      })}
    </div>)
}

export function LiveSummary({ live }: { live: LiveBlock }) {
  switch (live.type) {
    case 'robot':
      return <span className="inline-flex items-center gap-1"><Chip tone={CONN_TONE[live.connection]}>{live.connection.replace('_', ' ').toLowerCase()}</Chip>
        {live.simulation && <Chip tone="warn">simulation</Chip>}</span>
    case 'consumables': {
      const b = live.bins[0]
      return b ? <span>{b.qty_est == null ? 'no count' : `~${b.qty_est} left`}{live.bins.length > 1 ? ` +${live.bins.length - 1} bins` : ''}</span> : null
    }
    case 'reusable_bin':
      return <span>{live.items.filter(i => i.status === 'AVAILABLE').length} available · {live.items.filter(i => i.status === 'CHECKED_OUT').length} out</span>
    case 'environment':
      return <span>{live.readings.slice(0, 2).map(r => `${r.metric.slice(0, 4)} ${Number.isInteger(r.value) ? r.value : r.value.toFixed(1)}${r.unit}`).join(' · ') || 'no readings'}</span>
    case 'door':
      return <span>door {live.door?.toLowerCase() ?? 'not reported'}</span>
    case 'pc':
      return <span>{live.online ? 'online' : 'offline'}{live.agent_state ? ` · ${live.agent_state.toLowerCase()}` : ''}</span>
    default:
      return <span>{live.online ? 'online' : 'offline'}</span>
  }
}

export default function LiveTargetPanel({ card, person }: { card?: ScanCard | null; person?: ScanPerson | null }) {
  if (person && !card) return (
    <div className="card p-3.5 space-y-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[15px] font-semibold text-white">{person.auth_subject} · {person.name}</span>
        <span className="ml-auto"><Chip tone="ok">face match{person.score != null ? ` ${Math.round(person.score * 100)}%` : ''}</Chip></span>
      </div>
      <div className="text-[13px] text-slate-300">{person.role.replace(/_/g, ' ').toLowerCase()}
        {person.department ? ` · ${person.department}` : ''}{person.student_id ? ` · ID ${person.student_id}` : ''}</div>
      <div className="text-[12px] text-slate-400">{person.inside_by_door ? 'Checked in at the lab door (open session).' : 'No open door session right now.'}
        {person.verified_at ? ` · face verified ${new Date(person.verified_at).toLocaleTimeString()}` : ''}</div>
    </div>)
  if (!card) return null
  const live = card.live
  return (
    <div className="card p-3.5 space-y-2.5">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[15px] font-semibold text-white">{card.name}</span>
        <span className="text-[12px] text-slate-400">{card.type}{card.lab_code ? ` · ${card.lab_code}` : ''}</span>
        <span className="ml-auto flex items-center gap-1.5">{live && <LiveSummary live={live} />}</span>
      </div>
      {live?.type === 'robot' && <>
        <div className="text-[12px] text-slate-400">Telemetry {fmtAge(live.telemetry_age_s)}
          {live.rate_hz ? ` · ${live.rate_hz} Hz` : ''} · state {live.state ?? 'not reported'}
          {live.control ? ` · control ${live.control}` : ''}{live.home ? ` · home ${live.home}` : ''}</div>
        <div className="text-[12px] text-slate-400">Robot mode {live.robot_mode ?? 'not reported'} · safety {live.safety_mode ?? 'not reported'}
          <span className="text-slate-500"> (UR RTDE codes)</span></div>
        <RobotBars live={live} />
        {live.tcp && <div className="text-[12px] text-slate-300 tnum">TCP x {live.tcp.x_mm} · y {live.tcp.y_mm} · z {live.tcp.z_mm} mm
          <span className="text-slate-500"> ({live.tcp.rotation} {live.tcp.rx}, {live.tcp.ry}, {live.tcp.rz})</span></div>}
        {live.connection !== 'LIVE' && <div className="text-[12px] text-warn-soft">
          {live.connection === 'NO_TELEMETRY' ? 'This robot has never sent telemetry - no live values.'
            : `Not live: the values are from ${fmtAge(live.telemetry_age_s)} and may not match the arm you see.`}</div>}
      </>}
      {live?.type === 'consumables' && <ul className="space-y-1.5">
        {live.bins.map(b => <li key={b.code} className="rounded-lg border border-ink-600 px-2.5 py-1.5 text-[13px]">
          <div className="flex items-center gap-2"><span className="text-white">{b.item}</span>
            <span className="mono text-[11px] text-slate-500">{b.code}</span>
            {b.low && <Chip tone="bad">low</Chip>}
            <span className="ml-auto"><Chip tone={b.quality === 'VALID' ? 'ok' : 'warn'}>{b.quality.toLowerCase().replace('_', ' ')}</Chip></span></div>
          <div className="text-slate-300 tnum">{b.qty_est == null ? 'No count - not calibrated' : `≈ ${b.qty_est}${b.qty_err ? ` ± ${b.qty_err}` : ''} pieces`}
            {b.mass_g != null ? ` · ${b.mass_g.toFixed(1)} g` : ''}{b.reorder_qty != null ? ` · reorder at ${b.reorder_qty}` : ''}</div>
          <div className="text-[11px] text-slate-500">{b.count_is} · measured {fmtAge(b.age_s)}</div>
        </li>)}
        {!live.bins.length && <li className="text-[12.5px] text-slate-400">No bin is linked to this node.</li>}
      </ul>}
      {live?.type === 'reusable_bin' && <div className="space-y-1">
        <ul className="grid sm:grid-cols-2 gap-1 text-[12.5px]">
          {live.items.map(i => <li key={i.tag} className="flex items-center gap-2">
            <span className="text-slate-200">{i.name}</span>
            <Chip tone={i.status === 'AVAILABLE' ? 'ok' : i.status === 'CHECKED_OUT' ? 'warn' : 'idle'}>{i.status.toLowerCase().replace('_', ' ')}</Chip>
            {i.holder && <span className="text-slate-400">{i.holder}</span>}</li>)}
        </ul>
        <div className="text-[11px] text-slate-500">{live.source}</div>
      </div>}
      {live?.type === 'environment' && <div className="space-y-1.5">
        <ul className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {live.readings.map(r => <li key={r.metric} className="rounded-lg border border-ink-600 px-2.5 py-1.5">
            <div className="text-[11px] text-slate-400">{r.metric}</div>
            <div className="text-[15px] text-white tnum">{Number.isInteger(r.value) ? r.value : r.value.toFixed(1)} {r.unit}</div>
            <div className={`text-[10.5px] ${r.quality === 'LIVE' ? 'text-slate-500' : 'text-warn-soft'}`}>{fmtAge(r.age_s)}{r.quality === 'STALE' ? ' - stale' : ''}</div></li>)}
        </ul>
        {!live.readings.length && <div className="text-[12.5px] text-warn-soft">No readings in the last 24 h.</div>}
        {live.open_alerts.map((a, i) => <div key={i} className="text-[12.5px] text-bad-soft">{a.severity}: {a.title}</div>)}
      </div>}
      {live?.type === 'door' && <div className="text-[13px] text-slate-300">Door {live.door ?? 'not reported'} · controller
        {live.online ? ' online' : ' NOT reporting'} · last report {fmtAge(live.age_s)}</div>}
      {live?.type === 'pc' && <div className="text-[13px] text-slate-300">{live.online ? 'Online' : 'Offline'} · agent {live.agent_state ?? 'not reported'}
        · mode {live.mode}{live.os_user ? ` · signed in: ${live.os_user}` : ''} · last report {fmtAge(live.age_s)}</div>}
      {!live && card.facts.length > 0 && <ul className="text-[13px] space-y-0.5">{card.facts.map(f => <li key={f.label}>
        <span className="text-slate-400">{f.label}</span> <span className="text-slate-100">{f.value}</span></li>)}</ul>}
      <div className="flex flex-wrap gap-2 text-[12px] text-slate-500 items-center">
        <span>Last report {fmtAge(card.seconds_since_seen)} · marker <span className="mono">{card.code}</span></span>
        <Link to={card.link} className="ml-auto btn-ghost btn-sm">Open in the portal</Link>
      </div>
    </div>)
}
