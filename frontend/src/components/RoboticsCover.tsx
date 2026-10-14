/**
 * Robotics Lab card cover: the generated UR5e + FANUC illustration with a light hover tilt and
 * animated trajectory accents. Decorative only - never a live robot status, never a command.
 * Falls back to the drawn category art if the image is missing; no motion with reduced-motion.
 */
import { useRef, useState } from 'react'

export const ROBOTICS_COVER = '/assets/labs/robotics-lab-cover.png'

export default function RoboticsCover({ fallback, className = '' }: { fallback: React.ReactNode; className?: string }) {
  const [ok, setOk] = useState(true)
  const ref = useRef<HTMLDivElement>(null)
  if (!ok) return <>{fallback}</>
  const tilt = (e: React.PointerEvent) => {
    const el = ref.current
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const r = el.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5
    el.style.transform = `perspective(700px) rotateY(${x * 5}deg) rotateX(${-y * 5}deg) scale(1.04)`
  }
  return (
    <div ref={ref} onPointerMove={tilt} onPointerLeave={() => { if (ref.current) ref.current.style.transform = '' }}
         className={`${className} transition-transform duration-300 will-change-transform`}>
      <img src={ROBOTICS_COVER} alt="Illustration: the lab's UR5e and FANUC robots with a conveyor"
           loading="lazy" decoding="async" onError={() => setOk(false)} className="w-full h-full object-cover" />
      <svg className="absolute inset-0 w-full h-full pointer-events-none motion-reduce:hidden" viewBox="0 0 100 60" preserveAspectRatio="none" aria-hidden>
        <path d="M22 18 Q 30 34 42 30" fill="none" stroke="#22d3ee" strokeWidth="0.6" strokeDasharray="1.5 2.5" className="animate-[dash_3s_linear_infinite]" />
        <path d="M80 18 Q 74 36 62 34" fill="none" stroke="#facc15" strokeWidth="0.6" strokeDasharray="1.5 2.5" className="animate-[dash_3.6s_linear_infinite]" />
      </svg>
      <style>{'@keyframes dash{to{stroke-dashoffset:-16}}'}</style>
    </div>)
}
