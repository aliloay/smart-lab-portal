/**
 * "Finish your lab access setup" - information only.
 *
 * A new person can book and pass step 1 at the door (QR or RFID card), but
 * step 2 (fingerprint or face) can only succeed once staff have registered
 * their biometrics. These components tell them so; the door never reads it.
 */
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { CheckCircle2, CircleDashed, Fingerprint, KeyRound, ScanFace, TriangleAlert, X } from 'lucide-react'
import { AccessSetup, api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDate } from '../lib/time'

const ICON = { identity: KeyRound, fingerprint: Fingerprint, face: ScanFace }

export function useAccessSetup(): AccessSetup | null {
  const { user } = useAuth()
  const [st, setSt] = useState<AccessSetup | null>(null)
  useEffect(() => {
    if (!user) { setSt(null); return }
    api.myAccessSetup().then(setSt).catch(() => setSt(null))
  }, [user?.id, user?.fingerprint_enrolled_at, user?.face_enrolled_at])
  return st
}

export function AccessSetupChecklist({ setup }: { setup: AccessSetup }) {
  return (
    <ul className="space-y-2.5">
      {setup.items.map(i => {
        const Icon = ICON[i.key]
        return (
          <li key={i.key} className={`flex gap-3 rounded-xl border p-3 ${i.done
            ? 'border-ok/30 bg-ok/[0.05]' : 'border-warn/35 bg-warn/[0.06]'}`}>
            <span className={`grid place-items-center w-9 h-9 rounded-lg shrink-0 ${i.done
              ? 'bg-ok/15 text-ok-soft' : 'bg-warn/15 text-warn-soft'}`}><Icon size={17} /></span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-[13.5px] text-white">
                {i.label}
                {i.value && <span className="mono text-accent-200 text-[12.5px]">{i.value}</span>}
              </div>
              <div className="text-[12px] text-slate-400 mt-0.5">
                {i.done ? (i.at ? `Confirmed ${fmtDate(i.at)}` : 'Done') : i.how}
              </div>
            </div>
            {i.done
              ? <CheckCircle2 size={18} className="text-ok-soft shrink-0 mt-1" />
              : <span className="text-[11px] font-semibold text-warn-soft shrink-0 mt-1.5">PENDING</span>}
          </li>)
      })}
    </ul>
  )
}

/** Shown at the top of every page after sign-in until the setup is complete. */
export function AccessSetupBanner() {
  const { user } = useAuth()
  const loc = useLocation()
  const setup = useAccessSetup()
  const key = `smartlab.setupBanner.${user?.id}`
  const [hidden, setHidden] = useState(() => {
    try { return sessionStorage.getItem(key) === '1' } catch { return false }
  })
  if (!setup || !setup.needed || hidden || loc.pathname === '/profile') return null
  const hide = () => { setHidden(true); try { sessionStorage.setItem(key, '1') } catch { /* ignore */ } }
  return (
    <div role="status" className="mb-5 flex items-start gap-3 rounded-xl border border-warn/40
                                  bg-warn/[0.08] px-4 py-3">
      <TriangleAlert size={18} className="text-warn-soft shrink-0 mt-0.5" />
      <div className="min-w-0 flex-1 text-[13px] text-amber-100/90">
        <div className="font-medium text-white">
          Action needed: confirm your {setup.pending.filter(p => p !== 'Door identity').join(' and ')}
        </div>
        <div className="mt-0.5">{setup.summary}</div>
        <Link to="/profile" className="inline-flex items-center gap-1 mt-1.5 text-[12.5px] link">
          <CircleDashed size={13} /> See the steps on your profile</Link>
      </div>
      <button onClick={hide} aria-label="Hide until next sign-in"
              className="p-1 text-slate-400 hover:text-white"><X size={16} /></button>
    </div>
  )
}
