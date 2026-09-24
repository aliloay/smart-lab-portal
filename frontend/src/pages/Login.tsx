import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Fingerprint, QrCode, ScanFace, ShieldCheck } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { ErrorBanner } from '../components/ui'
import { Bloom, GridField, NodeField, RoboticArm, SystemBadge } from '../components/visual'

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email.trim().toLowerCase(), password)
      nav('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[1.1fr_1fr]">
      {/* ---------------------------------------------------------------- */}
      {/* Identity panel. Hidden on phones, where it would push the actual  */}
      {/* form below the fold for no benefit.                              */}
      {/* ---------------------------------------------------------------- */}
      <aside className="relative hidden lg:flex flex-col justify-between
                        overflow-hidden bg-ink-900 p-12">
        <GridField />
        <Bloom />
        <NodeField className="absolute inset-0 w-full h-full opacity-70" />
        <RoboticArm className="absolute -right-16 bottom-0 w-[520px] h-auto
                               opacity-[.55] animate-floaty" />

        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-accent-600 grid place-items-center
                            text-white font-bold shadow-glow-accent">SL</div>
            <div>
              <div className="text-white font-semibold leading-tight">Smart Lab</div>
              <div className="label">Access Portal</div>
            </div>
          </div>
        </div>

        <div className="relative max-w-md">
          <motion.h1
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: .5 }}
            className="text-[34px] leading-[1.15] font-semibold text-white tracking-tight"
          >
            Intelligent<br />Research Laboratory
          </motion.h1>

          <motion.p
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            transition={{ delay: .15, duration: .5 }}
            className="mt-4 text-[15px] text-slate-400 leading-relaxed"
          >
            Reserve a laboratory, receive a time-bound access credential, and
            enter with two-factor verification at the door.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: .28, duration: .5 }}
            className="mt-8 flex flex-wrap items-center gap-2.5 text-slate-400"
          >
            <Step icon={<QrCode size={14} />} text="QR or RFID" />
            <ArrowRight size={13} className="text-slate-700" />
            <Step icon={<Fingerprint size={14} />} text="Fingerprint" />
            <span className="text-slate-700 text-xs">or</span>
            <Step icon={<ScanFace size={14} />} text="Face" />
            <ArrowRight size={13} className="text-slate-700" />
            <Step icon={<ShieldCheck size={14} />} text="Door unlocks" />
          </motion.div>
        </div>

        <div className="relative flex flex-wrap gap-2">
          <SystemBadge label="SYSTEM ONLINE" />
          <SystemBadge label="GIU · CAIRO" />
        </div>
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* Sign-in panel                                                    */}
      {/* ---------------------------------------------------------------- */}
      <main className="relative flex items-center justify-center px-5 py-12
                       bg-ink-950">
        <GridField className="lg:hidden opacity-60" />

        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: .4 }}
          className="relative w-full max-w-sm"
        >
          {/* Compact identity for phones, where the left panel is hidden. */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-lg bg-accent-600 grid place-items-center
                            text-white font-bold text-sm">SL</div>
            <div>
              <div className="text-white font-semibold text-sm leading-tight">
                Smart Lab
              </div>
              <div className="label">Access Portal</div>
            </div>
          </div>

          <h2 className="text-xl font-semibold text-white">Sign in</h2>
          <p className="text-sm text-slate-500 mt-1">
            Use your university account.
          </p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

            <div>
              <label htmlFor="email" className="label block mb-1.5">Email</label>
              <input id="email" className="input" type="email" value={email}
                     autoFocus autoComplete="username" required
                     placeholder="you@giu-uni.de"
                     onChange={e => setEmail(e.target.value)} />
            </div>

            <div>
              <label htmlFor="password" className="label block mb-1.5">Password</label>
              <input id="password" className="input" type="password"
                     value={password} autoComplete="current-password" required
                     onChange={e => setPassword(e.target.value)} />
            </div>

            <button className="btn-primary w-full !py-3" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
              {!busy && <ArrowRight size={15} />}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-ink-700">
            <p className="text-[11px] text-slate-600 leading-relaxed">
              Accounts are created by an administrator. Signing in here does
              not open a door — physical entry additionally requires an
              enrolled fingerprint or face at the laboratory itself.
            </p>
          </div>
        </motion.div>
      </main>
    </div>
  )
}

function Step({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg
                     bg-ink-800/70 border border-ink-600 text-xs">
      <span className="text-accent-400">{icon}</span>{text}
    </span>
  )
}
