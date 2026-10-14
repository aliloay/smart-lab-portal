import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Bot, Cpu, Eye, EyeOff, Lock, ShieldCheck, UserPlus } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'
import { ErrorBanner, Notice } from '../components/ui'
import { InstitutionLogo, SmartLabMark, Wordmark } from '../components/Brand'
import { GridField } from '../components/visual'

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [signupCfg, setSignupCfg] = useState<{ enabled: boolean; email_domains: string[]; requires_approval: boolean } | null>(null)
  const [fullName, setFullName] = useState('')
  const [studentId, setStudentId] = useState('')
  const [department, setDepartment] = useState('')
  const [done, setDone] = useState('')

  useEffect(() => { api.signupConfig().then(setSignupCfg).catch(() => setSignupCfg(null)) }, [])
  const signingUp = mode === 'signup'

  async function submit(e: FormEvent) {
    e.preventDefault()
    // Chrome's saved-password autofill shows the values but does not tell the
    // page until the user clicks somewhere - read them straight from the
    // fields so Enter works on an autofilled form too.
    const f = e.currentTarget as HTMLFormElement
    const emailNow = (f.querySelector('#email') as HTMLInputElement | null)?.value ?? email
    const pwNow = (f.querySelector('#password') as HTMLInputElement | null)?.value ?? password
    if (!emailNow || !pwNow) { setError('Enter your email and password.'); return }
    if (emailNow !== email) setEmail(emailNow)
    if (pwNow !== password) setPassword(pwNow)
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
      await login(emailNow.trim().toLowerCase(), pwNow)
      const next = params.get('next')
      // The IoT Command Center has its own port (8080 / 8443): land there, not on the overview.
      // First sign-in on this browser: the /welcome story (stays until Skip / Enter Dashboard).
      let first = false
      try { first = !localStorage.getItem(`smartlab.welcomed.${emailNow.trim().toLowerCase()}`) } catch { /* ignore */ }
      const home = ['8080', '8443'].includes(window.location.port) ? '/command' : first ? '/welcome' : '/'
      nav(next && next.startsWith('/') && !next.startsWith('//') ? next : home, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[1.15fr_1fr]">
      {/* ------------------------------------------------------ identity */}
      <aside className="relative hidden lg:flex flex-col justify-between overflow-hidden p-12 border-r border-ink-600/60 bg-ink-950">
        {/* The lab's own robots (photos), cross-faded, under a navy gradient. Decorative only. */}
        <img src="/equipment/our-ur5e.jpg" alt="" aria-hidden decoding="async"
             className="absolute inset-y-0 left-0 w-[62%] h-full object-cover opacity-55 [mask-image:linear-gradient(90deg,#000_55%,transparent)]" />
        <img src="/equipment/our-fanuc.jpg" alt="" aria-hidden decoding="async"
             className="absolute inset-y-0 right-0 w-[58%] h-full object-cover opacity-45 [mask-image:linear-gradient(270deg,#000_50%,transparent)]" />
        <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/75 to-ink-950/40" />
        <div aria-hidden className="absolute inset-0 bg-[radial-gradient(ellipse_at_20%_80%,rgba(34,211,238,.18),transparent_55%),radial-gradient(ellipse_at_85%_20%,rgba(251,191,36,.10),transparent_50%)]" />
        <svg aria-hidden className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
          <path d="M-5 78 C 25 60, 45 72, 70 48 S 100 30, 108 22" fill="none" stroke="#22d3ee" strokeOpacity=".55" strokeWidth=".25" strokeDasharray="1 2.2" className="login-trail" />
          <path d="M-5 92 C 30 80, 55 88, 80 66 S 100 55, 108 50" fill="none" stroke="#fbbf24" strokeOpacity=".4" strokeWidth=".2" strokeDasharray="1 2.6" className="login-trail login-trail-slow" />
          {[[18, 70], [44, 64], [70, 48], [86, 35]].map(([x, y]) => <circle key={x} cx={x} cy={y} r=".55" fill="#67e8f9" className="login-node" />)}
        </svg>
        <style>{`.login-trail{animation:lt 6s linear infinite}.login-trail-slow{animation-duration:9s}
          .login-node{animation:ln 3.2s ease-in-out infinite}@keyframes lt{to{stroke-dashoffset:-32}}
          @keyframes ln{50%{opacity:.25}}@media (prefers-reduced-motion:reduce){.login-trail,.login-node{animation:none}}`}</style>

        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4"><SmartLabMark size={60} animated /><Wordmark /></div>
          <span className="rounded-xl bg-white/90 px-3 py-1.5 shadow-lg shadow-black/30"><InstitutionLogo className="!h-10 xl:!h-11" /></span>
        </div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }}
                    className="relative max-w-xl">
          <div className="eyebrow">GERMAN INTERNATIONAL UNIVERSITY · CAIRO</div>
          <h1 className="mt-4 font-display text-[50px] xl:text-[58px] leading-[1.02] font-semibold tracking-tight text-white">
            One lab.<span className="block bg-gradient-to-r from-accent-200 via-cyan-300 to-amber-200 bg-clip-text text-transparent">
              Every system connected.</span></h1>
          <p className="mt-5 text-[16.5px] text-slate-300 leading-relaxed max-w-md">
            Where robotics, intelligent automation, and connected research work together.</p>
          <ul className="mt-9 flex flex-wrap gap-x-6 gap-y-3 text-[11.5px] font-semibold tracking-[.14em] text-slate-200">
            {[[<Bot size={15} />, 'ROBOTICS & DIGITAL TWINS'], [<Cpu size={15} />, 'INTELLIGENT AUTOMATION'],
              [<ShieldCheck size={15} />, 'SECURE LAB ACCESS']].map(([icon, t]) => (
              <li key={t as string} className="flex items-center gap-2"><span className="text-cyan-300">{icon}</span>{t}</li>))}
          </ul>
        </motion.div>
        <div />
      </aside>

      {/* ------------------------------------------------------- sign in */}
      <main className="relative flex items-center justify-center px-5 py-12">
        <GridField className="lg:hidden" />
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: .35 }} className="relative w-full max-w-[400px]">
          <div className="lg:hidden mb-6 flex flex-col items-start gap-4">
            <InstitutionLogo className="!h-9" />
            <div className="flex items-center gap-2.5"><SmartLabMark size={34} animated /><Wordmark /></div>
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
                      disabled={busy
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

        </motion.div>
      </main>
    </div>
  )
}
