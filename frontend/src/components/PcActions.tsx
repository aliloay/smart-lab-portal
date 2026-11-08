/**
 * Allowlisted actions on one lab PC: open / close an approved app, lock, and (admins) log off,
 * restart, shut down. The status shown is the PC agent's own report - QUEUED, EXECUTING,
 * COMPLETED, FAILED, or EXPIRED (= unreachable / timed out) - never assumed.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { AppWindow, Lock, LogOut, Power, RotateCw, XSquare } from 'lucide-react'
import { PcAction, api } from '../lib/api'
import { Chip } from './ui'
import { relative } from '../lib/time'
import { visibleInterval } from '../lib/visibleInterval'

const TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle'> = { COMPLETED: 'ok', EXECUTING: 'warn', QUEUED: 'idle', FAILED: 'bad', EXPIRED: 'bad' }
const LABEL: Record<string, string> = { open_app: 'Open', close_app: 'Close', lock: 'Lock', logoff: 'Log off', restart: 'Restart', shutdown: 'Shut down' }

export default function PcActions({ deviceId, name, admin, online }: { deviceId: number; name: string; admin: boolean; online: boolean }) {
  const [apps, setApps] = useState<string[]>([])
  const [app, setApp] = useState('')
  const [rows, setRows] = useState<PcAction[]>([])
  const [error, setError] = useState('')
  const busy = useRef(false)
  const [pending, setPending] = useState(false)
  const load = useCallback(() => api.pcActions(deviceId).then(r => { setApps(r.apps); setRows(r.actions) }).catch(() => {}), [deviceId])
  const active = rows[0] && ['QUEUED', 'EXECUTING'].includes(rows[0].status)
  useEffect(() => { load(); const t = visibleInterval(load, active ? 1500 : 30000); return () => window.clearInterval(t) }, [load, active])

  const run = async (action: string, opts: { app?: string; confirm?: string } = {}) => {
    if (busy.current) return                                   // no double submissions
    if (opts.confirm && !window.confirm(opts.confirm)) return
    busy.current = true; setPending(true); setError('')
    try { await api.pcAction(deviceId, { action, app: opts.app, confirmed: !!opts.confirm }) }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed') }
    finally { busy.current = false; setPending(false); load() }
  }
  const off = pending || !!active || !online
  const last = rows[0]
  // Restart / shut down: the PC confirmed and shows a 60 s countdown; the card counts down in step.
  const doneAt = last && ['restart', 'shutdown'].includes(last.action) && last.status === 'COMPLETED' && last.completed_at
    ? new Date(last.completed_at).getTime() : 0
  const [, tickNow] = useState(0)
  const left = doneAt ? Math.max(0, Math.round(60 - (Date.now() - doneAt) / 1000)) : 0
  useEffect(() => {
    if (!left) return
    const t = window.setInterval(() => tickNow(n => n + 1), 500)
    return () => window.clearInterval(t)
  }, [left > 0])                                              // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="pt-2 border-t border-ink-700/60 space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <select className="input !py-1 !text-[12px] w-auto" value={app} onChange={e => setApp(e.target.value)} aria-label="Approved application">
          <option value="">App…</option>{apps.map(a => <option key={a} value={a}>{a.replace('_', ' ')}</option>)}</select>
        <button className="btn-ghost btn-sm" disabled={off || !app} onClick={() => run('open_app', { app })}><AppWindow size={13} /> Open</button>
        <button className="btn-ghost btn-sm" disabled={off || !app}
                onClick={() => run('close_app', { app, confirm: `Close ${app} on ${name}? It may ask the user to save; unsaved work can be lost.` })}><XSquare size={13} /> Close</button>
        <button className="btn-ghost btn-sm" disabled={off} onClick={() => run('lock')}><Lock size={13} /> Lock now</button>
      </div>
      {admin && <div className="flex flex-wrap gap-1.5">
        <button className="btn-ghost btn-sm" disabled={off} onClick={() => run('logoff', { confirm: `Sign the user out of ${name}? Open programs close; unsaved work is lost.` })}><LogOut size={13} /> Log off</button>
        <button className="btn-ghost btn-sm" disabled={off} onClick={() => run('restart', { confirm: `Restart ${name}? The user gets a 1-minute warning to save.` })}><RotateCw size={13} /> Restart</button>
        <button className="btn-ghost btn-sm text-bad-soft" disabled={off} onClick={() => run('shutdown', { confirm: `Shut down ${name}? The user gets a 1-minute warning. Turning it back on needs someone at the PC (Wake-on-LAN is not set up).` })}><Power size={13} /> Shut down</button>
      </div>}
      {last && <div className="text-[11.5px] text-slate-400 flex flex-wrap items-center gap-1.5">
        Last: {LABEL[last.action] ?? last.action}{last.app ? ` ${last.app}` : ''} <Chip tone={TONE[last.status] ?? 'idle'}>{last.status.toLowerCase()}</Chip>
        <span className="text-slate-500">{last.message} · {relative(last.created_at)}</span></div>}
      {left > 0 && <div className="text-[12.5px] text-warn-soft font-medium">
        {last.action === 'restart' ? 'Restarting' : 'Shutting down'} in {left} s - the user sees the same countdown</div>}
      {error && <p className="text-[11.5px] text-bad-soft">{error}</p>}
    </div>
  )
}
