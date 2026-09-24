import { useEffect, useMemo, useState } from 'react'
import { FlaskConical, Search } from 'lucide-react'
import { Lab, LabStatus, api } from '../lib/api'
import { EmptyState, SectionTitle } from '../components/ui'
import LabStatusCard from '../components/LabStatusCard'

export default function Labs() {
  const [labs, setLabs] = useState<Lab[]>([])
  const [statuses, setStatuses] = useState<Record<number, LabStatus>>({})
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All')

  useEffect(() => {
    api.labs()
      .then(l => {
        setLabs(l)
        l.filter(x => x.has_controller).forEach(x =>
          api.lab(x.id).then(s => setStatuses(p => ({ ...p, [x.id]: s })))
            .catch(() => {}))
      })
      .finally(() => setLoading(false))
  }, [])

  const categories = useMemo(
    () => ['All', ...Array.from(new Set(labs.map(l => l.category))).sort()],
    [labs])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return labs.filter(l => {
      if (category !== 'All' && l.category !== category) return false
      if (!q) return true
      return [l.name, l.code, l.description, l.location, l.category]
        .some(f => f?.toLowerCase().includes(q))
    })
  }, [labs, query, category])

  // Group by category so eleven labs read as a structured facility rather
  // than a flat wall of cards.
  const grouped = useMemo(() => {
    const m = new Map<string, Lab[]>()
    for (const l of filtered) {
      const list = m.get(l.category) ?? []
      list.push(l)
      m.set(l.category, list)
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [filtered])

  return (
    <div>
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <h1 className="page-title">Laboratories</h1>
          <p className="page-sub">
            {labs.length} laboratories · {labs.filter(l => l.has_controller).length} with
            access-control hardware installed
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" />
          <input className="input pl-9" placeholder="Search laboratories"
                 value={query} onChange={e => setQuery(e.target.value)}
                 aria-label="Search laboratories" />
        </div>
      </div>

      <div className="mt-5 flex gap-2 flex-wrap">
        {categories.map(c => (
          <button key={c} onClick={() => setCategory(c)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
              ${category === c
                ? 'bg-accent-500/15 text-accent-300 border border-accent-500/40'
                : 'bg-ink-800/60 text-slate-400 border border-ink-600 hover:text-slate-200'}`}>
            {c}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 mt-6">
          {[0, 1, 2, 3, 4, 5].map(i => <div key={i} className="card-pad h-48 skeleton" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card mt-6">
          <EmptyState icon={<FlaskConical size={20} />}
                      title="No laboratories match"
                      detail="Try a different search term or category." />
        </div>
      ) : (
        <div className="mt-7 space-y-8">
          {grouped.map(([cat, list]) => (
            <section key={cat}>
              <SectionTitle>
                {cat}
                <span className="ml-2 text-slate-600 font-normal">({list.length})</span>
              </SectionTitle>
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
                {list.map((l, i) => (
                  <LabStatusCard key={l.id} lab={l} status={statuses[l.id]} index={i} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
