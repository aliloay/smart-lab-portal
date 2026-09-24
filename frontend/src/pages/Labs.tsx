import { ReactNode, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CircuitBoard, CalendarCheck, FlaskConical, LayoutGrid, Search, X, Zap } from 'lucide-react'
import { LabOverview, api } from '../lib/api'
import { useLiveMessages } from '../lib/live'
import { EmptyState, ErrorBanner, PageHeader, Skeleton } from '../components/ui'
import { categoryMeta } from '../components/labArt'
import LabCard from '../components/LabCard'

type Toggle = 'bookable' | 'hardware' | 'available'

export default function Labs() {
  const [rows, setRows] = useState<LabOverview[] | null>(null)
  const [error, setError] = useState('')
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const category = params.get('category') ?? 'All'
  const toggles = new Set((params.get('f') ?? '').split(',').filter(Boolean) as Toggle[])

  const load = () => api.labsOverview().then(setRows)
    .catch(e => { setError(e.message); setRows([]) })
  useEffect(() => { load() }, [])
  useLiveMessages(m => {
    if (m.type === 'access_event' && /^(ACCESS_GRANTED|DOOR|DEVICE|BOOKING)/.test(m.event.event_type)) load()
  })

  // Filters live in the URL: back/forward and a shared link keep them.
  function set(k: string, v: string | null) {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v); else p.delete(k)
    setParams(p, { replace: true })
  }
  function flip(t: Toggle) {
    const n = new Set(toggles)
    n.has(t) ? n.delete(t) : n.add(t)
    set('f', [...n].join(','))
  }

  const categories = useMemo(() => {
    const m = new Map<string, number>()
    ;(rows ?? []).forEach(r => m.set(r.lab.category, (m.get(r.lab.category) ?? 0) + 1))
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [rows])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (rows ?? []).filter(({ lab, ...o }) => {
      if (category !== 'All' && lab.category !== category) return false
      if (toggles.has('bookable') && !lab.is_active) return false
      if (toggles.has('hardware') && !lab.has_controller) return false
      if (toggles.has('available') && !o.available_now) return false
      if (!q) return true
      return [lab.name, lab.code, lab.description, lab.location, lab.category]
        .some(f => f?.toLowerCase().includes(q))
    })
  }, [rows, query, category, params])   // eslint-disable-line react-hooks/exhaustive-deps

  const total = rows?.length ?? 0
  const withHw = (rows ?? []).filter(r => r.lab.has_controller).length
  const availableNow = (rows ?? []).filter(r => r.available_now).length
  const anyFilter = query || category !== 'All' || toggles.size > 0

  return (
    <div>
      <PageHeader eyebrow="Laboratory network" title="Laboratories"
        sub={rows ? `${total} laboratories · ${availableNow} available now · ${withHw} with access-control hardware installed`
                  : 'Loading the laboratory catalogue…'} />

      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      <div className="card p-4 space-y-4">
        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input className="input pl-10" placeholder="Search by name, code, location or equipment"
                   value={query} onChange={e => set('q', e.target.value)}
                   aria-label="Search laboratories" />
          </div>
          <div className="flex gap-2 flex-wrap">
            {([
              ['bookable', 'Bookable', <CalendarCheck key="b" size={14} />],
              ['hardware', 'Access hardware', <CircuitBoard key="h" size={14} />],
              ['available', 'Available now', <Zap key="a" size={14} />],
            ] as [Toggle, string, JSX.Element][]).map(([k, label, icon]) => (
              <button key={k} onClick={() => flip(k)} aria-pressed={toggles.has(k)}
                className={`btn btn-sm border ${toggles.has(k)
                  ? 'bg-accent-500/15 text-accent-200 border-accent-500/45'
                  : 'border-ink-500 text-slate-300 hover:text-white bg-ink-800/40'}`}>
                {icon}{label}
              </button>
            ))}
          </div>
        </div>

        {/* category control: icon, label, count; scrolls horizontally on phones */}
        <div className="flex gap-2 overflow-x-auto no-scrollbar -mx-1 px-1 pb-0.5" role="tablist"
             aria-label="Category">
          <CategoryPill active={category === 'All'} onClick={() => set('category', null)}
                        icon={<LayoutGrid size={14} />} label="All" count={total} hue="#7dd3fc" />
          {categories.map(([c, n]) => {
            const m = categoryMeta(c)
            return <CategoryPill key={c} active={category === c} onClick={() => set('category', c)}
                                 icon={m.icon} label={c} count={n} hue={m.hue} />
          })}
        </div>
      </div>

      <div className="mt-5 mb-3 flex items-center justify-between text-[13px]">
        <span className="text-slate-400">
          {rows ? `Showing ${filtered.length} of ${total}` : ''}
        </span>
        {anyFilter && (
          <button onClick={() => setParams({}, { replace: true })}
                  className="link inline-flex items-center gap-1"><X size={13} />Clear filters</button>
        )}
      </div>

      {rows === null ? (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {[0, 1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-[380px]" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <EmptyState icon={<FlaskConical size={20} />} title="No laboratories match"
            detail="Try a different search term, category or filter."
            action={anyFilter ? <button className="btn-ghost"
              onClick={() => setParams({}, { replace: true })}>Clear filters</button> : undefined} />
        </div>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filtered.map(o => <LabCard key={o.lab.id} o={o} />)}
        </div>
      )}

      <p className="mt-6 text-[12px] text-slate-500">
        Laboratory images are illustrations of each discipline, not photographs of the rooms.
      </p>
    </div>
  )
}

function CategoryPill({ active, onClick, icon, label, count, hue }: {
  active: boolean; onClick: () => void; icon: ReactNode; label: string; count: number; hue: string
}) {
  return (
    <button onClick={onClick} role="tab" aria-selected={active}
      className={`shrink-0 flex items-center gap-2 pl-2.5 pr-2 py-1.5 rounded-xl border
                  text-[13px] transition-colors ${active
                    ? 'bg-ink-700 border-accent-400/60 text-white shadow-glow'
                    : 'bg-ink-900/40 border-ink-600 text-slate-300 hover:text-white hover:border-ink-500'}`}>
      <span className="grid place-items-center w-6 h-6 rounded-lg"
            style={{ color: hue, background: `${hue}1f` }}>{icon}</span>
      {label}
      <span className={`min-w-[22px] h-5 px-1.5 rounded-md grid place-items-center text-[11px] tnum
                        ${active ? 'bg-accent-500/25 text-accent-100' : 'bg-ink-700 text-slate-400'}`}>
        {count}
      </span>
    </button>
  )
}
