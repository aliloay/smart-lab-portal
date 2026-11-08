/**
 * Scroll reveal: one shared IntersectionObserver, each element animates once
 * (opacity + transform only, CSS classes in index.css: .reveal / .is-in).
 * No scroll handlers, no React state per scroll pixel. Reduced motion: shown at once.
 */
import { CSSProperties, ElementType, ReactNode, useEffect, useRef } from 'react'

let io: IntersectionObserver | null = null
function observer() {
  if (io || typeof IntersectionObserver === 'undefined') return io
  io = new IntersectionObserver(entries => {
    for (const e of entries) {
      if (e.isIntersecting) { e.target.classList.add('is-in'); io!.unobserve(e.target) }
    }
  // the area extends far ABOVE the viewport: anything scrolled past (even by a jump) counts as seen
  }, { rootMargin: '100000px 0px -8% 0px', threshold: 0.01 })
  return io
}

// Replay mode (the /welcome story): in when it enters the viewport, out again when it leaves, so
// scrolling back up revisits the animation. Still one shared observer, classes only.
let io2: IntersectionObserver | null = null
function replayObserver() {
  if (io2 || typeof IntersectionObserver === 'undefined') return io2
  io2 = new IntersectionObserver(entries => {
    for (const e of entries) e.target.classList.toggle('is-in', e.isIntersecting)
  }, { rootMargin: '0px 0px -10% 0px', threshold: 0.01 })
  return io2
}

export function Reveal({ as: Tag = 'div', delay = 0, className = '', children, style, replay = false }: {
  as?: ElementType; delay?: number; className?: string; children: ReactNode; style?: CSSProperties; replay?: boolean
}) {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const el = ref.current, o = replay ? replayObserver() : observer()
    if (!el) return
    if (!o) { el.classList.add('is-in'); return }
    o.observe(el)
    return () => o.unobserve(el)
  }, [replay])
  return <Tag ref={ref} className={`reveal ${className}`} style={{ ...style, transitionDelay: delay ? `${delay}ms` : undefined }}>{children}</Tag>
}
