/**
 * After sign-in: the Smart Lab welcome story (six sections, scroll-driven).
 *
 * Informational only: one GET /labs (real names and count). No telemetry, no
 * statuses, nothing is commanded. Photos marked "our lab" are photographs of
 * our own equipment; the others are category photos (Wikimedia, credited in
 * the equipment gallery). The 3D robots are the manufacturers' meshes moving
 * through a demo motion - labelled as such.
 *
 * Leaves only on Skip / Enter Dashboard ("/" = this role's own dashboard).
 * No timers. Reaching the true bottom is recorded once (sessionStorage).
 * Older version: backups/Welcome.before-claude-design.tsx.
 */
import { lazy, Suspense, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { ArrowDown, ArrowRight, Bot, Camera, Car, CircuitBoard, Cpu, DoorClosed, Factory, Fingerprint, Gauge, Hammer, Microchip, Network, PenTool, QrCode, ScrollText, Server, Shirt, Workflow, Zap, type LucideIcon } from 'lucide-react'
import { api, Lab } from '../lib/api'
import { firstName, useAuth } from '../lib/auth'
import { warmRoute } from '../lib/warm'
import { InstitutionLogo, SmartLabMark } from '../components/Brand'
import './welcome.css'
import { WRITE } from '../components/welcome/writeState'

const WelcomePair = lazy(() => import('../components/welcome/WelcomePair'))
const L1 = 'Your laboratory.', L2 = 'One connected system.', TOTAL = L1.length + L2.length
/** Writing timeline (0..1): the robot comes in, writes line 1, travels to line 2, writes it. */
function typingAt(w: number) {
  const seg = (a: number, b: number) => Math.max(0, Math.min(1, (w - a) / (b - a)))
  const n1 = Math.round(seg(0.1, 0.45) * L1.length), n2 = Math.round(seg(0.55, 0.95) * L2.length)
  const line = w <= 0 || w >= 0.97 ? 0 : w < 0.5 ? 1 : 2       // where the caret (and the pen) is
  return { n1: w >= 0.97 ? L1.length : n1, n2: w >= 0.97 ? L2.length : n2, line }
}
/** The finale heading: types itself while the robot writes it (its own state - the page does not
 *  re-render on every letter). Replays each time it scrolls into view. */
function EndHeading() {
  const [write, setWrite] = useState(0)
  useEffect(() => {
    const el = document.getElementById('wl-end')
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setWrite(1); WRITE.v = 1; return }
    let raf = 0, t0 = 0
    const step = (now: number) => {
      if (!t0) t0 = now
      const p = Math.min(1, (now - t0) / 6500)
      WRITE.v = p
      setWrite(Math.round(p * TOTAL * 2) / (TOTAL * 2))
      if (p < 1) raf = requestAnimationFrame(step)
    }
    const io = new IntersectionObserver(([e]) => {
      cancelAnimationFrame(raf)
      if (e.isIntersecting) { t0 = 0; raf = requestAnimationFrame(step) } else { setWrite(0); WRITE.v = 0 }
    }, { threshold: 0.45 })
    io.observe(el)
    return () => { io.disconnect(); cancelAnimationFrame(raf) }
  }, [])
  const typing = typingAt(write)
  return (
    <h2 className="font-display font-bold text-white leading-[1.04] text-[clamp(40px,6vw,72px)] mt-4 min-h-[2.1em]" aria-label="Your laboratory. One connected system.">
      <span>{L1.slice(0, typing.n1)}{typing.line === 1 && <span className="wl-caret" aria-hidden="true" />}</span><br />
      <span className="wl-grad">{L2.slice(0, typing.n2)}</span>{typing.line === 2 && <span className="wl-caret" aria-hidden="true" />}</h2>)
}

const WelcomeFleet = lazy(() => import('../components/welcome/WelcomeFleet'))

/** A 3D scene only while it is near the screen, and never while leaving: both scenes used to start
 *  as soon as their code arrived, ran off-screen the whole time, and compiled their shaders right when
 *  "Enter Dashboard" was pressed - a 6 s frozen browser on the way to the dashboard (profiled 2026-10-18). */
function Near({ children, leaving, className }: { children: ReactNode; leaving: boolean; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [near, setNear] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    // 2026-10-27 (owner: "the welcome page freezes a bit"; measured: 14 frames > 50 ms, worst 267 ms): the scene was
    // unmounted when it left the screen and rebuilt (WebGL + shader compile) every time it came back. It now stays once
    // built - both scenes stop drawing by themselves while off screen (demand frameloop / own visibility check).
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setNear(true); io.disconnect() } }, { rootMargin: '600px 0px' })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return <div ref={ref} className={className ?? 'absolute inset-0'}>{near && !leaving ? children : null}</div>
}

/** Workcell illustration per lab: an equipment icon for its category (illustrative, not a photo). */
const LAB_ICON: Record<string, LucideIcon> = {
  LAB_01: Bot, LAB_02: Server, LAB_03: Factory, LAB_04: Gauge, LAB_05: Car, LAB_06: CircuitBoard,
  LAB_07: Microchip, LAB_08: Zap, LAB_09: Hammer, LAB_10: PenTool, LAB_11: Shirt,
}
/** Photographs of our own equipment, shown in the selected lab's panel. */
const LAB_PHOTO: Record<string, { src: string; alt: string }> = {
  LAB_01: { src: '/equipment/our-ur5e.jpg', alt: 'Our UR5e under its gantry in the Robotics Lab' },
}

/** Toggles .wl-in while the element is on screen, so reveals reverse on the way up. */
function useInView<T extends HTMLElement>(threshold = 0.2) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => el.classList.toggle('wl-in', e.isIntersecting), { threshold })
    io.observe(el)
    return () => io.disconnect()
  }, [threshold])
  return ref
}

function Section({ id, className = '', children }: { id: string; className?: string; children: ReactNode }) {
  const ref = useInView<HTMLElement>(0.15)
  return <section id={id} ref={ref} className={`wl-sec ${className}`}>{children}</section>
}

const R = ({ d = 0, className = '', children }: { d?: number; className?: string; children: ReactNode }) =>
  <div className={`wl-r ${className}`} style={{ '--d': `${d}ms` } as CSSProperties}>{children}</div>

const Eyebrow = ({ n, children }: { n: string; children: ReactNode }) =>
  <div className="font-mono text-[11.5px] tracking-[.18em] uppercase text-cyan-300">{n} · {children}</div>

const Tag = ({ children, tone = 'cyan' }: { children: ReactNode; tone?: 'cyan' | 'amber' | 'slate' }) =>
  <span className={`wl-tag wl-tag-${tone}`}>{children}</span>

// ------------------------------------------------------------------ 02 network
/** Organic ring of workcells around the hub (percent of the stage). */
const SPOTS: [number, number][] = [[50, 11], [73, 16], [88, 33], [90, 57], [77, 78], [56, 84], [33, 82], [14, 66], [9, 43], [17, 22], [32, 12]]

function LabNetwork({ labs }: { labs: Lab[] }) {
  const [sel, setSel] = useState<string | null>(null)
  const ref = useInView<HTMLDivElement>(0.25)
  const [live, setLive] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => setLive(e.isIntersecting))
    io.observe(el)
    return () => io.disconnect()
  }, [ref])
  const nodes = labs.slice(0, SPOTS.length).map((l, i) => ({ lab: l, x: SPOTS[i][0], y: SPOTS[i][1] }))
  const cur = nodes.find(n => n.lab.code === sel)
  // curved path hub -> node, in a 1000x620 viewBox
  const path = (x: number, y: number) => {
    const X = x * 10, Y = y * 6.2, cx = 500, cy = 310
    const mx = (X + cx) / 2 + (Y - cy) * 0.25, my = (Y + cy) / 2 - (X - cx) * 0.18
    return `M${cx} ${cy} Q${mx} ${my} ${X} ${Y}`
  }
  return (
    <div ref={ref} className="wl-net">
      <div className="wl-net-floor" aria-hidden="true" />
      <svg viewBox="0 0 1000 620" className="wl-net-svg" aria-hidden="true" preserveAspectRatio="none">
        <defs>
          <linearGradient id="wl-path" x1="0" x2="1"><stop offset="0" stopColor="#24d4f2" /><stop offset="1" stopColor="#21b9b5" /></linearGradient>
        </defs>
        {nodes.map((n, i) => {
          const on = sel === n.lab.code
          const amber = n.lab.has_controller
          return (
            <g key={n.lab.code}>
              <path d={path(n.x, n.y)} pathLength={1} className={`wl-draw ${on ? 'wl-path-on' : ''}`}
                    stroke={amber ? '#ffb547' : 'url(#wl-path)'} strokeWidth={on ? 2.6 : 1.4} fill="none"
                    style={{ '--d': `${200 + i * 90}ms` } as CSSProperties} />
              {live && <circle r={on ? 3.4 : 2.4} fill={amber ? '#ffb547' : '#9ef3ff'} className="wl-particle">
                <animateMotion dur={`${5 + (i % 4)}s`} repeatCount="indefinite" path={path(n.x, n.y)} begin={`${i * 0.4}s`} />
              </circle>}
            </g>)
        })}
      </svg>
      <div className="wl-hub" style={{ left: '50%', top: '50%' }}>
        <div className="wl-hub-core"><SmartLabMark size={44} /></div>
        <div className="mt-2 font-mono text-[11px] tracking-[.2em] text-white">SMART LAB</div>
        <div className="font-mono text-[9.5px] tracking-[.16em] text-cyan-300/80">CENTRAL PORTAL</div>
      </div>
      {nodes.map((n, i) => {
        const Icon = LAB_ICON[n.lab.code] ?? Cpu
        return (
          <button key={n.lab.code} type="button" className={`wl-cell ${sel === n.lab.code ? 'is-sel' : ''}`}
                  style={{ left: `${n.x}%`, top: `${n.y}%`, '--d': `${400 + i * 90}ms` } as CSSProperties}
                  onClick={() => setSel(s => (s === n.lab.code ? null : n.lab.code))} aria-pressed={sel === n.lab.code}>
            <span className="wl-wc" style={{ '--f': `${(i % 5) * 0.7}s` } as CSSProperties}>
              <span className="wl-wc-holo"><Icon size={34} strokeWidth={1.6} /></span>
              <span className="wl-wc-beam" />
              <span className="wl-wc-plat"><span className="wl-wc-top" /></span>
            </span>
            <span className="wl-cell-label"><b>{n.lab.code}</b>{n.lab.name}</span>
          </button>)
      })}
      <div className={`wl-net-info ${cur ? 'is-on' : ''}`} aria-live="polite">
        {cur ? <>
          <div className="font-mono text-[11px] text-cyan-300">{cur.lab.code}{cur.lab.location ? ` · ${cur.lab.location}` : ''}</div>
          {LAB_PHOTO[cur.lab.code] && <figure className="wl-net-photo"><img src={LAB_PHOTO[cur.lab.code].src} alt={LAB_PHOTO[cur.lab.code].alt} decoding="async" />
            <figcaption><Tag tone="amber">Our lab</Tag></figcaption></figure>}
          <div className="text-white font-semibold text-[15px] mt-0.5">{cur.lab.name}</div>
          {cur.lab.category && <div className="text-[11.5px] text-slate-400">{cur.lab.category}</div>}
          {cur.lab.description && <p className="text-[12.5px] text-slate-300 mt-1 line-clamp-3">{cur.lab.description}</p>}
          <div className="text-[11.5px] mt-1.5 text-slate-400">
            {cur.lab.has_controller ? <span className="text-amber-300">Door access hardware installed</span> : 'No door hardware yet'}
            {cur.lab.capacity ? ` · capacity ${cur.lab.capacity}` : ''}</div>
        </> : <span className="text-[12.5px] text-slate-400">Select a workcell to see its record. Workcells are illustrations of each lab's category.</span>}
      </div>
    </div>)
}

// ------------------------------------------------------------------ page
export default function Welcome() {
  const nav = useNavigate()
  const { user } = useAuth()
  const [labs, setLabs] = useState<Lab[] | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const [leaving, setLeaving] = useState(false)
  const [typed, setTyped] = useState('')
  // (typing derived below)
  const TITLE = 'SMART LAB'
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setTyped(TITLE); return }
    let k = 0, t = 0
    const step = () => { k += 1; setTyped(TITLE.slice(0, k)); if (k < TITLE.length) t = window.setTimeout(step, k === 5 ? 260 : 120) }
    t = window.setTimeout(step, 900)
    return () => window.clearTimeout(t)
  }, [])

  useEffect(() => {
    const warm = () => { import('../components/welcome/WelcomePair'); import('../components/welcome/WelcomeFleet') }
    const ric = (window as unknown as { requestIdleCallback?: (f: () => void) => number }).requestIdleCallback
    const t = ric ? ric(warm) : window.setTimeout(warm, 1500)
    return () => { if (!ric) window.clearTimeout(t) }
  }, [])
  useEffect(() => { api.labs().then(ls => setLabs([...ls].sort((a, b) => a.code.localeCompare(b.code)))).catch(() => setLabs([])) }, [])

  // Hero parallax: one CSS variable, written at most once per frame.
  useEffect(() => {
    const el = root.current
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let raf = 0
    const on = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const hero = document.getElementById('wl-hero'), bg = hero?.querySelector<HTMLElement>('.wl-hero-bg')
        const d = el.scrollTop - (hero?.offsetTop ?? 0)
        if (bg && d > -el.clientHeight && d < el.clientHeight) bg.style.setProperty('--wl-scroll', String(Math.round(d)))
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - 4) {
          try { if (!sessionStorage.getItem('welcome.bottom')) sessionStorage.setItem('welcome.bottom', String(Date.now())) } catch { /* private mode */ }
        }
      })
    }
    el.addEventListener('scroll', on, { passive: true })
    return () => { el.removeEventListener('scroll', on); cancelAnimationFrame(raf) }
  }, [])

  const target = () => {
    const next = new URLSearchParams(window.location.search).get('next')
    return next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/welcome') ? next : '/'
  }
  // pointer on Skip / Enter: the dashboard's data starts loading before the click (owner 2026-10-20:
  // "after skipping it should dive into the portal immediately")
  const prime = () => warmRoute(user?.role, target())
  const enter = () => {
    if (leaving) return
    setLeaving(true)
    prime()
    // straight in: no wait for a fade-out (was 380 ms); the portal page fades itself in
    nav(target(), { replace: true })
  }
  const go = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  const count = labs?.length ?? 0
  const doors = useMemo(() => (labs ?? []).filter(l => l.has_controller).length, [labs])

  return createPortal(
    <div ref={root} className={`wl-root ${leaving ? 'is-leaving' : ''}`}>
      {/* persistent header */}
      <header className="wl-head">
        <div className="flex items-center gap-3 min-w-0">
          <SmartLabMark size={40} />
          <div className="min-w-0">
            <div className="font-display font-bold tracking-[.2em] text-white text-[15px] leading-none">SMART <span className="text-cyan-300">LAB</span></div>
            <div className="hidden sm:block mt-1 text-[10px] font-semibold tracking-[.16em] text-slate-300">INTELLIGENT RESEARCH LABORATORY</div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button type="button" onClick={enter} onPointerEnter={prime} onFocus={prime} className="wl-btn">Skip <ArrowRight size={15} /></button>
          <InstitutionLogo className="hidden md:block !h-12" />
        </div>
      </header>

      {/* 00 INTRO - typed title */}
      <Section id="wl-intro" className="wl-intro">
        <div className="wl-intro-in">
          <div className="wl-intro-logo"><SmartLabMark size={112} animated /></div>
          <h1 className="wl-typed" aria-label="Smart Lab">
            <span>{typed.slice(0, 5)}</span><span className="text-cyan-300">{typed.slice(5)}</span><span className="wl-caret" aria-hidden="true" />
          </h1>
          <div className={`wl-intro-after ${typed.length === TITLE.length ? 'is-on' : ''}`}>
            <div className="font-mono text-[12.5px] tracking-[.34em] text-slate-300">INTELLIGENT RESEARCH LABORATORY</div>
            <div className="mt-10 flex flex-wrap gap-3 justify-center">
              <button type="button" className="wl-btn-primary" onClick={() => go('wl-hero')}>Dive in <ArrowDown size={17} /></button>
              <button type="button" className="wl-btn" onClick={enter} onPointerEnter={prime} onFocus={prime}>Skip to dashboard <ArrowRight size={15} /></button>
            </div>
          </div>
        </div>
        <button type="button" onClick={() => go('wl-hero')} className={`wl-cue wl-intro-after ${typed.length === TITLE.length ? 'is-on' : ''}`}><span>Scroll for more</span><ArrowDown size={16} /></button>
      </Section>

      {/* 01 HERO */}
      <Section id="wl-hero" className="wl-hero">
        <div className="wl-hero-bg" aria-hidden="true">
          <img src="/assets/labs/login-robots.jpg" alt="" className="wl-kb" decoding="async" />
        </div>
        <div className="wl-hero-shade" aria-hidden="true" />
        <div className="wl-orbit-frame" aria-hidden="true" />
        <div className="wl-wrap relative">
          <div className="max-w-2xl">
            <R><div className="font-mono text-[12px] tracking-[.18em] uppercase text-slate-300">Welcome{user ? `, ${firstName(user.full_name)}` : ''}</div></R>
            <R d={120}><h1 className="font-display font-bold text-white leading-[1.02] text-[clamp(44px,7vw,80px)] mt-3">Multiple labs.<br /><span className="wl-grad">One connected system.</span></h1></R>
            <R d={280}><p className="mt-5 text-[17px] leading-relaxed text-slate-200 max-w-xl">Where robotics, intelligent automation, IoT and secure research infrastructure work together.</p></R>
            <R d={420} className="mt-7 flex flex-wrap gap-2.5">
              <button type="button" className="wl-chip" onClick={() => go('wl-robots')}><Bot size={15} /> Robotics &amp; Digital Twins</button>
              <button type="button" className="wl-chip" onClick={() => go('wl-auto')}><Workflow size={15} /> Intelligent Automation</button>
              <button type="button" className="wl-chip" onClick={() => go('wl-access')}><Fingerprint size={15} /> Secure Lab Access</button>
            </R>
            <R d={560} className="mt-6 text-[12.5px] text-slate-400">{labs ? `${count} registered laboratories · one portal` : 'Loading laboratories…'}</R>
          </div>
        </div>
        <button type="button" onClick={() => go('wl-labs')} className="wl-cue"><span>Scroll to explore</span><ArrowDown size={16} /></button>
      </Section>

      {/* 02 CONNECTED LABS */}
      <Section id="wl-labs">
        <div className="wl-wrap">
          <R><Eyebrow n="02">The connected laboratory</Eyebrow></R>
          <R d={100}><h2 className="wl-h2">All labs. <span className="wl-grad">Connected.</span></h2></R>
          <R d={200}><p className="wl-p">{count || 'Every'} laboratories share one portal for bookings, secure access, equipment records and issue tracking. Select a workcell to see its record.</p></R>
          <R d={250} className="mt-2 flex flex-wrap gap-2 text-[11.5px]">
            <Tag>Cyan path · registered in the portal</Tag><Tag tone="amber">Amber · door hardware installed ({doors})</Tag><Tag tone="slate">Structure, not live traffic</Tag>
          </R>
          {labs && labs.length > 0 && <R d={300} className="mt-8"><LabNetwork labs={labs} /></R>}
          {labs && labs.length > 0 && (
            <div className="wl-net-mobile mt-6">
              {labs.map(l => (
                <div key={l.code} className={`wl-mcell ${l.has_controller ? 'is-door' : ''}`}>
                  {(() => { const I = LAB_ICON[l.code] ?? Cpu; return <span><I size={18} /></span> })()}
                  <div><b>{l.code}</b>{l.name}</div>
                </div>))}
            </div>)}
        </div>
      </Section>

      {/* 03 ROBOTICS */}
      <Section id="wl-robots" className="wl-band">
        <div className="wl-wrap">
          <R><Eyebrow n="03">Robotics &amp; digital twins</Eyebrow></R>
          <R d={100}><h2 className="wl-h2">Real robots. <span className="wl-grad">Living twins.</span></h2></R>
          <R d={200}><p className="wl-p">The Robotics Lab runs an inverted UR5e under its gantry and a FANUC ER-4iA in its cell. The portal draws both from the manufacturers' 3D meshes and follows their joints - read-only, so watching never moves a robot.</p></R>
          <div className="mt-10 grid lg:grid-cols-[1fr_1fr] gap-6">
            <R d={200} className="grid grid-cols-2 gap-4">
              <figure className="wl-photo-card wl-crop col-span-2"><img src="/equipment/our-ur5e.jpg" alt="Our UR5e mounted upside down under its gantry" loading="lazy" decoding="async" />
                <figcaption><Tag tone="amber">Our lab</Tag> UR5e + Robotiq 2F-85 · inverted on the gantry</figcaption></figure>
              <figure className="wl-photo-card"><img src="/equipment/our-fanuc.jpg" alt="Our FANUC ER-4iA" loading="lazy" decoding="async" style={{ objectPosition: '40% 30%' }} />
                <figcaption><Tag tone="amber">Our lab</Tag> FANUC ER-4iA</figcaption></figure>
              <figure className="wl-photo-card"><img src="/equipment/our-pcs.jpg" alt="Our Robotics Lab workstations" loading="lazy" decoding="async" />
                <figcaption><Tag tone="amber">Our lab</Tag> Lab workstations</figcaption></figure>
            </R>
            <R d={350} className="wl-arms-card">
              <Near leaving={leaving}>
                <Suspense fallback={<div className="h-full grid place-items-center text-slate-400 text-sm">Loading 3D…</div>}>
                  <WelcomePair className="absolute inset-0" />
                </Suspense>
              </Near>
              <div className="wl-arms-cap"><Tag>One workcell · true scale · drag a link to turn its joint</Tag><Tag tone="slate">Preview only · nothing is sent to a robot</Tag></div>
            </R>
          </div>
          <R d={300} className="mt-6 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {[['Live joints', 'UR5e over RTDE (receive only), FANUC position page'], ['3D digital twins', 'URDF chains + manufacturer meshes, views and replay'],
              ['Virtual workcell', 'Table and obstacles with a modelled collision check'], ['Control groundwork', 'Ownership, checks and audit - dry run only']]
              .map(([t, s]) => <div key={t} className="wl-fact"><b>{t}</b><span>{s}</span></div>)}
          </R>
        </div>
      </Section>

      {/* 04 AUTOMATION */}
      <Section id="wl-auto">
        <div className="wl-wrap">
          <R><Eyebrow n="04">Intelligent automation &amp; IoT</Eyebrow></R>
          <R d={100}><h2 className="wl-h2">From sensor <span className="wl-grad">to decision.</span></h2></R>
          <R d={200}><p className="wl-p">Sensors report, workflows react, data lands in one place.</p></R>
          <R d={250} className="wl-pipe mt-10">
            <svg viewBox="0 0 1000 120" preserveAspectRatio="none" aria-hidden="true" className="wl-pipe-svg">
              <path d="M60 60 C 250 10, 300 110, 500 60 S 760 10, 940 60" pathLength={1} className="wl-draw" stroke="#24d4f2" strokeWidth="2" fill="none" />
              {[0, 1.2, 2.4, 3.6].map(b => <circle key={b} r="3.5" fill={b % 2.4 ? '#ffb547' : '#9ef3ff'} className="wl-particle">
                <animateMotion dur="4.8s" begin={`${b}s`} repeatCount="indefinite" path="M60 60 C 250 10, 300 110, 500 60 S 760 10, 940 60" /></circle>)}
            </svg>
            {[
              { i: <Cpu />, t: 'Sensors', s: 'ESP32 nodes · door, environment, bins' },
              { i: <Workflow />, t: 'Automation', s: 'n8n workflows · alerts, reminders, reports' },
              { i: <Network />, t: 'Data', s: 'FastAPI + PostgreSQL · knowledge vault' },
              { i: <ScrollText />, t: 'Smart Lab Portal', s: 'Dashboards, twins and notifications' },
            ].map((s, k) => (
              <div key={s.t} className="wl-stage" style={{ '--d': `${300 + k * 140}ms` } as CSSProperties}>
                <div className="wl-stage-ic">{s.i}</div>
                <b>{s.t}</b><span>{s.s}</span>
              </div>))}
          </R>
        </div>
      </Section>

      {/* 05 ACCESS */}
      <Section id="wl-access" className="wl-band">
        <div className="wl-wrap grid lg:grid-cols-[.8fr_1.2fr] gap-8 items-center">
          <div>
            <R><Eyebrow n="05">Secure lab access &amp; vision</Eyebrow></R>
            <R d={100}><h2 className="wl-h2">Two factors. <span className="wl-grad">One decision.</span></h2></R>
            <R d={200}><p className="wl-p">The portal verifies and records. The door controller alone decides whether the lock opens.</p></R>
            <ol className="mt-7 space-y-3">
              {[
                [<QrCode key="a" />, 'Booking or credential', 'A QR code from a booking, or an RFID card.'],
                [<Fingerprint key="b" />, 'Identity check', 'Fingerprint or face must match that same person.'],
                [<DoorClosed key="c" />, 'The Master ESP32 decides', 'Only the physical controller drives the lock.'],
                [<ScrollText key="d" />, 'Every attempt is logged', 'Granted and denied attempts appear in the access monitor.'],
              ].map(([ic, t, s], k) => (
                <R key={k} d={250 + k * 120} className="wl-step"><span className="wl-step-n">{ic}</span><div><b>{t}</b><span>{s}</span></div></R>))}
            </ol>
          </div>
          <R d={300} className="wl-door">
            <svg viewBox="12 44 736 410" role="img" className="wl-scene"
                 aria-label="Illustration: the red lab door with camera, NFC tablet and fingerprint reader, the Master ESP32 that drives the lock, and the lab PC running the portal">
              <defs>
                <linearGradient id="dr" x1="0" x2="1"><stop offset="0" stopColor="#9f1d22" /><stop offset=".5" stopColor="#c62a2f" /><stop offset="1" stopColor="#8c181d" /></linearGradient>
                <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#10243f" /><stop offset="1" stopColor="#0a1a2f" /></linearGradient>
                <radialGradient id="cam" cx=".4" cy=".35"><stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#c9d3df" /></radialGradient>
                <linearGradient id="scr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#0b2a47" /><stop offset="1" stopColor="#071426" /></linearGradient>
                <filter id="gl"><feGaussianBlur stdDeviation="4" /></filter>
              </defs>
              <rect width="760" height="460" rx="14" fill="url(#wall)" />
              <rect y="392" width="760" height="68" fill="#081627" /><path d="M0 392H760" stroke="#1f3a60" />
              {/* door */}
              <rect x="128" y="96" width="176" height="296" rx="3" fill="#1d2f4a" />
              <rect x="138" y="104" width="156" height="288" fill="#050d18" />
              <g className="ac-door">
              <rect x="138" y="104" width="156" height="288" rx="2" fill="url(#dr)" />
              <rect x="160" y="128" width="112" height="70" rx="3" fill="#0d1f36" stroke="#5e1014" strokeWidth="3" opacity=".9" />
              <path d="M170 136l30 54M196 136l30 54" stroke="#9ec9ff" strokeOpacity=".15" strokeWidth="6" />
              <rect x="190" y="214" width="52" height="16" rx="3" fill="#e5e7eb" /><text x="216" y="226" textAnchor="middle" fontSize="10" fontWeight="700" fill="#111827" fontFamily="monospace">LAB_01</text>
              <rect x="270" y="252" width="10" height="44" rx="5" fill="#d1d5db" /><rect x="262" y="270" width="24" height="7" rx="3" fill="#e5e7eb" />
              </g>
              <rect x="138" y="100" width="156" height="8" fill="#4b5563" /><rect x="186" y="99" width="60" height="10" rx="2" fill="#9ca3af" />
              <text x="216" y="92" textAnchor="middle" fontSize="9" fill="#7e97b8" fontFamily="monospace">MAGLOCK</text>
              {/* MC210 camera above the door */}
              <g transform="translate(330 70)">
                <rect x="-20" y="-6" width="40" height="8" rx="3" fill="#94a3b8" />
                <rect x="-16" y="2" width="32" height="20" rx="8" fill="url(#cam)" />
                <circle cy="40" r="25" fill="url(#cam)" stroke="#aab6c5" />
                <rect x="-21" y="31" width="42" height="18" rx="9" fill="#111827" />
                <circle cx="-4" cy="40" r="7" fill="#0b1220" stroke="#24d4f2" strokeWidth="1.5" /><circle cx="-6" cy="38" r="2" fill="#7dd3fc" />
                <circle cx="12" cy="40" r="2" fill="#22c55e" className="wl-blink" />
                <text y="80" textAnchor="middle" fontSize="9.5" fill="#cbd5e1" fontFamily="monospace">MC210 CAMERA</text>
                <path d="M-10 64 L-150 330 M10 64 L40 330" stroke="#24d4f2" strokeOpacity=".18" />
              </g>
              {/* tablet (QR / NFC) + fingerprint reader beside the door */}
              <g transform="translate(36 170)">
                <rect width="74" height="104" rx="9" fill="#0b1220" stroke="#475569" />
                <rect x="6" y="8" width="62" height="86" rx="4" fill="url(#scr)" />
                <g className="ac-nfc" stroke="#24d4f2" fill="none" strokeWidth="2" strokeLinecap="round"><path d="M31 40a8 8 0 0 1 0 12" /><path d="M36 35a15 15 0 0 1 0 22" /><path d="M41 30a22 22 0 0 1 0 32" /></g>
                <rect x="20" y="40" width="9" height="12" rx="2" fill="#24d4f2" />
                <g className="ac-card"><rect x="-58" y="34" width="40" height="26" rx="4" fill="#e2e8f0" /><rect x="-52" y="40" width="10" height="8" rx="1" fill="#f59e0b" /></g>
                <text x="37" y="76" textAnchor="middle" fontSize="7.5" fill="#cbd5e1" fontFamily="sans-serif">Tap card</text>
                <text x="37" y="86" textAnchor="middle" fontSize="7" fill="#7e97b8" fontFamily="sans-serif">or scan QR</text>
                <rect x="17" y="122" width="40" height="52" rx="8" fill="#1f2937" stroke="#475569" />
                <ellipse cx="37" cy="145" rx="11" ry="14" fill="#0b1220" stroke="#24d4f2" strokeOpacity=".7" />
                <g stroke="#24d4f2" strokeOpacity=".6" fill="none"><ellipse cx="37" cy="145" rx="7" ry="9" /><ellipse cx="37" cy="145" rx="3.5" ry="5" /></g>
                <rect className="ac-scan" x="26" y="131" width="22" height="2" rx="1" fill="#67e8f9" />
                <text x="37" y="196" textAnchor="middle" fontSize="8.5" fill="#cbd5e1" fontFamily="monospace">NFC · QR · FINGER</text>
              </g>
              {/* Master ESP32 */}
              <g transform="translate(400 250)">
                <rect width="120" height="74" rx="6" fill="#1e293b" stroke="#ffb547" />
                <rect x="10" y="10" width="62" height="40" rx="3" fill="#0f172a" stroke="#334155" />
                <rect x="20" y="16" width="42" height="28" rx="2" fill="#94a3b8" /><text x="41" y="34" textAnchor="middle" fontSize="7" fill="#0f172a" fontFamily="monospace" fontWeight="700">ESP32</text>
                {Array.from({ length: 9 }).map((_, k) => <rect key={k} x={10 + k * 11} y="60" width="5" height="8" fill="#cbd5e1" />)}
                <rect x="82" y="12" width="28" height="22" rx="2" fill="#2563eb" /><text x="96" y="27" textAnchor="middle" fontSize="6" fill="#fff" fontFamily="monospace">RELAY</text>
                <circle cx="96" cy="46" r="4" className="ac-relay" />
                <text x="60" y="92" textAnchor="middle" fontSize="10" fill="#ffd08a" fontFamily="monospace" fontWeight="700">MASTER ESP32</text>
              </g>
              {/* lab PC running the portal */}
              <g transform="translate(560 128)">
                <rect width="170" height="112" rx="8" fill="#0b1220" stroke="#475569" />
                <rect x="7" y="7" width="156" height="90" rx="3" fill="url(#scr)" />
                <circle cx="85" cy="44" r="22" fill="#24d4f2" opacity=".18" filter="url(#gl)" />
                <image href="/favicon.svg" x="68" y="24" width="34" height="34" />
                <text x="85" y="76" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing="2" fill="#fff" fontFamily="sans-serif">SMART <tspan fill="#24d4f2">LAB</tspan></text>
                <text x="85" y="88" textAnchor="middle" fontSize="5.5" letterSpacing="1" fill="#94a3b8" fontFamily="sans-serif">INTELLIGENT RESEARCH LABORATORY</text>
                <rect x="74" y="112" width="22" height="22" fill="#334155" /><rect x="50" y="132" width="70" height="7" rx="3" fill="#475569" />
                <rect x="20" y="146" width="130" height="12" rx="3" fill="#1f2937" stroke="#334155" />
                <text x="85" y="178" textAnchor="middle" fontSize="10" fill="#cbd5e1" fontFamily="monospace">LAB PC · PORTAL</text>
              </g>
              <text className="ac-step" x="560" y="300" fontSize="11" fill="#9ef3ff" fontFamily="monospace">
                <tspan className="ac-t1">1 card / QR read</tspan><tspan className="ac-t2" x="560">2 face / finger check</tspan>
                <tspan className="ac-t3" x="560">3 ESP32: unlock</tspan><tspan className="ac-t4" x="560">4 door open · logged</tspan></text>
              {[['M110 230 C 180 300, 330 300, 400 285', '0s'], ['M460 250 C 460 200, 300 140, 270 108', '2.4s'], ['M520 285 C 590 285, 640 260, 645 245', '3.6s']].map(([d, b]) =>
                <circle key={d} r="4" fill="#9ef3ff" className="ac-pulse"><animateMotion dur="2.4s" begin={b} path={d} repeatCount="indefinite" /></circle>)}
              {/* links */}
              <path d="M110 230 C 180 300, 330 300, 400 285" stroke="#24d4f2" strokeWidth="2" fill="none" pathLength={1} className="wl-draw" />
              <path d="M460 250 C 460 200, 300 140, 270 108" stroke="#ffb547" strokeWidth="2.2" fill="none" pathLength={1} className="wl-draw" style={{ '--d': '300ms' } as CSSProperties} />
              <path d="M520 285 C 590 285, 640 260, 645 245" stroke="#24d4f2" strokeWidth="2" strokeDasharray="5 7" fill="none" className="wl-flow" />
              <path d="M355 110 C 430 110, 520 140, 560 160" stroke="#24d4f2" strokeOpacity=".7" strokeWidth="1.6" strokeDasharray="3 6" fill="none" className="wl-flow" />
              <text x="250" y="320" fontSize="9" fill="#7e97b8" fontFamily="monospace">credential</text>
              <text x="355" y="180" fontSize="9" fill="#ffd08a" fontFamily="monospace">lock</text>
              <text x="570" y="300" fontSize="9" fill="#7e97b8" fontFamily="monospace">events</text>
              <text x="440" y="122" fontSize="9" fill="#7e97b8" fontFamily="monospace">video</text>
              <text x="20" y="440" fontSize="10" fill="#7e97b8" fontFamily="monospace">ILLUSTRATION · DEMO LOOP · NOT LIVE</text>
            </svg>
            <div className="mt-3 flex flex-wrap gap-2">
              <Tag><Camera size={12} /> MC210 camera · person detection on the lab PC</Tag>
              <Tag tone="amber">{doors} door{doors === 1 ? '' : 's'} with access hardware</Tag>
            </div>
          </R>
        </div>
      </Section>

      {/* 06 CTA */}
      <Section id="wl-end" className="wl-end">
        <div className="wl-end-bg" aria-hidden="true">
          <Near leaving={leaving}><Suspense fallback={null}><WelcomeFleet className="wl-end-arms" /></Suspense></Near>
        </div>
        <div className="wl-end-shade" aria-hidden="true" />
        <div className="wl-wrap relative text-center">
          <R><Eyebrow n="06">Ready to explore?</Eyebrow></R>
          <EndHeading />
          <R d={260}><p className="mt-5 mx-auto max-w-xl text-[17px] text-slate-200">Explore connected laboratories, equipment records, bookings and secure access through one portal.</p></R>
          <R d={400} className="mt-8 flex flex-wrap gap-3 justify-center">
            <button type="button" onClick={enter} onPointerEnter={prime} onFocus={prime} className="wl-btn-primary">Enter Dashboard <ArrowRight size={17} /></button>
            <button type="button" onClick={enter} onPointerEnter={prime} onFocus={prime} className="wl-btn">Skip for now</button>
          </R>
          <R d={460}><div className="mt-6 inline-flex"><Tag tone="slate">Background: ABB IRB 2400 (writing), Kinova Gen3 &amp; UR5e models · demo motion</Tag></div></R>
          <R d={500}><div className="mt-10 font-mono text-[10.5px] tracking-[.2em] text-slate-500">END OF WELCOME</div></R>
        </div>
      </Section>
    </div>, document.body)
}
