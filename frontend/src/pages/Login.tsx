import { FormEvent, useEffect, useRef, useState } from 'react'
import './login.css'
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

  // Restrained parallax for the background layer (desktop, pointer only, never with reduced motion).
  const stage = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = stage.current
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches || !window.matchMedia('(pointer: fine)').matches) return
    let raf = 0
    const on = (e: PointerEvent) => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        el.style.setProperty('--lx', ((e.clientX / window.innerWidth) - 0.5).toFixed(3))
        el.style.setProperty('--ly', ((e.clientY / window.innerHeight) - 0.5).toFixed(3))
      })
    }
    window.addEventListener('pointermove', on, { passive: true })
    return () => { window.removeEventListener('pointermove', on); cancelAnimationFrame(raf) }
  }, [])
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
      // After every sign-in: the /welcome story; it stays until Skip / Enter Dashboard, which go to
      // "/" = this role's own dashboard. A deep link (?next=) still wins; the Command Center port too.
      // Owner 2026-10-18: the welcome shows after EVERY sign-in, also when the sign-in came from an
      // expired session or a link - its Enter button then continues to that page.
      const ok = next && next.startsWith('/') && !next.startsWith('//')
      nav(['8080', '8443'].includes(window.location.port) ? (ok ? next! : '/command')
          : ok ? `/welcome?next=${encodeURIComponent(next!)}` : '/welcome', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div ref={stage} className="login-stage relative min-h-screen overflow-x-hidden bg-ink-950 lg:grid lg:grid-cols-[1.15fr_1fr]">
      {/* One environment behind both halves: grid, glows, and light paths that leave the robot
          picture, cross the seam and fade out above / below the sign-in card. Decorative, CSS/SVG only. */}
      <div aria-hidden className="login-env pointer-events-none absolute inset-0 hidden lg:block">
        <div className="login-env-grid" />
        <div className="login-env-glow" />
        <svg className="login-env-paths" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            {/* both trails fade out well before the sign-in card */}
            <linearGradient id="lp-c" x1="0" x2="1"><stop offset="0" stopColor="#22d3ee" stopOpacity=".05" /><stop offset=".45" stopColor="#22d3ee" stopOpacity=".7" /><stop offset=".75" stopColor="#22d3ee" stopOpacity=".3" /><stop offset="1" stopColor="#22d3ee" stopOpacity="0" /></linearGradient>
            <linearGradient id="lp-a" x1="0" x2="1"><stop offset="0" stopColor="#fbbf24" stopOpacity="0" /><stop offset=".45" stopColor="#fbbf24" stopOpacity=".5" /><stop offset="1" stopColor="#fbbf24" stopOpacity="0" /></linearGradient>
          </defs>
          {/* amber trail stays on the left */}
          <path d="M-2 84 C 20 80, 38 88, 52 90" stroke="url(#lp-a)" strokeWidth=".16" fill="none" className="login-path login-path-slow" />
        </svg>
      </div>
      {/* ------------------------------------------------------ identity */}
      <aside className="relative z-[1] hidden lg:flex flex-col justify-between overflow-hidden p-12">
        {/* The seam between the two halves: two light rays (cyan, amber) running along it. CSS only. */}
        <div aria-hidden className="absolute top-0 right-0 h-full w-px bg-gradient-to-b from-transparent via-cyan-400/30 to-transparent z-10">
          <span className="seam-ray" /><span className="seam-ray seam-ray-amber" />
        </div>
        {/* The lab's own UR5e (left) and FANUC (right): /assets/labs/login-robots.jpg, a crop of our two
            photos so the robots, not the frame, fill the picture. Decorative only. */}
        <img src="/assets/labs/login-robots.jpg" alt="" aria-hidden decoding="async"
             className="absolute top-0 inset-x-0 w-full h-[64%] object-cover object-center opacity-85" />
        {/* Both robots stay visible across the top; the picture fades into navy under the headline. */}
        <div aria-hidden className="absolute top-0 inset-x-0 h-[64%] bg-gradient-to-b from-ink-950/65 via-ink-950/10 to-ink-950" />
        <div aria-hidden className="absolute inset-0 bg-[radial-gradient(ellipse_at_20%_80%,rgba(34,211,238,.18),transparent_55%),radial-gradient(ellipse_at_85%_20%,rgba(251,191,36,.10),transparent_50%)]" />
        <style>{`.login-trail{animation:lt 6s linear infinite}.login-trail-slow{animation-duration:9s}
          .login-node{animation:ln 3.2s ease-in-out infinite}@keyframes lt{to{stroke-dashoffset:-32}}
          @keyframes ln{50%{opacity:.25}}.seam-ray{position:absolute;left:-1px;width:3px;height:22%;border-radius:2px;background:linear-gradient(transparent,#22d3ee,transparent);box-shadow:0 0 12px 2px rgba(34,211,238,.55);animation:sr 5s linear infinite}.seam-ray-amber{background:linear-gradient(transparent,#67e8f9,transparent);box-shadow:0 0 12px 2px rgba(103,232,249,.5);animation-duration:7s;animation-direction:reverse;animation-delay:-2s}@keyframes sr{from{top:-25%}to{top:105%}}@media (prefers-reduced-motion:reduce){.login-trail,.login-node,.seam-ray{animation:none}.seam-ray{display:none}}`}</style>

        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4"><SmartLabMark size={60} animated /><Wordmark /></div>
          <InstitutionLogo className="!h-9 xl:!h-10 ml-auto -mr-9 drop-shadow-[0_2px_8px_rgba(0,0,0,.6)]" />
        </div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }}
                    className="relative max-w-xl">
          <h1 className="font-display text-[50px] xl:text-[58px] leading-[1.02] font-semibold tracking-tight text-white">
            Multiple labs.<span className="block bg-gradient-to-r from-accent-200 via-cyan-300 to-amber-200 bg-clip-text text-transparent">
              One connected system.</span></h1>
          <p className="mt-5 text-[16.5px] text-slate-300 leading-relaxed max-w-md">
            Where robotics, intelligent automation, and connected research work together.</p>
          <ul className="mt-9 flex flex-wrap xl:flex-nowrap items-center gap-x-5 gap-y-2.5 text-[11px] font-semibold tracking-[.1em] text-slate-100">
            {[[<Bot size={15} />, 'ROBOTICS & DIGITAL TWINS'], [<Cpu size={15} />, 'INTELLIGENT AUTOMATION'],
              [<ShieldCheck size={15} />, 'SECURE LAB ACCESS']].map(([icon, t]) => (
              <li key={t as string} className="flex items-center gap-1.5 whitespace-nowrap"><span className="text-cyan-300 shrink-0">{icon}</span>{t}</li>))}
          </ul>
        </motion.div>
        <div />
      </aside>

      {/* ------------------------------------------------------- sign in */}
      <main className="relative z-[3] flex items-center justify-center px-5 py-12">
        <GridField className="lg:hidden" />
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: .35 }} className="relative w-full max-w-[400px]">
          <div className="lg:hidden mb-6 flex flex-col items-start gap-4">
            <InstitutionLogo className="!h-9" />
            <div className="flex items-center gap-2.5"><SmartLabMark size={34} animated /><Wordmark /></div>
          </div>

          <div aria-hidden className="login-card-glow" />
          <div className="card login-glass relative p-7 sm:p-8">
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
