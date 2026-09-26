import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight, Fingerprint, UserPlus, QrCode, ScanFace, ShieldCheck, Lock, Eye, EyeOff,
} from 'lucide-react'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'
import { ErrorBanner, Notice } from '../components/ui'
import { InstitutionLogo, SmartLabMark, Wordmark } from '../components/Brand'
import { AccessFlow, Bloom, GridField, NodeField, RoboticArm, SystemBadge } from '../components/visual'

const FLOW = [
  { icon: <QrCode size={18} />, title: 'QR code or RFID card',
    detail: 'Step 1 identifies you and your booking.' },
  { icon: <span className="flex -space-x-1"><Fingerprint size={16} /><ScanFace size={16} /></span>,
    title: 'Fingerprint or face',
    detail: 'Step 2 must match the identity from step 1.' },
  { icon: <ShieldCheck size={18} />, title: 'Authorized access',
    detail: 'Only then does the door controller unlock.' },
]

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [portalUp, setPortalUp] = useState<boolean | null>(null)
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [signupCfg, setSignupCfg] = useState<{ enabled: boolean; email_domains: string[]; requires_approval: boolean } | null>(null)
  const [fullName, setFullName] = useState('')
  const [studentId, setStudentId] = useState('')
  const [department, setDepartment] = useState('')
  const [done, setDone] = useState('')

  useEffect(() => { api.signupConfig().then(setSignupCfg).catch(() => setSignupCfg(null)) }, [])
  const signingUp = mode === 'signup'

  // A real check, not a decorative "SYSTEM ONLINE" label.
  useEffect(() => {
    fetch('/api/health').then(r => r.json())
      .then(b => setPortalUp(b.status === 'ok'))
      .catch(() => setPortalUp(false))
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (signingUp) {
        const r = await api.signup({
          email: email.trim().toLowerCase(), full_name: fullName.trim(), password,
          student_id: studentId.trim() || undefined, department: department.trim() || undefined,
        })
        if (r.pending_approval) {
          setDone(r.message || 'Account created. An administrator must approve it before you can sign in.')
          setMode('signin'); setPassword('')
          return
        }
      }
      await login(email.trim().toLowerCase(), password)
      const next = params.get('next')
      nav(next && next.startsWith('/') && !next.startsWith('//') ? next : '/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
    } finally {
      setBusy(false)
    }
  }

  const badge = portalUp === null ? { t: 'CHECKING PORTAL', tone: 'idle' as const }
    : portalUp ? { t: 'PORTAL ONLINE', tone: 'ok' as const }
    : { t: 'PORTAL UNREACHABLE', tone: 'warn' as const }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[1.15fr_1fr]">
      {/* ------------------------------------------------------ identity */}
      <aside className="relative hidden lg:flex flex-col justify-between overflow-hidden
                        p-12 border-r border-ink-600/60 bg-ink-900/60">
        <GridField className="!opacity-80" />
        <Bloom />
        <Bloom tone="teal" className="!left-auto !right-0 !top-auto !bottom-0" />
        <NodeField className="absolute inset-0 w-full h-full opacity-60" />
        <RoboticArm className="absolute -right-10 bottom-0 w-[500px] h-auto opacity-80" />

        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-3.5">
            <SmartLabMark size={46} animated />
            <Wordmark />
          </div>
          <InstitutionLogo className="!h-12 xl:!h-14" />
        </div>

        <div className="relative max-w-lg">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: .45 }}>
            <div className="eyebrow">German International University · Cairo</div>
            <h1 className="mt-4 font-display text-[46px] leading-[1.02] font-semibold
                           tracking-tight text-white">
              SMART LAB
              <span className="block mt-2 text-[26px] leading-tight font-medium
                               bg-gradient-to-r from-accent-200 via-signal-300 to-teal-300
                               bg-clip-text text-transparent">
                Intelligent Research Laboratory
              </span>
            </h1>
            <p className="mt-5 text-[16px] text-slate-300 leading-relaxed">
              Connected laboratories. Secure access. Smarter research.
            </p>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: .15, duration: .45 }}
                      className="mt-9 card !bg-ink-850/80 p-5 max-w-sm">
            <div className="label mb-4">How entry works</div>
            <AccessFlow steps={FLOW} />
          </motion.div>
        </div>

        <div className="relative flex flex-wrap gap-2">
          <SystemBadge label={badge.t} tone={badge.tone} />
          <SystemBadge label="TWO-FACTOR ACCESS" tone="idle" />
          <SystemBadge label="GIU · CAIRO" tone="idle" />
        </div>
      </aside>

      {/* ------------------------------------------------------- sign in */}
      <main className="relative flex items-center justify-center px-5 py-12">
        <GridField className="lg:hidden" />
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: .35 }} className="relative w-full max-w-[400px]">
          <div className="lg:hidden mb-8 space-y-6">
            <InstitutionLogo className="!h-11" />
            <div className="flex items-center gap-3">
              <SmartLabMark size={40} animated />
              <Wordmark />
            </div>
          </div>

          <div className="card p-7 sm:p-8">
            <div className="flex items-center gap-2.5">
              <span className="grid place-items-center w-9 h-9 rounded-xl bg-accent-500/15
                               border border-accent-500/30 text-accent-300">
                {signingUp ? <UserPlus size={16} /> : <Lock size={16} />}
              </span>
              <div>
                <h2 className="font-display text-xl font-semibold text-white">
                  {signingUp ? 'Create account' : 'Sign in'}</h2>
                <p className="text-[13px] text-slate-400">
                  {signingUp ? 'Student accounts. Staff are added by an administrator.'
                    : 'Use your university account.'}</p>
              </div>
            </div>

            {signupCfg?.enabled && (
              <div role="tablist" className="mt-5 grid grid-cols-2 gap-1 p-1 rounded-xl bg-ink-800/70 border border-ink-600/70">
                {(['signin', 'signup'] as const).map(m => (
                  <button key={m} type="button" role="tab" aria-selected={mode === m}
                    onClick={() => { setMode(m); setError(''); setDone('') }}
                    className={`py-1.5 rounded-lg text-[13px] font-medium transition-colors ${mode === m
                      ? 'bg-accent-500/20 text-white border border-accent-400/30' : 'text-slate-400 hover:text-white'}`}>
                    {m === 'signin' ? 'Sign in' : 'Sign up'}
                  </button>))}
              </div>)}

            <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
              {params.get('expired') && !error && (
                <Notice tone="warn">Your session ended. Sign in again to continue.</Notice>
              )}
              {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
              {done && <Notice tone="ok">{done}</Notice>}

              {signingUp && (
                <div>
                  <label htmlFor="full_name" className="label block mb-1.5">Full name</label>
                  <input id="full_name" className="input" value={fullName} autoComplete="name"
                         required minLength={2} onChange={e => setFullName(e.target.value)} />
                </div>)}

              <div>
                <label htmlFor="email" className="label block mb-1.5">Email</label>
                <input id="email" className="input" type="email" value={email}
                       autoFocus autoComplete="username" required
                       placeholder={signingUp && signupCfg?.email_domains.length
                         ? `you@${signupCfg.email_domains[0]}` : 'you@giu-uni.de'}
                       onChange={e => setEmail(e.target.value)} />
              </div>
              <div>
                <label htmlFor="password" className="label block mb-1.5">Password</label>
                <div className="relative">
                  <input id="password" className="input pr-11" type={show ? 'text' : 'password'}
                         value={password} required
                         autoComplete={signingUp ? 'new-password' : 'current-password'}
                         onChange={e => setPassword(e.target.value)} />
                  <button type="button" onClick={() => setShow(s => !s)}
                          aria-label={show ? 'Hide password' : 'Show password'}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5
                                     text-slate-400 hover:text-white">
                    {show ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {signingUp && (<>
                <p className="-mt-2 text-[11.5px] text-slate-500">At least 8 characters.</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="student_id" className="label block mb-1.5">Student ID</label>
                    <input id="student_id" className="input" value={studentId} maxLength={64}
                           onChange={e => setStudentId(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="department" className="label block mb-1.5">Department</label>
                    <input id="department" className="input" value={department} maxLength={128}
                           onChange={e => setDepartment(e.target.value)} />
                  </div>
                </div>
              </>)}

              <button type="submit" className="btn-primary w-full !py-3"
                      disabled={busy || !email || !password
                        || (signingUp && (fullName.trim().length < 2 || password.length < 8))}>
                {busy ? (signingUp ? 'Creating account…' : 'Signing in…')
                  : (signingUp ? 'Create account' : 'Sign in')}
                {!busy && <ArrowRight size={16} />}
              </button>
            </form>
          </div>

          <p className="mt-5 text-[12px] text-slate-400 leading-relaxed text-center px-2">
            {signupCfg?.enabled
              ? 'New students can sign up here; staff and admin accounts are created by an administrator.'
              : 'Accounts are created by an administrator.'} Signing in does not open a
            door — entry also needs your fingerprint or face, enrolled by lab staff.
          </p>

          <div className="lg:hidden mt-8 card p-5">
            <div className="label mb-4">How entry works</div>
            <AccessFlow steps={FLOW} />
          </div>
        </motion.div>
      </main>
    </div>
  )
}
