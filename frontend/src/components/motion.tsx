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

export function Reveal({ as: Tag = 'div', delay = 0, className = '', children, style }: {
  as?: ElementType; delay?: number; className?: string; children: ReactNode; style?: CSSProperties
}) {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const el = ref.current, o = observer()
    if (!el) return
    if (!o) { el.classList.add('is-in'); return }
    o.observe(el)
    return () => o.unobserve(el)
  }, [])
  return <Tag ref={ref} className={`reveal ${className}`} style={{ ...style, transitionDelay: delay ? `${delay}ms` : undefined }}>{children}</Tag>
}
