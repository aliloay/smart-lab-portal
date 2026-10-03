/**
 * Emergency tab (administrators): the one place the portal can open a door.
 *
 * It opens only with the emergency password, for a few minutes (the token is
 * kept in memory only - a reload closes it). Per lab: hold the door OPEN (for
 * N minutes or until back to normal), LOCKDOWN (no entry), a message on the
 * door LCD and tablet, the evacuation alarm. All lab PCs: lock, unlock,
 * message. Every action is audited and announced to all staff; the door
 * controller applies the state itself and the card shows when it has.
 */
import { FormEvent, useCallback, useEffect, useState } from 'react'
import {
  BellRing, CircleCheck, DoorOpen, KeyRound, Lock, LockKeyhole, MessageSquare, Monitor,
  RotateCcw, ShieldAlert, Siren, Unlock, WifiOff,
} from 'lucide-react'
import { ApiError, EmergencyAction, EmergencyLab, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { relative } from '../lib/time'
import { Chip, ErrorBanner, Field, Notice, PageHeader, SectionTitle, Skeleton } from '../components/ui'

type Status = Awaited<ReturnType<typeof api.emergencyStatus>>
type Session = { token: string; expiresAt: number }

const OPEN_FOR: [string, string][] = [
  ['10', '10 minutes'], ['30', '30 minutes'], ['60', '1 hour'], ['', 'Until back to normal'],
]

function mmss(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function Emergency() {
  const [st, setSt] = useState<Status | null>(null)
  const [error, setError] = useState('')
  const [session, setSession] = useState<Session | null>(null)
  const [now, setNow] = useState(Date.now())

  const load = useCallback(() => {
    api.emergencyStatus().then(s => { setSt(s); setError('') }).catch(e => setError(e.message))
  }, [])
  useEffect(() => {
    load()
    const t = window.setInterval(load, 3000)
    return () => window.clearInterval(t)
  }, [load])
  useLiveMessages(m => { if (m.type === 'staff') load() })
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  useEffect(() => {
    if (session && now >= session.expiresAt) setSession(null)
  }, [now, session])

  /** Runs an emergency action; a lapsed session closes the controls. */
  const run = useCallback(async (fn: (token: string) => Promise<unknown>) => {
    if (!session) return false
    try {
      await fn(session.token)
      load()
      return true
    } catch (e) {
      if (e instanceof ApiError && e.code === 'EMERGENCY_LOCKED') setSession(null)
      setError(e instanceof Error ? e.message : String(e))
      return false
    }
  }, [session, load])

  return (
    <div className="max-w-6xl">
      <PageHeader eyebrow="Administration" title="Emergency"
        sub="Open or lock a lab door, warn people at the door and on the PCs, sound the alarm. Every action is logged and sent to all staff."
        actions={session && (
          <div className="flex items-center gap-2">
            <Chip tone="bad" dot>Controls open · {mmss(session.expiresAt - now)}</Chip>
            <button className="btn-ghost btn-sm" onClick={() => setSession(null)}>
              <LockKeyhole size={13} /> Close now</button>
          </div>)} />
      {error && <div className="mb-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}
      {!st ? <Skeleton className="h-80" /> : (
        <div className="space-y-6">
          {!st.password_set && (
            <Notice tone="warn" icon={<KeyRound size={15} />}>
              No emergency password is set. Add <span className="mono">EMERGENCY_PASSWORD=…</span> to
              the <span className="mono">.env</span> file next to docker-compose.yml and restart the backend.
            </Notice>)}
          {st.password_set && !session && <Unlock_ onOpen={setSession} />}

          <section>
            <SectionTitle icon={<Siren size={15} />}
              sub="The door controller reads its lab's state every second and applies it itself.">
              Laboratories</SectionTitle>
            <div className="grid lg:grid-cols-2 gap-4">
              {st.labs.map(l => <LabCard key={l.lab_id} l={l} open={!!session} run={run} />)}
            </div>
          </section>

          <PcsCard pcs={st.pcs} open={!!session} run={run} />
          {session && <PasswordCard run={run} />}
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------- password ---
function Unlock_({ onOpen }: { onOpen: (s: Session) => void }) {
  const [pw, setPw] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const r = await api.emergencySession(pw)
      onOpen({ token: r.token, expiresAt: new Date(r.expires_at).getTime() })
      setPw('')
    } catch (x) {
      setErr(x instanceof Error ? x.message : String(x))
    } finally { setBusy(false) }
  }
  return (
    <form onSubmit={submit} className="card p-5 border-bad/40 flex flex-wrap items-end gap-4">
      <div className="flex items-center gap-3 mr-auto">
        <span className="grid place-items-center w-10 h-10 rounded-xl bg-bad/15 text-bad-soft">
          <ShieldAlert size={18} /></span>
        <div>
          <div className="text-white font-semibold">Controls are locked</div>
          <div className="text-[12.5px] text-slate-400">Enter the emergency password. The controls stay open for a few minutes.</div>
        </div>
      </div>
      <div className="w-full sm:w-72">
        <Field label="Emergency password" error={err} htmlFor="em-pw">
          <input id="em-pw" type="password" className="input w-full" autoComplete="off"
                 value={pw} onChange={e => setPw(e.target.value)} />
        </Field>
      </div>
      <button className="btn-primary" disabled={busy || !pw}>Open controls</button>
    </form>
  )
}

// ------------------------------------------------------------------- labs ---
function LabCard({ l, open, run }: {
  l: EmergencyLab; open: boolean; run: (fn: (t: string) => Promise<unknown>) => Promise<boolean>
}) {
  const [minutes, setMinutes] = useState('10')
  const [msg, setMsg] = useState('')
  const [msgMinutes, setMsgMinutes] = useState('30')
  const [busy, setBusy] = useState(false)

  async function act(a: EmergencyAction, confirm?: string) {
    if (confirm && !window.confirm(confirm)) return
    setBusy(true)
    await run(t => api.emergencyAct(t, l.lab_id, a))
    setBusy(false)
  }
  async function normal() {
    if (!window.confirm(`${l.code}: back to normal? The door locks, the message and the alarm stop.`)) return
    setBusy(true)
    await run(t => api.emergencyNormal(t, l.lab_id))
    setBusy(false)
  }
  async function sendMessage() {
    setBusy(true)
    const ok = await run(t => api.emergencyAct(t, l.lab_id,
      { message: msg.trim(), message_minutes: msgMinutes ? Number(msgMinutes) : null }))
    if (ok) setMsg('')
    setBusy(false)
  }

  const frame = l.active ? 'border-bad/60 bg-bad/[0.06]' : ''
  const dis = !open || busy
  return (
    <div className={`card p-4 space-y-3 ${frame}`}>
      <div className="flex items-start gap-2">
        <div className="min-w-0">
          <div className="text-white font-semibold">{l.code} <span className="text-slate-400 font-normal">· {l.name}</span></div>
          <div className="text-[12px] text-slate-400 mt-0.5 flex flex-wrap gap-x-3">
            {!l.has_door ? <span>No door controller</span>
              : l.controller_online === false
                ? <span className="text-warn-soft inline-flex items-center gap-1"><WifiOff size={12} /> Controller offline</span>
                : <span>Door {l.door_closed === null ? 'no data' : l.door_closed ? 'closed' : 'open'}
                    {' · '}{l.lock_released ? 'unlocked' : 'locked'}</span>}
            {l.updated_by && l.version > 0 && <span>Last set by {l.updated_by} {relative(l.updated_at)}</span>}
          </div>
        </div>
        <div className="ml-auto flex flex-col items-end gap-1 shrink-0">
          {l.active ? <Chip tone="bad" dot>Emergency</Chip> : <Chip tone="ok" dot>Normal</Chip>}
          {l.has_door && l.version > 0 && (l.applied
            ? <span className="text-[11px] text-ok-soft inline-flex items-center gap-1"><CircleCheck size={11} /> Applied by the door</span>
            : <span className="text-[11px] text-warn-soft">Waiting for the door…</span>)}
        </div>
      </div>

      {l.active && (
        <div className="rounded-lg bg-bad/10 border border-bad/30 px-3 py-2 text-[13px] text-slate-100 space-y-0.5">
          {l.door_mode === 'UNLOCKED' && <div><DoorOpen size={13} className="inline -mt-0.5" /> Door held OPEN
            {l.door_remaining_s != null ? ` · ${Math.ceil(l.door_remaining_s / 60)} min left` : ' until back to normal'}</div>}
          {l.door_mode === 'LOCKDOWN' && <div><Lock size={13} className="inline -mt-0.5" /> LOCKDOWN: no QR code or card opens the door</div>}
          {l.message && <div><MessageSquare size={13} className="inline -mt-0.5" /> “{l.message}”</div>}
          {l.alarm && <div className="text-bad-soft font-semibold"><BellRing size={13} className="inline -mt-0.5" /> Evacuation alarm sounding</div>}
        </div>)}

      {l.has_door && <>
        <div className="flex flex-wrap items-center gap-2">
          <select className="input !py-1.5 !text-[12.5px] w-auto" value={minutes} disabled={dis}
                  onChange={e => setMinutes(e.target.value)} aria-label="Keep the door open for">
            {OPEN_FOR.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
          <button className="btn-ghost btn-sm" disabled={dis}
            onClick={() => act({ door: 'UNLOCKED', minutes: minutes ? Number(minutes) : null },
              `${l.code}: unlock the door and keep it open ${minutes ? `for ${minutes} min` : 'until back to normal'}?`)}>
            <Unlock size={13} /> Hold door open</button>
          <button className="btn-ghost btn-sm" disabled={dis || l.door_mode === 'LOCKDOWN'}
            onClick={() => act({ door: 'LOCKDOWN' }, `${l.code}: LOCKDOWN? No QR code or card will open the door.`)}>
            <Lock size={13} /> Lockdown</button>
          <button className={`btn-sm ${l.alarm ? 'btn-ghost' : 'btn-ghost text-bad-soft'}`} disabled={dis}
            onClick={() => act({ alarm: !l.alarm }, l.alarm ? undefined : `${l.code}: sound the evacuation alarm?`)}>
            <BellRing size={13} /> {l.alarm ? 'Alarm off' : 'Alarm'}</button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input className="input !py-1.5 !text-[12.5px] flex-1 min-w-[180px]" maxLength={96} disabled={dis}
                 placeholder="Message on the door screen and tablet" value={msg} onChange={e => setMsg(e.target.value)} />
          <select className="input !py-1.5 !text-[12.5px] w-auto" value={msgMinutes} disabled={dis}
                  onChange={e => setMsgMinutes(e.target.value)} aria-label="Show the message for">
            <option value="10">10 min</option><option value="30">30 min</option>
            <option value="120">2 hours</option><option value="">Until cleared</option>
          </select>
          <button className="btn-ghost btn-sm" disabled={dis || !msg.trim()} onClick={sendMessage}>
            <MessageSquare size={13} /> Show</button>
          {l.message && <button className="btn-ghost btn-sm" disabled={dis} onClick={() => act({ message: '' })}>
            Clear message</button>}
        </div>
      </>}

      {l.active && (
        <button className="btn-primary btn-sm" disabled={dis} onClick={normal}>
          <RotateCcw size={13} /> Back to normal</button>)}
    </div>
  )
}

// -------------------------------------------------------------------- PCs ---
function PcsCard({ pcs, open, run }: {
  pcs: Status['pcs']; open: boolean; run: (fn: (t: string) => Promise<unknown>) => Promise<boolean>
}) {
  const [text, setText] = useState('')
  const [master, setMaster] = useState(false)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)

  async function act(action: 'LOCK' | 'UNLOCK' | 'MESSAGE', confirm?: string) {
    if (confirm && !window.confirm(confirm)) return
    setBusy(true)
    setDone(null)
    let n = 0
    const ok = await run(async t => { n = (await api.emergencyPcs(t, { action, text: text.trim(), include_master: master })).done })
    if (ok) {
      setDone(`${action === 'LOCK' ? 'Locked' : action === 'UNLOCK' ? 'Unlocked' : 'Message sent to'} ${n} PC${n === 1 ? '' : 's'}.`)
      if (action === 'MESSAGE') setText('')
    }
    setBusy(false)
  }
  const who = master ? 'ALL PCs, the master PC included' : 'all lab PCs (not the master PC)'
  const dis = !open || busy || pcs.total === 0
  return (
    <section>
      <SectionTitle icon={<Monitor size={15} />}
        sub={`${pcs.total} PC${pcs.total === 1 ? '' : 's'} · ${pcs.locked} locked · ${pcs.master ? '1 master PC' : 'no master PC marked'}`}>
        Lab PCs</SectionTitle>
      <div className="card p-4 space-y-3">
        {pcs.total === 0 && <div className="text-[13px] text-slate-400">No PC agent has reported yet (tools/pc_agent).</div>}
        <label className="flex items-center gap-2 text-[13px] text-slate-300">
          <input type="checkbox" checked={master} disabled={!open} onChange={e => setMaster(e.target.checked)} />
          Include the lab engineer's master PC
        </label>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost btn-sm" disabled={dis}
            onClick={() => act('LOCK', `Lock ${who}? They stay locked until unlocked.`)}>
            <Lock size={13} /> Lock all</button>
          <button className="btn-ghost btn-sm" disabled={dis || pcs.locked === 0}
            onClick={() => act('UNLOCK', `Give access back on ${who}?`)}>
            <Unlock size={13} /> Unlock all</button>
        </div>
        <div className="flex flex-wrap gap-2">
          <input className="input !py-1.5 !text-[12.5px] flex-1 min-w-[200px]" maxLength={200} disabled={!open}
                 placeholder="Message popping up on every PC" value={text} onChange={e => setText(e.target.value)} />
          <button className="btn-ghost btn-sm" disabled={dis || !text.trim()} onClick={() => act('MESSAGE')}>
            <MessageSquare size={13} /> Send to all</button>
        </div>
        {done && <div className="text-[12.5px] text-ok-soft">{done}</div>}
      </div>
    </section>
  )
}

// --------------------------------------------------------- change password ---
function PasswordCard({ run }: { run: (fn: (t: string) => Promise<unknown>) => Promise<boolean> }) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const mismatch = b.length > 0 && a !== b
  async function save(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setDone(false)
    if (await run(t => api.emergencyPassword(t, a))) { setA(''); setB(''); setDone(true) }
    setBusy(false)
  }
  return (
    <section>
      <SectionTitle icon={<KeyRound size={15} />}
        sub="Stored hashed in the database; the .env password stops working once changed here.">
        Emergency password</SectionTitle>
      <form onSubmit={save} className="card p-4 flex flex-wrap items-end gap-3">
        <div className="w-full sm:w-60"><Field label="New password" hint="At least 6 characters" htmlFor="em-new">
          <input id="em-new" type="password" className="input w-full" autoComplete="new-password"
                 value={a} onChange={e => setA(e.target.value)} /></Field></div>
        <div className="w-full sm:w-60"><Field label="Repeat" error={mismatch ? 'Does not match' : null} htmlFor="em-rep">
          <input id="em-rep" type="password" className="input w-full" autoComplete="new-password"
                 value={b} onChange={e => setB(e.target.value)} /></Field></div>
        <button className="btn-primary" disabled={busy || a.length < 6 || a !== b}>Change</button>
        {done && <span className="text-[12.5px] text-ok-soft">Changed. Staff were notified.</span>}
      </form>
    </section>
  )
}
