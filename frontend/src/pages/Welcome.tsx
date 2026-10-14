/**
 * Smart Lab home - the entrance to the laboratory, inside the normal portal
 * frame (sidebar and routes unchanged). Images come only from
 * lib/labVisuals.ts; missing ones show a compact "photo pending" tile.
 * Data: one GET /labs on open (already used by the Labs page). No polling,
 * no live values invented here - the live pages are linked instead.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { SmartLabMark } from '../components/Brand'
import { ArrowDown, ArrowRight, Bot, Building2, Cctv, ChevronRight, ImageOff, LayoutDashboard, Radar, Thermometer } from 'lucide-react'
import { api, Lab } from '../lib/api'
import { firstName, isStaff, useAuth } from '../lib/auth'
import { Reveal } from '../components/motion'
import { Modal } from '../components/ui'
import { BY_LAB } from '../components/EquipmentGallery'
import {
  EQUIPMENT, EquipmentVisual, heroOf, KIND_LABEL, LabImage, LABS, ROLE_LABEL, SITE_HERO, sortedImages,
} from '../lib/labVisuals'

function Pending({ label = 'Photo pending', className = '' }: { label?: string; className?: string }) {
  return (
    <div className={`grid place-items-center bg-[linear-gradient(135deg,rgba(30,48,76,.55),rgba(14,24,40,.75))] ${className}`}>
      <span className="flex items-center gap-1.5 text-[11px] text-slate-400"><ImageOff size={13} /> {label}</span>
    </div>)
}

function Img({ img, className = '', eager = false, sizes }: { img: LabImage; className?: string; eager?: boolean; sizes?: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <Pending label="Image file missing" className={className} />
  return <img src={img.thumb && !eager ? img.thumb : img.src} alt={img.alt} width={img.width} height={img.height}
              sizes={sizes} loading={eager ? 'eager' : 'lazy'} decoding="async" onError={() => setFailed(true)}
              className={`object-cover ${className}`} />
}

function EquipmentDetail({ item, onClose }: { item: EquipmentVisual | null; onClose: () => void }) {
  const [i, setI] = useState(0)
  useEffect(() => setI(0), [item])
  const { user } = useAuth()
  if (!item) return <Modal open={false} onClose={onClose} title=""><span /></Modal>
  const imgs = sortedImages(item)
  const cur = imgs[i]
  const canRoute = item.route && (!item.route.staffOnly || isStaff(user))
  return (
    <Modal open onClose={onClose} title={item.title}
           footer={canRoute ? <Link to={item.route!.to} className="btn-primary btn-sm">{item.route!.label} <ChevronRight size={14} /></Link> : undefined}>
      <div className="space-y-3">
        <div className="aspect-[4/3] rounded-xl overflow-hidden border border-white/10">
          {cur ? <img src={cur.src} alt={cur.alt} decoding="async" className="w-full h-full object-contain bg-ink-950" />
               : <Pending className="w-full h-full" label="Photos of our unit are pending" />}
        </div>
        {cur && <div className="text-[11.5px] text-slate-400">{ROLE_LABEL[cur.role]} · <span className={cur.kind === 'illustration' || cur.kind === 'dimensional' ? 'text-amber-300' : ''}>{KIND_LABEL[cur.kind]}</span>
          {cur.credit && <> · {cur.credit}</>}{cur.from && <> · made from {cur.from}</>}</div>}
        {imgs.length > 1 && (
          <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Views">
            {imgs.map((im, j) => (
              <button key={im.src} type="button" role="tab" aria-selected={j === i} onClick={() => setI(j)}
                      className={`shrink-0 w-20 h-14 rounded-md overflow-hidden border ${j === i ? 'border-accent-400' : 'border-white/10'}`}>
                <img src={im.thumb ?? im.src} alt={`${ROLE_LABEL[im.role]}: ${im.alt}`} loading="lazy" className="w-full h-full object-cover" />
              </button>))}
          </div>)}
        {item.model && <div className="text-[12.5px] text-slate-300">Model: <span className="text-white">{item.model}</span></div>}
        <p className="text-[13px] text-slate-300 leading-relaxed">{item.description}</p>
        {item.docs && <a href={item.docs.href} target="_blank" rel="noopener noreferrer" className="text-[12.5px] text-accent-300 underline">{item.docs.label}</a>}
      </div>
    </Modal>)
}

const STORY = [
  { eyebrow: 'Robotics', title: 'Two robots, two live digital twins.', img: '/equipment/our-ur5e.jpg',
    alt: "The lab's UR5e robot on its frame", icon: <Bot size={56} />,
    text: 'The inverted UR5e and the FANUC ER-4iA report their joints to the portal, where 3D twins follow every movement - read-only, so watching never moves a robot.',
    tags: ['UR5e · RTDE', 'FANUC ER-4iA', 'Joint telemetry', 'Movement history'] },
  { eyebrow: 'Intelligent laboratory', title: 'Sensors, equipment and workstations on one network.', img: '/equipment/our-pcs.jpg',
    alt: 'The robotics lab workstations', icon: <Thermometer size={56} />,
    text: 'An environment node watches temperature, humidity, smoke, flame and motion; bins, equipment and lab PCs report to the same portal.',
    tags: ['Environment', 'Smart bins', 'Equipment', 'Lab PCs'] },
  { eyebrow: 'Computer vision & security', title: 'A room that knows who is inside.', img: null,
    alt: '', icon: <Cctv size={56} />,
    text: 'The security camera finds people and desks, and the door asks for two factors - a QR code or card, then a fingerprint or face - before the lab opens.',
    tags: ['People detection', 'Two-factor door', 'Face ID', 'Access log'] },
  { eyebrow: 'Research workflow', title: 'From booking to results.', img: '/equipment/our-fanuc.jpg',
    alt: "The lab's FANUC robot", icon: <Building2 size={56} />,
    text: 'Book a lab, borrow equipment, follow the monitoring and keep your experiments - one portal from the first booking to the last report.',
    tags: ['Bookings', 'Equipment', 'Monitoring', 'Reports'] },
]

export default function Welcome() {
  const { user } = useAuth()
  // Seen once: from now on, signing in goes straight to the dashboard (Login.tsx).
  useEffect(() => { try { if (user?.email) localStorage.setItem(`smartlab.welcomed.${user.email.toLowerCase()}`, '1') } catch { /* ignore */ } }, [user?.email])
  const staff = isStaff(user)
  const [labs, setLabs] = useState<Lab[] | null>(null)
  const [open, setOpen] = useState<EquipmentVisual | null>(null)
  useEffect(() => { api.labs().then(setLabs).catch(() => setLabs([])) }, [])

  const live = [
    { to: '/robots', label: 'Robot digital twin', sub: 'UR5e joints, read-only', icon: <Bot size={18} />, show: true },
    { to: '/admin/security', label: 'Security camera', sub: 'People, zones, equipment boxes', icon: <Cctv size={18} />, show: staff },
    { to: '/command', label: 'IoT dashboard', sub: 'Door, environment, bins, devices', icon: <Radar size={18} />, show: staff },
    { to: '/labs', label: 'Laboratories', sub: 'Status, bookings, environment', icon: <Thermometer size={18} />, show: true },
  ].filter(x => x.show)

  return (
    <div className="welcome -mt-2">
      {/* 1. Hero */}
      <section className="relative overflow-hidden rounded-3xl border border-white/10 min-h-[68vh] flex items-end">
        {SITE_HERO ? <Img img={SITE_HERO} eager className="absolute inset-0 w-full h-full hero-img" />
                   : <div className="absolute inset-0 bg-ink-950" />}
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(9,15,26,.25)_0%,rgba(9,15,26,.55)_45%,rgba(9,15,26,.94)_100%)]" />
        <div className="absolute inset-0 welcome-grid" aria-hidden />
        <div className="relative p-6 sm:p-10 max-w-3xl">
          <Link to="/" className="fixed top-24 right-6 z-30 btn-ghost btn-sm bg-ink-900/80 backdrop-blur">Skip <ChevronRight size={14} /> Dashboard</Link>
          <Reveal replay className="mb-4"><SmartLabMark size={56} animated /></Reveal>
          <Reveal replay as="p" className="text-[11px] tracking-[.32em] text-cyan-300/90 font-semibold">
            SMART LAB · GIU{user?.full_name ? ` · WELCOME, ${firstName(user.full_name).toUpperCase()}` : ''}</Reveal>
          <Reveal replay as="h1" delay={80} className="mt-3 font-display text-4xl sm:text-6xl font-semibold text-white leading-[1.05]">
            One lab.<span className="block text-cyan-200">Every system connected.</span></Reveal>
          <Reveal replay as="p" delay={160} className="mt-4 text-[15px] sm:text-base text-slate-300 max-w-xl">
            Where robotics, intelligent automation, and connected research work together.</Reveal>
          <Reveal replay delay={240} className="mt-6 flex flex-wrap gap-3">
            <Link to="/" className="btn-primary"><LayoutDashboard size={16} /> Enter the dashboard</Link>
            <a href="#discover" className="btn-ghost">Discover the lab <ArrowDown size={15} /></a>
          </Reveal>
        </div>
        <div className="absolute bottom-4 right-5 hidden sm:flex flex-col items-center gap-1 text-[10px] tracking-[.25em] text-slate-400" aria-hidden>
          SCROLL<span className="scroll-cue" />
        </div>
      </section>

      {/* The story - real photos of our lab; nothing here shows a live value. */}
      {STORY.map((c, k) => (
        <section key={c.title} className={`pt-20 grid gap-8 items-center lg:grid-cols-2 ${k % 2 ? 'lg:[&>*:first-child]:order-2' : ''}`}>
          <Reveal replay className="rounded-3xl overflow-hidden border border-white/10 aspect-[16/10] bg-ink-900">
            {c.img ? <img src={c.img} alt={c.alt} loading="lazy" decoding="async" className="w-full h-full object-cover story-img" />
                   : <div className="w-full h-full grid place-items-center text-cyan-300/70">{c.icon}</div>}
          </Reveal>
          <div>
            <Reveal replay as="p" className="eyebrow-line">{c.eyebrow}</Reveal>
            <Reveal replay as="h2" delay={60} className="font-display text-2xl sm:text-4xl text-white font-semibold leading-tight">{c.title}</Reveal>
            <Reveal replay as="p" delay={120} className="mt-4 text-[15px] text-slate-300 leading-relaxed max-w-lg">{c.text}</Reveal>
            <Reveal replay delay={180} className="mt-5 flex flex-wrap gap-2">
              {c.tags.map(t => <span key={t} className="mono text-[11px] px-2 py-1 rounded-md border border-cyan-400/25 text-cyan-100">{t}</span>)}
            </Reveal>
          </div>
        </section>))}

      {/* 2. Discover the laboratory */}
      <section id="discover" className="pt-16 scroll-mt-4">
        <Reveal replay><p className="eyebrow-line">Discover</p>
          <h2 className="font-display text-2xl sm:text-3xl text-white font-semibold">The equipment</h2></Reveal>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {EQUIPMENT.map((e, k) => {
            const h = heroOf(e)
            return (
              <Reveal replay key={e.id} delay={(k % 3) * 70}>
                <button type="button" onClick={() => setOpen(e)}
                        className="group w-full text-left rounded-2xl overflow-hidden border border-white/10 bg-ink-900/40 hover:border-cyan-400/40 transition-colors">
                  <div className="aspect-[4/3] overflow-hidden">
                    {h ? <Img img={h} className="w-full h-full transition-transform duration-500 group-hover:scale-[1.03]" sizes="(min-width:1024px) 33vw, (min-width:640px) 50vw, 100vw" />
                       : <Pending className="w-full h-full" />}
                  </div>
                  <div className="p-4">
                    <div className="flex items-baseline justify-between gap-2">
                      <h3 className="text-[15px] font-semibold text-white">{e.title}</h3>
                      {e.model && <span className="mono text-[11px] text-slate-400 truncate">{e.model}</span>}
                    </div>
                    <p className="mt-1 text-[12.5px] text-slate-400 line-clamp-2">{e.description}</p>
                    <span className="mt-2 inline-flex items-center gap-1 text-[12px] text-cyan-300">Details <ArrowRight size={13} /></span>
                  </div>
                </button>
              </Reveal>)
          })}
        </div>
      </section>

      {/* 3. Explore the labs */}
      <section className="pt-16">
        <Reveal replay><p className="eyebrow-line">Explore</p>
          <h2 className="font-display text-2xl sm:text-3xl text-white font-semibold">The laboratories</h2></Reveal>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {labs === null && [0, 1].map(i => <div key={i} className="h-44 rounded-2xl bg-ink-800/50 animate-pulse" />)}
          {labs?.map((l, k) => {
            const v = LABS[l.code]
            const items = (BY_LAB[l.code] ?? []).slice(0, 3)
            return (
              <Reveal replay key={l.id} delay={(k % 2) * 80}>
                <Link to={`/labs/${l.id}`} className="group grid grid-cols-[38%_1fr] rounded-2xl overflow-hidden border border-white/10 bg-ink-900/40 hover:border-cyan-400/40 transition-colors min-h-[11rem]">
                  {v?.hero ? <Img img={v.hero} className="w-full h-full" /> : <Pending className="w-full h-full" />}
                  <div className="p-4 min-w-0">
                    <div className="mono text-[10.5px] text-slate-500">{l.code}</div>
                    <h3 className="text-[15px] font-semibold text-white truncate">{l.name}</h3>
                    <p className="mt-1 text-[12.5px] text-slate-400 line-clamp-2">{v?.intro ?? l.description}</p>
                    {items.length > 0 && <ul className="mt-2 flex flex-wrap gap-1.5">
                      {items.map(it => <li key={it.label} className="text-[11px] px-2 py-0.5 rounded-md bg-white/5 text-slate-300 truncate max-w-full">{it.label}</li>)}
                    </ul>}
                    <span className="mt-2 inline-flex items-center gap-1 text-[12px] text-cyan-300">Open lab <ArrowRight size={13} /></span>
                  </div>
                </Link>
              </Reveal>)
          })}
          {labs?.length === 0 && <p className="text-[13px] text-slate-400">The laboratory list could not be loaded.</p>}
        </div>
      </section>

      {/* 4. Live intelligence: links to the real live pages - no values shown here */}
      <section className="pt-16 pb-6">
        <Reveal replay><p className="eyebrow-line">Live</p>
          <h2 className="font-display text-2xl sm:text-3xl text-white font-semibold">The lab, as it is right now</h2>
          <p className="mt-2 text-[13px] text-slate-400 max-w-2xl">Live readings stay on their own pages, where they are measured and labelled.</p></Reveal>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {live.map((x, k) => (
            <Reveal replay key={x.to} delay={k * 60}>
              <Link to={x.to} className="flex items-start gap-3 rounded-2xl border border-white/10 bg-ink-900/40 p-4 hover:border-cyan-400/40 transition-colors h-full">
                <span className="text-cyan-300 mt-0.5">{x.icon}</span>
                <span><span className="block text-[14px] font-semibold text-white">{x.label}</span>
                  <span className="block text-[12px] text-slate-400">{x.sub}</span></span>
              </Link>
            </Reveal>))}
        </div>
        <Reveal replay className="mt-14 rounded-3xl border border-cyan-400/25 bg-gradient-to-br from-cyan-500/10 to-amber-400/5 p-8 sm:p-12 text-center">
          <h2 className="font-display text-2xl sm:text-4xl text-white font-semibold">Ready when you are.</h2>
          <p className="mt-3 text-slate-300">Bookings, equipment, monitoring and the robots - all in the portal.</p>
          <Link to="/" className="btn-primary mt-6 inline-flex !px-6 !py-3"><LayoutDashboard size={16} /> Enter Dashboard</Link>
        </Reveal>
        <Reveal replay className="mt-8 flex flex-wrap gap-3">
          <Link to="/labs" className="btn-ghost"><Building2 size={16} /> All laboratories</Link>
        </Reveal>
      </section>

      <EquipmentDetail item={open} onClose={() => setOpen(null)} />
    </div>)
}
